import { Component, booleanAttribute, computed, input } from '@angular/core';

export type TipoOrigem =
  | 'real'
  | 'tempo-real'
  | 'simulado'
  | 'estimado'
  | 'indisponivel'
  | 'base-oficial'
  | 'verificando';

const MAPA: Record<TipoOrigem, { rotulo: string; descricao: string }> = {
  real: { rotulo: 'Dados da SPTrans', descricao: 'previsões em tempo real da SPTrans' },
  'tempo-real': { rotulo: 'Tempo real · SPTrans', descricao: 'resposta montada com as previsões da SPTrans' },
  simulado: { rotulo: 'SIMULADO', descricao: 'dados de demonstração, não são ônibus reais' },
  estimado: { rotulo: 'Estimado', descricao: 'valor calculado a partir das previsões consultadas, sem confirmar chegada ou atraso' },
  indisponivel: { rotulo: 'Indisponível', descricao: 'sem dados no momento' },
  'base-oficial': { rotulo: 'Base oficial', descricao: 'resposta baseada em documentos oficiais' },
  verificando: { rotulo: 'Verificando…', descricao: '' },
};

/**
 * Selo de origem dos dados. Cada tipo tem forma própria (ponto cheio, hachura, meio círculo, contorno tracejado),
 * então nunca depende só da cor. O texto oculto completa a frase para leitores de tela.
 */
@Component({
  selector: 'pf-origem',
  template: `
    <span class="origem origem--{{ tipo() }}" [class.origem--forte]="forte()">
      <span class="origem__marca" aria-hidden="true"></span>
      <span class="origem__rotulo">{{ rotulo() || info().rotulo }}</span>
      @if (info().descricao && !semDescricao()) {
        <span class="vo">: {{ info().descricao }}</span>
      }
    </span>
  `,
})
export class Origem {
  readonly tipo = input.required<TipoOrigem>();
  readonly rotulo = input<string>('');
  readonly forte = input(false, { transform: booleanAttribute });
  readonly semDescricao = input(false, { transform: booleanAttribute });
  protected readonly info = computed(() => MAPA[this.tipo()] ?? MAPA.indisponivel);
}
