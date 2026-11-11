import { Component, computed, input } from '@angular/core';
import { StatusLinha } from '../core/models';
import { Selo, TomSelo } from './selo';

const MAPA: Record<StatusLinha, { texto: string; icone: string; tom: TomSelo }> = {
  CRITICA: { texto: 'Atraso forte', icone: '✖', tom: 'critico' },
  ATENCAO: { texto: 'Atenção', icone: '⚠', tom: 'aviso' },
  OK: { texto: 'Normal', icone: '✔', tom: 'ok' },
  SEM_DADOS: { texto: 'Sem dados', icone: '○', tom: 'neutro' },
};

/** Estado de uma linha: forma do ícone + palavra + cor. */
@Component({
  selector: 'pf-status-linha',
  imports: [Selo],
  template: `<pf-selo [tom]="info().tom" [icone]="info().icone">{{ info().texto }}</pf-selo>`,
})
export class StatusLinhaPill {
  readonly status = input.required<StatusLinha>();
  protected readonly info = computed(() => MAPA[this.status()] ?? MAPA.SEM_DADOS);
}
