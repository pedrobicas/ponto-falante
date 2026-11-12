import { Component, input } from '@angular/core';
import { Fonte } from '../core/models';
import { Selo } from './selo';

/** Mostra de onde vêm os dados. SIMULADO sempre vira "Dados de demonstração". */
@Component({
  selector: 'pf-selo-fonte',
  imports: [Selo],
  template: `
    @if (fonte() === 'SIMULADO') {
      <pf-selo tom="aviso" icone="frasco">Dados de demonstração</pf-selo>
    } @else {
      <pf-selo tom="ok" icone="certo-circulo">Dados da SPTrans</pf-selo>
    }
  `,
})
export class SeloFonte {
  readonly fonte = input.required<Fonte>();
}
