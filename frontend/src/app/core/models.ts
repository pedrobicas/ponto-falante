/** Modelos tipados a partir de contratos/openapi-mvp.yaml e openapi-integracao.yaml. */

export type Fonte = 'OLHO_VIVO' | 'SIMULADO';
export type Modo = 'auto' | 'demo';

export interface Status {
  versao?: string;
  sptrans: 'REAL' | 'DEMO' | 'INDISPONIVEL';
  assistente: 'DISPONIVEL' | 'INDISPONIVEL';
  ultimo_boletim?: string | null;
  horario_servidor?: string;
}

export interface Ponto {
  codigo: number;
  nome: string;
  endereco?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  fonte: Fonte;
}

export interface BuscaPontos {
  fonte: Fonte;
  pontos: Ponto[];
}

export interface OnibusPrevisto {
  letreiro: string;
  destino: string;
  sentido?: number;
  previsto_em: string;
  minutos: number;
  acessivel: boolean;
  veiculo?: string;
}

export interface PrevisoesPonto {
  ponto: Ponto;
  fonte: Fonte;
  tipo: 'PREVISAO';
  horario_referencia?: string;
  consultado_em: string;
  onibus: OnibusPrevisto[];
  frase_falada: string;
}

export interface PerguntaChat {
  pergunta: string;
}

export interface FonteResposta {
  documento: string;
  trecho_id: string;
}

export interface RespostaChat {
  resposta: string;
  fontes: FonteResposta[];
  confianca: 'alta' | 'media' | 'baixa';
  nao_consta: boolean;
  disponivel: boolean;
  latencia_ms?: number;
}

export type StatusLinha = 'CRITICA' | 'ATENCAO' | 'OK' | 'SEM_DADOS';

export interface LinhaBoletim {
  linha: string;
  status: StatusLinha;
  rotulo?: string;
  atraso_medio_min?: number | null;
  intervalo_max_min?: number | null;
  passagens?: number;
  acessiveis_pct?: number | null;
  fontes?: string[];
  motivo?: string;
  frase: string;
}

export interface Boletim {
  data_referencia: string;
  gerado_em: string;
  desatualizado: boolean;
  motivo_desatualizado?: string | null;
  dados_simulados?: boolean;
  rede?: string | null;
  linhas: LinhaBoletim[];
  resumo_falado: string;
  avisos?: string[];
  recebido_em?: string;
  /** Pode existir no JSON do robô, mas NUNCA é usado com [innerHTML]. */
  html?: string;
}

export interface BoletimResumo {
  data_referencia: string;
  desatualizado: boolean;
  dados_simulados?: boolean;
  criticas: number;
  atencao: number;
  recebido_em?: string;
}

/** Erro já traduzido para uma frase simples (ver erro.interceptor.ts). */
export class ErroApi extends Error {
  constructor(
    readonly status: number,
    mensagem: string,
    readonly codigo?: string,
  ) {
    super(mensagem);
    this.name = 'ErroApi';
  }
}
