import { Component, DestroyRef, ElementRef, computed, effect, inject, input, signal, untracked, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, OrigemResposta, RespostaChat, origemDaResposta } from '../../core/models';
import { PreferencesService } from '../../core/preferences.service';
import { ErroVoz, SpeechService } from '../../core/speech.service';
import { StatusService } from '../../core/status.service';
import { Icone } from '../../shared/icone';
import { Origem } from '../../shared/origem';

export interface Mensagem {
  id: number;
  pergunta: string;
  estado: 'enviando' | 'ok' | 'erro';
  resposta?: RespostaChat;
  erro?: string;
}

export const LIMITE = 500;

export function confiancaEmPalavras(c: RespostaChat['confianca']): string {
  switch (c) {
    case 'alta':
      return 'Confiança alta: a resposta está nas fontes consultadas.';
    case 'media':
      return 'Confiança média: vale confirmar com a SPTrans ou a prefeitura.';
    default:
      return 'Confiança baixa: confirme antes de decidir.';
  }
}

/** Resposta de tempo real montada com dados de demonstração precisa do selo SIMULADO. */
export function respostaSimulada(r: RespostaChat, sptransDemo: boolean): boolean {
  if (origemDaResposta(r) !== 'TEMPO_REAL') return false;
  return !!r.dados_simulados || sptransDemo || r.fontes.some((f) => /simulad|demonstra/i.test(f.documento));
}

