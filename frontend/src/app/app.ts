import { DOCUMENT } from '@angular/common';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { PreferencesService } from './core/preferences.service';
import { StatusService } from './core/status.service';
import { Icone, type NomeIcone } from './shared/icone';

interface Estacao {
  rota: string;
  texto: string;
  exata: boolean;
  icone: NomeIcone;
}

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icone],
  template: `
    <a class="pular" href="#conteudo" (click)="irParaConteudo($event)">Pular para o conteúdo</a>

    <header class="topo">
      <div class="topo__interno">
        <a class="marca" routerLink="/" [queryParams]="modoNavegacao()" aria-label="Ponto Falante, página inicial">
          <svg class="marca__simbolo" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
            <circle class="marca__ponto" cx="13" cy="20" r="8.5" />
            <circle class="marca__miolo" cx="13" cy="20" r="3.4" />
            <path class="marca__onda" d="M25.5 13.5a9.5 9.5 0 0 1 0 13" />
            <path class="marca__onda marca__onda--2" d="M31 8.5a16.5 16.5 0 0 1 0 23" />
          </svg>
          <span class="marca__nome" aria-hidden="true">ponto<span class="marca__ponto-final">.</span><small>falante</small></span>
        </a>

        <span class="topo__edicao" aria-hidden="true">São Paulo</span>

        @if (status.demo() || modoNavegacao()) {
          <a class="topo__simulado" routerLink="/sobre" fragment="dados">
            <span class="hachura" aria-hidden="true"></span>
            <span>SIMULADO</span><span class="vo">: modo demonstração, os horários não são ônibus reais. Saiba mais.</span>
          </a>
        }

        <nav class="trajeto" aria-label="Principal">
          <ul class="trajeto__lista">
            @for (e of estacoes; track e.rota) {
              <li class="trajeto__item">
                <a
                  class="estacao"
                  [routerLink]="e.rota"
                  [queryParams]="modoNavegacao()"
                  routerLinkActive="estacao--rota"
                  [routerLinkActiveOptions]="{ exact: e.exata }"
                  [class.estacao--atual]="rla.isActive || (e.rota === '/' && buscaAtiva())"
                  #rla="routerLinkActive"
                  [attr.aria-current]="(rla.isActive || (e.rota === '/' && buscaAtiva())) ? 'page' : null"
                >
                  <pf-icone [nome]="e.icone" />
                  <span class="estacao__nome">{{ e.texto }}</span>
                </a>
              </li>
            }
          </ul>
        </nav>
      </div>
    </header>

    <main id="conteudo" class="principal">
      <router-outlet />
    </main>

    <footer class="rodape">
      <div class="rodape__interno">
        <p class="rodape__marca">ponto<span aria-hidden="true">.</span> falante</p>
        <p>Mobilidade acessível em São Paulo. Projeto acadêmico · FIAP 2026.</p>
        <p><a routerLink="/sobre">Sobre, dados e privacidade</a></p>
      </div>
    </footer>
  `,
})
export class App {
  private readonly router = inject(Router);
  private readonly doc = inject(DOCUMENT);
  protected readonly status = inject(StatusService);
  protected readonly buscaAtiva = signal(false);
  protected readonly modoNavegacao = signal<{ modo: string } | null>(null);

  protected readonly estacoes: Estacao[] = [
    { rota: '/', texto: 'Buscar', exata: true, icone: 'busca' },
    { rota: '/favoritos', texto: 'Favoritos', exata: false, icone: 'estrela' },
    { rota: '/assistente', texto: 'Assistente', exata: false, icone: 'conversa' },
    { rota: '/boletim', texto: 'Boletim', exata: false, icone: 'boletim' },
    { rota: '/acessibilidade', texto: 'Ajustes', exata: false, icone: 'ajustes' },
  ];

  constructor() {
    inject(PreferencesService); // aplica as preferências salvas já na abertura
    void this.status.carregar();
    let caminhoAnterior: string | null = null;
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((e) => {
        const caminho = e.urlAfterRedirects.split(/[?#]/)[0];
        this.modoNavegacao.set(this.router.parseUrl(e.urlAfterRedirects).queryParams['modo'] === 'demo' ? { modo: 'demo' } : null);
        this.buscaAtiva.set(caminho === '/busca' || caminho.startsWith('/ponto/'));
        const anterior = caminhoAnterior;
        caminhoAnterior = caminho;
        // Primeira carga ou só a busca (query) mudou: o foco fica onde a pessoa está.
        if (anterior === null || anterior === caminho) return;
        // Espera a página renderizar e leva o foco para o título (h1).
        setTimeout(() => this.focarTitulo(), 50);
      });
  }

  protected irParaConteudo(evento: Event): void {
    evento.preventDefault();
    this.focarTitulo() || this.focar(this.doc.getElementById('conteudo'));
  }

  private focarTitulo(): boolean {
    return this.focar(this.doc.querySelector('main h1'));
  }

  private focar(el: Element | null): boolean {
    if (!(el instanceof HTMLElement)) return false;
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
    el.focus({ preventScroll: false });
    return true;
  }
}
