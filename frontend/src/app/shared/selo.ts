import { Component, input } from '@angular/core';

export type TomSelo = 'info' | 'ok' | 'aviso' | 'critico' | 'neutro';

/** Selo com ícone + texto (nunca depende só de cor). */
@Component({
  selector: 'pf-selo',
  template: `
    <span class="selo selo--{{ tom() }}">
      <span class="selo__icone" aria-hidden="true">{{ icone() }}</span>
      <span><ng-content /></span>
    </span>
  `,
})
export class Selo {
  readonly tom = input<TomSelo>('info');
  readonly icone = input<string>('ℹ');
}
