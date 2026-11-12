import { Component, DestroyRef, effect, inject, input, signal, untracked } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { horaCurta, textoMinutos } from '../../core/format';
import { ErroApi, Modo, OnibusPrevisto, PrevisoesPonto } from '../../core/models';
import { PreferencesService } from '../../core/preferences.service';
import { RecentesService } from '../../core/recentes.service';
import { SpeechService } from '../../core/speech.service';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { MensagemErro } from '../../shared/mensagem-erro';
import { SeloFonte } from '../../shared/selo-fonte';
import { Selo } from '../../shared/selo';

export const INTERVALO_ATUALIZACAO_MS = 30_000;

@Component({
  selector: 'pf-ponto',
  imports: [RouterLink, Carregando, MensagemErro, SeloFonte, Selo, Icone],
  template: `
    <section class="cabecalho-pagina">
      <div class="miolo">
        <a routerLink="/" [queryParams]="demo() ? { modo: 'demo' } : null" class="voltar">
          <pf-icone nome="seta-esquerda" /> Buscar outro ponto
        </a>
        <p class="cabecalho-pagina__chapeu"><pf-icone nome="ponto" /> Ponto de ônibus</p>
        <h1>{{ dados()?.ponto?.nome ?? 'Ponto ' + codigo() }}</h1>
        @if (dados(); as d) {
          @if (d.ponto.endereco) {
            <p class="lead">{{ d.ponto.endereco }}</p>
          }
          <div class="faixa">
            <pf-selo-fonte [fonte]="d.fonte" />
            <span class="ajuda">Ponto {{ d.ponto.codigo }} · {{ d.fonte === 'SIMULADO' ? 'horários simulados' : 'horários previstos pela SPTrans' }}</span>
          </div>
        }
      </div>
    </section>

    <div class="miolo miolo--largo">
      @if (erro(); as e) {
        <pf-erro
          [titulo]="e.status === 503 ? 'A SPTrans não está respondendo' : 'Não foi possível ver este ponto'"
          [mensagem]="e.status === 503 ? 'O serviço de previsões está fora do ar agora. Você pode ver uma demonstração com dados simulados.' : e.message"
          [tentarNovamente]="e.status !== 404"
          (repetir)="carregar()"
        >
          @if (e.status === 503 && !demo()) {
            <button type="button" class="botao botao--primario" (click)="verDemo()">Ver demonstração</button>
          }
        </pf-erro>
      }

      @if (carregando() && !dados()) {
        <pf-carregando texto="Buscando os próximos ônibus…" />
      }

      @if (dados(); as d) {
        <div class="barra-acoes">
          <button type="button" class="botao botao--primario botao--grande" (click)="ouvir()" [disabled]="!fala.suportaSintese">
            <pf-icone nome="volume" /> Ouvir próximos ônibus
          </button>
          @if (fala.falando()) {
            <button type="button" class="botao botao--grande" (click)="fala.parar()">
              <pf-icone nome="parar" /> Parar a voz
            </button>
          }
          <label class="interruptor">
            <input type="checkbox" [checked]="anunciar()" (change)="alternarAnuncio($any($event.target).checked)" />
            <span class="interruptor__trilho" aria-hidden="true"></span>
            <span>Anunciar automaticamente quando o primeiro ônibus mudar</span>
          </label>
        </div>
        @if (!fala.suportaSintese) {
          <p class="ajuda">Seu navegador não tem voz. Você pode ler a lista abaixo.</p>
        }

        <section class="painel" [class.painel--demo]="d.fonte === 'SIMULADO'" aria-label="Painel de próximos ônibus">
          @if (d.fonte === 'SIMULADO') {
            <p class="painel__demo">
              <pf-icone nome="frasco" />
              <span><strong>Demonstração.</strong> Estes horários são simulados e não são ônibus de verdade.</span>
            </p>
          }
          <div class="painel__topo">
            <p class="painel__titulo">Próximos ônibus <span>previsão</span></p>
            <p class="painel__hora">
              <pf-icone nome="relogio" /> Atualizado às {{ atualizadoEm() }}
            </p>
          </div>
          <p class="painel__atualiza">Atualiza sozinho a cada 30 segundos.</p>
          <p class="visualmente-oculto" aria-live="polite" role="status">{{ anuncio() }}</p>

          @if (d.onibus.length === 0) {
            <p class="painel__vazio">Nenhum ônibus previsto para este ponto agora.</p>
          } @else {
            <ul class="painel__lista" aria-label="Próximos ônibus previstos">
              @for (o of d.onibus; track o.letreiro + (o.veiculo ?? '') + o.previsto_em) {
                <li class="onibus" [class.onibus--agora]="o.minutos <= 0">
                  <p class="onibus__linha"><span class="visualmente-oculto">Linha </span><span class="placa">{{ o.letreiro }}</span></p>
                  <div class="onibus__info">
                    <p class="onibus__destino">{{ o.destino }}</p>
                    @if (o.acessivel) {
                      <pf-selo tom="info" icone="acessivel">Acessível para cadeira de rodas</pf-selo>
                    } @else {
                      <span class="onibus__sem"><pf-icone nome="vazio" /> Sem informação de acessibilidade</span>
                    }
                  </div>
                  <p class="onibus__tempo">
                    @if (o.minutos <= 0) {
                      <span class="tempo__agora">Previsto agora</span>
                    } @else {
                      <span class="visualmente-oculto">{{ tempo(o) }}</span>
                      <span class="tempo__qual" aria-hidden="true">previsto em</span>
                      <span class="tempo__valor" aria-hidden="true"><span class="tempo__num">{{ o.minutos }}</span> <span class="tempo__un">min</span></span>
                    }
                    <span class="onibus__hora">previsão às {{ o.previsto_em }}</span>
                  </p>
                </li>
              }
            </ul>
          }
        </section>
      }
    </div>
  `,
})
export class PontoPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly prefs = inject(PreferencesService);
  private readonly recentes = inject(RecentesService);
  protected readonly fala = inject(SpeechService);

  /** Parâmetros da rota (component input binding). */
  readonly codigo = input.required<string>();
  readonly modo = input<string | undefined>();

  protected readonly dados = signal<PrevisoesPonto | null>(null);
  protected readonly erro = signal<ErroApi | null>(null);
  protected readonly carregando = signal(false);
  protected readonly atualizadoEm = signal('');
  protected readonly anuncio = signal('');
  protected readonly anunciar = signal(this.prefs.prefs().anunciarAuto);

  private chaveUltimo: string | null | undefined = undefined;
  private timer: ReturnType<typeof setInterval> | null = null;

  protected demo(): boolean {
    return this.modo() === 'demo';
  }

  constructor() {
    effect(() => {
      this.codigo();
      this.modo();
      untracked(() => {
        this.dados.set(null);
        this.erro.set(null);
        this.chaveUltimo = undefined;
        void this.carregar();
        this.reiniciarTimer();
      });
    });
    inject(DestroyRef).onDestroy(() => this.pararTimer());
  }

  protected tempo(o: OnibusPrevisto): string {
    return textoMinutos(o.minutos);
  }

  private reiniciarTimer(): void {
    this.pararTimer();
    this.timer = setInterval(() => void this.carregar(true), INTERVALO_ATUALIZACAO_MS);
  }

  private pararTimer(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  async carregar(silencioso = false): Promise<void> {
    if (!silencioso) this.carregando.set(true);
    const modo: Modo = this.demo() ? 'demo' : 'auto';
    try {
      const d = await firstValueFrom(this.api.previsoes(this.codigo(), modo));
      this.dados.set(d);
      this.erro.set(null);
      this.atualizadoEm.set(horaCurta(new Date()));
      this.recentes.adicionar({ codigo: d.ponto.codigo, nome: d.ponto.nome });
      this.tratarMudanca(d);
    } catch (e) {
      // Em atualização silenciosa, mantém a última lista e só avisa do erro.
      this.erro.set(e instanceof ErroApi ? e : new ErroApi(-1, 'Algo deu errado. Tente de novo.'));
    } finally {
      this.carregando.set(false);
    }
  }

  private tratarMudanca(d: PrevisoesPonto): void {
    const primeiro = d.onibus[0];
    const chave = primeiro ? `${primeiro.letreiro}|${primeiro.veiculo ?? ''}` : null;
    const mudou = this.chaveUltimo !== undefined && chave !== this.chaveUltimo;
    this.chaveUltimo = chave;
    if (this.chaveUltimo === undefined || !primeiro) return;
    const frase = `Próximo ônibus: linha ${primeiro.letreiro}, ${primeiro.destino}, ${
      textoMinutos(primeiro.minutos)
    }.`;
    // Texto da região viva só muda quando o primeiro ônibus muda (evita repetir a cada 30 s).
    if (mudou || !this.anuncio()) {
      this.anuncio.set(frase);
      if (mudou && this.anunciar()) this.fala.falar(d.frase_falada);
    }
  }

  protected ouvir(): void {
    const d = this.dados();
    if (d) this.fala.falar(d.frase_falada);
  }

  protected alternarAnuncio(ligado: boolean): void {
    this.anunciar.set(ligado);
  }

  protected verDemo(): void {
    void this.router.navigate([], { queryParams: { modo: 'demo' }, queryParamsHandling: 'merge' });
  }
}
