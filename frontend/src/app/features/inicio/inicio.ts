import { Component, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, Modo, Ponto, Status } from '../../core/models';
import { RecentesService } from '../../core/recentes.service';
import { Carregando } from '../../shared/carregando';
import { Icone } from '../../shared/icone';
import { MensagemErro } from '../../shared/mensagem-erro';
import { Selo } from '../../shared/selo';

@Component({
  selector: 'pf-inicio',
  imports: [FormsModule, RouterLink, Carregando, MensagemErro, Selo, Icone],
  template: `
    <section class="hero">
      <div class="miolo">
        <p class="hero__chapeu"><pf-icone nome="ponto" /> São Paulo · ônibus</p>
        <h1>Qual ônibus você espera?</h1>
        <p class="hero__texto">
          Veja os próximos ônibus <strong>previstos</strong> para o seu ponto e ouça tudo em voz alta.
        </p>

        <form class="busca" (ngSubmit)="buscar()" novalidate>
          <label for="busca" class="busca__rotulo">Nome, rua ou código do ponto</label>
          <div class="busca__campo">
            <pf-icone nome="busca" />
            <input
              id="busca"
              name="busca"
              type="search"
              autocomplete="off"
              maxlength="80"
              placeholder="Ex.: Avenida Paulista"
              [(ngModel)]="texto"
              [attr.aria-invalid]="erroCampo() ? 'true' : null"
              [attr.aria-describedby]="erroCampo() ? 'busca-erro busca-ajuda' : 'busca-ajuda'"
            />
            <button type="submit" class="botao botao--sinal" [disabled]="buscando()">Buscar</button>
          </div>
          <p id="busca-ajuda" class="busca__ajuda">Você também pode digitar o número do ponto, como 700001234.</p>
          @if (erroCampo()) {
            <p id="busca-erro" class="erro-campo"><pf-icone nome="erro-circulo" /> {{ erroCampo() }}</p>
          }
        </form>

        <section class="estado" aria-label="Estado dos serviços">
          @if (demo() || status()?.sptrans === 'DEMO') {
            <pf-selo tom="aviso" icone="frasco">Modo demonstração: dados simulados</pf-selo>
          } @else if (status()?.sptrans === 'REAL') {
            <pf-selo tom="ok" icone="certo-circulo">Dados em tempo real da SPTrans</pf-selo>
          } @else if (status()?.sptrans === 'INDISPONIVEL') {
            <pf-selo tom="critico" icone="erro-circulo">SPTrans fora do ar agora</pf-selo>
          } @else if (statusFalhou()) {
            <pf-selo tom="neutro" icone="vazio">Não foi possível verificar os serviços</pf-selo>
          } @else {
            <pf-selo tom="neutro" icone="relogio">Verificando os serviços…</pf-selo>
          }
          @if (status(); as s) {
            @if (s.assistente === 'DISPONIVEL') {
              <pf-selo tom="ok" icone="certo-circulo">Assistente ligado</pf-selo>
            } @else {
              <pf-selo tom="neutro" icone="lua">Assistente desligado agora</pf-selo>
            }
          }
        </section>
      </div>
    </section>

    <div class="miolo miolo--largo">
      <div aria-live="polite" class="resultado">
        @if (buscando()) {
          <pf-carregando texto="Procurando pontos…" />
        } @else if (erroBusca(); as e) {
          <pf-erro titulo="Não foi possível buscar" [mensagem]="e.message" [tentarNovamente]="e.status !== 503" (repetir)="buscar()">
            @if (e.status === 503) {
              <button type="button" class="botao botao--primario" (click)="buscarEmDemo()">Ver demonstração</button>
            }
          </pf-erro>
        } @else if (resultados(); as lista) {
          @if (lista.length === 0) {
            <p class="vazio">Nenhum ponto encontrado para “{{ ultimaBusca() }}”. Tente outro nome ou parte do endereço.</p>
          } @else {
            <h2>{{ lista.length === 1 ? '1 ponto encontrado' : lista.length + ' pontos encontrados' }}</h2>
            <ul class="lista-pontos">
              @for (p of lista; track p.codigo) {
                <li>
                  <a class="ponto-card" [routerLink]="['/ponto', p.codigo]" [queryParams]="qpModo()">
                    <span class="ponto-card__marca"><pf-icone nome="ponto" /></span>
                    <span class="ponto-card__texto">
                      <span class="ponto-card__nome">{{ p.nome }}</span>
                      @if (p.endereco) {
                        <span class="ponto-card__sub">{{ p.endereco }}</span>
                      }
                      <span class="ponto-card__sub">Ponto {{ p.codigo }}</span>
                    </span>
                    <pf-icone nome="seta-direita" />
                  </a>
                </li>
              }
            </ul>
          }
        }
      </div>

      @if (recentes.lista().length > 0) {
        <section aria-labelledby="recentes-titulo">
          <h2 id="recentes-titulo">Pontos recentes</h2>
          <ul class="lista-pontos">
            @for (p of recentes.lista(); track p.codigo) {
              <li>
                <a class="ponto-card" [routerLink]="['/ponto', p.codigo]" [queryParams]="qpModo()">
                  <span class="ponto-card__marca"><pf-icone nome="relogio" /></span>
                  <span class="ponto-card__texto">
                    <span class="ponto-card__nome">{{ p.nome }}</span>
                    <span class="ponto-card__sub">Ponto {{ p.codigo }}</span>
                  </span>
                  <pf-icone nome="seta-direita" />
                </a>
              </li>
            }
          </ul>
          <button type="button" class="botao botao--discreto" (click)="recentes.limpar()">Limpar pontos recentes</button>
        </section>
      }

      <section aria-labelledby="atalhos-titulo">
        <h2 id="atalhos-titulo">Mais formas de ajudar na viagem</h2>
        <ul class="atalhos">
          <li>
            <a class="atalho" routerLink="/assistente">
              <span class="atalho__icone"><pf-icone nome="conversa" /></span>
              <span class="atalho__titulo">Assistente</span>
              <span class="atalho__texto">Tire dúvidas sobre gratuidade, bilhete e acessibilidade.</span>
            </a>
          </li>
          <li>
            <a class="atalho" routerLink="/boletim">
              <span class="atalho__icone"><pf-icone nome="boletim" /></span>
              <span class="atalho__titulo">Boletim de atrasos</span>
              <span class="atalho__texto">Veja quais linhas estão atrasadas hoje.</span>
            </a>
          </li>
          <li>
            <a class="atalho" routerLink="/acessibilidade">
              <span class="atalho__icone"><pf-icone nome="letras" /></span>
              <span class="atalho__titulo">Letras, cores e voz</span>
              <span class="atalho__texto">Aumente o texto, troque as cores e escolha a velocidade da voz.</span>
            </a>
          </li>
        </ul>
      </section>
    </div>
  `,
})
export class Inicio {
  private readonly api = inject(ApiService);
  protected readonly recentes = inject(RecentesService);

