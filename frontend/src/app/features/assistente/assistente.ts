import { Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, RespostaChat } from '../../core/models';
import { PreferencesService } from '../../core/preferences.service';
import { ErroVoz, SpeechService } from '../../core/speech.service';
import { Carregando } from '../../shared/carregando';

export interface Mensagem {
  id: number;
  pergunta: string;
  resposta?: RespostaChat;
  erro?: string;
}

export const LIMITE = 500;

export function confiancaEmPalavras(c: RespostaChat['confianca']): string {
  switch (c) {
    case 'alta':
      return 'Confiança alta: a resposta está nos documentos oficiais.';
    case 'media':
      return 'Confiança média: vale confirmar com a SPTrans ou a prefeitura.';
    default:
      return 'Confiança baixa: confirme antes de decidir.';
  }
}

@Component({
  selector: 'pf-assistente',
  imports: [FormsModule, Carregando],
  template: `
    <h1>Assistente</h1>
    <p class="lead">Pergunte sobre gratuidade, bilhete único, acessibilidade e como usar o ônibus em São Paulo.</p>

    <section class="conversa" aria-label="Conversa" role="log" aria-live="polite">
      @if (mensagens().length === 0) {
        <p class="vazio">Nenhuma pergunta ainda. Escreva abaixo, por exemplo: “Tenho 65 anos, preciso pagar o ônibus?”</p>
      }
      @for (m of mensagens(); track m.id) {
        <article class="mensagem">
          <p class="mensagem__pergunta"><strong>Você perguntou:</strong> {{ m.pergunta }}</p>
          @if (m.resposta; as r) {
            @if (!r.disponivel) {
              <div class="caixa caixa--calmo">
                <p class="caixa__titulo"><span aria-hidden="true">ℹ</span> O assistente está descansando agora</p>
                <p>{{ r.resposta || 'O assistente roda no computador de um voluntário e pode estar desligado.' }}</p>
                <p>O resto do aplicativo continua funcionando: você ainda pode ver os próximos ônibus e o boletim.</p>
              </div>
            } @else {
              <div class="mensagem__resposta">
                <p class="mensagem__texto"><strong>Resposta:</strong> {{ r.resposta }}</p>
                @if (r.nao_consta) {
                  <p class="aviso-inline"><span aria-hidden="true">⚠</span> Não encontrei essa informação nos documentos.</p>
                }
                <p class="ajuda"><span aria-hidden="true">●</span> {{ confianca(r) }}</p>
                @if (r.fontes.length > 0) {
                  <details>
                    <summary>Fontes ({{ r.fontes.length }})</summary>
                    <ul>
                      @for (f of r.fontes; track f.documento + f.trecho_id) {
                        <li>{{ f.documento }} · trecho {{ f.trecho_id }}</li>
                      }
                    </ul>
                  </details>
                }
                <button type="button" class="botao" (click)="ouvir(r.resposta)" [disabled]="!fala.suportaSintese">
                  <span aria-hidden="true">🔊</span> Ouvir resposta
                </button>
              </div>
            }
          }
          @if (m.erro) {
            <p class="erro-campo" role="alert"><span aria-hidden="true">✖</span> {{ m.erro }}</p>
          }
        </article>
      }
      @if (enviando()) {
        <pf-carregando texto="O assistente está pensando…" />
      }
    </section>

    <form class="cartao" (ngSubmit)="enviar()" novalidate>
      <label for="pergunta" class="rotulo">Sua pergunta</label>
      <div class="linha-form">
        <input
          #campo
          id="pergunta"
          name="pergunta"
          type="text"
          autocomplete="off"
          [attr.maxlength]="limite"
          [(ngModel)]="texto"
          [attr.aria-invalid]="erroCampo() ? 'true' : null"
          [attr.aria-describedby]="erroCampo() ? 'pergunta-erro pergunta-privacidade' : 'pergunta-privacidade'"
        />
        <button type="submit" class="botao botao--primario" [disabled]="enviando()">Enviar pergunta</button>
        @if (fala.suportaReconhecimento) {
          <button type="button" class="botao" (click)="ditar()" [disabled]="fala.ouvindo() || enviando()">
            <span aria-hidden="true">🎤</span> {{ fala.ouvindo() ? 'Ouvindo…' : 'Falar a pergunta' }}
          </button>
        }
      </div>
      @if (erroCampo()) {
        <p id="pergunta-erro" class="erro-campo"><span aria-hidden="true">✖</span> {{ erroCampo() }}</p>
      }
      <p id="pergunta-privacidade" class="ajuda">
        Suas perguntas não são guardadas. Até {{ limite }} caracteres.
      </p>
      <label class="opcao">
        <input type="checkbox" name="auto" [checked]="lerAuto()" (change)="lerAuto.set($any($event.target).checked)" />
        <span>Ler as respostas em voz alta automaticamente</span>
      </label>
    </form>
  `,
})
export class Assistente {
  private readonly api = inject(ApiService);
  private readonly prefs = inject(PreferencesService);
  protected readonly fala = inject(SpeechService);
  private readonly campo = viewChild<ElementRef<HTMLInputElement>>('campo');

  protected readonly limite = LIMITE;
  protected texto = '';
  protected readonly mensagens = signal<Mensagem[]>([]);
  protected readonly enviando = signal(false);
  protected readonly erroCampo = signal('');
  protected readonly lerAuto = signal(this.prefs.prefs().lerRespostaAuto);
  private contador = 0;

  protected confianca(r: RespostaChat): string {
    return confiancaEmPalavras(r.confianca);
  }

  protected ouvir(texto: string): void {
    this.fala.falar(texto);
  }

  protected async ditar(): Promise<void> {
    this.erroCampo.set('');
    try {
      const dito = await this.fala.escutar();
      this.texto = dito.slice(0, LIMITE);
      this.campo()?.nativeElement.focus();
    } catch (e) {
      const codigo = e instanceof ErroVoz ? e.codigo : 'falha';
      this.erroCampo.set(
        codigo === 'sem-permissao'
          ? 'Não consegui usar o microfone. Libere o microfone no navegador ou escreva a pergunta.'
          : codigo === 'nada-ouvido'
            ? 'Não ouvi nada. Tente de novo ou escreva a pergunta.'
            : 'A entrada por voz não funcionou. Escreva a pergunta.',
      );
    }
  }

  protected async enviar(): Promise<void> {
    const pergunta = this.texto.trim();
    if (!pergunta) {
      this.erroCampo.set('Escreva uma pergunta antes de enviar.');
      return;
    }
    if (pergunta.length > LIMITE) {
      this.erroCampo.set(`A pergunta pode ter no máximo ${LIMITE} caracteres.`);
      return;
    }
    this.erroCampo.set('');
    this.enviando.set(true);
    const id = ++this.contador;
    this.texto = '';
    try {
      const resposta = await firstValueFrom(this.api.perguntar(pergunta));
      this.mensagens.update((l) => [...l, { id, pergunta, resposta }]);
      if (resposta.disponivel && this.lerAuto()) this.fala.falar(resposta.resposta);
    } catch (e) {
      const status = e instanceof ErroApi ? e.status : -1;
      const erro =
        status === 400
          ? `Escreva uma pergunta de até ${LIMITE} caracteres.`
          : status === 429
            ? 'Muitas perguntas seguidas. Espere um minuto e tente de novo.'
            : 'Não foi possível falar com o assistente agora. O resto do aplicativo continua funcionando.';
      this.mensagens.update((l) => [...l, { id, pergunta, erro }]);
    } finally {
      this.enviando.set(false);
    }
  }
}
