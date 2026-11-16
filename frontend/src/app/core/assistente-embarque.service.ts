import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { AJUDA_EMBARQUE, Comando, acharFavorito, extrairLinha, interpretar } from './comandos-embarque';
import { TrajetoFavorito } from './embarque.models';
import { EmbarqueStore, OpcaoLinha } from './embarque.store';
import { ErroApi, Ponto } from './models';

export interface FalaAssistente {
  id: number;
  autor: 'voce' | 'assistente';
  texto: string;
  /** Sugestões tocáveis: cada uma envia o comando como se a pessoa tivesse dito. */
  sugestoes?: string[];
  /** Resposta veio do assistente geral (/api/chat), e não de um comando do aplicativo. */
  geral?: boolean;
}

interface Confirmacao {
  pergunta: string;
  executar: () => Promise<string>;
}

type Lista =
  | { tipo: 'ponto'; itens: Ponto[] }
  | { tipo: 'linha'; itens: OpcaoLinha[] }
  | { tipo: 'favorito'; itens: TrajetoFavorito[]; acao: 'usar' | 'remover' };

function minutos(m?: number | null): string {
  if (m == null) return 'sem previsão agora';
  if (m <= 0) return 'previsto para agora';
  return m === 1 ? 'próximo em 1 minuto' : `próximo em ${m} minutos`;
}

function nomeFavorito(f: TrajetoFavorito): string {
  return `${f.apelido ? f.apelido + ': ' : ''}linha ${f.linha}${f.destino ? ' sentido ' + f.destino : ''}, no ponto ${f.ponto_nome}`;
}

/**
 * A assistente do Embarque Assistido: entende comandos (voz ou texto), EXECUTA as ações no aplicativo pelo mesmo
 * estado da tela e pede confirmação antes do que muda ou apaga algo. Perguntas que não são comandos vão ao
 * assistente geral (/api/chat) com o ponto e a linha atuais; horários sempre vêm da SPTrans, nunca da IA.
 */
@Injectable({ providedIn: 'root' })
export class AssistenteEmbarque {
  private readonly store = inject(EmbarqueStore);
  private readonly api = inject(ApiService);

  readonly mensagens = signal<FalaAssistente[]>([]);
  readonly processando = signal(false);
  readonly confirmando = signal<string | null>(null);
  private pendente: Confirmacao | null = null;
  private lista: Lista | null = null;
  private seq = 0;

  limpar(): void {
    this.mensagens.set([]);
    this.pendente = null;
    this.confirmando.set(null);
    this.lista = null;
  }

  /** Processa o que a pessoa disse ou digitou. falar=true quando veio da voz (a resposta é sempre falada). */
  async enviar(texto: string, falar = false): Promise<void> {
    const limpo = texto.trim();
    if (!limpo || this.processando()) return;
    this.registrar('voce', limpo);
    this.processando.set(true);
    try {
      const r = await this.executar(interpretar(limpo), limpo);
      this.responder(r.texto, falar, r.sugestoes, r.geral);
    } catch (e) {
      this.responder(e instanceof ErroApi ? e.message : 'Não consegui fazer isso agora. Tente de novo.', falar);
    } finally {
      this.processando.set(false);
    }
  }

  /** A tela também conversa: avisos importantes de ações feitas por toque aparecem no histórico. */
  informar(texto: string): void {
    this.registrar('assistente', texto);
  }

  private responder(texto: string, falar: boolean, sugestoes?: string[], geral = false): void {
    this.registrar('assistente', texto, sugestoes, geral);
    if (falar) this.store.dizer(texto, true);
    else this.store.dizer(texto);
  }

  private registrar(autor: FalaAssistente['autor'], texto: string, sugestoes?: string[], geral = false): void {
    this.mensagens.update((l) => [...l.slice(-30), { id: ++this.seq, autor, texto, sugestoes, geral }]);
  }

  private confirmar(pergunta: string, executar: () => Promise<string>): { texto: string; sugestoes: string[] } {
    this.pendente = { pergunta, executar };
    this.confirmando.set(pergunta);
    return { texto: pergunta + ' Diga sim ou não.', sugestoes: ['Sim', 'Não'] };
  }

