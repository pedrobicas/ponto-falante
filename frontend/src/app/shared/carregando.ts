import { Component, input } from '@angular/core';

@Component({
  selector: 'pf-carregando',
  template: `
    <p class="carregando" role="status">
      <span class="carregando__roda" aria-hidden="true"></span>
      <span>{{ texto() }}</span>
    </p>
  `,
})
export class Carregando {
  readonly texto = input('Carregando…');
}
