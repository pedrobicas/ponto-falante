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
import { MensagemErro } from '../../shared/mensagem-erro';
import { SeloFonte } from '../../shared/selo-fonte';
import { Selo } from '../../shared/selo';

export const INTERVALO_ATUALIZACAO_MS = 30_000;

@Component({
  selector: 'pf-ponto',
  imports: [RouterLink, Carregando, MensagemErro, SeloFonte, Selo],
  template: `
    <p><a routerLink="/" [queryParams]="demo() ? { modo: 'demo' } : null" class="voltar">← Buscar outro ponto</a></p>
    <h1>{{ dados()?.ponto?.nome ?? 'Ponto ' + codigo() }}</h1>
    @if (dados(); as d) {
      @if (d.ponto.endereco) {
        <p class="lead">{{ d.ponto.endereco }}</p>
      }
      <p class="faixa">
        <pf-selo-fonte [fonte]="d.fonte" />
        <span class="ajuda">Ponto {{ d.ponto.codigo }} · horários previstos pela SPTrans</span>
      </p>
    }

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
      <div class="acoes acoes--topo">
        <button type="button" class="botao botao--primario" (click)="ouvir()" [disabled]="!fala.suportaSintese">
          <span aria-hidden="true">🔊</span> Ouvir próximos ônibus
        </button>
        @if (fala.falando()) {
          <button type="button" class="botao" (click)="fala.parar()">Parar a voz</button>
        }
        <label class="opcao">
          <input type="checkbox" [checked]="anunciar()" (change)="alternarAnuncio($any($event.target).checked)" />
          <span>Anunciar automaticamente quando o primeiro ônibus mudar</span>
        </label>
      </div>
      @if (!fala.suportaSintese) {
        <p class="ajuda">Seu navegador não tem voz. Você pode ler a lista abaixo.</p>
      }

      <p class="atualizado">
        <span aria-hidden="true">🕒</span> Atualizado às {{ atualizadoEm() }}
        <span class="ajuda">· atualiza sozinho a cada 30 segundos</span>
      </p>
      <p class="visualmente-oculto" aria-live="polite" role="status">{{ anuncio() }}</p>

      @if (d.onibus.length === 0) {
        <p class="vazio">Nenhum ônibus previsto para este ponto agora.</p>
      } @else {
        <ul class="lista-cartoes" aria-label="Próximos ônibus previstos">
          @for (o of d.onibus; track o.letreiro + (o.veiculo ?? '') + o.previsto_em) {
            <li class="onibus" [class.onibus--chegando]="o.minutos <= 0">
              <p class="onibus__linha"><span class="visualmente-oculto">Linha </span>{{ o.letreiro }}</p>
              <div class="onibus__info">
                <p class="onibus__destino">{{ o.destino }}</p>
                <p class="onibus__tempo">
                  @if (o.minutos <= 0) {
                    <span aria-hidden="true">➜</span> Chegando
                  } @else {
                    {{ tempo(o) }}
                  }
                  <span class="onibus__hora">(previsão às {{ o.previsto_em }})</span>
                </p>
                @if (o.acessivel) {
                  <pf-selo tom="info" icone="♿">Acessível para cadeira de rodas</pf-selo>
                } @else {
                  <pf-selo tom="neutro" icone="○">Sem informação de acessibilidade</pf-selo>
                }
              </div>
            </li>
          }
        </ul>
      }
    }
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
      primeiro.minutos <= 0 ? 'chegando' : textoMinutos(primeiro.minutos)
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
