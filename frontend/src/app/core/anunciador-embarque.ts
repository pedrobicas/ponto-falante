import { OnibusPrevisto } from './models';

/**
 * Decide QUANDO falar durante o acompanhamento. Regra de ouro: só fala quando algo importante mudou,
 * nunca repete a mesma frase e nunca inventa horário (usa só os minutos previstos pela SPTrans).
 *
 * Fala: ao começar; ao cruzar 10, 5 e 3 minutos; quando chega a 1 minuto ou menos ("chegando");
 * quando a previsão atrasa 3 minutos ou mais; quando o ônibus acompanhado some da previsão (pode ter passado);
 * quando deixa de haver previsão; depois de 2 falhas seguidas de atualização; e quando volta a atualizar.
 */
export const MARCOS_MINUTOS = [10, 5, 3] as const;
export const ATRASO_RELEVANTE_MIN = 3;
export const FALHAS_PARA_AVISAR = 2;

export type TipoAnuncio = 'inicio' | 'marco' | 'chegando' | 'atraso' | 'troca' | 'sem-previsao' | 'falha' | 'retomou';

export interface Anuncio {
  tipo: TipoAnuncio;
  texto: string;
  /** Chegando e "pode ter passado" interrompem o que estiver sendo falado e vibram o aparelho. */
  urgente: boolean;
}

export interface Leitura {
  onibus: OnibusPrevisto[];
  simulado: boolean;
}

function minutosFalados(m: number): string {
  if (m <= 0) return 'previsto para agora';
  return m === 1 ? 'em 1 minuto' : `em ${m} minutos`;
}

function chave(o: OnibusPrevisto): string {
  return `${o.letreiro}|${o.veiculo ?? ''}`;
}

function destino(o: OnibusPrevisto): string {
  return o.destino ? `, sentido ${o.destino}` : '';
}

export class AnunciadorEmbarque {
  private veiculo: string | null = null;
  private minutos: number | null = null;
  /** Menor marco já anunciado (ou já ultrapassado) para o veículo atual. */
  private marco = Number.POSITIVE_INFINITY;
  private chegandoAvisado = false;
  /** Minutos do último aviso falado para este veículo (base para detectar atraso). */
  private minutosAnunciados: number | null = null;
  private semPrevisao = false;
  private falhas = 0;
  private falhaAvisada = false;
  private iniciado = false;
  private ultimoTexto = '';

  /** Última frase falada (para "repetir"). */
  get ultimo(): string {
    return this.ultimoTexto;
  }

  reiniciar(): void {
    this.veiculo = null;
    this.minutos = null;
    this.marco = Number.POSITIVE_INFINITY;
    this.chegandoAvisado = false;
    this.minutosAnunciados = null;
    this.semPrevisao = false;
    this.falhas = 0;
    this.falhaAvisada = false;
    this.iniciado = false;
    this.ultimoTexto = '';
  }

  /** Atualização bem-sucedida da SPTrans. Devolve o aviso a falar, ou null para ficar em silêncio. */
  avaliar(leitura: Leitura, linhasEscolhidas: string[]): Anuncio | null {
    const retomou = this.falhaAvisada;
    this.falhas = 0;
    this.falhaAvisada = false;
    const anuncio = this.decidir(leitura, linhasEscolhidas);
    if (anuncio) return this.registrar(anuncio);
    if (retomou) return this.registrar({ tipo: 'retomou', texto: 'As previsões voltaram a atualizar.', urgente: false });
    return null;
  }

  /** Atualização que falhou. Só avisa depois de falhas seguidas, e uma única vez. */
  falhou(): Anuncio | null {
    this.falhas++;
    if (this.falhas < FALHAS_PARA_AVISAR || this.falhaAvisada) return null;
    this.falhaAvisada = true;
    return this.registrar({
      tipo: 'falha',
      texto: 'Não estou conseguindo atualizar as previsões da SPTrans. A última informação pode estar desatualizada. Continuo tentando.',
      urgente: false,
    });
  }

  private registrar(a: Anuncio): Anuncio | null {
    if (a.texto === this.ultimoTexto && a.tipo !== 'chegando') return null;
    this.ultimoTexto = a.texto;
    return a;
  }

