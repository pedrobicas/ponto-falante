import { Injectable, signal } from '@angular/core';
import { gravarJson, lerJson } from './storage';

export interface PontoRecente {
  codigo: number;
  nome: string;
}

const CHAVE = 'pf.recentes';
const MAXIMO = 5;

@Injectable({ providedIn: 'root' })
export class RecentesService {
  private readonly _lista = signal<PontoRecente[]>(this.carregar());
  readonly lista = this._lista.asReadonly();

  adicionar(ponto: PontoRecente): void {
    const nova = [ponto, ...this._lista().filter((p) => p.codigo !== ponto.codigo)].slice(0, MAXIMO);
    this._lista.set(nova);
    gravarJson(CHAVE, nova);
  }

  limpar(): void {
    this._lista.set([]);
    gravarJson(CHAVE, []);
  }

  private carregar(): PontoRecente[] {
    const bruto = lerJson<unknown>(CHAVE);
    if (!Array.isArray(bruto)) return [];
    return bruto
      .filter((p): p is PontoRecente => !!p && typeof p.codigo === 'number' && typeof p.nome === 'string')
      .slice(0, MAXIMO);
  }
}