@Component({
  selector: 'pf-assistente',
  imports: [FormsModule, RouterLink, Icone, Origem],
  template: `
    <div class="pagina assistente">
      <header class="cabecalho assistente__cabecalho">
        <p class="sobretitulo"><pf-icone nome="conversa" /> Assistente</p>
        <h1>Como posso ajudar?</h1>
        <p class="cabecalho__apoio">Tire dúvidas sobre ônibus, Bilhete Único e acessibilidade.</p>
        <div class="disponibilidade disponibilidade--{{ status.assistente() }}" role="status">
          <span class="disponibilidade__luz" aria-hidden="true"></span>
          <p>
            @switch (status.assistente()) {
              @case ('disponivel') {
                <strong>Disponível</strong> · Respostas com fontes oficiais.
              }
              @case ('parcial') {
                <strong>Parcial.</strong> Responde sobre horários em tempo real; dúvidas gerais indisponíveis no momento.
              }
              @case ('indisponivel') {
                <strong>Indisponível no momento.</strong> Tente novamente em alguns instantes.
              }
              @default {
                Verificando o assistente…
              }
            }
          </p>
          @if (status.assistente() === 'indisponivel' || status.assistente() === 'parcial') {
            <button class="botao-texto" type="button" (click)="status.carregar(true)">Verificar novamente</button>
          }
        </div>
      </header>

      <section class="conversa" aria-label="Conversa com o assistente" role="log" aria-live="polite" aria-relevant="additions text">
        @if (mensagens().length === 0) {
          <div class="conversa__inicio">
            
            <div class="sugestoes" role="group" aria-label="Sugestões de pergunta">
              <p class="sugestoes__titulo">Comece por uma pergunta</p>
              <ul class="sugestoes__lista sugestoes__lista--coluna">
                @for (s of sugestoesTempoReal; track s) {
                  <li><button type="button" class="chip chip--pergunta" (click)="usarSugestao(s)">{{ s }}</button></li>
                }
              </ul>
              <details class="perguntas-gerais"><summary>Bilhete Único e acessibilidade{{ status.assistente() === 'parcial' ? ' · indisponível agora' : '' }}</summary>
              <ul class="sugestoes__lista sugestoes__lista--coluna">
                @for (s of sugestoesGerais; track s) {
                  <li><button type="button" class="chip chip--pergunta" [disabled]="status.assistente() !== 'disponivel'" (click)="usarSugestao(s)">{{ s }}</button></li>
                }
              </ul></details>
            </div>
          </div>
        }

        @for (m of mensagens(); track m.id) {
          <article class="troca" [attr.aria-label]="'Pergunta ' + m.id">
            <div class="fala fala--voce">
              <p class="fala__autor">Você</p>
              <p class="fala__texto">{{ m.pergunta }}</p>
            </div>

            @switch (m.estado) {
              @case ('enviando') {
                <div class="fala fala--assistente fala--processando">
                  <p class="fala__autor">Assistente</p>
                  <p class="processando"><span class="processando__pontos" aria-hidden="true"><i></i><i></i><i></i></span>Processando a pergunta…</p>
                </div>
              }
              @case ('erro') {
                <div class="fala fala--assistente fala--erro">
                  <p class="fala__autor">Assistente</p>
                  <p class="fala__texto"><pf-icone nome="alerta" /> {{ m.erro }}</p>
                  <button type="button" class="botao botao--contorno botao--pequeno" (click)="reenviar(m)" [disabled]="enviando()">
                    <pf-icone nome="atualizar" /> Tentar de novo
                  </button>
                </div>
              }
              @case ('ok') {
                @if (m.resposta; as r) {
                  @if (origem(r) === 'INDISPONIVEL') {
                    <div class="fala fala--assistente fala--indisponivel">
                      <div class="fala__cabeca">
                        <p class="fala__autor">Assistente</p>
                        <pf-origem tipo="indisponivel" rotulo="Indisponível" semDescricao />
                      </div>
                      <p class="fala__titulo">O assistente está fora do ar agora</p>
                      <p class="fala__texto">{{ r.resposta || 'Tente de novo em alguns minutos.' }}</p>
                      <p class="fala__texto">
                        O resto do aplicativo continua funcionando:
                        <a routerLink="/busca">veja os próximos ônibus</a> ou <a routerLink="/boletim">o boletim</a>.
                      </p>
                    </div>
                  } @else {
                    <div class="fala fala--assistente">
                      <div class="fala__cabeca">
                        <p class="fala__autor">Assistente</p>
                        @if (origem(r) === 'TEMPO_REAL') {
                          @if (simulada(r)) {
                            <pf-origem tipo="simulado" rotulo="SIMULADO · tempo real de demonstração" [forte]="true" />
                          } @else {
                            <pf-origem tipo="tempo-real" />
                          }
                        } @else {
                          <pf-origem tipo="base-oficial" />
                        }
                      </div>
                      <p class="fala__texto">{{ r.resposta }}</p>

                      @if (r.nao_consta) {
                        <div class="nao-consta">
                          <p class="nao-consta__titulo"><pf-icone nome="info" /> Não consta nas fontes oficiais consultadas</p>
                          <p>Confirme pela Central 156 da Prefeitura ou no site da SPTrans antes de decidir.</p>
                        </div>
                      }

                      <p class="confianca confianca--{{ r.confianca }}">
                        <span class="confianca__barras" aria-hidden="true"><i></i><i></i><i></i></span>
                        <span>{{ confianca(r) }}</span>
                      </p>

                      @if (r.fontes.length > 0) {
                        <details class="citacoes"><summary>Ver fontes da resposta</summary>
                          <p class="citacoes__titulo" [id]="'fontes-' + m.id">Fontes</p>
                          <ol class="citacoes__lista" [attr.aria-labelledby]="'fontes-' + m.id">
                            @for (f of r.fontes; track f.documento + f.trecho_id) {
                              <li>
                                <span class="citacoes__doc">{{ f.documento }}</span>
                                @if (f.trecho_id) {
                                  <span class="citacoes__trecho">trecho {{ f.trecho_id }}</span>
                                }
                              </li>
                            }
                          </ol>
                        </details>
                      }

                      <div class="fala__acoes">
                        @if (fala.falando() && lendo() === m.id) {
                          <button type="button" class="botao botao--contorno botao--pequeno" (click)="pararLeitura()">
                            <pf-icone nome="parar" /> Parar leitura
                          </button>
                        } @else {
                          <button type="button" class="botao botao--contorno botao--pequeno" (click)="ouvir(m)" [disabled]="!fala.suportaSintese">
                            <pf-icone nome="volume" /> Ouvir resposta
                          </button>
                        }
                      </div>
                    </div>
                  }
                }
              }
            }
          </article>
        }
      </section>

      <form class="compositor" (ngSubmit)="enviar()" novalidate>
        <label for="pergunta" class="compositor__rotulo">Sua pergunta</label>
        <div class="compositor__caixa" [class.compositor__caixa--erro]="erroCampo()" [class.compositor__caixa--ouvindo]="fala.ouvindo()">
          <textarea
            #campo
            id="pergunta"
            name="pergunta"
            rows="1"
            autocomplete="off"
            enterkeyhint="send"
            [attr.maxlength]="limite"
            [(ngModel)]="texto"
            (ngModelChange)="erroCampo.set('')"
            (keydown.enter)="teclaEnter($event)"
            (input)="ajustarAltura()"
            [placeholder]="fala.ouvindo() ? 'Ouvindo…' : 'Escreva sua pergunta'"
            [attr.aria-invalid]="erroCampo() ? 'true' : null"
            [attr.aria-describedby]="erroCampo() ? 'pergunta-erro pergunta-ajuda' : 'pergunta-ajuda'"
          ></textarea>
          <div class="compositor__botoes">
            @if (fala.suportaReconhecimento) {
              <button
                type="button"
                class="botao-icone"
                [class.botao-icone--ativo]="fala.ouvindo()"
                (click)="fala.ouvindo() ? fala.pararEscuta() : ditar()"
                [disabled]="enviando()"
              >
                <pf-icone nome="microfone" />
                <span class="vo">{{ fala.ouvindo() ? 'Parar de ouvir' : 'Falar a pergunta' }}</span>
              </button>
            }
            <button type="submit" class="botao-icone botao-icone--enviar" [disabled]="enviando()">
              <pf-icone nome="enviar" />
              <span class="vo">Enviar pergunta</span>
            </button>
          </div>
        </div>
        @if (fala.ouvindo()) {
          <p class="compositor__ouvindo" role="status">Ouvindo… fale a pergunta.</p>
        }
        @if (erroCampo()) {
          <p id="pergunta-erro" class="erro-campo"><pf-icone nome="alerta" /> {{ erroCampo() }}</p>
        }
        <div class="compositor__rodape">
          <p id="pergunta-ajuda" class="ajuda">
            Enter envia; Shift+Enter quebra a linha. As perguntas não são guardadas.
            <span class="compositor__conta" [class.compositor__conta--limite]="texto.length > limite - 50">{{ texto.length }}/{{ limite }}</span>
          </p>
          <label class="interruptor interruptor--compacto">
            <input type="checkbox" role="switch" name="auto" [checked]="lerAuto()" (change)="prefs.atualizar({ lerRespostaAuto: $any($event.target).checked })" />
            <span class="interruptor__trilho" aria-hidden="true"></span>
            <span>Ler respostas em voz alta</span>
          </label>
          @if (mensagens().length > 0) {
            <button type="button" class="botao-texto" (click)="limpar()">Limpar conversa</button>
          }
        </div>
      </form>
    </div>
  `,
})
export class Assistente {
  private readonly api = inject(ApiService);
  protected readonly prefs = inject(PreferencesService);
  protected readonly status = inject(StatusService);
  protected readonly fala = inject(SpeechService);
  private readonly campo = viewChild<ElementRef<HTMLTextAreaElement>>('campo');

