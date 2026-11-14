import { Component, DestroyRef, ElementRef, computed, effect, inject, input, signal, untracked, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { BuscasRecentesService } from '../../core/buscas-recentes.service';
import { ErroApi, Fonte, Linha, Modo, Ponto } from '../../core/models';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { Letreiro } from '../../shared/letreiro';
import { MensagemErro } from '../../shared/mensagem-erro';
import { SeloFonte } from '../../shared/selo-fonte';
import { EXEMPLOS_BUSCA } from '../inicio/inicio';

export type TipoBusca = 'pontos' | 'linhas';

@Component({
  selector: 'pf-busca',
  imports: [FormsModule, RouterLink, Carregando, MensagemErro, SeloFonte, Icone, Letreiro],
  template: `
    <div class="pagina busca">
      <header class="cabecalho">
        
        <h1>{{ tipoAtual() === 'linhas' ? 'Buscar linha' : 'Buscar ponto' }}</h1>
        <p class="cabecalho__apoio">{{ linha() && tipoAtual() === 'pontos' ? 'Linha ' + linha() + ': busque o ponto onde você vai embarcar para consultar as previsões.' : 'Previsões para sua próxima viagem.' }}</p>
      </header>

      <form class="busca__form" role="search" aria-label="Buscar ponto ou linha" (ngSubmit)="enviar()" novalidate>
        <fieldset class="segmentos">
          <legend class="vo">O que você procura</legend>
          <label class="segmento">
            <input type="radio" name="tipo" value="pontos" [checked]="tipoAtual() === 'pontos'" (change)="trocarTipo('pontos')" />
            <span>Pontos</span>
          </label>
          <label class="segmento">
            <input type="radio" name="tipo" value="linhas" [checked]="tipoAtual() === 'linhas'" (change)="trocarTipo('linhas')" />
            <span>Linhas</span>
          </label>
        </fieldset>

        <div class="campo-busca">
          <label for="termo" class="campo-busca__rotulo">
            {{ tipoAtual() === 'linhas' ? 'Número ou destino da linha' : 'Nome do ponto, rua ou código' }}
          </label>
          <div class="campo-busca__linha" [class.campo-busca__linha--erro]="erroCampo()">
            <pf-icone nome="busca" />
            <input
              #campo
              id="termo"
              name="termo"
              type="search"
              enterkeyhint="search"
              autocomplete="off"
              maxlength="80"
              [placeholder]="tipoAtual() === 'linhas' ? 'Ex.: 8000 ou Lapa' : 'Ex.: Av. Paulista, 1000'"
              [(ngModel)]="texto"
              (ngModelChange)="erroCampo.set('')"
              [attr.aria-invalid]="erroCampo() ? 'true' : null"
              [attr.aria-describedby]="erroCampo() ? 'termo-erro termo-ajuda' : 'termo-ajuda'"
            />
            <button type="submit" class="botao botao--primario">Buscar</button>
          </div>
          <p id="termo-ajuda" class="vo">
            {{ tipoAtual() === 'linhas' ? 'Digite o número que aparece no letreiro, como 8000-10, ou o bairro de destino.' : 'Você pode digitar o nome da rua com o número, o nome do ponto ou o código que fica na placa do ponto.' }}
          </p>
          @if (erroCampo()) {
            <p id="termo-erro" class="erro-campo"><pf-icone nome="alerta" /> {{ erroCampo() }}</p>
          }
        </div>
        @if (tipoAtual() === 'pontos' && modo() !== 'demo') {
          <div class="busca__perto">
            <button type="button" class="botao botao--contorno" (click)="pertoDeMim()" [disabled]="localizando()">
              <pf-icone nome="ponto" /> {{ localizando() ? 'Obtendo sua localização…' : 'Pontos perto de mim' }}
            </button>
            @if (erroLocal()) {
              <p class="erro-campo" role="alert"><pf-icone nome="alerta" /> {{ erroLocal() }}</p>
            }
          </div>
        }
      </form>

      <section class="resultados" aria-labelledby="resultados-titulo" [attr.aria-busy]="buscando()">
        <h2 id="resultados-titulo" class="vo">Resultados</h2>
        <p class="vo" role="status">{{ anuncio() }}</p>

        @if (buscando()) {
          <pf-carregando [texto]="tipoAtual() === 'linhas' ? 'Procurando linhas…' : 'Procurando pontos…'" [linhas]="3" />
        } @else if (erro(); as e) {
          <pf-erro
            [titulo]="e.status === 503 ? 'A SPTrans não respondeu' : 'Não foi possível buscar'"
            [mensagem]="e.status === 503 ? 'O serviço de previsões está fora do ar agora. Tente de novo em instantes ou veja a demonstração com dados simulados.' : e.message"
            (repetir)="executar()"
          >
            @if (e.status === 503 && modo() !== 'demo') {
              <a class="botao botao--primario" routerLink="/busca" [queryParams]="{ q: termo(), tipo: tipoAtual(), modo: 'demo' }">Ver demonstração</a>
            }
          </pf-erro>
        } @else if ((termo() || perto()) && resultadoTipo() === tipoAtual()) {
          @if (contagem() === 0) {
            <div class="vazio">
              <p class="vazio__titulo">{{ perto() ? 'Nenhum ponto perto de você.' : 'Nada encontrado para “' + termo() + '”.' }}</p>
              @if (aviso()) {
                <p>{{ aviso() }}</p>
              }
              <ul class="vazio__dicas">
                @if (tipoAtual() === 'pontos') {
                  <li>Digite só o nome da rua, como “Paulista”, ou a rua com o número.</li>
                  <li>Se você sabe o código da placa do ponto, digite só os números.</li>
                } @else {
                  <li>Confira a grafia ou use só uma parte do nome, como “Lapa”.</li>
                  <li>Digite só o número da linha, sem o final, como “8000”.</li>
                }
              </ul>
              @if (!perto()) {
                <button type="button" class="botao botao--contorno" (click)="trocarTipo(tipoAtual() === 'pontos' ? 'linhas' : 'pontos')">
                  <pf-icone nome="troca" /> Procurar “{{ termo() }}” em {{ tipoAtual() === 'pontos' ? 'linhas' : 'pontos' }}
                </button>
              }
            </div>
          } @else {
            <div class="resultados__topo">
              <p class="resultados__conta" aria-hidden="true">
                <strong>{{ contagem() }}</strong> {{ rotuloContagem() }} {{ perto() ? 'perto de você' : 'para “' + termo() + '”' }}
              </p>
              @if (fonte(); as f) {
                <pf-selo-fonte [fonte]="f" />
              }
            </div>

            @if (aviso()) {
              <p class="aviso-linha busca__aviso"><pf-icone nome="alerta" /> <span>{{ aviso() }}</span></p>
            }

            @if (tipoAtual() === 'pontos') {
              <ul class="paradas paradas--resultado">
                @for (p of pontos(); track p.codigo) {
                  <li class="parada">
                    <a class="parada__link" [routerLink]="['/ponto', p.codigo]" [queryParams]="contextoPonto()">
                      <span class="parada__marca" aria-hidden="true"></span>
                      <span class="parada__texto">
                        <span class="parada__nome">{{ p.nome }}</span>
                        <span class="parada__meta">
                          @if (p.distancia_metros !== null && p.distancia_metros !== undefined) {
                            <strong>a {{ p.distancia_metros }} m</strong> ·
                          }
                          @if (p.endereco) {
                            {{ p.endereco }} ·
                          }
                          Ponto {{ p.codigo }}
                        </span>
                        @if (p.linhas?.length) {
                          <span class="parada__meta parada__linhas"><span class="vo">Linhas que param aqui: </span>{{ resumoLinhas(p.linhas!) }}</span>
                        }
                      </span>
                      <pf-icone class="parada__seta" nome="chevron" />
                    </a>
                  </li>
                }
              </ul>
            } @else {
              <ul class="linhas-resultado">
                @for (l of linhas(); track $index) {
                  <li class="linha-item">
                    <pf-letreiro [codigo]="l.letreiro" />
                    <div class="linha-item__texto">
                      <p class="linha-item__trajeto">
                        @if (l.circular) {
                          Circular · {{ l.terminal_principal }}
                        } @else {
                          <span class="vo">Sentido </span>{{ l.destino || l.terminal_secundario }}
                        }
                      </p>
                      @if (!l.circular && l.terminal_principal && l.terminal_secundario) {
                        <p class="linha-item__meta">{{ origemDa(l) }} → {{ l.destino || l.terminal_secundario }}</p>
                      }
                    </div>
                    @if (modo() === 'demo') {
                      <a class="botao-texto" routerLink="/busca" [queryParams]="{ linha: l.letreiro, modo: 'demo' }">
                        Escolher ponto<span class="vo"> para consultar a linha {{ l.letreiro }} sentido {{ l.destino || l.terminal_secundario }}</span><pf-icone nome="chevron" />
                      </a>
                    } @else {
                      <a class="botao-texto" [routerLink]="['/linha', l.letreiro]" [queryParams]="{ sentido: l.sentido }">
                        Ver paradas<span class="vo"> da linha {{ l.letreiro }} sentido {{ l.destino || l.terminal_secundario }}</span><pf-icone nome="chevron" />
                      </a>
                    }
                  </li>
                }
              </ul>
            }
          }
        } @else {
          <div class="sugestoes sugestoes--busca">
            <p class="sugestoes__titulo" id="sug-busca">{{ buscasRecentes.lista().length ? 'Buscas recentes' : 'Experimente' }}</p>
            <ul class="sugestoes__lista" aria-labelledby="sug-busca">
              @for (s of sugestoes(); track s) {
                <li><button type="button" class="chip" (click)="usar(s)">{{ s }}</button></li>
              }
            </ul>
            @if (buscasRecentes.lista().length) {
              <button type="button" class="botao-texto" (click)="buscasRecentes.limpar()">Limpar buscas recentes</button>
            }
          </div>
        }
      </section>
    </div>
  `,
})
export class Busca {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  protected readonly buscasRecentes = inject(BuscasRecentesService);
  private readonly campo = viewChild<ElementRef<HTMLInputElement>>('campo');

  /** Query params (component input binding): ?q=&tipo=&modo= */
  readonly q = input<string | undefined>();
  readonly tipo = input<string | undefined>();
  readonly modo = input<string | undefined>();
  readonly linha = input<string | undefined>();
  /** ?perto=1 (vindo do assistente): pede a localização ao abrir, com a permissão do navegador. */
  readonly pertoParam = input<string | undefined>(undefined, { alias: 'perto' });

  protected texto = '';
  protected readonly tipoAtual = signal<TipoBusca>('pontos');
  protected readonly termo = signal('');
  protected readonly erroCampo = signal('');
  protected readonly buscando = signal(false);
  protected readonly erro = signal<ErroApi | null>(null);
  protected readonly pontos = signal<Ponto[]>([]);
  protected readonly linhas = signal<Linha[]>([]);
  protected readonly fonte = signal<Fonte | null>(null);
  protected readonly resultadoTipo = signal<TipoBusca | null>(null);
  protected readonly anuncio = signal('');
  protected readonly aviso = signal<string | null>(null);
  /** Resultado atual veio da localização do aparelho (que nunca vai para a URL nem é guardada). */
  protected readonly perto = signal(false);
  protected readonly localizando = signal(false);
  protected readonly erroLocal = signal('');
  private pedido = 0;

  protected readonly contagem = computed(() =>
    this.resultadoTipo() === 'linhas' ? this.linhas().length : this.pontos().length,
  );
  protected readonly sugestoes = computed(() =>
    this.buscasRecentes.lista().length ? this.buscasRecentes.lista() : EXEMPLOS_BUSCA,
  );

  constructor() {
    inject(DestroyRef).onDestroy(() => this.pedido++);
    effect(() => {
      const q = (this.q() ?? '').trim().slice(0, 80);
      const tipo: TipoBusca = this.tipo() === 'linhas' ? 'linhas' : 'pontos';
      this.modo();
      this.pertoParam();
      untracked(() => {
        this.tipoAtual.set(tipo);
        this.texto = q;
        this.termo.set(q);
        if (q.length >= (tipo === 'linhas' ? 1 : 2)) void this.executar();
        else if (this.pertoParam() === '1' && tipo === 'pontos') this.pertoDeMim();
        else {
          this.pedido++;
          this.buscando.set(false);
          this.anuncio.set('');
          this.perto.set(false);
          this.aviso.set(null);
          this.resultadoTipo.set(null);
          this.erro.set(null);
          setTimeout(() => this.campo()?.nativeElement.focus(), 0);
        }
      });
    });
  }

  protected rotuloContagem(): string {
    const n = this.contagem();
    if (this.resultadoTipo() === 'linhas') return n === 1 ? 'linha' : 'linhas';
    return n === 1 ? 'ponto' : 'pontos';
  }

  private encontrados(n: number, tipo: TipoBusca): string {
    return (tipo === 'linhas' ? 'encontrada' : 'encontrado') + (n === 1 ? '' : 's');
  }

  protected resumoLinhas(linhas: string[]): string {
    const max = 6;
    return linhas.slice(0, max).join(' · ') + (linhas.length > max ? ` · mais ${linhas.length - max}` : '');
  }

  protected pertoDeMim(): void {
    this.erroLocal.set('');
    if (!('geolocation' in navigator)) {
      this.erroLocal.set('Este aparelho não informa a localização. Busque pelo nome da rua.');
      return;
    }
    const pedido = ++this.pedido;
    this.localizando.set(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this.localizando.set(false);
        if (pedido === this.pedido) void this.executarPerto(pos.coords.latitude, pos.coords.longitude);
      },
      (err) => {
        this.localizando.set(false);
        this.erroLocal.set(
          err.code === err.PERMISSION_DENIED
            ? 'A localização não foi autorizada. Você pode buscar pelo nome da rua ou pelo código do ponto.'
            : 'Não consegui obter sua localização agora. Tente de novo ou busque pelo nome da rua.',
        );
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
    );
  }

  private async executarPerto(lat: number, lon: number): Promise<void> {
    const pedido = ++this.pedido;
    this.buscando.set(true);
    this.erro.set(null);
    this.anuncio.set('');
    this.tipoAtual.set('pontos');
    try {
      let r = await firstValueFrom(this.api.pontosProximos(lat, lon, 400));
      if (pedido === this.pedido && r.pontos.length === 0 && !r.aviso?.includes('fora da área')) {
        r = await firstValueFrom(this.api.pontosProximos(lat, lon, 1000));
      }
      if (pedido !== this.pedido) return;
      this.perto.set(true);
      this.pontos.set(r.pontos);
      this.fonte.set(r.fonte);
      this.aviso.set(r.aviso ?? null);
      this.resultadoTipo.set('pontos');
      const n = r.pontos.length;
      this.anuncio.set(n === 0 ? (r.aviso ?? 'Nenhum ponto perto de você.') : `${n} ${n === 1 ? 'ponto' : 'pontos'} perto de você, do mais próximo ao mais distante.`);
    } catch (e) {
      if (pedido !== this.pedido) return;
      this.resultadoTipo.set(null);
      this.erro.set(e instanceof ErroApi ? e : new ErroApi(-1, 'Algo deu errado. Tente de novo.'));
    } finally {
      if (pedido === this.pedido) this.buscando.set(false);
    }
  }

  protected origemDa(l: Linha): string {
    const destino = l.destino || l.terminal_secundario;
    return destino === l.terminal_principal ? (l.terminal_secundario ?? '') : (l.terminal_principal ?? '');
  }

  protected trocarTipo(tipo: TipoBusca): void {
    this.tipoAtual.set(tipo);
    this.erroCampo.set('');
    const termo = this.texto.trim();
    if (termo) this.navegar(termo, tipo);
    else this.campo()?.nativeElement.focus();
  }

  protected usar(s: string): void {
    this.texto = s;
    this.navegar(s, this.tipoAtual());
  }

  protected enviar(): void {
    const termo = this.texto.trim();
    const minimo = this.tipoAtual() === 'linhas' ? 1 : 2;
    if (termo.length < minimo) {
      this.erroCampo.set(minimo === 1 ? 'Digite o número ou o destino da linha.' : 'Digite pelo menos 2 letras ou números.');
      this.campo()?.nativeElement.focus();
      return;
    }
    // Mesma busca de novo: executa sem navegar.
    if (termo === this.termo() && this.tipoAtual() === (this.tipo() === 'linhas' ? 'linhas' : 'pontos')) {
      void this.executar();
      return;
    }
    this.navegar(termo, this.tipoAtual());
  }

  private navegar(q: string, tipo: TipoBusca): void {
    const qp: Record<string, string> = { q };
    if (tipo === 'linhas') qp['tipo'] = 'linhas';
    if (this.modo() === 'demo') qp['modo'] = 'demo';
    if (tipo === 'pontos' && this.linha()) qp['linha'] = this.linha()!;
    void this.router.navigate(['/busca'], { queryParams: qp });
  }

  protected contextoPonto(): Record<string, string> {
    return { ...(this.modo() === 'demo' ? { modo: 'demo' } : {}), ...(this.linha() ? { linha: this.linha()! } : {}) };
  }

  async executar(): Promise<void> {
    const pedido = ++this.pedido;
    const termo = this.termo();
    const tipo = this.tipoAtual();
    const modo: Modo = this.modo() === 'demo' ? 'demo' : 'auto';
    this.buscando.set(true);
    this.erro.set(null);
    this.anuncio.set('');
    this.perto.set(false);
    this.aviso.set(null);
    try {
      if (tipo === 'linhas') {
        const r = await firstValueFrom(this.api.buscarLinhas(termo, modo));
        if (pedido !== this.pedido) return;
        this.linhas.set(r.linhas);
        this.fonte.set(r.fonte);
      } else {
        const r = await firstValueFrom(this.api.buscarPontos(termo, modo));
        if (pedido !== this.pedido) return;
        this.pontos.set(r.pontos);
        this.fonte.set(r.fonte);
        this.aviso.set(r.aviso ?? null);
      }
      this.resultadoTipo.set(tipo);
      this.buscasRecentes.adicionar(termo);
      const n = this.contagem();
      const simulado = this.fonte() === 'SIMULADO' ? ' Dados simulados.' : '';
      this.anuncio.set(
        n === 0
          ? `Nenhum resultado para ${termo}. ${this.aviso() ?? ''}`
          : `${n} ${this.rotuloContagem()} ${this.encontrados(n, tipo)} para ${termo}.${simulado} ${this.aviso() ?? ''}`,
      );
    } catch (e) {
      if (pedido !== this.pedido) return;
      this.resultadoTipo.set(null);
      this.erro.set(e instanceof ErroApi ? e : new ErroApi(-1, 'Algo deu errado. Tente de novo.'));
    } finally {
      if (pedido === this.pedido) this.buscando.set(false);
    }
  }
}