  private async executar(c: Comando, original: string): Promise<{ texto: string; sugestoes?: string[]; geral?: boolean }> {
    const s = this.store;
    if (c.tipo !== 'sim' && c.tipo !== 'nao' && this.pendente) {
      // Outro pedido no meio de uma confirmação: a confirmação anterior é descartada.
      this.pendente = null;
      this.confirmando.set(null);
    }
    switch (c.tipo) {
      case 'sim': {
        if (this.pendente) {
          const p = this.pendente;
          this.pendente = null;
          this.confirmando.set(null);
          return { texto: await p.executar() };
        }
        if (s.ponto() && !s.pontoConfirmado()) return { texto: await this.confirmarPontoEListar() };
        return { texto: 'Não há nada esperando confirmação agora.' };
      }
      case 'nao': {
        if (this.pendente) {
          this.pendente = null;
          this.confirmando.set(null);
          return { texto: 'Tudo bem, não fiz nada.' };
        }
        if (s.ponto() && !s.pontoConfirmado()) {
          s.trocarPonto();
          return { texto: 'Certo. Diga o nome da rua do ponto ou "pontos perto de mim".', sugestoes: ['Pontos perto de mim'] };
        }
        return { texto: 'Certo.' };
      }
      case 'ajuda':
        return { texto: AJUDA_EMBARQUE, sugestoes: ['Pontos perto de mim', 'Quanto falta', 'Meus favoritos'] };
      case 'repetir': {
        const t = s.repetir();
        return { texto: t || s.situacaoFalada() };
      }
      case 'quanto-falta':
        if (!s.sessao()) return this.semAcompanhamento();
        await s.atualizar();
        return { texto: s.situacaoFalada() };
      case 'silenciar':
        s.alternarVoz(false);
        return { texto: 'Voz do aplicativo desligada. Os avisos continuam na tela e no leitor de tela.' };
      case 'falar':
        s.alternarVoz(true);
        return { texto: 'Voz ligada. Vou falar os avisos do ônibus.' };
      case 'embarquei':
        if (!s.sessao()) return { texto: 'Você não está acompanhando nenhum ônibus agora.' };
        await s.encerrar('EMBARQUEI');
        return { texto: 'Boa viagem! Encerrei o acompanhamento.' };
      case 'parar': {
        const sessao = s.sessao();
        if (!sessao) return { texto: 'Não há acompanhamento em andamento.' };
        const linhas = sessao.linhas.map((l) => l.letreiro).join(', ');
        return this.confirmar(`Encerrar o acompanhamento da linha ${linhas}?`, async () => {
          await s.encerrar('DESISTI');
          return 'Acompanhamento encerrado.';
        });
      }
      case 'perto': {
        const pontos = await s.pontosPerto();
        if (!pontos.length) return { texto: s.avisoBusca() || 'Não encontrei pontos perto de você.' };
        return this.listarPontos(pontos, 'Pontos perto de você');
      }
      case 'buscar-ponto': {
        const pontos = await s.buscarPontos(c.termo);
        if (!pontos.length) return { texto: s.avisoBusca() || `Não encontrei pontos para ${c.termo}.` };
        return this.listarPontos(pontos, 'Encontrei');
      }
      case 'trocar-ponto':
        if (s.sessao()) {
          return this.confirmar('Para trocar de ponto preciso encerrar o acompanhamento atual. Encerrar?', async () => {
            await s.encerrar('DESISTI');
            s.trocarPonto();
            return 'Encerrado. Diga o nome da rua do novo ponto ou "pontos perto de mim".';
          });
        }
        s.trocarPonto();
        return { texto: 'Certo. Diga o nome da rua do ponto ou "pontos perto de mim".', sugestoes: ['Pontos perto de mim'] };
      case 'escolher':
        return this.escolher(c.indice);
      case 'acompanhar':
        return this.acompanhar(c.linha, c.ponto);
      case 'listar-favoritos': {
        const favs = s.favoritos();
        if (!favs.length) return { texto: 'Você ainda não tem trajetos salvos. Quando estiver acompanhando um ônibus, diga "salvar nos favoritos".' };
        this.lista = { tipo: 'favorito', itens: favs.slice(0, 6), acao: 'usar' };
        return {
          texto: `Seus trajetos: ${favs.slice(0, 6).map((f, i) => `${i + 1}, ${nomeFavorito(f)}`).join('. ')}. Diga o número para acompanhar.`,
          sugestoes: favs.slice(0, 3).map((_, i) => `${i + 1}`),
        };
      }
      case 'usar-favorito': {
        const achados = acharFavorito(s.favoritos(), c.alvo);
        if (!achados.length) {
          // Pode não ser um favorito ("ir para a Paulista"): vira pergunta ao assistente geral.
          return this.perguntaGeral(original);
        }
        if (achados.length > 1) {
          this.lista = { tipo: 'favorito', itens: achados.slice(0, 6), acao: 'usar' };
          return { texto: `Encontrei ${achados.length} trajetos: ${achados.slice(0, 6).map((f, i) => `${i + 1}, ${nomeFavorito(f)}`).join('. ')}. Qual deles?` };
        }
        return this.usarFavorito(achados[0]);
      }
      case 'salvar-favorito': {
        const ponto = s.sessao() ? s.sessao()!.ponto_nome : s.ponto()?.nome;
        const linha = s.sessao()?.linhas[0] ?? s.escolhidas()[0];
        if (!ponto || !linha) return { texto: 'Primeiro escolha o ponto e a linha. Depois diga "salvar nos favoritos".' };
        const apelido = c.apelido ? c.apelido.slice(0, 40) : null;
        return this.confirmar(`Salvar a linha ${linha.letreiro} no ponto ${ponto} nos seus favoritos${apelido ? ` como "${apelido}"` : ''}?`, async () => {
          const f = await s.salvarFavoritoAtual(apelido);
          return `Trajeto salvo${f.apelido ? ` como "${f.apelido}"` : ''}. Da próxima vez, é só tocar nele ou dizer "ir para ${f.apelido ?? 'o trajeto'}".`;
        });
      }
      case 'remover-favorito': {
        const favs = s.favoritos();
        if (!favs.length) return { texto: 'Você não tem trajetos salvos.' };
        const alvo = c.alvo ? acharFavorito(favs, c.alvo) : s.favoritoAtual() ? [s.favoritoAtual()!] : [];
        if (alvo.length === 1) return this.confirmarRemocao(alvo[0]);
        const itens = (alvo.length ? alvo : favs).slice(0, 6);
        this.lista = { tipo: 'favorito', itens, acao: 'remover' };
        return { texto: `Qual trajeto remover? ${itens.map((f, i) => `${i + 1}, ${nomeFavorito(f)}`).join('. ')}.` };
      }
      case 'conferir-camera':
        return { texto: 'Use o botão "Conferir o letreiro pela câmera" no acompanhamento. Se o reconhecimento ainda não estiver conectado, confirme a linha com o motorista.' };
      case 'pergunta':
        return this.perguntaGeral(c.texto);
    }
  }

