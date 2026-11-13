import { Component, input } from '@angular/core';

/** Código da linha no estilo do letreiro eletrônico do ônibus (âmbar sobre preto). */
@Component({
  selector: 'pf-letreiro',
  template: `<span class="letreiro" [class.letreiro--grande]="grande()"><span class="vo">Linha </span>{{ codigo() }}</span>`,
})
export class Letreiro {
  readonly codigo = input.required<string>();
  readonly grande = input(false);
}