  /** ?pergunta= vindo de outra tela (ex.: busca de linhas). */
  readonly pergunta = input<string | undefined>();

  protected readonly limite = LIMITE;
  protected readonly sugestoesTempoReal = ['Qual o destino da linha 8000-10?'];
  protected readonly sugestoesGerais = [
    'Tenho 65 anos, preciso pagar o ônibus?',
    'Como funciona o Bilhete Único?',
    'Como o ônibus ajuda quem usa cadeira de rodas?',
  ];
  protected texto = '';
  protected readonly mensagens = signal<Mensagem[]>([]);
  protected readonly enviando = computed(() => this.mensagens().some((m) => m.estado === 'enviando'));
  protected readonly erroCampo = signal('');
  protected readonly lerAuto = computed(() => this.prefs.prefs().lerRespostaAuto);
  protected readonly lendo = signal<number | null>(null);
  private contador = 0;
  private sessao = 0;

  constructor() {
    void this.status.carregar(true);
    effect(() => {
      const p = (this.pergunta() ?? '').trim();
      if (p) untracked(() => (this.texto = p.slice(0, LIMITE)));
    });
    inject(DestroyRef).onDestroy(() => {
      this.sessao++;
      this.fala.parar();
      this.fala.pararEscuta();
    });
  }

  protected origem(r: RespostaChat): OrigemResposta {
    return origemDaResposta(r);
  }