  private semAcompanhamento(): { texto: string; sugestoes: string[] } {
    return { texto: 'Você ainda não está acompanhando um ônibus. Diga "pontos perto de mim" ou o nome da rua do ponto.', sugestoes: ['Pontos perto de mim', 'Meus favoritos'] };
  }

  private listarPontos(pontos: Ponto[], titulo: string): { texto: string; sugestoes: string[] } {
    const itens = pontos.slice(0, 5);
    this.lista = { tipo: 'ponto', itens };
    if (itens.length === 1) {
      this.store.escolherPonto(itens[0]);
      return { texto: `${titulo} um ponto: ${this.descreverPonto(itens[0])}. É este? Diga sim ou não.`, sugestoes: ['Sim', 'Não'] };
    }
    const lista = itens.map((p, i) => `${i + 1}, ${this.descreverPonto(p)}`).join('. ');
    return { texto: `${titulo} ${itens.length} pontos. ${lista}. Diga o número do seu ponto.`, sugestoes: itens.slice(0, 3).map((_, i) => `${i + 1}`) };
  }

  private descreverPonto(p: Ponto): string {
    const dist = p.distancia_metros != null ? `, a ${p.distancia_metros} metros` : '';
    return `${p.nome}${p.endereco ? ', ' + p.endereco : ''}${dist}`;
  }

  private async escolher(n: number): Promise<{ texto: string; sugestoes?: string[] }> {
    const s = this.store;
    const lista: Lista | null = this.lista ?? (s.etapa() === 'linha' && s.linhas().length
      ? { tipo: 'linha', itens: s.linhas() }
      : s.opcoesPonto().length ? { tipo: 'ponto', itens: s.opcoesPonto() } : null);
    if (!lista) return { texto: 'Não há uma lista para escolher agora.' };
    const item = lista.itens[n - 1];
    if (!item) return { texto: `A lista tem ${lista.itens.length} opções. Diga um número de 1 a ${lista.itens.length}.` };
    this.lista = null;
    if (lista.tipo === 'ponto') {
      const p = item as Ponto;
      s.escolherPonto(p);
      return { texto: `${this.descreverPonto(p)}. É este o seu ponto? Diga sim ou não.`, sugestoes: ['Sim', 'Não'] };
    }
    if (lista.tipo === 'linha') {
      const l = item as OpcaoLinha;
      s.escolhidas.set([{ letreiro: l.letreiro, sentido: l.sentido || null, destino: l.destino }]);
      await s.iniciar();
      return { texto: `Acompanhando a linha ${l.letreiro}${l.destino ? ' sentido ' + l.destino : ''}. Vou avisar quando estiver chegando.` };
    }
    const f = item as TrajetoFavorito;
    return lista.acao === 'remover' ? this.confirmarRemocao(f) : this.usarFavorito(f);
  }

  private confirmarRemocao(f: TrajetoFavorito): { texto: string; sugestoes: string[] } {
    return this.confirmar(`Remover dos favoritos ${nomeFavorito(f)}?`, async () => {
      await this.store.removerFavorito(f);
      return 'Trajeto removido dos favoritos.';
    });
  }

