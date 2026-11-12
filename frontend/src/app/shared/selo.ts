import { Component, input } from '@angular/core';
import { Icone, NomeIcone } from './icone';

export type TomSelo = 'info' | 'ok' | 'aviso' | 'critico' | 'neutro';

/** Selo com ícone + texto (nunca depende só de cor). */
@Component({
  selector: 'pf-selo',
  imports: [Icone],
  template: `
    <span class="selo selo--{{ tom() }}">
      <pf-icone [nome]="icone()" />
      <span><ng-content /></span>
    </span>
  `,
})
export class Selo {
  readonly tom = input<TomSelo>('info');
  readonly icone = input<NomeIcone>('info');
}
