import { DOCUMENT } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { PreferencesService } from './core/preferences.service';

interface ItemMenu {
  rota: string;
  texto: string;
  icone: string;
}

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <a class="pular" href="#conteudo" (click)="irParaConteudo($event)">Pular para o conteúdo</a>

    <header class="topo">
      <div class="topo__interno">
        <a class="marca" routerLink="/" aria-label="Ponto Falante, ir para o início">
          <span class="marca__icone" aria-hidden="true">🚌</span>
          <span class="marca__nome">Ponto Falante</span>
        </a>
        <nav class="menu" aria-label="Principal">
          <ul>
            @for (item of itens; track item.rota) {
              <li>
                <a
                  [routerLink]="item.rota"
                  routerLinkActive="ativo"
                  [routerLinkActiveOptions]="{ exact: item.rota === '/' }"
                  #rla="routerLinkActive"
                  [attr.aria-current]="rla.isActive ? 'page' : null"
                >
                  <span class="menu__icone" aria-hidden="true">{{ item.icone }}</span>
                  <span class="menu__texto">{{ item.texto }}</span>
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
      <p>Ponto Falante · projeto acadêmico FIAP · as previsões são estimativas da SPTrans.</p>
      <p><a routerLink="/sobre">Sobre e privacidade</a></p>
    </footer>
  `,
})
export class App {
  private readonly router = inject(Router);
  private readonly doc = inject(DOCUMENT);

  protected readonly itens: ItemMenu[] = [
    { rota: '/', texto: 'Início', icone: '🏠' },
    { rota: '/assistente', texto: 'Assistente', icone: '💬' },
    { rota: '/boletim', texto: 'Boletim', icone: '📋' },
    { rota: '/acessibilidade', texto: 'Ajustes', icone: '⚙️' },
    { rota: '/sobre', texto: 'Sobre', icone: 'ℹ️' },
  ];

  constructor() {
    inject(PreferencesService); // aplica as preferências salvas já na abertura
    let primeira = true;
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe(() => {
        if (primeira) {
          primeira = false;
          return;
        }
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
    el.focus();
    return true;
  }
}