  private async usarFavorito(f: TrajetoFavorito): Promise<{ texto: string; sugestoes?: string[] }> {
    const s = this.store;
    const atual = s.sessao();
    const iniciar = async () => {
      await s.usarFavorito(f);
      return `Acompanhando ${nomeFavorito(f)}. Vou avisar quando estiver chegando.`;
    };
    if (atual && !(atual.ponto === f.ponto && atual.linhas.some((l) => l.letreiro === f.linha))) {
      return this.confirmar(`Você já está acompanhando a linha ${atual.linhas[0]?.letreiro}. Trocar para ${nomeFavorito(f)}?`, iniciar);
    }
    return { texto: await iniciar() };
  }

  private async confirmarPontoEListar(): Promise<string> {
    const s = this.store;
    const linhas = await s.confirmarPonto();
    if (!linhas.length) return s.avisoLinhas() || 'Não encontrei linhas para este ponto agora.';
    const itens = linhas.slice(0, 6);
    this.lista = { tipo: 'linha', itens };
    return `Ponto confirmado. Linhas: ${itens.map((l, i) => `${i + 1}, ${l.letreiro}${l.destino ? ' sentido ' + l.destino : ''}, ${minutos(l.proximo_min)}`).join('. ')}. Qual você quer acompanhar? Diga o número.`;
  }

  private async acompanhar(linha?: string, codigoPonto?: number): Promise<{ texto: string; sugestoes?: string[] }> {
    const s = this.store;
    if (codigoPonto && codigoPonto !== s.ponto()?.codigo) {
      if (s.sessao()) await s.encerrar('DESISTI');
      s.escolherPonto({ codigo: codigoPonto, nome: `Ponto ${codigoPonto}` });
      await s.confirmarPonto();
    }
    if (!s.ponto()) {
      return { texto: `Em qual ponto você está${linha ? ' para pegar o ' + linha : ''}? Diga "pontos perto de mim" ou o nome da rua.`, sugestoes: ['Pontos perto de mim'] };
    }
    if (!s.pontoConfirmado()) await s.confirmarPonto();
    const opcoes = s.linhas().length ? s.linhas() : await s.carregarLinhas();
    if (!linha) {
      this.lista = { tipo: 'linha', itens: opcoes.slice(0, 6) };
      return { texto: `Linhas neste ponto: ${opcoes.slice(0, 6).map((l, i) => `${i + 1}, ${l.letreiro}${l.destino ? ' sentido ' + l.destino : ''}, ${minutos(l.proximo_min)}`).join('. ')}. Qual você quer acompanhar?` };
    }
    const alvo = extrairLinha(linha.toLowerCase()) ?? linha;
    const compativeis = opcoes.filter((l) => l.letreiro === alvo || l.letreiro.startsWith(alvo + '-'));
    if (!compativeis.length) {
      return { texto: `A linha ${alvo} não aparece neste ponto (${s.ponto()!.nome}). ${opcoes.length ? 'Aqui passam: ' + opcoes.slice(0, 6).map((l) => l.letreiro).join(', ') + '.' : ''} Confira se está no ponto certo.` };
    }
    if (compativeis.length > 1) {
      this.lista = { tipo: 'linha', itens: compativeis.slice(0, 6) };
      return { texto: `Há ${compativeis.length} opções: ${compativeis.slice(0, 6).map((l, i) => `${i + 1}, ${l.letreiro} sentido ${l.destino}, ${minutos(l.proximo_min)}`).join('. ')}. Qual sentido você quer?` };
    }
    const l = compativeis[0];
    s.escolhidas.set([{ letreiro: l.letreiro, sentido: l.sentido || null, destino: l.destino }]);
    await s.iniciar();
    return { texto: `Acompanhando a linha ${l.letreiro}${l.destino ? ' sentido ' + l.destino : ''} no ponto ${s.ponto()!.nome}. Vou avisar quando estiver chegando.` };
  }

  private async perguntaGeral(texto: string): Promise<{ texto: string; geral: boolean }> {
    const s = this.store;
    const sessao = s.sessao();
    const linha = sessao?.linhas[0] ?? s.escolhidas()[0];
    const contexto = {
      ponto: sessao?.ponto ?? (s.pontoConfirmado() ? s.ponto()?.codigo : null) ?? null,
      linha: linha && /^[0-9]{3,4}[A-Za-z]?(-[0-9]{1,2})?$/.test(linha.letreiro) ? linha.letreiro : null,
      sentido: linha?.sentido ?? null,
    };
    const r = await firstValueFrom(this.api.perguntar(texto.slice(0, 500), contexto.ponto || contexto.linha ? contexto : null));
    return { texto: r.resposta, geral: true };
  }
}
