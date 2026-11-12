import { Component, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { formatarData, formatarDataHora } from '../../core/format';
import { Boletim, BoletimResumo, ErroApi, LinhaBoletim, StatusLinha } from '../../core/models';
import { SpeechService } from '../../core/speech.service';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { MensagemErro } from '../../shared/mensagem-erro';
import { Selo } from '../../shared/selo';
import { StatusLinhaPill } from '../../shared/status-linha';

const ORDEM: Record<StatusLinha, number> = { CRITICA: 0, ATENCAO: 1, SEM_DADOS: 2, OK: 3 };

@Component({
  selector: 'pf-boletim',
  imports: [Carregando, MensagemErro, Selo, StatusLinhaPill, Icone],
  template: `
    <section class="cabecalho-pagina">
      <div class="miolo">
        <p class="cabecalho-pagina__chapeu"><pf-icone nome="boletim" /> Resumo diário</p>
        <h1>Boletim de atrasos</h1>
        <p class="lead">Resumo diário feito por um robô automático: quais linhas estão atrasadas.</p>
      </div>
    </section>

    <div class="miolo">
      @if (carregando()) {
        <pf-carregando texto="Carregando o boletim…" />
      } @else if (naoHa()) {
        <p class="vazio" role="status">Nenhum boletim publicado ainda.</p>
      } @else if (erro(); as e) {
        <pf-erro titulo="Não foi possível abrir o boletim" [mensagem]="e" (repetir)="carregar()" />
      } @else if (boletim(); as b) {
        <section class="cartao boletim-resumo" aria-labelledby="resumo-titulo">
          <h2 id="resumo-titulo">Boletim de {{ data(b.data_referencia) }}</h2>
          <div class="faixa">
            @if (b.dados_simulados) {
              <pf-selo tom="aviso" icone="frasco">Dados simulados</pf-selo>
            }
            @if (b.desatualizado) {
              <pf-selo tom="aviso" icone="alerta">Desatualizado</pf-selo>
            }
            <span class="ajuda">Gerado em {{ dataHora(b.gerado_em) }}</span>
          </div>

          @if (b.desatualizado) {
            <div class="caixa caixa--aviso" role="note">
              <p class="caixa__titulo"><pf-icone nome="alerta" /> <span>Atenção: este boletim está desatualizado</span></p>
              <p>{{ b.motivo_desatualizado || 'Os dados de hoje ainda não chegaram.' }}</p>
              <p>Use as informações com cuidado.</p>
            </div>
          }
          @for (aviso of b.avisos ?? []; track aviso) {
            <p class="aviso-inline"><pf-icone nome="info" /> {{ aviso }}</p>
          }

          <ul class="totais" aria-label="Totais por situação">
            <li class="total total--critico">
              <pf-icone nome="erro-circulo" />
              <span class="total__num">{{ contagem().criticas }}</span>
              <span class="total__txt">com atraso forte</span>
            </li>
            <li class="total total--aviso">
              <pf-icone nome="alerta" />
              <span class="total__num">{{ contagem().atencao }}</span>
              <span class="total__txt">em atenção</span>
            </li>
            <li class="total total--ok">
              <pf-icone nome="certo-circulo" />
              <span class="total__num">{{ contagem().normais }}</span>
              <span class="total__txt">normais</span>
            </li>
          </ul>

          <div class="acoes">
            <button type="button" class="botao botao--primario" (click)="ouvirResumo()" [disabled]="!fala.suportaSintese">
              <pf-icone nome="volume" /> Ouvir resumo
            </button>
            @if (fala.falando()) {
              <button type="button" class="botao" (click)="fala.parar()"><pf-icone nome="parar" /> Parar a voz</button>
            }
          </div>
          <p class="resumo-texto">{{ b.resumo_falado }}</p>
        </section>

        <section aria-labelledby="linhas-titulo">
          <h2 id="linhas-titulo">Linhas ({{ linhas().length }})</h2>
          <ul class="lista-linhas">
            @for (l of linhas(); track l.linha) {
              <li class="linha-boletim linha-boletim--{{ l.status.toLowerCase() }}">
                <div class="linha-boletim__topo">
                  <p class="linha-boletim__numero"><span class="visualmente-oculto">Linha </span><span class="placa">{{ l.linha }}</span></p>
                  <pf-status-linha [status]="l.status" />
                </div>
                <p class="linha-boletim__frase">{{ l.frase }}</p>
              </li>
            }
          </ul>
        </section>
      }

      <section aria-labelledby="anteriores-titulo">
        <h2 id="anteriores-titulo">Boletins anteriores</h2>
        @if (anteriores().length === 0) {
          <p class="vazio">Nenhum boletim anterior para mostrar.</p>
        } @else {
          <ul class="lista-cartoes">
            @for (r of anteriores(); track r.data_referencia) {
              <li class="cartao cartao--linha">
                <div>
                  <p class="cartao__titulo">{{ data(r.data_referencia) }}</p>
                  <p class="cartao__sub">
                    {{ r.criticas }} {{ r.criticas === 1 ? 'linha com atraso forte' : 'linhas com atraso forte' }} ·
                    {{ r.atencao }} em atenção
                    @if (r.desatualizado) { · desatualizado }
                    @if (r.dados_simulados) { · dados simulados }
                  </p>
                </div>
                <button type="button" class="botao" (click)="abrir(r.data_referencia)">
                  Ver boletim de {{ data(r.data_referencia) }}
                </button>
              </li>
            }
          </ul>
        }
      </section>
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

  protected readonly linhas = computed<LinhaBoletim[]>(() =>
    [...(this.boletim()?.linhas ?? [])].sort((a, b) => ORDEM[a.status] - ORDEM[b.status]),
  );

  protected readonly contagem = computed(() => {
    const l = this.boletim()?.linhas ?? [];
    const n = (s: StatusLinha) => l.filter((x) => x.status === s).length;
    return { criticas: n('CRITICA'), atencao: n('ATENCAO'), normais: n('OK') };
  });

  protected data = formatarData;
  protected dataHora = formatarDataHora;

  constructor() {
    void this.carregar();
    firstValueFrom(this.api.boletins())
      .then((l) => this.anteriores.set(l))
      .catch(() => this.anteriores.set([]));
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    this.naoHa.set(false);
    await this.buscar(() => this.api.boletim());
  }

  protected async abrir(data: string): Promise<void> {
    this.carregando.set(true);
    await this.buscar(() => this.api.boletimDaData(data));
  }

  private async buscar(fonte: () => ReturnType<ApiService['boletim']>): Promise<void> {
    try {
      this.boletim.set(await firstValueFrom(fonte()));
      this.erro.set(null);
      this.naoHa.set(false);
    } catch (e) {
      this.boletim.set(null);
      if (e instanceof ErroApi && e.status === 404) this.naoHa.set(true);
      else this.erro.set(e instanceof ErroApi ? e.message : 'Algo deu errado. Tente de novo.');
    } finally {
      this.carregando.set(false);
    }
  }

  protected ouvirResumo(): void {
    const b = this.boletim();
    if (b) this.fala.falar(b.resumo_falado);
  }
}
