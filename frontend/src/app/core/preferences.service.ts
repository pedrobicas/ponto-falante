import { DOCUMENT } from '@angular/common';
import { Injectable, inject, signal } from '@angular/core';
import { gravarJson, lerJson } from './storage';

export type TamanhoFonte = 'normal' | 'grande' | 'muito-grande';
export type Tema = 'auto' | 'alto-escuro' | 'alto-claro';

export interface Preferencias {
  tamanhoFonte: TamanhoFonte;
  tema: Tema;
  velocidadeVoz: number;
  anunciarAuto: boolean;
  lerRespostaAuto: boolean;
  reduzirMovimento: boolean;
}

export const PADRAO: Preferencias = {
  tamanhoFonte: 'normal',
  tema: 'auto',
  velocidadeVoz: 0.9,
  anunciarAuto: false,
  lerRespostaAuto: false,
  reduzirMovimento: false,
};

const CHAVE = 'pf.preferencias';
const ESCALAS: Record<TamanhoFonte, string> = { normal: '1', grande: '1.2', 'muito-grande': '1.45' };

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
      tema: ['auto', 'alto-escuro', 'alto-claro'].includes(p.tema) ? p.tema : PADRAO.tema,
      velocidadeVoz: Number.isFinite(v) ? Math.min(1.4, Math.max(0.5, v)) : PADRAO.velocidadeVoz,
      anunciarAuto: !!p.anunciarAuto,
      lerRespostaAuto: !!p.lerRespostaAuto,
      reduzirMovimento: !!p.reduzirMovimento,
    };
  }

  /** Aplica as preferências como atributos/variáveis CSS em :root. */
  private aplicar(p: Preferencias): void {
    const raiz = this.doc.documentElement;
    raiz.style.setProperty('--escala-fonte', ESCALAS[p.tamanhoFonte]);
    if (p.tema === 'auto') raiz.removeAttribute('data-tema');
    else raiz.setAttribute('data-tema', p.tema);
    if (p.reduzirMovimento) raiz.setAttribute('data-movimento', 'reduzido');
    else raiz.removeAttribute('data-movimento');
  }
}
