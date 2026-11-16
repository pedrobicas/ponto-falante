import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { identificadorDoAparelho } from './dispositivo';
import {
  ConferenciaLetreiro,
  Desfecho,
  EstadoVisao,
  LinhaEscolhida,
  LinhasDoPonto,
  NovoTrajeto,
  SessaoEmbarque,
  SituacaoEmbarque,
  TrajetoFavorito,
} from './embarque.models';
import { Modo } from './models';

/** Chamadas do Embarque Assistido. Toda escrita leva o identificador aleatório do aparelho. */
@Injectable({ providedIn: 'root' })
export class EmbarqueApiService {
  private readonly http = inject(HttpClient);

  private get cabecalhos(): HttpHeaders {
    return new HttpHeaders({ 'X-PF-Dispositivo': identificadorDoAparelho() });
  }

  favoritos(): Observable<TrajetoFavorito[]> {
    return this.http.get<TrajetoFavorito[]>('/api/embarque/favoritos', { headers: this.cabecalhos });
  }

  salvarFavorito(t: NovoTrajeto): Observable<TrajetoFavorito> {
    return this.http.post<TrajetoFavorito>('/api/embarque/favoritos', t, { headers: this.cabecalhos });
  }

  renomearFavorito(id: number, apelido: string | null): Observable<TrajetoFavorito> {
    return this.http.patch<TrajetoFavorito>(`/api/embarque/favoritos/${id}`, { apelido }, { headers: this.cabecalhos });
  }

  removerFavorito(id: number): Observable<void> {
    return this.http.delete<void>(`/api/embarque/favoritos/${id}`, { headers: this.cabecalhos });
  }

  iniciar(ponto: number, pontoNome: string, linhas: LinhaEscolhida[], modo: Modo): Observable<SessaoEmbarque> {
    return this.http.post<SessaoEmbarque>(
      '/api/embarque/sessoes',
      { ponto, ponto_nome: pontoNome, linhas: linhas.map((l) => ({ letreiro: l.letreiro, sentido: l.sentido ?? null })), modo },
      { headers: this.cabecalhos },
    );
  }

  /** 204 (sem acompanhamento aberto) chega como null. */
  sessaoAtual(): Observable<SessaoEmbarque | null> {
    return this.http.get<SessaoEmbarque | null>('/api/embarque/sessoes/atual', { headers: this.cabecalhos });
  }

  situacao(id: string): Observable<SituacaoEmbarque> {
    return this.http.get<SituacaoEmbarque>(`/api/embarque/sessoes/${encodeURIComponent(id)}/situacao`, { headers: this.cabecalhos });
  }

  encerrar(id: string, desfecho: Extract<Desfecho, 'EMBARQUEI' | 'DESISTI'>): Observable<SessaoEmbarque> {
    return this.http.post<SessaoEmbarque>(`/api/embarque/sessoes/${encodeURIComponent(id)}/encerrar`, { desfecho }, { headers: this.cabecalhos });
  }

  apagarDados(): Observable<void> {
    return this.http.delete<void>('/api/embarque/dados', { headers: this.cabecalhos });
  }

  linhasDoPonto(codigo: number, modo: Modo): Observable<LinhasDoPonto> {
    let params = new HttpParams();
    if (modo === 'demo') params = params.set('modo', 'demo');
    return this.http.get<LinhasDoPonto>(`/api/pontos/${encodeURIComponent(String(codigo))}/linhas`, { params });
  }

  estadoVisao(): Observable<EstadoVisao> {
    return this.http.get<EstadoVisao>('/api/embarque/visao');
  }

  conferirLetreiro(imagem: Blob, linhaEsperada: string, sessao?: string | null): Observable<ConferenciaLetreiro> {
    const corpo = new FormData();
    corpo.append('imagem', imagem, 'letreiro.jpg');
    corpo.append('linha_esperada', linhaEsperada);
    if (sessao) corpo.append('sessao', sessao);
    return this.http.post<ConferenciaLetreiro>('/api/embarque/visao/conferir', corpo, { headers: this.cabecalhos });
  }
}
