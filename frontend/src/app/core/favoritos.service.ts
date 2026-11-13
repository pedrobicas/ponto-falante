import { Injectable, computed, signal } from '@angular/core';
import { gravarJson } from './storage';
import { Modo } from './models';
import { PontoRecente, chavePonto, lerPontosSalvos } from './recentes.service';

const CHAVE = 'pf.favoritos';

/** Pontos salvos pela pessoa. Ficam só neste aparelho. */
@Injectable({ providedIn: 'root' })
export class FavoritosService {
  private readonly _lista = signal<PontoRecente[]>(this.carregar());
  readonly lista = this._lista.asReadonly();
  private readonly codigos = computed(() => new Set(this._lista().map(chavePonto)));

  eFavorito(codigo: number, modo: Modo = 'auto'): boolean {
    return this.codigos().has(chavePonto({ codigo, nome: '', modo }));
  }

  alternar(ponto: PontoRecente): boolean {
    const ja = this.eFavorito(ponto.codigo, ponto.modo);
    const nova = ja
      ? this._lista().filter((p) => chavePonto(p) !== chavePonto(ponto))
      : [...this._lista(), { codigo: ponto.codigo, nome: ponto.nome, modo: ponto.modo ?? 'auto' }];
    this._lista.set(nova);
    gravarJson(CHAVE, nova);
    return !ja;
  }

  private carregar(): PontoRecente[] {
    return lerPontosSalvos(CHAVE);
  }
}
