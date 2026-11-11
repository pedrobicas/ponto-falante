import { Component, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { formatarData, formatarDataHora } from '../../core/format';
import { Boletim, BoletimResumo, ErroApi, LinhaBoletim, StatusLinha } from '../../core/models';
import { SpeechService } from '../../core/speech.service';
import { Carregando } from '../../shared/carregando';
import { MensagemErro } from '../../shared/mensagem-erro';
import { Selo } from '../../shared/selo';
import { StatusLinhaPill } from '../../shared/status-linha';

const ORDEM: Record<StatusLinha, number> = { CRITICA: 0, ATENCAO: 1, SEM_DADOS: 2, OK: 3 };

@Component({
  selector: 'pf-boletim',
  imports: [Carregando, MensagemErro, Selo, StatusLinhaPill],
  template: `
    <h1>Boletim de atrasos</h1>
    <p class="lead">Resumo diário feito por um robô automático: quais linhas estão atrasadas.</p>

    @if (carregando()) {
      <pf-carregando texto="Carregando o boletim…" />
    } @else if (naoHa()) {
      <p class="vazio" role="status">Nenhum boletim publicado ainda.</p>
    } @else if (erro(); as e) {
      <pf-erro titulo="Não foi possível abrir o boletim" [mensagem]="e" (repetir)="carregar()" />
    } @else if (boletim(); as b) {
      <section class="cartao" aria-labelledby="resumo-titulo">
        <h2 id="resumo-titulo">Boletim de {{ data(b.data_referencia) }}</h2>
        <p class="faixa">
          @if (b.dados_simulados) {
            <pf-selo tom="aviso" icone="⚠">Dados simulados</pf-selo>
          }
          @if (b.desatualizado) {
            <pf-selo tom="aviso" icone="⚠">Desatualizado</pf-selo>
          }
        </p>
        <p class="ajuda">Gerado em {{ dataHora(b.gerado_em) }}</p>

        @if (b.desatualizado) {
          <div class="caixa caixa--aviso" role="note">
            <p class="caixa__titulo"><span aria-hidden="true">⚠</span> Atenção: este boletim está desatualizado</p>
            <p>{{ b.motivo_desatualizado || 'Os dados de hoje ainda não chegaram.' }}</p>
            <p>Use as informações com cuidado.</p>
          </div>
        }
        @for (aviso of b.avisos ?? []; track aviso) {
          <p class="aviso-inline"><span aria-hidden="true">ℹ</span> {{ aviso }}</p>
        }

        <div class="acoes">
          <button type="button" class="botao botao--primario" (click)="ouvirResumo()" [disabled]="!fala.suportaSintese">
            <span aria-hidden="true">🔊</span> Ouvir resumo
          </button>
          @if (fala.falando()) {
            <button type="button" class="botao" (click)="fala.parar()">Parar a voz</button>
          }
        </div>
        <p class="resumo-texto">{{ b.resumo_falado }}</p>
      </section>

      <section aria-labelledby="linhas-titulo">
        <h2 id="linhas-titulo">Linhas ({{ linhas().length }})</h2>
        <ul class="lista-cartoes">
          @for (l of linhas(); track l.linha) {
            <li class="cartao linha-boletim">
              <div class="linha-boletim__topo">
                <p class="linha-boletim__numero"><span class="visualmente-oculto">Linha </span>{{ l.linha }}</p>
                <pf-status-linha [status]="l.status" />
              </div>
              <p>{{ l.frase }}</p>
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
