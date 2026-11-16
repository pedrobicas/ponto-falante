import { Component, ElementRef, computed, effect, inject, input, signal, untracked, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AssistenteEmbarque } from '../../core/assistente-embarque.service';
import { TrajetoFavorito } from '../../core/embarque.models';
import { EmbarqueStore, INTERVALO_ACOMPANHAMENTO_MS, MAX_LINHAS, OpcaoLinha } from '../../core/embarque.store';
import { horaCurta } from '../../core/format';
import { ErroApi, OnibusPrevisto, Ponto } from '../../core/models';
import { SpeechService } from '../../core/speech.service';
import { Icone } from '../../shared/icone';
import { Letreiro } from '../../shared/letreiro';
import { SeloFonte } from '../../shared/selo-fonte';
import { AssistenteEmbarquePainel } from './assistente-embarque';
import { ConferirLetreiro } from './conferir-letreiro';

export function minutosCurtos(m?: number | null): string {
  if (m == null) return 'sem previsão agora';
  if (m <= 0) return 'agora';
  return m === 1 ? '1 min' : `${m} min`;
}

export function fraseOnibusEmbarque(o: OnibusPrevisto): string {
  const tempo = o.minutos <= 0 ? 'previsto para agora' : o.minutos === 1 ? 'previsto em 1 minuto' : `previsto em ${o.minutos} minutos`;
  return `Linha ${o.letreiro}${o.destino ? ', sentido ' + o.destino : ''}, ${tempo}, às ${o.previsto_em}.${o.acessivel ? ' Veículo acessível.' : ''}`;
}

