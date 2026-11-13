import { Injectable, signal } from '@angular/core';
import { gravarJson, lerJson } from './storage';

const CHAVE = 'pf.buscas';
const MAXIMO = 5;

/** Termos buscados recentemente, usados como sugestões. Ficam só neste aparelho. */
@Injectable({ providedIn: 'root' })
export class BuscasRecentesService {
  private readonly _lista = signal<string[]>(this.carregar());
  readonly lista = this._lista.asReadonly();

  adicionar(termo: string): void {
    const t = termo.trim().slice(0, 80);
    if (t.length < 2) return;
    const nova = [t, ...this._lista().filter((x) => x.toLowerCase() !== t.toLowerCase())].slice(0, MAXIMO);
    this._lista.set(nova);
    gravarJson(CHAVE, nova);
  }

  limpar(): void {
    this._lista.set([]);
    gravarJson(CHAVE, []);
  }

  private carregar(): string[] {
    const bruto = lerJson<unknown>(CHAVE);
    return Array.isArray(bruto) ? bruto.filter((x): x is string => typeof x === 'string').slice(0, MAXIMO) : [];
  }
}
