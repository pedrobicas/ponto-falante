import { DOCUMENT } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { PreferencesService } from './core/preferences.service';
import { Icone, NomeIcone } from './shared/icone';

interface ItemMenu {
  rota: string;
  texto: string;
  icone: NomeIcone;
}

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icone],
  template: `
    <a class="pular" href="#conteudo" (click)="irParaConteudo($event)">Pular para o conteúdo</a>

    <header class="topo">
      <div class="topo__interno">
        <a class="marca" routerLink="/" aria-label="Ponto Falante, ir para o início">
          <span class="marca__placa" aria-hidden="true"><pf-icone nome="onibus" /></span>
          <span class="marca__nome" aria-hidden="true">Ponto <strong>Falante</strong></span>
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
                  <pf-icone [nome]="item.icone" />
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
      <div class="rodape__interno">
        <p>Ponto Falante · projeto acadêmico FIAP. Quando os dados são reais, os horários são previsões da SPTrans.</p>
        <p><a routerLink="/sobre">Sobre e privacidade</a></p>
      </div>
    </footer>
  `,
})
export class App {
  private readonly router = inject(Router);
  private readonly doc = inject(DOCUMENT);

  protected readonly itens: ItemMenu[] = [
    { rota: '/', texto: 'Início', icone: 'casa' },
    { rota: '/assistente', texto: 'Assistente', icone: 'conversa' },
    { rota: '/boletim', texto: 'Boletim', icone: 'boletim' },
    { rota: '/acessibilidade', texto: 'Ajustes', icone: 'ajustes' },
    { rota: '/sobre', texto: 'Sobre', icone: 'info' },
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