@Component({
  selector: 'pf-embarque',
  imports: [FormsModule, RouterLink, Icone, Letreiro, SeloFonte, AssistenteEmbarquePainel, ConferirLetreiro],
  template: `
    <div class="pagina embarque">
      <header class="embarque__cabecalho">
        <p class="sobretitulo"><pf-icone nome="volume" /> Embarque assistido</p>
        <h1>Do ponto até o ônibus, com aviso por voz.</h1>
        <p class="embarque__apoio">Escolha o ponto e o ônibus. Eu acompanho as previsões reais da SPTrans e aviso quando ele estiver chegando, sem repetir à toa.</p>
        <ol class="etapas" aria-label="Etapas">
          @for (e of etapas; track e.id; let i = $index) {
            <li class="etapas__item" [class.etapas__item--feita]="indiceEtapa() > i" [attr.aria-current]="indiceEtapa() === i ? 'step' : null">
              <span class="etapas__num" aria-hidden="true">{{ indiceEtapa() > i ? '✓' : i + 1 }}</span>
              <span>{{ e.texto }}</span>
              <span class="vo">{{ indiceEtapa() > i ? ' (concluída)' : indiceEtapa() === i ? ' (etapa atual)' : '' }}</span>
            </li>
          }
        </ol>
      </header>

      <p class="vo" aria-live="polite">{{ store.avisoVivo() }}</p>
      <p class="vo" role="alert">{{ store.avisoUrgente() }}</p>

      <div class="embarque__grade">
        <div class="embarque__principal">
          @switch (store.etapa()) {
            @case ('ponto') {
              @if (store.favoritos().length) {
                <section class="cartao embarque__favoritos" aria-labelledby="fav-titulo">
                  <h2 id="fav-titulo"><pf-icone nome="estrela" /> Seus trajetos</h2>
                  @if (store.erroFavoritos()) { <p class="ajuda">{{ store.erroFavoritos() }}</p> }
                  <ul class="rotas-fav">
                    @for (f of store.favoritos(); track f.id) {
                      <li class="rota-fav">
                        <button type="button" class="rota-fav__principal" (click)="usarFavorito(f)" [disabled]="store.iniciando()">
                          <pf-letreiro [codigo]="f.linha" />
                          <span class="rota-fav__texto">
                            <span class="rota-fav__nome">{{ f.apelido || 'Linha ' + f.linha }}</span>
                            <span class="rota-fav__meta">{{ f.destino ? 'sentido ' + f.destino + ' · ' : '' }}{{ f.ponto_nome }}{{ f.simulado ? ' · SIMULADO' : '' }}</span>
                          </span>
                          <span class="rota-fav__acao"><pf-icone nome="volume" /> Acompanhar<span class="vo"> {{ f.apelido || 'linha ' + f.linha }}</span></span>
                        </button>
                        <div class="rota-fav__extra">
                          @if (editando() === f.id) {
                            <form class="rota-fav__renomear" (ngSubmit)="renomear(f)">
                              <label [for]="'apelido-' + f.id">Novo apelido</label>
                              <input [id]="'apelido-' + f.id" name="apelido" maxlength="40" [(ngModel)]="apelido" autocomplete="off" />
                              <button type="submit" class="botao botao--pequeno botao--primario">Salvar</button>
                              <button type="button" class="botao botao--pequeno botao--contorno" (click)="editando.set(null)">Cancelar</button>
                            </form>
                          } @else if (removendo() === f.id) {
                            <p class="rota-fav__confirmar" role="group" aria-label="Confirmar remoção">
                              Remover este trajeto?
                              <button type="button" class="botao botao--pequeno botao--perigo" (click)="remover(f)">Remover</button>
                              <button type="button" class="botao botao--pequeno botao--contorno" (click)="removendo.set(null)">Cancelar</button>
                            </p>
                          } @else {
                            <button type="button" class="botao-texto" (click)="editar(f)">Renomear<span class="vo"> {{ f.apelido || 'linha ' + f.linha }}</span></button>
                            <button type="button" class="botao-texto" (click)="removendo.set(f.id)">Remover<span class="vo"> {{ f.apelido || 'linha ' + f.linha }}</span></button>
                          }
                        </div>
                      </li>
                    }
                  </ul>
                </section>
              }

              <section class="cartao" aria-labelledby="ponto-titulo">
                <h2 id="ponto-titulo" tabindex="-1" #tituloPonto><pf-icone nome="ponto" /> Em qual ponto você está?</h2>
                <button type="button" class="botao botao--primario botao--grande embarque__gps" (click)="perto()" [disabled]="store.localizando()">
                  <pf-icone nome="ponto" /> {{ store.localizando() ? 'Procurando pontos perto de você…' : 'Usar minha localização' }}
                </button>
                <p class="ajuda">A localização é pedida ao navegador, usada só nesta busca e não fica guardada.</p>
                <form class="campo-busca" role="search" aria-label="Buscar ponto" (ngSubmit)="buscar()" novalidate>
                  <label for="emb-busca" class="campo-busca__rotulo">Ou digite o nome do ponto, a rua com número ou o código</label>
                  <div class="campo-busca__linha">
                    <pf-icone nome="busca" />
                    <input id="emb-busca" name="busca" type="search" autocomplete="off" maxlength="80" enterkeyhint="search"
                           [placeholder]="store.modo() === 'demo' ? 'Ex.: Paulista' : 'Ex.: Avenida Paulista 1000'" [(ngModel)]="termo" />
                    <button type="submit" class="botao botao--primario" [disabled]="store.buscando()">Buscar</button>
                  </div>
                </form>
                @if (store.avisoBusca()) { <p class="ajuda" role="status">{{ store.avisoBusca() }}</p> }

                @if (store.ponto(); as p) {
                  <div class="confirmar-ponto" role="group" aria-labelledby="confirmar-titulo">
                    <h3 id="confirmar-titulo" tabindex="-1" #tituloConfirmar>É este o seu ponto?</h3>
                    <p class="confirmar-ponto__nome">{{ p.nome }}</p>
                    <p class="confirmar-ponto__meta">
                      {{ p.endereco ? p.endereco + ' · ' : '' }}código {{ p.codigo }}{{ p.distancia_metros != null ? ' · a ' + p.distancia_metros + ' m de você' : '' }}
                    </p>
                    @if (p.linhas?.length) {
                      <p class="ajuda">Linhas no cadastro: {{ p.linhas!.slice(0, 8).join(', ') }}{{ p.linhas!.length > 8 ? '…' : '' }}</p>
                    }
                    <div class="confirmar-ponto__acoes">
                      <button type="button" class="botao botao--primario botao--grande" (click)="confirmarPonto()"><pf-icone nome="certo" /> Sim, é este ponto</button>
                      <button type="button" class="botao botao--contorno botao--grande" (click)="store.trocarPonto()">Escolher outro</button>
                    </div>
                  </div>
                } @else if (store.opcoesPonto().length) {
                  <h3 class="embarque__subtitulo">Escolha o ponto</h3>
                  <ul class="opcoes-ponto">
                    @for (p of store.opcoesPonto(); track p.codigo; let i = $index) {
                      <li>
                        <button type="button" class="opcao-ponto" (click)="escolherPonto(p)">
                          <span class="opcao-ponto__num" aria-hidden="true">{{ i + 1 }}</span>
                          <span class="opcao-ponto__texto">
                            <span class="opcao-ponto__nome">{{ p.nome }}</span>
                            <span class="opcao-ponto__meta">{{ p.endereco ? p.endereco + ' · ' : '' }}{{ p.distancia_metros != null ? p.distancia_metros + ' m · ' : '' }}código {{ p.codigo }}</span>
                          </span>
                          <pf-icone nome="chevron" />
                        </button>
                      </li>
                    }
                  </ul>
                }
              </section>
            }

            @case ('linha') {
              <section class="cartao" aria-labelledby="linha-titulo">
                <div class="ponto-confirmado">
                  <pf-icone nome="ponto" />
                  <div>
                    <p class="ponto-confirmado__rotulo">Seu ponto</p>
                    <p class="ponto-confirmado__nome">{{ store.ponto()?.nome }}</p>
                    <p class="ajuda">{{ store.ponto()?.endereco ? store.ponto()?.endereco + ' · ' : '' }}código {{ store.ponto()?.codigo }}</p>
                  </div>
                  <button type="button" class="botao-texto" (click)="store.trocarPonto()">Trocar ponto</button>
                </div>
                <h2 id="linha-titulo" tabindex="-1" #tituloLinha><pf-icone nome="onibus" /> Qual ônibus você vai pegar?</h2>
                <p class="ajuda">Escolha até {{ maxLinhas }} linhas. O sentido aparece pelo destino: confira se é para onde você vai.</p>
                @if (store.carregandoLinhas()) {
                  <p role="status" class="ajuda">Buscando as linhas deste ponto…</p>
                } @else {
                  @if (store.avisoLinhas()) { <p class="ajuda" role="status">{{ store.avisoLinhas() }}</p> }
                  <fieldset class="opcoes-linha">
                    <legend class="vo">Linhas que param neste ponto</legend>
                    @for (l of store.linhas(); track l.letreiro + l.sentido) {
                      <label class="opcao-linha" [class.opcao-linha--marcada]="store.linhaEscolhida(l)">
                        <input type="checkbox" [checked]="store.linhaEscolhida(l)" (change)="store.alternarLinha(l)"
                               [disabled]="!store.linhaEscolhida(l) && store.escolhidas().length >= maxLinhas" />
                        <pf-letreiro [codigo]="l.letreiro" />
                        <span class="opcao-linha__texto">
                          <span class="opcao-linha__destino">{{ l.destino ? 'sentido ' + l.destino : 'sentido não informado' }}</span>
                          <span class="opcao-linha__prev" [class.opcao-linha__prev--sem]="l.proximo_min == null">{{ textoProximo(l) }}</span>
                        </span>
                      </label>
                    }
                  </fieldset>
                }
                <div class="embarque__rodape-acao">
                  <button type="button" class="botao botao--primario botao--grande" (click)="iniciar()"
                          [disabled]="!store.escolhidas().length || store.iniciando()">
                    <pf-icone nome="volume" /> {{ store.iniciando() ? 'Começando…' : 'Começar a acompanhar' }}
                  </button>
                  @if (store.escolhidas().length) {
                    <p class="ajuda">{{ store.escolhidas().length }} {{ store.escolhidas().length === 1 ? 'linha escolhida' : 'linhas escolhidas' }}: {{ nomesEscolhidas() }}</p>
                  }
                </div>
                @if (store.erro()) { <p class="aviso-linha" role="alert"><pf-icone nome="alerta" /><span>{{ store.erro() }}</span></p> }
              </section>
            }

            @case ('acompanhando') {
              <section class="painel-emb" [class.painel-emb--simulado]="store.sessao()?.simulado" aria-labelledby="acomp-titulo">
                @if (store.sessao()?.simulado) {
                  <p class="quadro__fita"><span class="quadro__fita-marca">SIMULADO</span><span>Horários de demonstração. Não são ônibus reais.</span></p>
                }
                <div class="painel-emb__topo">
                  <div>
                    <h2 id="acomp-titulo" tabindex="-1" #tituloAcomp>Acompanhando</h2>
                    <p class="painel-emb__ponto">{{ store.sessao()?.ponto_nome }}</p>
                  </div>
                  <span class="painel-emb__vivo" aria-hidden="true"><span class="painel-emb__pulso"></span> ao vivo</span>
                </div>

                @if (store.situacao(); as sit) {
                  @if (sit.proximo; as o) {
                    <div class="painel-emb__proximo" [class.painel-emb__proximo--chegando]="o.minutos <= 1">
                      <span class="vo">Próximo ônibus: {{ frase(o) }}</span>
                      <div class="painel-emb__linha" aria-hidden="true">
                        <pf-letreiro [codigo]="o.letreiro" [grande]="true" />
                        <span class="painel-emb__destino">{{ o.destino }}</span>
                      </div>
                      <div class="painel-emb__tempo" aria-hidden="true">
                        @if (o.minutos <= 1) {
                          <span class="painel-emb__chegando">{{ o.minutos <= 0 ? 'chegando' : '1 min' }}</span>
                        } @else {
                          <span class="painel-emb__num">{{ o.minutos }}</span><span class="painel-emb__un">min</span>
                        }
                        <span class="painel-emb__hora">previsão {{ o.previsto_em }}</span>
                      </div>
                      <p class="painel-emb__acessivel" aria-hidden="true">
                        @if (o.acessivel) { <pf-icone nome="acessivel" /> Veículo acessível } @else { Sem informação de acessibilidade }
                      </p>
                    </div>
                    @if (sit.onibus.length > 1) {
                      <h3 class="painel-emb__depois">Depois dele</h3>
                      <ul class="painel-emb__lista">
                        @for (x of sit.onibus.slice(1, 4); track x.letreiro + x.veiculo + x.previsto_em) {
                          <li><span class="vo">{{ frase(x) }}</span><span aria-hidden="true"><strong>{{ x.letreiro }}</strong> · {{ minutosCurtos(x.minutos) }} · {{ x.previsto_em }}</span></li>
                        }
                      </ul>
                    }
                  } @else {
                    <div class="painel-emb__vazio" role="status">
                      <p><strong>Nenhum ônibus {{ linhasTexto() }} previsto agora.</strong></p>
                      <p>Continuo consultando a SPTrans a cada {{ intervaloSeg }} segundos e aviso quando aparecer.</p>
                      @if (sit.outras_linhas_previstas?.length) {
                        <p class="ajuda">Outras linhas previstas neste ponto: {{ sit.outras_linhas_previstas!.slice(0, 6).join(', ') }}.</p>
                      }
                    </div>
                  }
                  <div class="painel-emb__rodape">
                    <pf-selo-fonte [fonte]="sit.fonte" />
                    <span>Atualizado às {{ hora(sit.consultado_em) }} · atualiza sozinho</span>
                  </div>
                } @else {
                  <p class="painel-emb__carregando" role="status">Consultando as previsões da SPTrans…</p>
                }
                @if (store.falhando()) {
                  <p class="aviso-linha painel-emb__falha" role="alert"><pf-icone nome="alerta" /><span>{{ store.erro() }} Mostrando a última previsão recebida.</span>
                    <button type="button" class="botao-texto" (click)="store.atualizar()">Tentar agora</button></p>
                }
              </section>

              @if (store.ultimoAviso(); as a) {
                <div class="ultimo-aviso" [class.ultimo-aviso--urgente]="a.urgente">
                  <p><span class="ultimo-aviso__rotulo">Último aviso</span> {{ a.texto }}</p>
                </div>
              }

              <div class="embarque__comandos">
                <button type="button" class="botao botao--primario botao--grande embarque__embarquei" (click)="embarquei()">
                  <pf-icone nome="certo-circulo" /> Embarquei
                </button>
                <button type="button" class="botao botao--contorno botao--grande" (click)="repetir()">
                  <pf-icone nome="volume" /> Repetir aviso
                </button>
                <button type="button" class="botao botao--contorno botao--grande" [attr.aria-pressed]="store.vozAtiva()" (click)="store.alternarVoz()">
                  <pf-icone [nome]="store.vozAtiva() ? 'volume' : 'parar'" /> Voz do aplicativo: {{ store.vozAtiva() ? 'ligada' : 'desligada' }}
                </button>
                <button type="button" class="botao botao--contorno botao--grande" (click)="camera.set(!camera())" [attr.aria-expanded]="camera()">
                  <pf-icone nome="onibus" /> Conferir o letreiro pela câmera
                </button>
              </div>

              @if (camera()) {
                <pf-conferir-letreiro [linha]="store.sessao()!.linhas[0].letreiro" [sessao]="store.sessao()!.id" (fechar)="camera.set(false)" />
              }

              <div class="embarque__secundarios">
                @if (!store.favoritoAtual()) {
                  @if (salvando()) {
                    <form class="rota-fav__renomear" (ngSubmit)="salvarFavorito()">
                      <label for="novo-apelido">Apelido do trajeto (opcional)</label>
                      <input id="novo-apelido" name="novoApelido" maxlength="40" placeholder="Ex.: Trabalho" [(ngModel)]="apelido" autocomplete="off" />
                      <button type="submit" class="botao botao--pequeno botao--primario">Salvar trajeto</button>
                      <button type="button" class="botao botao--pequeno botao--contorno" (click)="salvando.set(false)">Cancelar</button>
                    </form>
                  } @else {
                    <button type="button" class="botao-texto" (click)="salvando.set(true)"><pf-icone nome="estrela" /> Salvar este trajeto nos favoritos</button>
                  }
                } @else {
                  <p class="ajuda"><pf-icone nome="estrela" /> Trajeto salvo{{ store.favoritoAtual()?.apelido ? ' como "' + store.favoritoAtual()?.apelido + '"' : '' }}.</p>
                }
                <button type="button" class="botao-texto" (click)="encerrar()">Encerrar acompanhamento</button>
              </div>
              <p class="vo" role="status">{{ mensagem() }}</p>

              <p class="embarque__seguranca">
                <pf-icone nome="escudo" />
                <span>Previsão da SPTrans: o ônibus pode adiantar, atrasar ou não passar. Confirme sempre a linha com o motorista.
                  {{ store.telaAcesa() ? 'A tela fica acesa enquanto acompanho.' : 'Deixe esta tela aberta para receber os avisos.' }}</span>
              </p>
            }
          }
          @if (store.etapa() !== 'acompanhando' && mensagem()) {
            <p class="ajuda" role="status">{{ mensagem() }}</p>
          }
        </div>

        <aside class="embarque__lateral" aria-label="Assistente de embarque">
          <pf-assistente-embarque />
        </aside>
      </div>

      <section class="embarque__privacidade" aria-labelledby="priv-titulo">
        <h2 id="priv-titulo" class="vo">Privacidade</h2>
        <p>Sem login: seus trajetos ficam ligados a um código aleatório deste aparelho. Localização e fotos não são guardadas.
          <a routerLink="/sobre" fragment="dados">Saiba mais</a>.</p>
        @if (apagando()) {
          <p role="group" aria-label="Confirmar exclusão">Apagar trajetos e histórico de acompanhamento deste aparelho?
            <button type="button" class="botao botao--pequeno botao--perigo" (click)="apagarDados()">Apagar tudo</button>
            <button type="button" class="botao botao--pequeno botao--contorno" (click)="apagando.set(false)">Cancelar</button>
          </p>
        } @else {
          <button type="button" class="botao-texto" (click)="apagando.set(true)">Apagar meus dados do embarque</button>
        }
      </section>
    </div>
  `,
})
export class EmbarquePage {
  protected readonly store = inject(EmbarqueStore);
  protected readonly assistente = inject(AssistenteEmbarque);
  protected readonly fala = inject(SpeechService);

