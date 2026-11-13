import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { formatarData, formatarDataHora } from '../../core/format';
import { Boletim, BoletimResumo, ErroApi, LinhaBoletim, StatusLinha } from '../../core/models';
import { SpeechService } from '../../core/speech.service';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { Letreiro } from '../../shared/letreiro';
import { MensagemErro } from '../../shared/mensagem-erro';
import { Origem, TipoOrigem } from '../../shared/origem';
import { StatusLinhaPill } from '../../shared/status-linha';

const ORDEM: Record<StatusLinha, number> = { CRITICA: 0, ATENCAO: 1, SEM_DADOS: 2, OK: 3 };

/** A fonte SPTrans comprova a consulta, nunca uma passagem ou atraso observado. */
export function naturezaDaLinha(l: LinhaBoletim, boletimSimulado: boolean): TipoOrigem {
  if (l.status === 'SEM_DADOS' || l.classificacao === 'INDISPONIVEL') return 'indisponivel';
  const fontes = (l.fontes ?? []).map((f) => f.toLowerCase());
  if (l.classificacao === 'SIMULADO' || fontes.includes('simulador') || fontes.includes('simulado')) return 'simulado';
  if (l.classificacao === 'ESTIMADO') return 'estimado';
  if (boletimSimulado) return 'simulado';
  if (fontes.includes('olhovivo') || fontes.includes('olho_vivo')) return 'estimado';
  return 'indisponivel';
}

function numero(v: number | null | undefined, casas = 1): string {
  return v == null ? '—' : v.toLocaleString('pt-BR', { maximumFractionDigits: casas });
}

