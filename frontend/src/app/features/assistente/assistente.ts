import { Component, DestroyRef, ElementRef, computed, effect, inject, input, signal, untracked, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, OrigemResposta, RespostaChat, TipoResposta, origemDaResposta, tipoDaResposta } from '../../core/models';
import { PreferencesService } from '../../core/preferences.service';
import { ErroVoz, SpeechService } from '../../core/speech.service';
import { StatusService } from '../../core/status.service';
import { Icone } from '../../shared/icone';
import { Origem } from '../../shared/origem';
import { ConversaService, Mensagem } from '../../core/conversa.service';
export type { Mensagem } from '../../core/conversa.service';


export const LIMITE = 500;

/** Frase sob a resposta. Depende do tipo, não só da confiança: uma recusa nunca aparece como "confiança alta". */
export function situacaoEmPalavras(r: RespostaChat, simulada = false): string {
  const tipo = tipoDaResposta(r);
  if (tipo === 'CONSULTA' && simulada) {
    return 'Consulta com dados simulados de demonstração, sem inteligência artificial: não use para decidir a viagem.';
  }
  if (tipo === 'CONSULTA' && r.confianca === 'baixa') {
    return 'Consulta direta, mas sem dados suficientes agora: confirme antes de decidir.';
  }
  switch (tipo) {
    case 'FUNDAMENTADA':
      return r.confianca === 'alta'
        ? 'Resposta baseada nas fontes oficiais citadas abaixo.'
        : 'Resposta baseada em parte nas fontes citadas: vale confirmar com a SPTrans ou a prefeitura.';
    case 'CONSULTA':
      return origemDaResposta(r) === 'BOLETIM'
        ? 'Consulta direta ao boletim do robô: confira a data e a cobertura antes de decidir.'
        : origemDaResposta(r) === 'CADASTRO'
          ? 'Consulta direta ao cadastro oficial da SPTrans, sem inteligência artificial.'
          : 'Consulta direta à previsão da SPTrans, sem inteligência artificial. Previsão não é chegada confirmada.';
    case 'RECUSA':
      return 'Não encontrei isso nas fontes oficiais: confirme antes de decidir.';
    case 'FORA_DA_AREA':
      return 'Sem dados oficiais fora de São Paulo: confirme com o órgão de transporte da cidade citada.';
    case 'INDISPONIVEL':
      return 'Assistente indisponível agora.';
    default:
      return 'Informação insuficiente nas fontes: confirme antes de decidir.';
  }
}

/** Resposta de tempo real montada com dados de demonstração precisa do selo SIMULADO. */
export function respostaSimulada(r: RespostaChat, sptransDemo: boolean): boolean {
  if (!['TEMPO_REAL', 'CADASTRO'].includes(origemDaResposta(r))) return false;
  return !!r.dados_simulados || sptransDemo || r.fontes.some((f) => /simulad|demonstra/i.test(f.documento));
}