  protected simulada(r: RespostaChat): boolean {
    return respostaSimulada(r, this.status.demo());
  }

  protected confianca(r: RespostaChat): string {
    return confiancaEmPalavras(r.confianca);
  }

  protected segundos(ms: number): string {
    return ms < 1000 ? 'menos de 1 s' : `${(ms / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`;
  }

  protected usarSugestao(texto: string): void {
    this.texto = texto;
    void this.enviar();
  }

  protected teclaEnter(e: Event): void {
    const k = e as KeyboardEvent;
    if (k.shiftKey || k.isComposing) return;
    k.preventDefault();
    void this.enviar();
  }

  protected ajustarAltura(): void {
    const el = this.campo()?.nativeElement;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }

  protected ouvir(m: Mensagem): void {
    if (m.resposta && this.fala.falar(m.resposta.resposta)) this.lendo.set(m.id);
  }

  protected pararLeitura(): void {
    this.fala.parar();
    this.lendo.set(null);
  }

  protected limpar(): void {
    this.sessao++;
    this.pararLeitura();
    this.fala.pararEscuta();
    this.mensagens.set([]);
    this.campo()?.nativeElement.focus();
  }

  protected async ditar(): Promise<void> {
    const sessao = this.sessao;
    this.erroCampo.set('');
    try {
      const dito = await this.fala.escutar();
      if (sessao !== this.sessao) return;
      this.texto = dito.slice(0, LIMITE);
      this.campo()?.nativeElement.focus();
    } catch (e) {
      if (sessao !== this.sessao) return;
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

  protected reenviar(m: Mensagem): void {
    this.mensagens.update((l) => l.filter((x) => x.id !== m.id));
    void this.perguntar(m.pergunta);
  }

  protected async enviar(): Promise<void> {
    const pergunta = this.texto.trim();
    if (!pergunta) {
      this.erroCampo.set('Escreva uma pergunta antes de enviar.');
      this.campo()?.nativeElement.focus();
      return;
    }
    if (pergunta.length > LIMITE) {
      this.erroCampo.set(`A pergunta pode ter no máximo ${LIMITE} caracteres.`);
      return;
    }
    if (this.enviando()) return;
    this.erroCampo.set('');
    this.texto = '';
    setTimeout(() => this.ajustarAltura(), 0);
    await this.perguntar(pergunta);
  }

  private async perguntar(pergunta: string): Promise<void> {
    const sessao = this.sessao;
    const id = ++this.contador;
    this.mensagens.update((l) => [...l, { id, pergunta, estado: 'enviando' }]);
    const atualizar = (m: Partial<Mensagem>) =>
      this.mensagens.update((l) => l.map((x) => (x.id === id ? { ...x, ...m } : x)));
    try {
      const resposta = await firstValueFrom(this.api.perguntar(pergunta));
      if (sessao !== this.sessao) return;
      atualizar({ estado: 'ok', resposta });
      if (origemDaResposta(resposta) !== 'INDISPONIVEL' && this.lerAuto() && this.fala.falar(resposta.resposta)) {
        this.lendo.set(id);
      }
    } catch (e) {
      if (sessao !== this.sessao) return;
      const status = e instanceof ErroApi ? e.status : -1;
      const erro =
        status === 400
          ? `Escreva uma pergunta de até ${LIMITE} caracteres.`
          : status === 429
            ? 'Muitas perguntas seguidas. Espere um minuto e tente de novo.'
            : 'Não foi possível falar com o assistente agora. O resto do aplicativo continua funcionando.';
      atualizar({ estado: 'erro', erro });
    }
  }
}
