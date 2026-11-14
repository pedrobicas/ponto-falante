import { Component, DestroyRef, ElementRef, computed, effect, inject, input, signal, untracked, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, Itinerario, SentidoLinha, Ponto, PrevisoesPonto } from '../../core/models';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { Letreiro } from '../../shared/letreiro';
import { MensagemErro } from '../../shared/mensagem-erro';

/** Paradas de uma linha, em ordem, com escolha do sentido (cadastro oficial da SPTrans). */
@Component({
  selector: 'pf-linha',
  imports: [RouterLink, FormsModule, Carregando, MensagemErro, Icone, Letreiro],
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
            <div class="linha__filtro">
              <label for="filtrar-parada">Encontre sua parada</label>
              <input id="filtrar-parada" type="search" class="campo" placeholder="Nome, rua ou código do ponto" [ngModel]="busca()" (ngModelChange)="filtrar($event)" />
              <p class="ajuda" role="status">{{ filtradas().length }} de {{ s.paradas.length }} paradas · na ordem do trajeto</p>
            </div>
            @if (selecionada(); as p) {
              <section #painel class="linha__selecionada" tabindex="-1" aria-label="Ponto selecionado" aria-live="polite">
                <div class="fala__cabeca"><h3>{{ p.nome }}</h3><button class="botao-texto" type="button" (click)="fecharPonto()">Fechar seleção</button></div>
                <p class="ajuda">Ponto {{ p.codigo }} · linha {{ letreiro() }} · sentido {{ s.destino }}</p>
                @if (carregandoPrevisao()) { <p role="status">Consultando previsões na SPTrans…</p> }
                @else if (erroPrevisao()) { <p role="alert">{{ erroPrevisao() }}</p> }
                @else if (previsao(); as pr) {
                  <p class="ajuda">{{ pr.fonte === 'SIMULADO' ? 'Dados simulados' : 'SPTrans · previsão, não é chegada confirmada' }} · referência {{ pr.horario_referencia }}</p>
                  @for (o of onibus(); track $index) { <p class="linha__previsao">Previsto em <strong>{{ o.minutos }} min</strong> @if (o.acessivel) { · acessível }</p> }
                  @empty { <p>Sem previsão para esta linha e sentido neste ponto agora.</p> }
                }
                <div class="fala__acoes">
                  <button class="botao botao--contorno botao--pequeno" type="button" [disabled]="carregandoPrevisao()" (click)="selecionar(p)">Atualizar previsões</button>
                  <a class="botao botao--pequeno" [routerLink]="['/ponto', p.codigo]" [queryParams]="{ linha: letreiro() }">Abrir ponto</a>
                </div>
              </section>
            }
            <ol class="paradas linha__paradas">
              @for (item of visiveis(); track item.ordem) {
                <li class="parada" [value]="item.ordem" [class.parada--selecionada]="selecionada()?.codigo === item.p.codigo">
                  <button type="button" class="parada__link" [attr.aria-pressed]="selecionada()?.codigo === item.p.codigo" (click)="selecionar(item.p)">
                    <span class="parada__ordem" aria-hidden="true">{{ item.ordem }}</span>
                    <span class="parada__texto">
                      <span class="parada__nome">{{ item.p.nome }}</span>
                      <span class="parada__meta">@if (item.p.endereco) { {{ item.p.endereco }} · } Ponto {{ item.p.codigo }} · Ver previsões</span>
                    </span>
                    <pf-icone class="parada__seta" nome="chevron" />
                  </button>
                </li>
              } @empty { <li class="vazio">Nenhuma parada encontrada neste sentido. Tente outra rua ou limpe a busca.</li> }
            </ol>
            @if (visiveis().length < filtradas().length) {
              <button class="botao botao--contorno" type="button" (click)="limite.set(limite() + 15)">Mostrar mais paradas ({{ visiveis().length }} de {{ filtradas().length }})</button>
            }
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
  protected readonly busca = signal('');
  protected readonly limite = signal(15);
  protected readonly selecionada = signal<Ponto | null>(null);
  protected readonly previsao = signal<PrevisoesPonto | null>(null);
  protected readonly carregandoPrevisao = signal(false);
  protected readonly erroPrevisao = signal('');
  protected readonly filtradas = computed(() => {
    const normalizar = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
    const termos = normalizar(this.busca()).trim().split(/\s+/);
    return (this.atual()?.paradas ?? []).map((p, i) => ({ p, ordem: i + 1 })).filter(({ p }) => termos.every(t => normalizar(`${p.nome} ${p.endereco ?? ''} ${p.codigo}`).includes(t)));
  });
  protected readonly visiveis = computed(() => this.filtradas().slice(0, this.limite()));
  protected readonly onibus = computed(() => (this.previsao()?.onibus ?? []).filter(o => o.letreiro === this.letreiro() && o.sentido === this.atual()?.sentido).sort((a, b) => a.minutos - b.minutos));
  protected readonly atual = computed<SentidoLinha | null>(() => {
    const d = this.dados();
    if (!d || d.sentidos.length === 0) return null;
    return d.sentidos.find((s) => s.sentido === this.sentidoAtual()) ?? d.sentidos[0];
  });
  private pedido = 0;
  private pedidoPrevisao = 0;
  private readonly painel = viewChild<ElementRef<HTMLElement>>('painel');

  constructor() {
    inject(DestroyRef).onDestroy(() => { this.pedido++; this.pedidoPrevisao++; });
    effect(() => {
      this.letreiro();
      untracked(() => void this.carregar());
    });
  }

  protected escolher(sentido: number): void {
    this.fecharPonto();
    this.limite.set(15);
    this.sentidoAtual.set(sentido);
    const s = this.atual();
    if (s) this.anuncio.set(`Sentido ${s.destino}: ${s.paradas.length} paradas.`);
  }

  protected filtrar(termo: string): void { this.busca.set(termo); this.limite.set(15); }
  protected fecharPonto(): void { this.pedidoPrevisao++; this.selecionada.set(null); this.previsao.set(null); this.carregandoPrevisao.set(false); this.erroPrevisao.set(''); }
  protected async selecionar(ponto: Ponto): Promise<void> {
    const pedido = ++this.pedidoPrevisao;
    const mudou = this.selecionada()?.codigo !== ponto.codigo;
    this.selecionada.set(ponto); this.previsao.set(null); this.erroPrevisao.set(''); this.carregandoPrevisao.set(true);
    if (mudou) setTimeout(() => { if (pedido === this.pedidoPrevisao) this.painel()?.nativeElement.focus(); }, 0);
    try {
      const p = await firstValueFrom(this.api.previsoes(ponto.codigo));
      if (pedido === this.pedidoPrevisao) this.previsao.set(p);
    } catch {
      if (pedido === this.pedidoPrevisao) this.erroPrevisao.set('A SPTrans não respondeu agora. Tente atualizar em instantes.');
    } finally { if (pedido === this.pedidoPrevisao) this.carregandoPrevisao.set(false); }
  }

  async carregar(): Promise<void> {
    this.fecharPonto(); this.busca.set(''); this.limite.set(15);
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