@Component({
  selector: 'pf-assistente',
  imports: [FormsModule, RouterLink, Icone, Origem],
  template: `
    <div class="pagina assistente">
      <header class="cabecalho assistente__cabecalho">
        <p class="sobretitulo"><pf-icone nome="conversa" /> Assistente</p>
        <h1>Seu caminho começa aqui.</h1>
        <p class="cabecalho__apoio">Encontre seu ônibus. Confira o sentido. Entenda seus direitos.</p>
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

      <section class="conversa" aria-label="Conversa com o assistente" role="log" aria-live="polite" aria-relevant="additions text" [attr.aria-busy]="enviando()">
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
                  <p class="processando"><span class="processando__pontos" aria-hidden="true"><i></i><i></i><i></i></span>{{ esperaLonga() ? 'A consulta está levando mais tempo. Você pode continuar usando o aplicativo.' : 'Consultando as fontes para você…' }}</p>
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
                  @if (!r.disponivel || origem(r) === 'INDISPONIVEL') {
                    <div class="fala fala--assistente fala--indisponivel">
                      <div class="fala__cabeca">
                        <p class="fala__autor">Assistente</p>
                        <pf-origem tipo="indisponivel" rotulo="Indisponível" semDescricao />
                      </div>
                      <p class="fala__titulo">{{ origem(r) === 'TEMPO_REAL' ? 'A SPTrans não respondeu agora' : 'O assistente está fora do ar agora' }}</p>
                      <p class="fala__texto">{{ r.resposta || 'Tente de novo em alguns minutos.' }}</p>
                      <p class="fala__texto">
                        O resto do aplicativo continua funcionando:
                        <a routerLink="/busca">veja os próximos ônibus</a> ou <a routerLink="/boletim">o boletim</a>.
                      </p>
                      <button type="button" class="botao botao--contorno botao--pequeno" (click)="reenviar(m)" [disabled]="enviando()">Tentar de novo</button>
                    </div>
                  } @else {
                    <div class="fala fala--assistente">
                      <div class="fala__cabeca">
                        <p class="fala__autor">Assistente</p>
                        @if (origem(r) === 'TEMPO_REAL' || origem(r) === 'CADASTRO') {
                          @if (simulada(r)) {
                            <pf-origem tipo="simulado" rotulo="SIMULADO · tempo real de demonstração" [forte]="true" />
                          } @else if (origem(r) === 'CADASTRO') {
                            <pf-origem tipo="base-oficial" rotulo="Cadastro SPTrans" />
                          } @else {
                            <pf-origem tipo="tempo-real" />
                          }
                        } @else if (origem(r) === 'BOLETIM') {
                          <pf-origem [tipo]="r.natureza_dados === 'SIMULADO' ? 'simulado' : r.natureza_dados === 'ESTIMADO' ? 'estimado' : 'indisponivel'" />
                        } @else if (origem(r) === 'FORA_DA_AREA') {
                          <pf-origem tipo="indisponivel" rotulo="Fora da área atendida" semDescricao />
                        } @else {
                          <pf-origem tipo="base-oficial" />
                        }
                      </div>
                      <p class="fala__texto">{{ r.resposta }}</p>

                      @if (tipo(r) === 'RECUSA') {
                        <div class="nao-consta">
                          <p class="nao-consta__titulo"><pf-icone nome="info" /> Não consta nas fontes oficiais consultadas</p>
                          <p>Confirme pela Central 156 da Prefeitura ou no site da SPTrans antes de decidir.</p>
                        </div>
                      }

                      <p class="confianca confianca--{{ classeSituacao(r) }}" [attr.data-tipo]="tipo(r)">
                        <span class="confianca__barras" aria-hidden="true"><i></i><i></i><i></i></span>
                        <span>{{ confianca(r) }}</span>
                      </p>

                      @if (r.fontes.length > 0) {
                        <details class="citacoes"><summary>Ver fontes da resposta</summary>
                          <p class="citacoes__titulo" [id]="'fontes-' + m.id">Fontes</p>
                          <ol class="citacoes__lista" [attr.aria-labelledby]="'fontes-' + m.id">
                            @for (f of r.fontes; track f.documento + f.trecho_id) {
                              <li>
                                @if (fonteSegura(f.url)) {
                                  <a class="citacoes__doc" [href]="f.url" target="_blank" rel="noopener noreferrer">{{ f.documento }} <span class="vo">(abre em outra aba)</span></a>
                                } @else { <span class="citacoes__doc">{{ f.documento }}</span> }
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
                      @if ($last && r.acoes?.length) {
                        <div class="sugestoes__lista" role="group" aria-label="Continuar a conversa">
                          @for (a of r.acoes; track a.titulo) {
                            @if (a.pergunta) {
                              <button class="chip" type="button" [disabled]="enviando()" (click)="usarSugestao(a.pergunta)">{{ a.titulo }}</button>
                            } @else if (rotaSegura(a.rota)) {
                              <a class="chip" [routerLink]="a.rota!.split('?')[0]" [queryParams]="parametros(a.rota!)">{{ a.titulo }}</a>
                            }
                          }
                        </div>
                      }
                    </div>
                  }
                }
              }
            }
          </article>
        }
      </section>
      <div #fimConversa></div>

      <form class="compositor" (ngSubmit)="enviar()" novalidate>
        @if (conversa.contexto(); as c) {
          @if (c.ponto || c.linha) {
            <p class="compositor__contexto">Nesta conversa: @if (c.linha) { linha {{ c.linha }} } @if (c.ponto) { @if (c.linha) { · } ponto {{ c.ponto }} } @if (c.sentido) { · sentido {{ c.sentido }} }</p>
          }
        }
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
            Enter envia; Shift+Enter quebra a linha. Histórico só nesta sessão, apagado ao recarregar.
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
  protected readonly conversa = inject(ConversaService);
  protected readonly prefs = inject(PreferencesService);
  protected readonly status = inject(StatusService);
  protected readonly fala = inject(SpeechService);
  private readonly campo = viewChild<ElementRef<HTMLTextAreaElement>>('campo');
  private readonly fimConversa = viewChild<ElementRef<HTMLElement>>('fimConversa');

  /** ?pergunta= vindo de outra tela (ex.: busca de linhas). */
  readonly pergunta = input<string | undefined>();

  protected readonly limite = LIMITE;
  protected readonly sugestoesTempoReal = ['Quais linhas passam no ponto 70016916?', 'Quando vem a 875A-10?', 'Qual o destino da linha 875A-10?', 'Onde fica o ponto da Av. Paulista, 1374?'];
  protected readonly sugestoesGerais = [
    'Tenho 65 anos, preciso pagar o ônibus?',
    'Como funciona o Bilhete Único?',
    'Como o ônibus ajuda quem usa cadeira de rodas?',
  ];
  protected texto = '';
  protected readonly mensagens = this.conversa.mensagens;
  protected readonly enviando = computed(() => this.mensagens().some((m) => m.estado === 'enviando'));
  protected readonly erroCampo = signal('');
  protected readonly lerAuto = computed(() => this.prefs.prefs().lerRespostaAuto);
  protected readonly lendo = signal<number | null>(null);
  protected readonly esperaLonga = signal(false);
  private sessao = 0;

  constructor() {
    void this.status.carregar(true);
    effect(() => {
      const p = (this.pergunta() ?? '').trim();
      if (p) untracked(() => (this.texto = p.slice(0, LIMITE)));
    });
    inject(DestroyRef).onDestroy(() => {
      this.sessao++;
      this.mensagens.update(l => l.map(m => m.estado === 'enviando' ? { ...m, estado: 'erro', erro: 'Consulta interrompida ao sair. Tente novamente.' } : m));
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

  protected tipo(r: RespostaChat): TipoResposta {
    return tipoDaResposta(r);
  }

  /** Barras: três só para resposta fundamentada com confiança alta ou consulta direta; uma para recusa/insuficiente. */
  protected classeSituacao(r: RespostaChat): 'alta' | 'media' | 'baixa' {
    const t = tipoDaResposta(r);
    if (t === 'CONSULTA') {
      if (r.confianca === 'baixa' || this.simulada(r)) return 'baixa';
      return origemDaResposta(r) === 'BOLETIM' || r.confianca === 'media' ? 'media' : 'alta';
    }
    if (t === 'FUNDAMENTADA') return r.confianca === 'alta' ? 'alta' : 'media';
    return 'baixa';
  }

  protected confianca(r: RespostaChat): string {
    return situacaoEmPalavras(r, this.simulada(r));
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
    this.conversa.limpar();
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
    if (this.enviando()) return;
    this.mensagens.update((l) => l.filter((x) => x.id !== m.id));
    void this.perguntar(m.pergunta, m.contexto);
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

  protected fonteSegura(url?: string | null): boolean { return !!url && /^https:\/\/[a-z0-9.-]+\//i.test(url); }
  protected rotaSegura(rota?: string | null): boolean { return !!rota && /^\/(ponto\/\d+|linha\/[\w-]+)(\?sentido=[12])?$|^\/busca\?perto=1$|^\/boletim$/.test(rota); }
  protected parametros(rota: string): Record<string, string> { return Object.fromEntries(new URLSearchParams(rota.split('?')[1])); }

  private async perguntar(pergunta: string, contexto = this.conversa.contexto()): Promise<void> {
    const sessao = this.sessao;
    const id = ++this.conversa.contador;
    this.esperaLonga.set(false);
    const espera = setTimeout(() => this.esperaLonga.set(true), 8000);
    this.mensagens.update((l) => [...l.slice(-39), { id, pergunta, estado: 'enviando', contexto }]);
    setTimeout(() => this.fimConversa()?.nativeElement.scrollIntoView?.({ block: 'nearest' }), 0);
    const atualizar = (m: Partial<Mensagem>) =>
      this.mensagens.update((l) => l.map((x) => (x.id === id ? { ...x, ...m } : x)));
    try {
      const resposta = await firstValueFrom(this.api.perguntar(pergunta, contexto));
      if (sessao !== this.sessao) return;
      atualizar({ estado: 'ok', resposta });
      this.conversa.contexto.set(resposta.contexto ?? null);
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
    } finally {
      clearTimeout(espera);
    }
  }
}
