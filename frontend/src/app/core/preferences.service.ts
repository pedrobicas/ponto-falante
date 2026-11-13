import { DOCUMENT } from '@angular/common';
import { Injectable, inject, signal } from '@angular/core';
import { gravarJson, lerJson } from './storage';

export type TamanhoFonte = 'normal' | 'grande' | 'muito-grande' | 'maximo';
export type Tema = 'auto' | 'claro' | 'escuro' | 'alto-claro' | 'alto-escuro';

export interface Preferencias {
  tamanhoFonte: TamanhoFonte;
  tema: Tema;
  velocidadeVoz: number;
  /** voiceURI escolhida; vazio = primeira voz em português do aparelho. */
  voz: string;
  anunciarAuto: boolean;
  lerRespostaAuto: boolean;
  reduzirMovimento: boolean;
  /** Mais espaço entre letras, palavras e linhas (WCAG 1.4.12). */
  espacamento: boolean;
}

export const PADRAO: Preferencias = {
  tamanhoFonte: 'normal',
  tema: 'auto',
  velocidadeVoz: 0.9,
  voz: '',
  anunciarAuto: false,
  lerRespostaAuto: false,
  reduzirMovimento: false,
  espacamento: false,
};

const CHAVE = 'pf.preferencias';
export const ESCALAS: Record<TamanhoFonte, string> = {
  normal: '1',
  grande: '1.2',
  'muito-grande': '1.45',
  maximo: '1.75',
};
const TEMAS: Tema[] = ['auto', 'claro', 'escuro', 'alto-claro', 'alto-escuro'];

@Injectable({ providedIn: 'root' })
export class PreferencesService {
  private readonly doc = inject(DOCUMENT);
  private readonly _prefs = signal<Preferencias>(this.carregar());
  readonly prefs = this._prefs.asReadonly();

  constructor() {
    this.aplicar(this._prefs());
  }

  atualizar(parcial: Partial<Preferencias>): void {
    const novo = this.sanear({ ...this._prefs(), ...parcial });
    this._prefs.set(novo);
    gravarJson(CHAVE, novo);
    this.aplicar(novo);
  }

  restaurar(): void {
    this.atualizar({ ...PADRAO });
  }

  private carregar(): Preferencias {
    return this.sanear({ ...PADRAO, ...(lerJson<Partial<Preferencias>>(CHAVE) ?? {}) });
  }

  private sanear(p: Preferencias): Preferencias {
    const v = Number(p.velocidadeVoz);
    return {
      tamanhoFonte: p.tamanhoFonte in ESCALAS ? p.tamanhoFonte : PADRAO.tamanhoFonte,
      tema: TEMAS.includes(p.tema) ? p.tema : PADRAO.tema,
      velocidadeVoz: Number.isFinite(v) ? Math.min(1.4, Math.max(0.5, Math.round(v * 10) / 10)) : PADRAO.velocidadeVoz,
      voz: typeof p.voz === 'string' ? p.voz.slice(0, 200) : '',
      anunciarAuto: !!p.anunciarAuto,
      lerRespostaAuto: !!p.lerRespostaAuto,
      reduzirMovimento: !!p.reduzirMovimento,
      espacamento: !!p.espacamento,
    };
  }

  /** Aplica as preferências como atributos/variáveis CSS em :root. */
  private aplicar(p: Preferencias): void {
    const raiz = this.doc.documentElement;
    raiz.style.setProperty('--escala-fonte', ESCALAS[p.tamanhoFonte]);
    if (p.tema === 'auto') raiz.removeAttribute('data-tema');
    else raiz.setAttribute('data-tema', p.tema);
    this.marcar(raiz, 'data-movimento', p.reduzirMovimento ? 'reduzido' : null);
    this.marcar(raiz, 'data-espacamento', p.espacamento ? 'amplo' : null);
  }

  private marcar(el: HTMLElement, attr: string, valor: string | null): void {
    if (valor) el.setAttribute(attr, valor);
    else el.removeAttribute(attr);
  }
}
