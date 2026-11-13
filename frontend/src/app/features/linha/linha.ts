import { Component, DestroyRef, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, Itinerario, SentidoLinha } from '../../core/models';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { Letreiro } from '../../shared/letreiro';
import { MensagemErro } from '../../shared/mensagem-erro';

/** Paradas de uma linha, em ordem, com escolha do sentido (cadastro oficial da SPTrans). */
@Component({
  selector: 'pf-linha',
  imports: [RouterLink, Carregando, MensagemErro, Icone, Letreiro],
  template: `
    <div class="pagina linha">
      <header class="cabecalho">
        <a routerLink="/busca" [queryParams]="{ tipo: 'linhas' }" class="voltar"><pf-icone nome="chevron" /> Buscar outra linha</a>
        <h1 class="linha__titulo"><pf-letreiro [codigo]="letreiro()" /> <span>Paradas da linha</span></h1>
        @if (atual(); as s) {
          <p class="cabecalho__apoio">{{ s.nome_linha }}</p>
        }
      </header>

      <p class="vo" role="status">{{ anuncio() }}</p>

      @if (carregando()) {
        <pf-carregando texto="Carregando as paradas…" [linhas]="4" />
      } @else if (erro(); as e) {
        <pf-erro [titulo]="e.status === 404 ? 'Linha não encontrada' : 'Não foi possível carregar a linha'" [mensagem]="e.message" (repetir)="carregar()" />
      } @else if (dados(); as d) {
        @if (d.sentidos.length === 0) {
          <div class="vazio"><p class="vazio__titulo">Sem paradas para mostrar.</p><p>{{ d.aviso }}</p></div>
        } @else {
          @if (d.sentidos.length > 1) {
            <fieldset class="segmentos linha__sentidos">
              <legend>Para onde você vai?</legend>
              @for (s of d.sentidos; track s.sentido) {
                <label class="segmento">
                  <input type="radio" name="sentido" [value]="s.sentido" [checked]="s.sentido === sentidoAtual()" (change)="escolher(s.sentido)" />
                  <span><span class="vo">Sentido </span>{{ s.destino }}</span>
                </label>
              }
            </fieldset>
          }
          @if (atual(); as s) {
            <h2 class="linha__subtitulo">Sentido {{ s.destino }} · {{ s.paradas.length }} paradas</h2>
            <p class="ajuda">Escolha o ponto onde você vai embarcar para ver as previsões. Fonte: cadastro oficial da SPTrans.</p>
            <ol class="paradas linha__paradas">
              @for (p of s.paradas; track $index) {
                <li class="parada">
                  <a class="parada__link" [routerLink]="['/ponto', p.codigo]" [queryParams]="{ linha: letreiro() }">
                    <span class="parada__marca" aria-hidden="true"></span>
                    <span class="parada__texto">
                      <span class="parada__nome">{{ p.nome }}</span>
                      <span class="parada__meta">@if (p.endereco) { {{ p.endereco }} · } Ponto {{ p.codigo }}</span>
                    </span>
                    <pf-icone class="parada__seta" nome="chevron" />
                  </a>
                </li>
              }
            </ol>
          }
        }
      }
    </div>
  `,
})
export class LinhaPage {
  private readonly api = inject(ApiService);
  readonly letreiro = input.required<string>();
  /** ?sentido=1|2 (vindo da busca de linhas). */
  readonly sentido = input<string | undefined>();

  protected readonly carregando = signal(true);
  protected readonly erro = signal<ErroApi | null>(null);
  protected readonly dados = signal<Itinerario | null>(null);
  protected readonly sentidoAtual = signal(1);
  protected readonly anuncio = signal('');
  protected readonly atual = computed<SentidoLinha | null>(() => {
    const d = this.dados();
    if (!d || d.sentidos.length === 0) return null;
    return d.sentidos.find((s) => s.sentido === this.sentidoAtual()) ?? d.sentidos[0];
  });
  private pedido = 0;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.pedido++);
    effect(() => {
      this.letreiro();
      untracked(() => void this.carregar());
    });
  }

  protected escolher(sentido: number): void {
    this.sentidoAtual.set(sentido);
    const s = this.atual();
    if (s) this.anuncio.set(`Sentido ${s.destino}: ${s.paradas.length} paradas.`);
  }

  async carregar(): Promise<void> {
    const pedido = ++this.pedido;
    this.carregando.set(true);
    this.erro.set(null);
    try {
      const d = await firstValueFrom(this.api.itinerario(this.letreiro()));
      if (pedido !== this.pedido) return;
      this.dados.set(d);
      const pedidoSentido = Number(this.sentido());
      this.sentidoAtual.set(d.sentidos.some((s) => s.sentido === pedidoSentido) ? pedidoSentido : (d.sentidos[0]?.sentido ?? 1));
      const s = this.atual();
      this.anuncio.set(s ? `Linha ${d.letreiro}, sentido ${s.destino}: ${s.paradas.length} paradas.` : (d.aviso ?? ''));
    } catch (e) {
      if (pedido !== this.pedido) return;
      this.erro.set(e instanceof ErroApi ? e : new ErroApi(-1, 'Algo deu errado. Tente de novo.'));
    } finally {
      if (pedido === this.pedido) this.carregando.set(false);
    }
  }
}
