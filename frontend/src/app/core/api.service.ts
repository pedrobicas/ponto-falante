import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  BuscaLinhas,
  BuscaPontos,
  Boletim,
  BoletimResumo,
  Itinerario,
  Modo,
  PrevisoesPonto,
  RespostaChat,
  Status,
} from './models';

/** Único ponto de contato com a API (mesma origem, URLs relativas sob /api). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  status(): Observable<Status> {
    return this.http.get<Status>('/api/status');
  }

  buscarPontos(busca: string, modo?: Modo | null): Observable<BuscaPontos> {
    return this.http.get<BuscaPontos>('/api/pontos', { params: this.params({ busca }, modo) });
  }

  buscarLinhas(busca: string, modo?: Modo | null): Observable<BuscaLinhas> {
    return this.http.get<BuscaLinhas>('/api/linhas', { params: this.params({ busca }, modo) });
  }

  /** Localização vai no corpo (POST), nunca na URL. */
  pontosProximos(lat: number, lon: number, raio = 400): Observable<BuscaPontos> {
    return this.http.post<BuscaPontos>('/api/pontos/proximos', { lat, lon, raio });
  }

  itinerario(letreiro: string): Observable<Itinerario> {
    return this.http.get<Itinerario>(`/api/linhas/${encodeURIComponent(letreiro)}/paradas`);
  }

  previsoes(codigo: number | string, modo?: Modo | null): Observable<PrevisoesPonto> {
    return this.http.get<PrevisoesPonto>(`/api/pontos/${encodeURIComponent(String(codigo))}/previsoes`, {
      params: this.params({}, modo),
    });
  }

  perguntar(pergunta: string): Observable<RespostaChat> {
    return this.http.post<RespostaChat>('/api/chat', { pergunta });
  }

  boletim(): Observable<Boletim> {
    return this.http.get<Boletim>('/api/boletim');
  }

  boletimDaData(data: string): Observable<Boletim> {
    return this.http.get<Boletim>(`/api/boletim/${encodeURIComponent(data)}`);
  }

  boletins(): Observable<BoletimResumo[]> {
    return this.http.get<BoletimResumo[]>('/api/boletins');
  }

  private params(base: Record<string, string>, modo?: Modo | null): HttpParams {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(base)) p = p.set(k, v);
    if (modo === 'demo') p = p.set('modo', 'demo');
    return p;
  }
}