@Component({
  selector: 'pf-boletim',
  imports: [Carregando, MensagemErro, Origem, StatusLinhaPill, Icone, Letreiro],
  template: `
    <div class="pagina boletim">
      <header class="cabecalho">
        <p class="sobretitulo">Boletim diário</p>
        <h1>O dia nas linhas</h1>
        <p class="cabecalho__apoio">Veja as esperas previstas nas linhas acompanhadas.</p>
      </header>

      @if (carregando()) {
        <pf-carregando texto="Carregando o boletim…" [linhas]="4" />
      } @else if (naoHa()) {
        <div class="vazio vazio--amplo" role="status">
          @if (dataSelecionada(); as selecionada) {
            <p class="vazio__titulo">Boletim de {{ data(selecionada) }} não encontrado</p>
            <p>Esta edição não está disponível. Você pode consultar o boletim mais recente.</p>
            <button type="button" class="botao botao--contorno" (click)="carregar()">Ver boletim mais recente</button>
          } @else {
            <p class="vazio__titulo">Nenhum boletim publicado ainda</p>
            <p>O robô publica um boletim por dia. Quando o primeiro chegar, ele aparece aqui com a data de referência e a fonte dos dados.</p>
          }
        </div>
      } @else if (erro(); as e) {
        <pf-erro titulo="Não foi possível abrir o boletim" [mensagem]="e" (repetir)="repetir()" />
      } @else if (boletim(); as b) {
        <section class="ficha" aria-labelledby="ficha-titulo">
          <h2 id="ficha-titulo" class="ficha__titulo">
            Boletim de {{ data(b.data_referencia) }}
            @if (b.dados_simulados) {
              <pf-origem tipo="simulado" [forte]="true" />
            }
            @if (estimado()) {
              <pf-origem tipo="estimado" [forte]="true" />
            }
          </h2>
          <dl class="ficha__dados">
            <div><dt>Período observado</dt><dd>{{ periodoTexto() }}</dd></div>
            <div><dt>Última atualização</dt><dd>{{ dataHora(b.ultima_atualizacao || b.recebido_em || b.gerado_em) }}</dd></div>
            <div><dt>Fonte dos dados</dt><dd>{{ fonteTexto() }}</dd></div>
            <div>
              <dt>Situação</dt>
              <dd>
                @if (b.desatualizado) {
                  <span class="marca-texto marca-texto--aviso"><pf-icone nome="alerta" /> Desatualizado</span>
                } @else {
                  <span class="marca-texto"><pf-icone nome="certo-circulo" /> Em dia</span>
                }
              </dd>
            </div>
          </dl>

          @if (b.desatualizado) {
            <div class="aviso aviso--calmo" role="note">
              <pf-icone class="aviso__icone" nome="alerta" />
              <div class="aviso__corpo">
                <p class="aviso__titulo">Este boletim está desatualizado</p>
                <p>{{ b.motivo_desatualizado || 'Os dados mais recentes ainda não chegaram.' }} Use as informações com cuidado.</p>
              </div>
            </div>
          }
          @for (aviso of b.avisos ?? []; track aviso) {
            <p class="nota"><pf-icone nome="info" /> {{ aviso }}</p>
          }
        </section>

        <section class="placar" aria-labelledby="placar-titulo">
          <h2 id="placar-titulo">Resumo de {{ linhas().length }} {{ linhas().length === 1 ? 'linha' : 'linhas' }}</h2>
          @if (linhas().length) {
            <div class="placar__barra" aria-hidden="true">
              @for (s of segmentos(); track s.chave) {
                @if (s.n) {
                  <span class="placar__seg placar__seg--{{ s.chave }}" [style.flex-grow]="s.n"></span>
                }
              }
            </div>
          }
          <ul class="placar__lista">
            @for (s of segmentos(); track s.chave) {
              <li class="placar__item placar__item--{{ s.chave }}">
                <span class="placar__num">{{ s.n }}</span>
                <span class="placar__txt">{{ s.texto }}</span>
              </li>
            }
          </ul>
          <div class="placar__voz">
            @if (fala.falando()) {
              <button type="button" class="botao botao--contorno" (click)="fala.parar()"><pf-icone nome="parar" /> Parar a voz</button>
            } @else {
              <button type="button" class="botao botao--primario" (click)="ouvirResumo()" [disabled]="!fala.suportaSintese">
                <pf-icone nome="volume" /> Ouvir resumo
              </button>
            }
          </div>
          <p class="placar__resumo">{{ b.resumo_falado }}</p>
        </section>

        <section aria-labelledby="linhas-titulo">
          <h2 id="linhas-titulo">Linhas</h2>
          <ul class="tabela-linhas">
            @for (l of linhas(); track l.linha) {
              <li class="registro registro--{{ l.status.toLowerCase() }}">
                <div class="registro__id">
                  <pf-letreiro [codigo]="l.linha" />
                  <pf-status-linha [status]="l.status" [rotulo]="rotulo(l)" />
                </div>
                <dl class="registro__dados">
                  @if (natureza(l) === 'estimado') {
                    <div><dt>Espera típica <span class="registro__est">estimada</span></dt><dd>{{ min(l.espera_tipica_min) }}</dd></div>
                    <div><dt>Maior espera prevista</dt><dd>{{ min(l.maior_espera_prevista_min) }}</dd></div>
                    <div><dt>Consultas</dt><dd>{{ l.amostras ?? '—' }}</dd></div>
                  } @else {
                    <div><dt>Atraso médio <span class="registro__est">{{ natureza(l) === 'simulado' ? 'simulado' : 'não verificado' }}</span></dt><dd>{{ min(l.atraso_medio_min) }}</dd></div>
                    <div><dt>Maior intervalo</dt><dd>{{ min(l.intervalo_max_min) }}</dd></div>
                    <div><dt>Registros</dt><dd>{{ l.passagens ?? '—' }}</dd></div>
                  }
                  <div><dt>Acessíveis</dt><dd>{{ l.acessiveis_pct == null ? '—' : num(l.acessiveis_pct, 0) + '%' }}</dd></div>
                  <div><dt>Dados</dt><dd><pf-origem [tipo]="natureza(l)" [rotulo]="natureza(l) === 'real' ? 'Real' : ''" semDescricao /></dd></div>
                </dl>
                <p class="registro__frase">{{ l.frase }}</p>
              </li>
            }
          </ul>
        </section>
        <details class="metodologia"><summary>Como estes dados são calculados</summary>
        @if (estimado()) {
          <section class="coleta" aria-labelledby="coleta-titulo">
            <div class="coleta__explicacao">
              <p class="sobretitulo">Por trás dos números</p>
              <h2 id="coleta-titulo">Consulta real.<br />Espera estimada.</h2>
              <p>O robô consulta as previsões da SPTrans ao longo do dia. Esses horários permitem estimar a espera; não confirmam a chegada do ônibus nem medem atraso.</p>
            </div>
            @if (b.amostragem; as a) {
              <div class="coleta__amostra">
                <p class="coleta__numero">{{ a.consultas_validas ?? '—' }}<span>consultas válidas</span></p>
                <p class="coleta__cobertura">{{ a.cobertura_pct == null ? 'Cobertura não informada' : num(a.cobertura_pct) + '% das janelas de coleta previstas' }}</p>
                @if (a.cobertura_pct != null) {
                  <div class="coleta__trilho" aria-hidden="true"><span [style.width.%]="cobertura(a.cobertura_pct)"></span></div>
                }
                <p class="ajuda">Cobertura da coleta, não da cidade. Consultas repetidas não preenchem horários ou pontos sem observação.</p>
              </div>
            }
          </section>
        }

        <section class="legenda" aria-labelledby="legenda-titulo">
          <h2 id="legenda-titulo" class="legenda__titulo">Como ler os dados</h2>
          <dl class="legenda__lista">
            <div><dt><pf-origem tipo="estimado" semDescricao /></dt><dd>Espera calculada a partir de previsões da SPTrans. Não comprova chegada nem atraso.</dd></div>
            <div><dt><pf-origem tipo="simulado" semDescricao /></dt><dd>Dados de demonstração. Não descrevem ônibus reais.</dd></div>
            <div><dt><pf-origem tipo="indisponivel" semDescricao /></dt><dd>Informações insuficientes ou origem não identificada.</dd></div>
          </dl>
        </section>

        </details>
      }

      <details class="anteriores"><summary>Boletins anteriores</summary>
        @if (carregandoAnteriores()) {
          <pf-carregando texto="Carregando boletins anteriores…" [linhas]="0" />
        } @else if (erroAnteriores()) {
          <pf-erro titulo="Não foi possível consultar o histórico" [mensagem]="erroAnteriores()!" (repetir)="carregarAnteriores()" />
        } @else if (anteriores().length === 0) {
          <p class="texto-suave">Nenhum boletim anterior para mostrar.</p>
        } @else {
          <ul class="anteriores__lista">
            @for (r of anteriores(); track r.data_referencia) {
              <li class="anterior" [class.anterior--atual]="boletim()?.data_referencia === r.data_referencia">
                <div class="anterior__texto">
                  <p class="anterior__data">{{ data(r.data_referencia) }}</p>
                  <p class="anterior__sub">
                    {{ r.criticas }} em situação crítica · {{ r.atencao }} em atenção
                    @if (r.desatualizado) { · desatualizado }
                  </p>
                </div>
                @if (r.dados_simulados) {
                  <pf-origem tipo="simulado" />
                }
                <button type="button" class="botao botao--contorno botao--pequeno" (click)="abrir(r.data_referencia)"
                        [attr.aria-current]="boletim()?.data_referencia === r.data_referencia ? 'true' : null">
                  Abrir<span class="vo"> boletim de {{ data(r.data_referencia) }}</span>
                </button>
              </li>
            }
          </ul>
        }
      </details>
    </div>
  `,
})
export class BoletimPage {
  private readonly api = inject(ApiService);
  protected readonly fala = inject(SpeechService);

