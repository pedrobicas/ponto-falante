import { Component, computed, input } from '@angular/core';

/** Conjunto pequeno e coerente de ícones de traço (24x24). Sempre decorativos: o texto vizinho diz o que é. */
const ICONES = {
  casa: ['M3 11.5 12 4l9 7.5', 'M5.5 10v10h13V10', 'M10 20v-5.5h4V20'],
  onibus: ['M6 3.5h12a2 2 0 0 1 2 2V17a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17V5.5a2 2 0 0 1 2-2z', 'M4 11h16', 'M7 18.5v2', 'M17 18.5v2', 'M7.5 14.8h.01', 'M16.5 14.8h.01'],
  conversa: ['M21 11.5a8 8 0 0 1-11.7 7.1L4 20l1.2-4.5A8 8 0 1 1 21 11.5z', 'M8.5 10.5h7', 'M8.5 14h4'],
  boletim: ['M9 4h6v3H9z', 'M7 5.5H5v15h14v-15h-2', 'M8.5 12h7', 'M8.5 16h4.5'],
  ajustes: ['M4 7h9', 'M17 7h3', 'M4 17h3', 'M11 17h9', 'M15 4.5v5', 'M9 14.5v5'],
  info: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 11v5.5', 'M12 7.8h.01'],
  volume: ['M4 9.5v5h4l5 4v-13l-5 4z', 'M16.5 9a4.5 4.5 0 0 1 0 6', 'M19 6.5a8 8 0 0 1 0 11'],
  microfone: ['M12 3.5a3 3 0 0 0-3 3V12a3 3 0 0 0 6 0V6.5a3 3 0 0 0-3-3z', 'M5.5 11a6.5 6.5 0 0 0 13 0', 'M12 17.5v3'],
  relogio: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 7.5V12l3 2'],
  certo: ['M5 12.5l4.5 4.5L19 7'],
  'certo-circulo': ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M8 12.5l2.8 2.8L16 9.5'],
  'erro-circulo': ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M9 9l6 6', 'M15 9l-6 6'],
  alerta: ['M12 3.5 21.5 20h-19z', 'M12 10v4.5', 'M12 17.2h.01'],
  vazio: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M8.5 12h7'],
  acessivel: ['M10 4.2a1.3 1.3 0 1 0 0 .01', 'M10 8v7h5l3 5', 'M10 11.5h5', 'M7.2 12.8a5 5 0 1 0 7.3 6.2'],
  busca: ['M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z', 'M20 20l-4.4-4.4'],
  'seta-direita': ['M5 12h14', 'M13 6l6 6-6 6'],
  'seta-esquerda': ['M19 12H5', 'M11 6l-6 6 6 6'],
  enviar: ['M4 11.5 20 4l-5.5 16-3-6.5z', 'M11.5 13.5 20 4'],
  atualizar: ['M19.5 10.5A7.5 7.5 0 0 0 6 7L4.5 8.5', 'M4.5 4v4.5H9', 'M4.5 13.5A7.5 7.5 0 0 0 18 17l1.5-1.5', 'M19.5 20v-4.5H15'],
  ponto: ['M12 21s7-6 7-11.2a7 7 0 1 0-14 0C5 15 12 21 12 21z', 'M12 12.3a2.4 2.4 0 1 0 0-4.8 2.4 2.4 0 0 0 0 4.8z'],
  documento: ['M7 3.5h7.5L19 8v12.5H7z', 'M14.5 3.5V8H19', 'M10 13h6', 'M10 16.5h6'],
  frasco: ['M9.5 3.5h5', 'M10.5 3.5v5.8L5.7 17.5A2 2 0 0 0 7.4 20.5h9.2a2 2 0 0 0 1.7-3L13.5 9.3V3.5', 'M8 14.5h8'],
  lua: ['M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z'],
  escudo: ['M12 3.5l7.5 2.8v5.4c0 4.6-3.2 7.7-7.5 8.8-4.3-1.1-7.5-4.2-7.5-8.8V6.3z', 'M9 12l2.2 2.2L15.2 10'],
  parar: ['M7.5 7.5h9v9h-9z'],
  brilho: ['M12 3.5l1.8 5.2 5.2 1.8-5.2 1.8L12 17.5l-1.8-5.2L5 10.5l5.2-1.8z', 'M18.5 16.5v3.5', 'M16.8 18.2h3.4'],
  pessoas: ['M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', 'M3.5 19.5a5.5 5.5 0 0 1 11 0', 'M16 5.3a3 3 0 0 1 0 5.4', 'M17.5 14.2a5.5 5.5 0 0 1 3 5.3'],
  letras: ['M3.5 19 8 6l4.5 13', 'M5 15h6', 'M14.5 19l3-8 3 8', 'M15.6 16.5h3.8'],
  estrela: ['M12 3.8l2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.8l-5.1 2.7 1-5.7-4.1-4 5.7-.8z'],
  fechar: ['M6 6l12 12', 'M18 6 6 18'],
  chevron: ['M9.5 6l6 6-6 6'],
  troca: ['M5 9h14', 'M15 5l4 4-4 4', 'M19 15H5', 'M9 11l-4 4 4 4'],
  paleta: ['M12 3.5a8.5 8.5 0 1 0 0 17c1.4 0 2-.9 2-1.8 0-1.2-1-1.6-1-2.7 0-1 .8-1.7 1.8-1.7H17a3.5 3.5 0 0 0 3.5-3.5A8 8 0 0 0 12 3.5z', 'M7.8 11h.01', 'M10 7.6h.01', 'M14.2 7.6h.01'],
} as const;

export type NomeIcone = keyof typeof ICONES;

@Component({
  selector: 'pf-icone',
  template: `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
         stroke-linejoin="round" aria-hidden="true" focusable="false">
      @for (d of caminhos(); track $index) {
        <path [attr.d]="d" />
      }
    </svg>
  `,
  host: { class: 'icone', 'aria-hidden': 'true' },
})
export class Icone {
  readonly nome = input.required<NomeIcone>();
  protected readonly caminhos = computed<readonly string[]>(() => ICONES[this.nome()] ?? ICONES.info);
}
