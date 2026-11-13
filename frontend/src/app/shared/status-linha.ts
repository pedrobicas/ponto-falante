import { Component, computed, input } from '@angular/core';
import { StatusLinha } from '../core/models';
import { NomeIcone } from './icone';
import { Selo, TomSelo } from './selo';

const MAPA: Record<StatusLinha, { texto: string; icone: NomeIcone; tom: TomSelo }> = {
  CRITICA: { texto: 'Atraso forte', icone: 'erro-circulo', tom: 'critico' },
  ATENCAO: { texto: 'Atenção', icone: 'alerta', tom: 'aviso' },
  OK: { texto: 'Normal', icone: 'certo-circulo', tom: 'ok' },
  SEM_DADOS: { texto: 'Sem dados', icone: 'vazio', tom: 'neutro' },
};

/** Estado de uma linha: forma do ícone + palavra + cor. */
@Component({
  selector: 'pf-status-linha',
  imports: [Selo],
  template: `<pf-selo [tom]="info().tom" [icone]="info().icone">{{ rotulo() || info().texto }}</pf-selo>`,
})
export class StatusLinhaPill {
  readonly status = input.required<StatusLinha>();
  readonly rotulo = input('');
  protected readonly info = computed(() => MAPA[this.status()] ?? MAPA.SEM_DADOS);
}
