import { Component, ElementRef, effect, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AssistenteEmbarque } from '../../core/assistente-embarque.service';
import { EmbarqueStore } from '../../core/embarque.store';
import { ErroVoz, SpeechService } from '../../core/speech.service';
import { StatusService } from '../../core/status.service';
import { Icone } from '../../shared/icone';

/** Painel da assistente do Embarque Assistido: conversa por voz ou texto que executa as ações da tela. */
@Component({
  selector: 'pf-assistente-embarque',
  imports: [FormsModule, Icone],
  template: `
    <section class="assistente-emb" aria-labelledby="assistente-emb-titulo">
      <div class="assistente-emb__topo">
        <h2 id="assistente-emb-titulo"><pf-icone nome="conversa" /> Assistente de embarque</h2>
        <p class="assistente-emb__estado">
          <span class="ponto-status" [class.ponto-status--ok]="true" aria-hidden="true"></span>
          Comandos funcionam sempre{{ status.assistente() === 'disponivel' ? '; dúvidas gerais com a IA local' : '' }}
        </p>
      </div>

      <div class="assistente-emb__conversa" role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversa com a assistente" #conversa>
        @if (assistente.mensagens().length === 0) {
          <p class="assistente-emb__dica">
            Fale ou escreva o que precisa. Por exemplo: <em>"pontos perto de mim"</em>, <em>"quero pegar o 875A"</em>,
            <em>"quanto falta"</em> ou <em>"salvar nos favoritos como trabalho"</em>.
          </p>
        }
        @for (m of assistente.mensagens(); track m.id) {
          <div class="bolha" [class.bolha--voce]="m.autor === 'voce'">
            <span class="vo">{{ m.autor === 'voce' ? 'Você disse:' : 'Assistente:' }}</span>
            <p>{{ m.texto }}</p>
            @if (m.geral) {
              <p class="bolha__origem">Resposta do assistente geral do Ponto Falante.</p>
            }
            @if (m.sugestoes?.length && $last) {
              <div class="bolha__sugestoes">
                @for (sug of m.sugestoes; track sug) {
                  <button type="button" class="chip" (click)="enviar(sug)">{{ sug }}</button>
                }
              </div>
            }
          </div>
        }
        @if (assistente.processando()) {
          <p class="bolha bolha--pensando" aria-hidden="true"><span></span><span></span><span></span></p>
        }
      </div>

      <form class="assistente-emb__form" (ngSubmit)="enviar(texto)" novalidate>
        <label class="vo" for="assistente-emb-campo">Comando ou pergunta para a assistente</label>
        <input
          id="assistente-emb-campo"
          name="comando"
          type="text"
          autocomplete="off"
          enterkeyhint="send"
          maxlength="300"
          placeholder="Ex.: quanto falta?"
          [(ngModel)]="texto"
          [disabled]="assistente.processando()"
        />
        @if (fala.suportaReconhecimento) {
          <button
            type="button"
            class="botao-icone assistente-emb__mic"
            [class.assistente-emb__mic--ouvindo]="fala.ouvindo()"
            [attr.aria-pressed]="fala.ouvindo()"
            (click)="ouvir()"
          >
            <pf-icone nome="microfone" />
            <span class="vo">{{ fala.ouvindo() ? 'Parar de ouvir' : 'Falar um comando' }}</span>
          </button>
        }
        <button type="submit" class="botao-icone botao-icone--enviar" [disabled]="!texto.trim() || assistente.processando()">
          <pf-icone nome="enviar" /><span class="vo">Enviar</span>
        </button>
      </form>
      @if (erroVoz()) {
        <p class="ajuda" role="alert">{{ erroVoz() }}</p>
      }
      @if (assistente.confirmando(); as pergunta) {
        <div class="assistente-emb__confirmar" role="group" aria-label="Confirmação pendente">
          <p>{{ pergunta }}</p>
          <button type="button" class="botao botao--primario" (click)="enviar('sim')">Sim</button>
          <button type="button" class="botao botao--contorno" (click)="enviar('não')">Não</button>
        </div>
      }
    </section>
  `,
})
export class AssistenteEmbarquePainel {
  protected readonly assistente = inject(AssistenteEmbarque);
  protected readonly fala = inject(SpeechService);
  protected readonly status = inject(StatusService);
  protected readonly store = inject(EmbarqueStore);
  protected texto = '';
  protected readonly erroVoz = signal('');
  private readonly conversa = viewChild<ElementRef<HTMLElement>>('conversa');

  constructor() {
    effect(() => {
      this.assistente.mensagens();
      const el = this.conversa()?.nativeElement;
      if (el) queueMicrotask(() => (el.scrollTop = el.scrollHeight));
    });
  }

  protected enviar(texto: string, porVoz = false): void {
    const t = texto.trim();
    if (!t) return;
    this.texto = '';
    void this.assistente.enviar(t, porVoz);
  }

  protected async ouvir(): Promise<void> {
    if (this.fala.ouvindo()) {
      this.fala.pararEscuta();
      return;
    }
    this.erroVoz.set('');
    this.fala.parar();
    try {
      const dito = await this.fala.escutar();
      this.enviar(dito, true);
    } catch (e) {
      const codigo = e instanceof ErroVoz ? e.codigo : 'falha';
      this.erroVoz.set(
        codigo === 'sem-permissao'
          ? 'O navegador não liberou o microfone. Você pode permitir nas configurações ou escrever o comando.'
          : codigo === 'nada-ouvido'
            ? 'Não ouvi nada. Toque no microfone e fale de novo.'
            : 'O reconhecimento de voz falhou. Tente de novo ou escreva o comando.',
      );
    }
  }
}
