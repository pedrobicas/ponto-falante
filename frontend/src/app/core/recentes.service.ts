import { Injectable, signal } from '@angular/core';
import { gravarJson, lerJson } from './storage';
import { Modo } from './models';

export interface PontoRecente {
  codigo: number;
  nome: string;
  /** Ausente em dados antigos: mantém o comportamento automático existente. */
  modo?: Modo;
}

export function chavePonto(ponto: PontoRecente): string {
  return `${ponto.modo === 'demo' ? 'demo' : 'auto'}:${ponto.codigo}`;
}

/** Preserva registros antigos e normaliza apenas campos conhecidos. */
export function lerPontosSalvos(chave: string): PontoRecente[] {
  const bruto = lerJson<unknown>(chave);
  if (!Array.isArray(bruto)) return [];
  const vistos = new Set<string>();
  return bruto.flatMap((p) => {
    if (!p || !Number.isSafeInteger(p.codigo) || p.codigo < 0 || typeof p.nome !== 'string') return [];
    const ponto: PontoRecente = { codigo: p.codigo, nome: p.nome, modo: p.modo === 'demo' ? 'demo' : 'auto' };
    const id = chavePonto(ponto);
    if (vistos.has(id)) return [];
    vistos.add(id);
    return [ponto];
  });
}

const CHAVE = 'pf.recentes';
const MAXIMO = 5;

@Injectable({ providedIn: 'root' })
export class RecentesService {
  private readonly _lista = signal<PontoRecente[]>(this.carregar());
  readonly lista = this._lista.asReadonly();

  adicionar(ponto: PontoRecente): void {
    const novo = { ...ponto, modo: ponto.modo ?? 'auto' };
    const nova = [novo, ...this._lista().filter((p) => chavePonto(p) !== chavePonto(novo))].slice(0, MAXIMO);
    this._lista.set(nova);
    gravarJson(CHAVE, nova);
  }

  limpar(): void {
    this._lista.set([]);
    gravarJson(CHAVE, []);
  }

  private carregar(): PontoRecente[] {
    return lerPontosSalvos(CHAVE).slice(0, MAXIMO);
  }
}