  protected readonly boletim = signal<Boletim | null>(null);
  protected readonly anteriores = signal<BoletimResumo[]>([]);
  protected readonly carregando = signal(true);
  protected readonly naoHa = signal(false);
  protected readonly erro = signal<string | null>(null);
  protected readonly dataSelecionada = signal<string | null>(null);
  protected readonly carregandoAnteriores = signal(true);
  protected readonly erroAnteriores = signal<string | null>(null);
  private pedido = 0;
  private pedidoAnteriores = 0;
  protected readonly estimado = computed(() => this.boletim()?.natureza_dados === 'ESTIMADO' ||
    this.linhas().some(l => naturezaDaLinha(l, !!this.boletim()?.dados_simulados) === 'estimado'));
  protected readonly periodoTexto = computed(() => {
    const b = this.boletim();
    if (!b) return '';
    const p = b.periodo_referencia;
    return p?.inicio && p?.fim ? `${this.data(b.data_referencia)}, ${p.inicio}–${p.fim} (São Paulo)` : `${this.data(b.data_referencia)} · horários não informados`;
  });

  protected readonly linhas = computed<LinhaBoletim[]>(() =>
    [...(this.boletim()?.linhas ?? [])].sort((a, b) => ORDEM[a.status] - ORDEM[b.status]),
  );

