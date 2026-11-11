import { Component, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ErroApi, Modo, Ponto, Status } from '../../core/models';
import { RecentesService } from '../../core/recentes.service';
import { Carregando } from '../../shared/carregando';
import { MensagemErro } from '../../shared/mensagem-erro';
import { Selo } from '../../shared/selo';

@Component({
  selector: 'pf-inicio',
  imports: [FormsModule, RouterLink, Carregando, MensagemErro, Selo],
  template: `
    <h1>Qual ônibus você espera?</h1>
    <p class="lead">Digite o nome, a rua ou o número do ponto para ver os próximos ônibus previstos.</p>

    <section class="faixa" aria-label="Estado dos serviços">
      @if (demo() || status()?.sptrans === 'DEMO') {
        <pf-selo tom="aviso" icone="⚠">Modo demonstração: dados simulados</pf-selo>
      } @else if (status()?.sptrans === 'REAL') {
        <pf-selo tom="ok" icone="✔">Dados em tempo real da SPTrans</pf-selo>
      } @else if (status()?.sptrans === 'INDISPONIVEL') {
        <pf-selo tom="critico" icone="✖">SPTrans fora do ar agora</pf-selo>
      } @else if (statusFalhou()) {
        <pf-selo tom="neutro" icone="○">Não foi possível verificar os serviços</pf-selo>
      } @else {
        <pf-selo tom="neutro" icone="○">Verificando os serviços…</pf-selo>
      }
      @if (status(); as s) {
        @if (s.assistente === 'DISPONIVEL') {
          <pf-selo tom="ok" icone="✔">Assistente ligado</pf-selo>
        } @else {
          <pf-selo tom="neutro" icone="○">Assistente desligado agora</pf-selo>
        }
      }
    </section>

    <form class="cartao" (ngSubmit)="buscar()" novalidate>
      <label for="busca" class="rotulo">Nome, rua ou código do ponto</label>
      <p id="busca-ajuda" class="ajuda">Exemplo: Avenida Paulista, ou 700001234.</p>
      <div class="linha-form">
        <input
          id="busca"
          name="busca"
          type="search"
          autocomplete="off"
          maxlength="80"
          [(ngModel)]="texto"
          [attr.aria-invalid]="erroCampo() ? 'true' : null"
          [attr.aria-describedby]="erroCampo() ? 'busca-erro busca-ajuda' : 'busca-ajuda'"
        />
        <button type="submit" class="botao botao--primario" [disabled]="buscando()">Buscar ponto</button>
      </div>
      @if (erroCampo()) {
        <p id="busca-erro" class="erro-campo"><span aria-hidden="true">✖</span> {{ erroCampo() }}</p>
      }
    </form>

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
          <ul class="lista-cartoes">
            @for (p of lista; track p.codigo) {
              <li>
                <a class="cartao cartao--link" [routerLink]="['/ponto', p.codigo]" [queryParams]="qpModo()">
                  <span class="cartao__titulo">{{ p.nome }}</span>
                  @if (p.endereco) {
                    <span class="cartao__sub">{{ p.endereco }}</span>
                  }
                  <span class="cartao__sub">Ponto {{ p.codigo }}</span>
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
        <ul class="lista-cartoes">
          @for (p of recentes.lista(); track p.codigo) {
            <li>
              <a class="cartao cartao--link" [routerLink]="['/ponto', p.codigo]" [queryParams]="qpModo()">
                <span class="cartao__titulo">{{ p.nome }}</span>
                <span class="cartao__sub">Ponto {{ p.codigo }}</span>
              </a>
            </li>
          }
        </ul>
        <button type="button" class="botao" (click)="recentes.limpar()">Limpar pontos recentes</button>
      </section>
    }
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