  /** Parâmetros opcionais da rota (vindos do assistente geral): ?ponto=&linha=&sentido=&modo= */
  readonly ponto = input<string | undefined>();
  readonly linha = input<string | undefined>();
  readonly sentido = input<string | undefined>();
  readonly modo = input<string | undefined>();

  protected readonly etapas = [
    { id: 'ponto', texto: 'Ponto' },
    { id: 'linha', texto: 'Ônibus' },
    { id: 'acompanhando', texto: 'Acompanhar' },
  ];
  protected readonly maxLinhas = MAX_LINHAS;
  protected readonly intervaloSeg = INTERVALO_ACOMPANHAMENTO_MS / 1000;
  protected readonly indiceEtapa = computed(() => ['ponto', 'linha', 'acompanhando'].indexOf(this.store.etapa()));
  protected termo = '';
  protected apelido = '';
  protected readonly editando = signal<number | null>(null);
  protected readonly removendo = signal<number | null>(null);
  protected readonly salvando = signal(false);
  protected readonly apagando = signal(false);
  protected readonly camera = signal(false);
  protected readonly mensagem = signal('');
  protected readonly minutosCurtos = minutosCurtos;
  protected readonly frase = fraseOnibusEmbarque;

  private readonly tituloConfirmar = viewChild<ElementRef<HTMLElement>>('tituloConfirmar');
  private readonly tituloLinha = viewChild<ElementRef<HTMLElement>>('tituloLinha');
  private readonly tituloAcomp = viewChild<ElementRef<HTMLElement>>('tituloAcomp');
  private readonly tituloPonto = viewChild<ElementRef<HTMLElement>>('tituloPonto');

