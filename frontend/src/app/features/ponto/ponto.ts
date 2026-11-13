import { DOCUMENT } from '@angular/common';
import { Component, DestroyRef, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { FavoritosService } from '../../core/favoritos.service';
import { horaCurta, textoMinutos } from '../../core/format';
import { ErroApi, Modo, OnibusPrevisto, PrevisoesPonto } from '../../core/models';
import { PreferencesService } from '../../core/preferences.service';
import { RecentesService } from '../../core/recentes.service';
import { SpeechService } from '../../core/speech.service';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { Letreiro } from '../../shared/letreiro';
import { MensagemErro } from '../../shared/mensagem-erro';
import { SeloFonte } from '../../shared/selo-fonte';

export const INTERVALO_ATUALIZACAO_MS = 30_000;

export function chaveOnibus(o: OnibusPrevisto): string {
  return `${o.letreiro}|${o.veiculo ?? ''}|${o.destino}`;
}

/** Frase completa de uma linha do painel, para leitores de tela. */
export function fraseOnibus(o: OnibusPrevisto): string {
  const acess = o.acessivel ? ' Veículo acessível para cadeira de rodas.' : '';
  return `Linha ${o.letreiro}, destino ${o.destino}, ${textoMinutos(o.minutos)}, previsão às ${o.previsto_em}.${acess}`;
}

@Component({
  selector: 'pf-ponto',
  imports: [RouterLink, Carregando, MensagemErro, SeloFonte, Icone, Letreiro],
  template: `
    <div class="pagina ponto">
      <div class="ponto__info">
        <a routerLink="/busca" [queryParams]="demo() ? { modo: 'demo' } : null" class="voltar">
          <pf-icone nome="seta-esquerda" /> Buscar outro ponto
        </a>
        <p class="sobretitulo">Ponto {{ dados()?.ponto?.codigo ?? codigo() }}</p>
        <h1 class="ponto__nome">{{ dados()?.ponto?.nome ?? 'Ponto ' + codigo() }}</h1>
        @if (dados(); as d) {
          @if (d.ponto.endereco) {
            <p class="ponto__endereco">{{ d.ponto.endereco }}</p>
          }
          <div class="ponto__origem">
            <pf-selo-fonte [fonte]="d.fonte" [forte]="true" />
            <span class="ajuda">{{ d.fonte === 'SIMULADO' ? 'horários simulados para demonstração' : 'horários previstos pela SPTrans' }}</span>
          </div>

          <div class="ponto__acoes">
            <button type="button" class="botao botao--primario botao--grande" (click)="ouvir()" [disabled]="!fala.suportaSintese">
              <pf-icone nome="volume" /> Ouvir previsões
            </button>
            @if (fala.falando()) {
              <button type="button" class="botao botao--contorno botao--grande" (click)="fala.parar()">
                <pf-icone nome="parar" /> Parar a voz
              </button>
            }
            <button
              type="button"
              class="botao botao--contorno botao--grande botao--favorito"
              [class.botao--favorito-ativo]="favorito()"
              [attr.aria-pressed]="favorito()"
              (click)="alternarFavorito()"
            >
              <pf-icone nome="estrela" /> {{ favorito() ? 'Ponto salvo' : 'Salvar ponto' }}
            </button>
          </div>
          @if (!fala.suportaSintese) {
            <p class="ajuda">Este navegador não tem voz sintetizada. A lista ao lado tem as mesmas informações.</p>
          }
          <label class="interruptor">
            <input type="checkbox" role="switch" [checked]="anunciar()" (change)="prefs.atualizar({ anunciarAuto: $any($event.target).checked })" />
            <span class="interruptor__trilho" aria-hidden="true"></span>
            <span>Falar sozinho quando o próximo ônibus mudar</span>
          </label>
          <p class="vo" role="status">{{ avisoFavorito() }}</p>
        }
      </div>

      <div class="ponto__painel">
        @if (erro(); as e) {
          @if (dados()) {
            <p class="aviso-linha" role="alert">
              <pf-icone nome="alerta" />
              <span>Não foi possível atualizar agora. Mostrando a previsão das {{ atualizadoEm() }}.</span>
              <button type="button" class="botao-texto" (click)="carregar()">Tentar de novo</button>
            </p>
          } @else {
            <pf-erro
              [titulo]="e.status === 503 ? 'A SPTrans não está respondendo' : e.status === 404 ? 'Ponto não encontrado' : 'Não foi possível abrir este ponto'"
              [mensagem]="e.status === 503 ? 'O serviço de previsões está fora do ar agora. Você pode ver uma demonstração com dados simulados.' : e.message"
              [tentarNovamente]="e.status !== 404"
              (repetir)="carregar()"
            >
              @if (e.status === 503 && !demo()) {
                <button type="button" class="botao botao--primario" (click)="verDemo()">Ver demonstração</button>
              }
            </pf-erro>
          }
        }

        @if (carregando() && !dados() && !erro()) {
          <section class="quadro" aria-label="Próximos ônibus">
            <pf-carregando texto="Buscando os próximos ônibus…" [linhas]="4" [escuro]="true" />
          </section>
        }

        @if (dados(); as d) {
          <section class="quadro" [class.quadro--simulado]="d.fonte === 'SIMULADO'" aria-labelledby="quadro-titulo">
            @if (d.fonte === 'SIMULADO') {
              <p class="quadro__fita">
                <span class="quadro__fita-marca">SIMULADO</span>
                <span>Horários de demonstração. Não são ônibus reais.</span>
              </p>
            }
            <div class="quadro__topo">
              <h2 id="quadro-titulo" class="quadro__titulo">Próximos ônibus</h2>
              <div class="quadro__relogio">
                <span class="quadro__hora">
                  <span class="vo">Atualizado às </span><span aria-hidden="true">Atualizado </span>{{ atualizadoEm() }}
                </span>
                <button type="button" class="quadro__atualizar" (click)="carregar(true, true)" [disabled]="carregando()">
                  <pf-icone nome="atualizar" [class.gira]="carregando()" />
                  <span>Atualizar</span>
                </button>
              </div>
            </div>
            <div class="quadro__ciclo" aria-hidden="true">
              @for (c of [ciclo()]; track c) {
                <span class="quadro__ciclo-barra"></span>
              }
            </div>

            <p class="vo" aria-live="polite">{{ anuncio() }}</p>

            @if (linhasDisponiveis().length > 1) {
              <div class="quadro__filtro">
                <label for="filtro-linha">Linha</label>
                <select id="filtro-linha" class="seletor" [value]="linhaFiltro()" (change)="filtrar($any($event.target).value)">
                  <option value="">Todas as linhas</option>
                  @for (linha of linhasDisponiveis(); track linha) { <option [value]="linha">{{ linha }}</option> }
                </select>
              </div>
            }

            @if (d.onibus.length === 0) {
              <p class="quadro__vazio">Nenhum ônibus previsto para este ponto agora. A lista atualiza sozinha enquanto esta aba estiver aberta.</p>
            } @else if (filtrados().length === 0) {
              <div class="quadro__sem-linha" role="status">
                <p>Nenhum ônibus da linha <strong>{{ linhaFiltro() }}</strong> está previsto nesta atualização.</p>
                <button type="button" class="botao-texto" (click)="filtrar('')">Mostrar todas as linhas</button>
              </div>
            } @else {
              <div class="quadro__colunas" aria-hidden="true">
                <span>Linha · destino</span><span>Previsto em</span>
              </div>
              <ol class="quadro__lista">
                @for (o of visiveis(); track chave(o); let primeiro = $first) {
                  <li class="partida" [class.partida--primeira]="primeiro" [class.partida--mudou]="mudados().has(chave(o))">
                    <span class="vo">{{ frase(o) }}</span>
                    <div class="partida__linha" aria-hidden="true">
                      <pf-letreiro [codigo]="o.letreiro" [grande]="primeiro" />
                      <span class="partida__destino">{{ o.destino }}</span>
                      @if (o.acessivel) {
                        <span class="partida__acessivel"><pf-icone nome="acessivel" />Acessível</span>
                      } @else {
                        <span class="partida__sem">Sem informação de acessibilidade</span>
                      }
                    </div>
                    <div class="partida__tempo" aria-hidden="true">
                      @if (o.minutos <= 0) {
                        <span class="partida__agora">agora</span>
                      } @else {
                        <span class="partida__valor"><span class="partida__num">{{ o.minutos }}</span><span class="partida__un">min</span></span>
                      }
                      <span class="partida__hora">previsão {{ o.previsto_em }}</span>
                    </div>
                  </li>
                }
              </ol>
              <div class="quadro__mais">
                <p role="status">{{ visiveis().length }} de {{ filtrados().length }} previsões{{ linhaFiltro() ? ' nesta linha' : '' }}</p>
                @if (filtrados().length > 6) {
                  <button type="button" class="botao botao--contorno" (click)="limite.set(visiveis().length < filtrados().length ? limite() + 6 : 6)">{{ visiveis().length < filtrados().length ? 'Ver mais previsões' : 'Mostrar menos' }}</button>
                }
              </div>
            }
            <p class="quadro__rodape">
              Previsões {{ d.fonte === 'SIMULADO' ? 'simuladas' : 'da SPTrans' }}: o ônibus pode adiantar, atrasar ou não passar. Atualiza enquanto a aba estiver ativa.
            </p>
          </section>
        }
      </div>
    </div>
  `,
})
export class PontoPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly documento = inject(DOCUMENT);
  protected readonly prefs = inject(PreferencesService);
  private readonly recentes = inject(RecentesService);
  private readonly favoritos = inject(FavoritosService);
  protected readonly fala = inject(SpeechService);

  /** Parâmetros da rota (component input binding). */
  readonly codigo = input.required<string>();
  readonly modo = input<string | undefined>();
  readonly linha = input<string | undefined>();

  protected readonly dados = signal<PrevisoesPonto | null>(null);
  protected readonly linhaFiltro = signal('');
  protected readonly limite = signal(6);
  protected readonly linhasDisponiveis = computed(() => [...new Set([
    ...(this.dados()?.onibus ?? []).map(o => o.letreiro),
    ...(this.linhaFiltro() ? [this.linhaFiltro()] : []),
  ])]);
  protected readonly filtrados = computed(() => (this.dados()?.onibus ?? []).filter(o => !this.linhaFiltro() || o.letreiro === this.linhaFiltro()));
  protected readonly visiveis = computed(() => this.filtrados().slice(0, this.limite()));

  protected filtrar(linha: string): void {
    this.linhaFiltro.set(linha);
    this.limite.set(6);
    const dados = this.dados();
    if (dados) {
      this.chaveUltimo = undefined;
      this.anuncio.set('');
      this.tratarMudanca(dados);
    }
  }
  protected readonly erro = signal<ErroApi | null>(null);
  protected readonly carregando = signal(false);
  protected readonly atualizadoEm = signal('');
  protected readonly anuncio = signal('');
  protected readonly anunciar = computed(() => this.prefs.prefs().anunciarAuto);
  protected readonly ciclo = signal(0);
  protected readonly mudados = signal<ReadonlySet<string>>(new Set());
  protected readonly avisoFavorito = signal('');
  protected readonly favorito = computed(() => {
    const d = this.dados();
    return !!d && this.favoritos.eFavorito(d.ponto.codigo, d.fonte === 'SIMULADO' ? 'demo' : 'auto');
  });

  private chaveUltimo: string | null | undefined = undefined;
  private minutosAnteriores = new Map<string, number>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private limparMudados: ReturnType<typeof setTimeout> | null = null;
  private pedido = 0;

  protected demo(): boolean {
    return this.modo() === 'demo';
  }

  constructor() {
    effect(() => {
      this.codigo();
      this.modo();
      const linha = this.linha() ?? '';
      untracked(() => {
        this.dados.set(null);
        this.filtrar(linha);
        this.erro.set(null);
        this.chaveUltimo = undefined;
        this.anuncio.set('');
        this.atualizadoEm.set('');
        this.minutosAnteriores.clear();
        void this.carregar();
        this.reiniciarTimer();
      });
    });
    // Em abas ocultas, não consulte a API a cada 30 segundos. Ao voltar,
    // atualize imediatamente para evitar que a pessoa veja horários antigos.
    const aoVoltar = () => {
      if (!this.documento.hidden) {
        this.reiniciarTimer();
        void this.carregar(true);
      }
    };
    this.documento.addEventListener('visibilitychange', aoVoltar);
    inject(DestroyRef).onDestroy(() => {
      this.documento.removeEventListener('visibilitychange', aoVoltar);
      this.pedido++;
      this.fala.parar();
      this.pararTimer();
      if (this.limparMudados) clearTimeout(this.limparMudados);
    });
  }

  protected chave = chaveOnibus;
  protected frase = fraseOnibus;

  private reiniciarTimer(): void {
    this.pararTimer();
    this.ciclo.update((c) => c + 1);
    this.timer = setInterval(() => {
      if (!this.documento.hidden) void this.carregar(true);
    }, INTERVALO_ATUALIZACAO_MS);
  }

  private pararTimer(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  async carregar(silencioso = false, manual = false): Promise<void> {
    const pedido = ++this.pedido;
    if (!silencioso || manual) this.carregando.set(true);
    if (manual) this.reiniciarTimer();
    const modo: Modo = this.demo() ? 'demo' : 'auto';
    try {
      const d = await firstValueFrom(this.api.previsoes(this.codigo(), modo));
      if (pedido !== this.pedido) return;
      this.marcarMudancas(d);
      this.dados.set(d);
      this.erro.set(null);
      this.atualizadoEm.set(horaCurta(new Date(d.consultado_em)));
      if (silencioso && !manual) this.ciclo.update((c) => c + 1);
      this.recentes.adicionar({ codigo: d.ponto.codigo, nome: d.ponto.nome, modo: d.fonte === 'SIMULADO' ? 'demo' : 'auto' });
      this.tratarMudanca(d);
    } catch (e) {
      if (pedido !== this.pedido) return;
      // Em atualização silenciosa, mantém a última lista e só avisa do erro.
      this.erro.set(e instanceof ErroApi ? e : new ErroApi(-1, 'Algo deu errado. Tente de novo.'));
    } finally {
      if (pedido === this.pedido) this.carregando.set(false);
    }
  }

  /** Destaca por um instante os horários que mudaram desde a última atualização. */
  private marcarMudancas(d: PrevisoesPonto): void {
    const mudou = new Set<string>();
    const novo = new Map<string, number>();
    for (const o of d.onibus) {
      const k = chaveOnibus(o);
      novo.set(k, o.minutos);
      const antes = this.minutosAnteriores.get(k);
      if (antes !== undefined && antes !== o.minutos) mudou.add(k);
    }
    this.minutosAnteriores = novo;
    this.mudados.set(mudou);
    if (this.limparMudados) clearTimeout(this.limparMudados);
    if (mudou.size) this.limparMudados = setTimeout(() => this.mudados.set(new Set()), 1600);
  }

  private tratarMudanca(d: PrevisoesPonto): void {
    const primeiro = this.filtrados()[0];
    const chave = primeiro ? `${primeiro.letreiro}|${primeiro.veiculo ?? ''}` : null;
    const mudou = this.chaveUltimo !== undefined && chave !== this.chaveUltimo;
    this.chaveUltimo = chave;
    if (!primeiro) {
      this.anuncio.set(this.semPrevisao());
      return;
    }
    const simulado = d.fonte === 'SIMULADO' ? 'Simulado. ' : '';
    const frase = `${simulado}Próximo ônibus: linha ${primeiro.letreiro}, ${primeiro.destino}, ${textoMinutos(primeiro.minutos)}.`;
    // A região viva só muda quando o primeiro ônibus muda (evita repetir a cada 30 s).
    if (mudou || !this.anuncio()) {
      this.anuncio.set(frase);
      if (mudou && this.anunciar()) this.fala.falar(this.textoFalado(d));
    }
  }

  protected ouvir(): void {
    const d = this.dados();
    if (d) this.fala.falar(this.textoFalado(d));
  }

  private semPrevisao(): string {
    return this.linhaFiltro() ? `Nenhum ônibus da linha ${this.linhaFiltro()} previsto neste ponto agora.` : 'Nenhum ônibus previsto para este ponto agora.';
  }

  private textoFalado(d: PrevisoesPonto): string {
    if (!this.linhaFiltro()) return d.frase_falada;
    const origem = d.fonte === 'SIMULADO' ? 'Demonstração com dados simulados. ' : 'Previsões da SPTrans. ';
    const lista = this.filtrados().slice(0, 3);
    return origem + (lista.length ? lista.map(fraseOnibus).join(' ') + ' Os horários podem mudar.' : this.semPrevisao());
  }

  protected alternarFavorito(): void {
    const d = this.dados();
    if (!d) return;
    const salvo = this.favoritos.alternar({ codigo: d.ponto.codigo, nome: d.ponto.nome, modo: d.fonte === 'SIMULADO' ? 'demo' : 'auto' });
    this.avisoFavorito.set(salvo ? 'Ponto salvo em Favoritos.' : 'Ponto removido de Favoritos.');
  }

  protected verDemo(): void {
    void this.router.navigate([], { queryParams: { modo: 'demo' }, queryParamsHandling: 'merge' });
  }
}