  protected readonly segmentos = computed(() => {
    const l = this.boletim()?.linhas ?? [];
    const n = (s: StatusLinha) => l.filter((x) => x.status === s).length;
    const comDados = l.filter(x => x.status !== 'SEM_DADOS');
    const somenteSimulado = comDados.length > 0 && comDados.every(x => this.natureza(x) === 'simulado');
    const somenteEstimado = comDados.length > 0 && comDados.every(x => this.natureza(x) === 'estimado');
    return [
      { chave: 'critica', n: n('CRITICA'), texto: somenteSimulado ? 'com atraso forte' : somenteEstimado ? 'com espera longa' : 'em situação crítica' },
      { chave: 'atencao', n: n('ATENCAO'), texto: 'em atenção' },
      { chave: 'ok', n: n('OK'), texto: somenteSimulado ? 'normais' : 'na faixa esperada' },
      { chave: 'sem_dados', n: n('SEM_DADOS'), texto: 'sem dados' },
    ];
  });

  protected readonly fonteTexto = computed(() => {
    const b = this.boletim();
    if (!b) return '';
    const f = b.fonte_dados ?? {};
    const real = f['olhovivo'] ?? 0;
    const sim = f['simulador'] ?? 0;
    const partes: string[] = [];
    if (real) partes.push(`SPTrans Olho Vivo (${real} consultas)`);
    if (sim) partes.push(`simulador de demonstração (${sim} registros)`);
    if (partes.length) return partes.join(' e ');
    return b.dados_simulados ? 'Simulador de demonstração' : 'Fonte não informada';
  });

  protected data = formatarData;
  protected dataHora = formatarDataHora;
  protected num = numero;

  constructor() {
    inject(DestroyRef).onDestroy(() => { this.pedido++; this.pedidoAnteriores++; this.fala.parar(); });
    void this.carregar();
    void this.carregarAnteriores();
  }

  protected min(v: number | null | undefined): string {
    return v == null ? '—' : `${numero(v)} min`;
  }

  protected natureza(l: LinhaBoletim): TipoOrigem {
    return naturezaDaLinha(l, !!this.boletim()?.dados_simulados);
  }

  protected cobertura(valor: number): number { return Math.min(100, Math.max(0, valor)); }

  protected rotulo(l: LinhaBoletim): string {
    if (this.natureza(l) !== 'estimado') return l.rotulo ?? '';
    return ({ CRITICA: 'Espera longa', ATENCAO: 'Espera em atenção', OK: 'Espera na faixa esperada', SEM_DADOS: 'Sem dados' })[l.status];
  }

  async carregar(): Promise<void> {
    this.dataSelecionada.set(null);
    this.carregando.set(true);
    this.erro.set(null);
    this.naoHa.set(false);
    await this.buscar(() => this.api.boletim());
  }

  protected async abrir(data: string): Promise<void> {
    this.dataSelecionada.set(data);
    this.carregando.set(true);
    await this.buscar(() => this.api.boletimDaData(data));
  }

  protected repetir(): Promise<void> {
    const data = this.dataSelecionada();
    return data ? this.abrir(data) : this.carregar();
  }

  protected async carregarAnteriores(): Promise<void> {
    const pedido = ++this.pedidoAnteriores;
    this.carregandoAnteriores.set(true);
    this.erroAnteriores.set(null);
    try {
      const anteriores = await firstValueFrom(this.api.boletins());
      if (pedido === this.pedidoAnteriores) this.anteriores.set(anteriores);
    } catch (e) {
      if (pedido === this.pedidoAnteriores) {
        this.erroAnteriores.set(e instanceof ErroApi ? e.message : 'Tente novamente em instantes.');
      }
    } finally {
      if (pedido === this.pedidoAnteriores) this.carregandoAnteriores.set(false);
    }
  }

  private async buscar(fonte: () => ReturnType<ApiService['boletim']>): Promise<void> {
    const pedido = ++this.pedido;
    this.fala.parar();
    this.erro.set(null);
    this.naoHa.set(false);
    try {
      const boletim = await firstValueFrom(fonte());
      if (pedido !== this.pedido) return;
      this.boletim.set(boletim);
      this.erro.set(null);
      this.naoHa.set(false);
    } catch (e) {
      if (pedido !== this.pedido) return;
      this.boletim.set(null);
      if (e instanceof ErroApi && e.status === 404) this.naoHa.set(true);
      else this.erro.set(e instanceof ErroApi ? e.message : 'Algo deu errado. Tente de novo.');
    } finally {
      if (pedido === this.pedido) this.carregando.set(false);
    }
  }

  protected ouvirResumo(): void {
    const b = this.boletim();
    if (b) this.fala.falar((b.dados_simulados ? 'Atenção: dados simulados. ' : '') + b.resumo_falado);
  }
}