  constructor() {
    void this.store.carregarFavoritos();
    effect(() => {
      const modo = this.modo();
      const ponto = this.ponto();
      const linha = this.linha();
      const sentido = this.sentido();
      untracked(() => void this.abrir(modo, ponto, linha, sentido));
    });
    // Leva o foco para o título de cada etapa nova (leitores de tela anunciam onde a pessoa está).
    let anterior = this.store.etapa();
    effect(() => {
      const etapa = this.store.etapa();
      const temPonto = !!this.store.ponto();
      if (etapa === anterior && !(etapa === 'ponto' && temPonto)) {
        anterior = etapa;
        return;
      }
      anterior = etapa;
      setTimeout(() => {
        const alvo = etapa === 'acompanhando' ? this.tituloAcomp() : etapa === 'linha' ? this.tituloLinha()
          : temPonto ? this.tituloConfirmar() : this.tituloPonto();
        alvo?.nativeElement.focus();
      }, 60);
    });
  }

  private async abrir(modo?: string, ponto?: string, linha?: string, sentido?: string): Promise<void> {
    if (modo === 'demo') this.store.modoForcado.set('demo');
    const codigo = Number(ponto);
    if (ponto && Number.isSafeInteger(codigo) && codigo > 0) {
      if (this.store.sessao()?.ponto === codigo && (!linha || this.store.sessao()?.linhas.some((l) => l.letreiro === linha.toUpperCase()))) return;
      this.store.escolherPonto({ codigo, nome: `Ponto ${codigo}` });
      const opcoes = await this.store.confirmarPonto();
      if (linha) {
        const s = Number(sentido);
        const l = opcoes.find((o) => o.letreiro === linha.toUpperCase() && (!s || o.sentido === s || !o.sentido))
          ?? opcoes.find((o) => o.letreiro === linha.toUpperCase());
        if (l) {
          this.store.escolhidas.set([{ letreiro: l.letreiro, sentido: l.sentido || null, destino: l.destino }]);
          await this.tentar(() => this.store.iniciar(), `Acompanhando a linha ${l.letreiro}. Vou avisar quando estiver chegando.`);
        } else {
          this.mensagem.set(`A linha ${linha} não aparece agora neste ponto. Escolha uma das linhas abaixo.`);
        }
      }
      return;
    }
    await this.store.retomar();
  }

