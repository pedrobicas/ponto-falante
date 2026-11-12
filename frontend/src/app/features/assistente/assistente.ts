import { Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, RespostaChat } from '../../core/models';
import { PreferencesService } from '../../core/preferences.service';
import { ErroVoz, SpeechService } from '../../core/speech.service';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';

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
  imports: [FormsModule, Carregando, Icone],
  template: `
    <section class="cabecalho-pagina">
      <div class="miolo">
        <p class="cabecalho-pagina__chapeu"><pf-icone nome="conversa" /> Tire suas dúvidas</p>
        <h1>Assistente</h1>
        <p class="lead">Pergunte sobre gratuidade, bilhete único, acessibilidade e como usar o ônibus em São Paulo.</p>
      </div>
    </section>

    <div class="miolo chat">
      <section class="conversa" aria-label="Conversa" role="log" aria-live="polite">
        @if (mensagens().length === 0) {
          <div class="chat-vazio">
            <span class="chat-vazio__icone"><pf-icone nome="brilho" /></span>
            <p class="chat-vazio__titulo">Nenhuma pergunta ainda</p>
            <p>Escreva abaixo ou toque em uma sugestão. O assistente responde com base em documentos oficiais e mostra as fontes.</p>
          </div>
        }
        @for (m of mensagens(); track m.id) {
          <article class="troca">
            <div class="balao balao--voce">
              <p class="balao__autor">Você</p>
              <p>{{ m.pergunta }}</p>
            </div>
            @if (m.resposta; as r) {
              @if (!r.disponivel) {
                <div class="balao balao--calmo">
                  <p class="balao__autor"><pf-icone nome="lua" /> Assistente</p>
                  <p class="balao__titulo">O assistente está descansando agora</p>
                  <p>{{ r.resposta || 'O assistente roda no computador de um voluntário e pode estar desligado.' }}</p>
                  <p>O resto do aplicativo continua funcionando: você ainda pode ver os próximos ônibus e o boletim.</p>
                </div>
              } @else {
                <div class="balao balao--assistente">
                  <p class="balao__autor"><pf-icone nome="brilho" /> Assistente</p>
                  <p class="balao__texto">{{ r.resposta }}</p>
                  @if (r.nao_consta) {
                    <p class="aviso-inline"><pf-icone nome="alerta" /> Não encontrei essa informação nos documentos.</p>
                  }
                  <p class="confianca confianca--{{ r.confianca }}">
                    <span class="confianca__barras" aria-hidden="true"><i></i><i></i><i></i></span>
                    <span>{{ confianca(r) }}</span>
                  </p>
                  @if (r.fontes.length > 0) {
                    <div class="fontes">
                      <p class="fontes__titulo">Fontes ({{ r.fontes.length }})</p>
                      <ul class="fontes__lista">
                        @for (f of r.fontes; track f.documento + f.trecho_id) {
                          <li class="fonte-chip">
                            <pf-icone nome="documento" />
                            <span>{{ f.documento }} · trecho {{ f.trecho_id }}</span>
                          </li>
                        }
                      </ul>
                    </div>
                  }
                  <button type="button" class="botao botao--discreto" (click)="ouvir(r.resposta)" [disabled]="!fala.suportaSintese">
                    <pf-icone nome="volume" /> Ouvir resposta
                  </button>
                </div>
              }
            }
            @if (m.erro) {
              <p class="erro-campo" role="alert"><pf-icone nome="erro-circulo" /> {{ m.erro }}</p>
            }
          </article>
        }
        @if (enviando()) {
          <pf-carregando texto="O assistente está pensando…" />
        }
      </section>

      <form class="compositor" (ngSubmit)="enviar()" novalidate>
        @if (mensagens().length === 0) {
          <div class="sugestoes" role="group" aria-label="Sugestões de pergunta">
            @for (s of sugestoes; track s) {
              <button type="button" class="chip" (click)="usarSugestao(s)">{{ s }}</button>
            }
          </div>
        }
        <label for="pergunta" class="rotulo">Sua pergunta</label>
        <div class="compositor__campo">
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
          @if (fala.suportaReconhecimento) {
            <button type="button" class="botao botao--icone" (click)="ditar()" [disabled]="fala.ouvindo() || enviando()">
              <pf-icone nome="microfone" />
              <span class="visualmente-oculto">{{ fala.ouvindo() ? 'Ouvindo…' : 'Falar a pergunta' }}</span>
            </button>
          }
          <button type="submit" class="botao botao--primario" [disabled]="enviando()">
            <pf-icone nome="enviar" /> Enviar<span class="visualmente-oculto"> pergunta</span>
          </button>
        </div>
        @if (fala.ouvindo()) {
          <p class="ajuda" role="status">Ouvindo… fale a pergunta.</p>
        }
        @if (erroCampo()) {
          <p id="pergunta-erro" class="erro-campo"><pf-icone nome="erro-circulo" /> {{ erroCampo() }}</p>
        }
        <p id="pergunta-privacidade" class="ajuda">
          Suas perguntas não são guardadas. Até {{ limite }} caracteres.
        </p>
        <label class="interruptor">
          <input type="checkbox" name="auto" [checked]="lerAuto()" (change)="lerAuto.set($any($event.target).checked)" />
          <span class="interruptor__trilho" aria-hidden="true"></span>
          <span>Ler as respostas em voz alta automaticamente</span>
        </label>
      </form>
    </div>
  `,
})
export class Assistente {
  private readonly api = inject(ApiService);
  private readonly prefs = inject(PreferencesService);
  protected readonly fala = inject(SpeechService);
  private readonly campo = viewChild<ElementRef<HTMLInputElement>>('campo');

  protected readonly limite = LIMITE;
  protected readonly sugestoes = [
    'Tenho 65 anos, preciso pagar o ônibus?',
    'Como funciona o bilhete único?',
    'Como o ônibus ajuda quem usa cadeira de rodas?',
  ];
  protected texto = '';
  protected readonly mensagens = signal<Mensagem[]>([]);
  protected readonly enviando = signal(false);
  protected readonly erroCampo = signal('');
  protected readonly lerAuto = signal(this.prefs.prefs().lerRespostaAuto);
  private contador = 0;

  protected confianca(r: RespostaChat): string {
    return confiancaEmPalavras(r.confianca);
  }

  protected usarSugestao(texto: string): void {
    this.texto = texto;
    this.campo()?.nativeElement.focus();
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
