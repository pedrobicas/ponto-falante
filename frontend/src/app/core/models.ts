/** Modelos tipados a partir de contratos/openapi-mvp.yaml e openapi-integracao.yaml. */

/** OLHO_VIVO: tempo real. GTFS_SPTRANS: cadastro oficial de paradas e itinerários. SIMULADO: demonstração. */
export type Fonte = 'OLHO_VIVO' | 'GTFS_SPTRANS' | 'SIMULADO';
export type Modo = 'auto' | 'demo';

export interface Status {
  versao?: string;
  sptrans: 'REAL' | 'DEMO' | 'INDISPONIVEL';
  assistente: 'DISPONIVEL' | 'INDISPONIVEL';
  ultimo_boletim?: string | null;
  horario_servidor?: string;
  /** true quando o assistente responde horários em tempo real mesmo com a IA local fora do ar. */
  assistente_tempo_real?: boolean;
}

export interface Ponto {
  codigo: number;
  nome: string;
  endereco?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  fonte: Fonte;
  /** Letreiros que param no ponto, segundo o cadastro da SPTrans. */
  linhas?: string[] | null;
  /** Só em buscas por proximidade. */
  distancia_metros?: number | null;
}

export interface BuscaPontos {
  fonte: Fonte;
  pontos: Ponto[];
  /** Explicação curta: busca aproximada, código inexistente ou limite da fonte. */
  aviso?: string | null;
}

export interface SentidoLinha {
  letreiro: string;
  sentido: number;
  destino: string;
  nome_linha: string;
  paradas: Ponto[];
}

export interface Itinerario {
  fonte: Fonte;
  letreiro: string;
  sentidos: SentidoLinha[];
  aviso?: string | null;
}

export interface Linha {
  codigo?: number | null;
  letreiro: string;
  sentido?: number | null;
  terminal_principal?: string | null;
  terminal_secundario?: string | null;
  destino?: string | null;
  circular?: boolean;
}

export interface BuscaLinhas {
  fonte: Fonte;
  linhas: Linha[];
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
  url?: string | null;
}

export interface ContextoChat {
  ponto?: number | null;
  linha?: string | null;
  sentido?: number | null;
  pendencia?: string | null;
  tema?: string | null;
  publico?: string | null;
  idade?: number | null;
  veiculo_anterior?: string | null;
}

export interface AcaoChat { titulo: string; pergunta?: string | null; rota?: string | null; }

export interface RespostaChat {
  natureza_dados?: NaturezaDados | null;
  resposta: string;
  fontes: FonteResposta[];
  confianca: 'alta' | 'media' | 'baixa';
  nao_consta: boolean;
  disponivel: boolean;
  latencia_ms?: number;
  /** TEMPO_REAL (dados da SPTrans pelo backend), BASE_OFICIAL (IA local com fontes oficiais) ou INDISPONIVEL. */
  origem?: OrigemResposta | null;
  dados_simulados?: boolean;
  contexto?: ContextoChat | null;
  acoes?: AcaoChat[];
}

export type OrigemResposta = 'TEMPO_REAL' | 'CADASTRO' | 'BOLETIM' | 'BASE_OFICIAL' | 'INDISPONIVEL';

/** Origem efetiva: sem o campo, vale BASE_OFICIAL quando disponível e INDISPONIVEL quando não. */
export function origemDaResposta(r: Pick<RespostaChat, 'origem' | 'disponivel'>): OrigemResposta {
  if (r.origem === 'TEMPO_REAL' || r.origem === 'CADASTRO' || r.origem === 'BOLETIM' || r.origem === 'BASE_OFICIAL' || r.origem === 'INDISPONIVEL') return r.origem;
  return r.disponivel ? 'BASE_OFICIAL' : 'INDISPONIVEL';
}

export type StatusLinha = 'CRITICA' | 'ATENCAO' | 'OK' | 'SEM_DADOS';
export type NaturezaDados = 'ESTIMADO' | 'SIMULADO' | 'INDISPONIVEL';

export interface LinhaBoletim {
  classificacao?: NaturezaDados;
  espera_tipica_min?: number | null;
  maior_espera_prevista_min?: number | null;
  proximo_onibus_mediana_min?: number | null;
  amostras?: number;
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
  natureza_dados?: NaturezaDados;
  metodo?: string;
  ultima_atualizacao?: string;
  periodo_referencia?: { inicio?: string | null; fim?: string | null; fuso?: string };
  amostragem?: {
    consultas_validas?: number;
    consultas_esperadas?: number | null;
    cobertura_pct?: number | null;
    pontos_com_amostra?: string[];
    descricao?: string;
  };
  data_referencia: string;
  gerado_em: string;
  desatualizado: boolean;
  motivo_desatualizado?: string | null;
  dados_simulados?: boolean;
  fonte_dados?: Record<string, number> | null;
  estatisticas?: Record<string, number> | null;
  rede?: string | null;
  linhas: LinhaBoletim[];
  resumo_falado: string;
  avisos?: string[];
  recebido_em?: string;
  /** Pode existir no JSON do robô, mas NUNCA é usado com [innerHTML]. */
  html?: string;
}

export interface BoletimResumo {
  natureza_dados?: NaturezaDados;
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