  protected linhasTexto(): string {
    const l = this.store.sessao()?.linhas.map((x) => x.letreiro) ?? [];
    return l.length === 1 ? `da linha ${l[0]}` : `das linhas ${l.join(', ')}`;
  }

  protected nomesEscolhidas(): string {
    return this.store.escolhidas().map((l) => l.letreiro + (l.destino ? ` (${l.destino})` : '')).join(', ');
  }

  protected textoProximo(l: OpcaoLinha): string {
    if (l.proximo_min == null) return 'sem previsão agora';
    return l.proximo_min <= 0 ? 'próximo previsto para agora' : `próximo em ${l.proximo_min} min`;
  }

  protected hora(iso: string): string {
    return horaCurta(new Date(iso));
  }

  protected async buscar(): Promise<void> {
    this.store.trocarPonto();
    await this.store.buscarPontos(this.termo);
  }

  protected async perto(): Promise<void> {
    this.store.trocarPonto();
    await this.store.pontosPerto();
  }

  protected escolherPonto(p: Ponto): void {
    this.store.escolherPonto(p);
  }

  protected async confirmarPonto(): Promise<void> {
    await this.store.confirmarPonto();
  }

  protected async iniciar(): Promise<void> {
    await this.tentar(() => this.store.iniciar(), '');
  }

