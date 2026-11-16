import { Component, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { BuscasRecentesService } from '../../core/buscas-recentes.service';
import { FavoritosService } from '../../core/favoritos.service';
import { formatarData } from '../../core/format';
import { RecentesService, chavePonto } from '../../core/recentes.service';
import { StatusService } from '../../core/status.service';
import { Icone } from '../../shared/icone';
import { Origem } from '../../shared/origem';

export const EXEMPLOS_BUSCA = ['Paulista', 'Faria Lima', 'Luz', '990001'];

@Component({
  selector: 'pf-inicio',
  imports: [FormsModule, RouterLink, Icone, Origem],
  template: `
    <div class="pagina inicio">
      <section class="inicio__busca" aria-labelledby="inicio-titulo">
        <div class="inicio__texto">
          <p class="sobretitulo"><pf-icone nome="ponto" /> São Paulo</p>
          <h1 id="inicio-titulo">Seu próximo ônibus.</h1>
          <p class="inicio__apoio">Busque um ponto ou uma linha e veja quando sair.</p>
        </div>
        <div class="inicio__ferramenta">
          <form class="campo-busca campo-busca--grande" role="search" aria-label="Buscar ponto ou linha" (ngSubmit)="buscar()" novalidate>
            <fieldset class="segmentos inicio__tipos">
              <legend class="vo">O que você procura</legend>
              <label class="segmento"><input type="radio" name="tipo" value="pontos" [checked]="tipo() === 'pontos'" (change)="tipo.set('pontos'); erroCampo.set('')" /><span><pf-icone nome="busca" /> Ponto de ônibus</span></label>
              <label class="segmento"><input type="radio" name="tipo" value="linhas" [checked]="tipo() === 'linhas'" (change)="tipo.set('linhas'); erroCampo.set('')" /><span>Linha de ônibus</span></label>
            </fieldset>
            <label for="busca" class="campo-busca__rotulo">{{ tipo() === 'linhas' ? 'Número ou destino da linha' : 'Nome do ponto, rua ou código' }}</label>
            <div class="campo-busca__linha" [class.campo-busca__linha--erro]="erroCampo()">
              <pf-icone nome="busca" />
              <input
                id="busca"
                name="busca"
                type="search"
                inputmode="search"
                enterkeyhint="search"
                autocomplete="off"
                maxlength="80"
                [placeholder]="tipo() === 'linhas' ? 'Ex.: 8000-10 ou Lapa' : 'Ex.: Avenida Paulista'"
                [(ngModel)]="texto"
                (ngModelChange)="erroCampo.set('')"
                [attr.aria-invalid]="erroCampo() ? 'true' : null"
                [attr.aria-describedby]="erroCampo() ? 'busca-erro' : null"
              />
              <button type="submit" class="botao botao--primario">Buscar <pf-icone nome="seta-direita" /></button>
            </div>
            @if (erroCampo()) {
              <p id="busca-erro" class="erro-campo" role="alert"><pf-icone nome="alerta" /> {{ erroCampo() }}</p>
            }
          </form>
          <div class="sugestoes inicio__sugestoes">
            <p class="sugestoes__titulo" id="sugestoes-titulo">{{ buscasRecentes.lista().length ? 'Buscas recentes' : 'Exemplos de busca' }}</p>
            <ul class="sugestoes__lista" aria-labelledby="sugestoes-titulo">
              @for (s of sugestoes(); track s) {
                <li><a class="chip" routerLink="/busca" [queryParams]="qp(s)">{{ s }} <pf-icone nome="seta-direita" /></a></li>
              }
            </ul>
          </div>
        </div>
        <a class="inicio__embarque" routerLink="/embarque" [queryParams]="qpModo()">
          <span class="inicio__embarque-icone" aria-hidden="true"><pf-icone nome="volume" /></span>
          <span class="inicio__embarque-texto">
            <strong>Embarque assistido</strong>
            <span>Escolha o ponto e o ônibus: eu acompanho a SPTrans e aviso por voz quando ele estiver chegando.</span>
          </span>
          <pf-icone nome="seta-direita" />
        </a>
        <a class="inicio__voz" routerLink="/assistente"><pf-icone nome="microfone" /> Prefere perguntar? Fale com o assistente <pf-icone nome="seta-direita" /></a>
      </section>
      <section class="inicio__pontos" aria-labelledby="meus-titulo">
        <div class="secao-topo">
          <h2 id="meus-titulo">Seus favoritos</h2><a class="botao-texto" routerLink="/favoritos" [queryParams]="qpModo()">Ver todos{{ favoritos.lista().length ? ' (' + favoritos.lista().length + ')' : '' }} <pf-icone nome="chevron" /></a>
        </div>
        @if (favoritos.lista().length === 0) {
          <p class="vazio-trajeto">
            Seus pontos de sempre ficam aqui. Toque em <strong>Salvar ponto</strong> nas previsões.
          </p>
          <a class="botao-texto" routerLink="/busca" [queryParams]="qpModo()">Encontrar um ponto <pf-icone nome="seta-direita" /></a>
        } @else {
          <ul class="paradas paradas--favoritas">
            @for (p of favoritos.lista().slice(0, 3); track chavePonto(p)) {
              <li class="parada">
                <a class="parada__link" [routerLink]="['/ponto', p.codigo]" [queryParams]="p.modo === 'demo' ? { modo: 'demo' } : null">
                  <span class="parada__marca" aria-hidden="true"></span>
                  <span class="parada__texto">
                    <span class="parada__nome">{{ p.nome }}</span>
                    <span class="parada__meta">Ponto {{ p.codigo }}{{ p.modo === 'demo' ? ' · SIMULADO' : '' }}</span>
                  </span>
                  <pf-icone class="parada__seta" nome="chevron" />
                </a>
              </li>
            }
          </ul>
        }

        @if (recentesSemFavoritos().length) {
          <div class="secao-topo secao-topo--sub">
            <h2 id="recentes-titulo">Vistos recentemente</h2>
            <button type="button" class="botao-texto" (click)="recentes.limpar()">
              Limpar<span class="vo"> pontos vistos recentemente</span>
            </button>
          </div>
          <ul class="paradas" aria-labelledby="recentes-titulo">
            @for (p of recentesSemFavoritos(); track chavePonto(p)) {
              <li class="parada">
                <a class="parada__link" [routerLink]="['/ponto', p.codigo]" [queryParams]="p.modo === 'demo' ? { modo: 'demo' } : null">
                  <span class="parada__marca" aria-hidden="true"></span>
                  <span class="parada__texto">
                    <span class="parada__nome">{{ p.nome }}</span>
                    <span class="parada__meta">Ponto {{ p.codigo }}{{ p.modo === 'demo' ? ' · SIMULADO' : '' }}</span>
                  </span>
                  <pf-icone class="parada__seta" nome="chevron" />
                </a>
              </li>
            }
          </ul>
        }
      </section>

      <div class="inicio__servico">
        @if (demo()) { <pf-origem tipo="simulado" rotulo="SIMULADO · demonstração" /> }
        @else if (status.status()?.sptrans === 'REAL') { <pf-origem tipo="real" rotulo="Previsões da SPTrans" /> }
        @else if (status.status()?.sptrans === 'INDISPONIVEL' || status.falhou()) { <pf-origem tipo="indisponivel" rotulo="Previsões indisponíveis agora" /> }
        @else { <pf-origem tipo="verificando" /> }
        <a routerLink="/sobre" fragment="dados">Sobre os dados</a>
      </div>
    </div>
  `,
})
export class Inicio {
  private readonly router = inject(Router);
  protected readonly status = inject(StatusService);
  protected readonly recentes = inject(RecentesService);
  protected readonly favoritos = inject(FavoritosService);
  protected readonly buscasRecentes = inject(BuscasRecentesService);

  /** Vem de ?modo=demo (component input binding). */
  readonly modo = input<string | undefined>();
  protected readonly demo = computed(() => this.modo() === 'demo' || this.status.demo());
  protected readonly qpModo = computed(() => (this.modo() === 'demo' ? { modo: 'demo' } : null));

  protected texto = '';
  protected readonly tipo = signal<'pontos' | 'linhas'>('pontos');
  protected readonly erroCampo = signal('');
  protected readonly data = formatarData;
  protected readonly chavePonto = chavePonto;

  protected readonly sugestoes = computed(() =>
    this.tipo() === 'linhas' ? ['8000', 'Lapa', 'Pinheiros'] : this.buscasRecentes.lista().length ? this.buscasRecentes.lista().slice(0, 4) : EXEMPLOS_BUSCA,
  );

  protected readonly recentesSemFavoritos = computed(() =>
    this.recentes.lista().filter((p) => !this.favoritos.eFavorito(p.codigo, p.modo)),
  );

  protected qp(q: string): Record<string, string> {
    return { q, ...(this.tipo() === 'linhas' ? { tipo: 'linhas' } : {}), ...(this.modo() === 'demo' ? { modo: 'demo' } : {}) };
  }

  protected buscar(): void {
    const termo = this.texto.trim();
    if (termo.length < (this.tipo() === 'linhas' ? 1 : 2)) {
      this.erroCampo.set(this.tipo() === 'linhas' ? 'Digite o número ou o destino da linha.' : 'Digite pelo menos 2 letras ou números.');
      return;
    }
    void this.router.navigate(['/busca'], { queryParams: this.qp(termo) });
  }
}