  private decidir({ onibus, simulado }: Leitura, linhas: string[]): Anuncio | null {
    const prefixo = simulado ? 'Demonstração com horários simulados. ' : '';
    const primeiro = onibus[0];
    if (!primeiro) {
      const anterior = this.veiculo !== null && this.minutos !== null && this.minutos <= 2;
      this.veiculo = null;
      this.minutos = null;
      if (this.semPrevisao && this.iniciado) return null;
      this.semPrevisao = true;
      const quais = linhas.length === 1 ? `da linha ${linhas[0]}` : `das linhas ${linhas.join(', ')}`;
      const inicio = !this.iniciado;
      this.iniciado = true;
      if (anterior) {
        return { tipo: 'troca', urgente: true, texto: `O ônibus que estava chegando saiu da previsão. Ele pode ter passado. Nenhum outro ônibus ${quais} está previsto agora. Continuo acompanhando.` };
      }
      return { tipo: 'sem-previsao', urgente: false, texto: `${inicio ? prefixo : ''}Nenhum ônibus ${quais} está previsto agora neste ponto. Continuo acompanhando e aviso quando aparecer.` };
    }

    const m = Math.max(0, primeiro.minutos);
    const k = chave(primeiro);
    const voltouDoNada = this.semPrevisao;
    this.semPrevisao = false;

    if (!this.iniciado) {
      this.iniciado = true;
      this.novoVeiculo(k, m);
      if (m <= 1) {
        this.chegandoAvisado = true;
        return { tipo: 'chegando', urgente: true, texto: `${prefixo}Atenção: a linha ${primeiro.letreiro}${destino(primeiro)} está ${m <= 0 ? 'chegando agora' : 'a 1 minuto'}. Prepare-se e confirme a linha com o motorista.` };
      }
      return { tipo: 'inicio', urgente: false, texto: `${prefixo}Acompanhando. Próximo ônibus: linha ${primeiro.letreiro}${destino(primeiro)}, ${minutosFalados(m)}. Eu aviso quando ele estiver chegando.` };
    }

    // O veículo da frente mudou: o anterior passou ou sumiu da previsão.
    const mesmoVeiculo = k === this.veiculo && !(this.minutos !== null && this.minutos <= 2 && m >= this.minutos + 5);
    if (!mesmoVeiculo) {
      const estavaChegando = this.minutos !== null && this.minutos <= 2;
      this.novoVeiculo(k, m);
      if (voltouDoNada) {
        return { tipo: 'troca', urgente: false, texto: `Apareceu uma previsão: linha ${primeiro.letreiro}${destino(primeiro)}, ${minutosFalados(m)}.` };
      }
      if (estavaChegando) {
        return { tipo: 'troca', urgente: true, texto: `O ônibus que estava chegando saiu da previsão. Ele pode ter passado. O próximo da linha ${primeiro.letreiro} está previsto ${minutosFalados(m)}.` };
      }
      return { tipo: 'troca', urgente: false, texto: `A previsão mudou de ônibus. Agora o próximo é a linha ${primeiro.letreiro}${destino(primeiro)}, ${minutosFalados(m)}.` };
    }

    this.minutos = m;
    if (m <= 1 && !this.chegandoAvisado) {
      this.chegandoAvisado = true;
      this.marco = 0;
      this.minutosAnunciados = m;
      return { tipo: 'chegando', urgente: true, texto: `Atenção: a linha ${primeiro.letreiro}${destino(primeiro)} está ${m <= 0 ? 'chegando agora' : 'a 1 minuto'}. Prepare-se e confirme a linha com o motorista.` };
    }
    const cruzou = MARCOS_MINUTOS.filter((x) => m <= x && x < this.marco);
    if (cruzou.length && m > 1) {
      this.marco = Math.min(...cruzou);
      this.minutosAnunciados = m;
      return { tipo: 'marco', urgente: false, texto: `Linha ${primeiro.letreiro} ${minutosFalados(m)}.` };
    }
    if (this.minutosAnunciados !== null && m - this.minutosAnunciados >= ATRASO_RELEVANTE_MIN) {
      this.minutosAnunciados = m;
      // Atrasou: os marcos acima da nova previsão voltam a valer.
      this.marco = Math.min(...MARCOS_MINUTOS.filter((x) => x >= m), Number.POSITIVE_INFINITY);
      this.chegandoAvisado = m <= 1;
      return { tipo: 'atraso', urgente: false, texto: `A previsão atrasou: a linha ${primeiro.letreiro} agora está ${minutosFalados(m)}.` };
    }
    return null;
  }

  private novoVeiculo(k: string, m: number): void {
    this.veiculo = k;
    this.minutos = m;
    this.minutosAnunciados = m;
    this.chegandoAvisado = m <= 1;
    // Marcos iguais ou acima da previsão inicial não fazem sentido para este ônibus.
    const acima = MARCOS_MINUTOS.filter((x) => x >= m);
    this.marco = acima.length ? Math.min(...acima) : Number.POSITIVE_INFINITY;
  }
}
