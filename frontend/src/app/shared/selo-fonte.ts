import { Component, input } from '@angular/core';
import { Fonte } from '../core/models';
import { Origem } from './origem';

/** Origem dos dados de transporte: SIMULADO nunca aparece como dado da SPTrans. */
@Component({
  selector: 'pf-selo-fonte',
  imports: [Origem],
  template: `<pf-origem [tipo]="fonte() === 'SIMULADO' ? 'simulado' : 'real'" [forte]="forte()" />`,
})
export class SeloFonte {
  readonly fonte = input.required<Fonte>();
  readonly forte = input(false);
}
