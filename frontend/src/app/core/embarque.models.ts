/** Contratos do Embarque Assistido (contratos/openapi-mvp.yaml, seção Embarque Assistido). */
import { Fonte, OnibusPrevisto } from './models';

export interface LinhaEscolhida {
  letreiro: string;
  /** 1 ou 2 (cadastro da SPTrans); ausente = qualquer sentido. */
  sentido?: number | null;
  destino?: string | null;
}

export interface TrajetoFavorito {
  id: number;
  ponto: number;
  ponto_nome: string;
  linha: string;
  sentido?: number | null;
  destino?: string | null;
  apelido?: string | null;
  simulado: boolean;
  criado_em?: string;
}

export interface NovoTrajeto {
  ponto: number;
  ponto_nome: string;
  linha: string;
  sentido?: number | null;
  destino?: string | null;
  apelido?: string | null;
  simulado?: boolean;
}

export type Desfecho = 'EMBARQUEI' | 'DESISTI' | 'SUBSTITUIDA' | 'EXPIRADA';

export interface SessaoEmbarque {
  id: string;
  ponto: number;
  ponto_nome: string;
  linhas: LinhaEscolhida[];
  simulado: boolean;
  iniciada_em: string;
  encerrada_em?: string | null;
  desfecho?: Desfecho | null;
}

export interface SituacaoEmbarque {
  sessao: SessaoEmbarque;
  fonte: Fonte;
  consultado_em: string;
  horario_referencia?: string | null;
  onibus: OnibusPrevisto[];
  proximo?: OnibusPrevisto | null;
  frase_falada: string;
  outras_linhas_previstas?: string[];
}

export interface LinhaNoPonto {
  letreiro: string;
  sentido: number;
  destino: string;
  nome_linha: string;
}

export interface LinhasDoPonto {
  fonte: Fonte;
  codigo: number;
  linhas: LinhaNoPonto[];
  aviso?: string | null;
}

export type ResultadoConferencia = 'CONFERE' | 'NUMERO_CONFERE' | 'NAO_CONFERE' | 'INCONCLUSIVO';

export interface ConferenciaLetreiro {
  resultado: ResultadoConferencia;
  linha_esperada: string;
  linha_lida?: string | null;
  confianca?: number | null;
  frase_falada: string;
  modelo: string;
  latencia_ms?: number | null;
}

export interface EstadoVisao {
  conectada: boolean;
  mensagem: string;
}

/** Ponto escolhido pela pessoa (nome e endereço vêm da busca, do GPS ou das previsões). */
export interface PontoEscolhido {
  codigo: number;
  nome: string;
  endereco?: string | null;
  distancia_metros?: number | null;
  linhas?: string[] | null;
}