  /** Vem de ?modo=demo (component input binding). */
  readonly modo = input<string | undefined>();
  private readonly demoForcado = signal(false);
  protected readonly demo = computed(() => this.modo() === 'demo' || this.demoForcado());
  protected readonly qpModo = computed(() => (this.demo() ? { modo: 'demo' } : null));

  protected readonly status = signal<Status | null>(null);
  protected readonly statusFalhou = signal(false);

  protected texto = '';
  protected readonly erroCampo = signal('');
  protected readonly buscando = signal(false);
  protected readonly erroBusca = signal<ErroApi | null>(null);
  protected readonly resultados = signal<Ponto[] | null>(null);
  protected readonly ultimaBusca = signal('');

  constructor() {
    firstValueFrom(this.api.status())
      .then((s) => this.status.set(s))
      .catch(() => this.statusFalhou.set(true));
  }

  protected buscarEmDemo(): void {
    this.demoForcado.set(true);
    void this.buscar();
  }

  protected async buscar(): Promise<void> {
    const termo = this.texto.trim();
    if (termo.length < 2) {
      this.erroCampo.set('Digite pelo menos 2 letras ou números para buscar.');
      this.resultados.set(null);
      return;
    }
    this.erroCampo.set('');
    this.erroBusca.set(null);
    this.buscando.set(true);
    this.ultimaBusca.set(termo);
    const modo: Modo = this.demo() ? 'demo' : 'auto';
    try {
      const r = await firstValueFrom(this.api.buscarPontos(termo, modo));
      this.resultados.set(r.pontos);
    } catch (e) {
      this.resultados.set(null);
      this.erroBusca.set(e instanceof ErroApi ? e : new ErroApi(-1, 'Algo deu errado. Tente de novo.'));
    } finally {
      this.buscando.set(false);
    }
  }
}