  protected async usarFavorito(f: TrajetoFavorito): Promise<void> {
    await this.tentar(() => this.store.usarFavorito(f), '');
  }

  protected async embarquei(): Promise<void> {
    await this.store.encerrar('EMBARQUEI');
    this.mensagem.set('Boa viagem! Acompanhamento encerrado.');
  }

  protected async encerrar(): Promise<void> {
    await this.store.encerrar('DESISTI');
    this.mensagem.set('Acompanhamento encerrado.');
  }

  protected repetir(): void {
    const t = this.store.repetir();
    if (!t) this.store.dizer(this.store.situacaoFalada(), true);
  }

  protected editar(f: TrajetoFavorito): void {
    this.apelido = f.apelido ?? '';
    this.removendo.set(null);
    this.editando.set(f.id);
  }

  protected async renomear(f: TrajetoFavorito): Promise<void> {
    await this.tentar(() => this.store.renomearFavorito(f, this.apelido), 'Apelido salvo.');
    this.editando.set(null);
  }

  protected async remover(f: TrajetoFavorito): Promise<void> {
    await this.tentar(() => this.store.removerFavorito(f), 'Trajeto removido.');
    this.removendo.set(null);
  }

  protected async salvarFavorito(): Promise<void> {
    await this.tentar(async () => {
      await this.store.salvarFavoritoAtual(this.apelido);
    }, 'Trajeto salvo nos favoritos.');
    this.apelido = '';
    this.salvando.set(false);
  }

  protected async apagarDados(): Promise<void> {
    await this.tentar(() => this.store.apagarDados(), 'Seus dados do embarque foram apagados.');
    this.assistente.limpar();
    this.apagando.set(false);
  }

  private async tentar(acao: () => Promise<unknown>, sucesso: string): Promise<void> {
    this.mensagem.set('');
    try {
      await acao();
      if (sucesso) this.mensagem.set(sucesso);
    } catch (e) {
      const texto = e instanceof ErroApi ? e.message : 'Não foi possível concluir. Tente de novo.';
      this.mensagem.set(texto);
      this.store.erro.set(texto);
    }
  }
}
