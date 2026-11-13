import { Component, computed, input } from '@angular/core';

/** Carregamento acessível: frase em role=status + linhas-fantasma decorativas (estáticas com movimento reduzido). */
@Component({
  selector: 'pf-carregando',
  template: `
    <div class="carregando" [class.carregando--escuro]="escuro()">
      <p class="carregando__texto" role="status">
        <span class="carregando__trilho" aria-hidden="true"><i></i></span>
        <span>{{ texto() }}</span>
      </p>
      @if (linhas() > 0) {
        <ul class="fantasmas" aria-hidden="true">
          @for (i of contagem(); track i) {
            <li class="fantasma"><span class="fantasma__a"></span><span class="fantasma__b"></span><span class="fantasma__c"></span></li>
          }
        </ul>
      }
    </div>
  `,
})
export class Carregando {
  readonly texto = input('Carregando…');
  readonly linhas = input(0);
  readonly escuro = input(false);
  protected readonly contagem = computed(() => Array.from({ length: this.linhas() }, (_, i) => i));
}
