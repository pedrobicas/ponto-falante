import { Component, ElementRef, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FavoritosService } from '../../core/favoritos.service';
import { PontoRecente, chavePonto } from '../../core/recentes.service';
import { Icone } from '../../shared/icone';

@Component({
  selector: 'pf-favoritos',
  imports: [RouterLink, Icone],
  template: `
    <div class="pagina favoritos">
      <header class="cabecalho">
        <p class="sobretitulo">Sua rotina</p>
        <h1 tabindex="-1">Favoritos</h1>
        <p class="cabecalho__apoio">Seus pontos de sempre, a um toque.</p>
      </header>
      @if (favoritos.lista().length) {
        <ul class="paradas">
          @for (p of favoritos.lista(); track chave(p)) {
            <li class="parada parada--salva">
              <a class="parada__link" [routerLink]="['/ponto', p.codigo]" [queryParams]="p.modo === 'demo' ? { modo: 'demo' } : null">
                <pf-icone nome="ponto" />
                <span class="parada__texto"><span class="parada__nome">{{ p.nome }}</span><span class="parada__meta">Ponto {{ p.codigo }}{{ p.modo === 'demo' ? ' · SIMULADO' : '' }}</span></span>
                <pf-icone nome="chevron" />
              </a>
              <button class="botao-icone" type="button" (click)="remover(p, $event)" [attr.aria-label]="'Remover ' + p.nome + (p.modo === 'demo' ? ' (simulado)' : '') + ' dos favoritos'"><pf-icone nome="fechar" /></button>
            </li>
          }
        </ul>
      } @else {
        <div class="vazio vazio--favoritos">
          <pf-icone nome="estrela" />
          <h2>Seu próximo caminho fica aqui</h2>
          <p>Salve um ponto na tela de previsões para encontrá-lo rapidamente.</p>
          <a class="botao botao--primario" routerLink="/" [queryParams]="modo() === 'demo' ? { modo: 'demo' } : null">Encontrar um ponto <pf-icone nome="seta-direita" /></a>
        </div>
      }
      <p class="ajuda favoritos__privacidade"><pf-icone nome="escudo" /> Salvos somente neste aparelho.</p>
      <p class="feedback" role="status">{{ aviso() }}</p>
    </div>
  `,
})
export class Favoritos {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  protected readonly favoritos = inject(FavoritosService);
  readonly modo = input<string | undefined>();
  protected readonly aviso = signal('');
  protected readonly chave = chavePonto;
  protected remover(p: PontoRecente, event: Event): void {
    const item = (event.currentTarget as HTMLElement).closest('li');
    const vizinho = item?.nextElementSibling ?? item?.previousElementSibling;
    const destino = vizinho?.querySelector<HTMLElement>('a') ?? this.host.nativeElement.querySelector<HTMLElement>('h1');
    destino?.focus();
    this.favoritos.alternar(p);
    this.aviso.set(p.nome + ' removido dos favoritos.');
  }
}
