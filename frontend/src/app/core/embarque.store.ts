import { DOCUMENT } from '@angular/common';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { AnunciadorEmbarque, Anuncio } from './anunciador-embarque';
import { ApiService } from './api.service';
import { trocarIdentificador } from './dispositivo';
import { EmbarqueApiService } from './embarque-api.service';
import {
  LinhaEscolhida,
  LinhaNoPonto,
  PontoEscolhido,
  SessaoEmbarque,
  SituacaoEmbarque,
  TrajetoFavorito,
} from './embarque.models';
import { ErroApi, Modo, Ponto } from './models';
import { SpeechService } from './speech.service';
import { StatusService } from './status.service';
import { gravarJson, lerJson } from './storage';

export const INTERVALO_ACOMPANHAMENTO_MS = 20_000;
export const MAX_LINHAS = 3;
const CHAVE_CACHE = 'pf.embarque.favoritos';
const CHAVE_VOZ = 'pf.embarque.voz';

/** Linha disponível no ponto, com a próxima previsão (quando a SPTrans tiver uma). */
export interface OpcaoLinha extends LinhaNoPonto {
  proximo_min?: number | null;
}

export type Etapa = 'ponto' | 'linha' | 'acompanhando';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Livre = any;

/**
 * Estado e regras do Embarque Assistido no navegador: ponto, linhas, acompanhamento, avisos e favoritos.
 * A tela e a assistente usam o mesmo estado, então o que se faz por voz aparece na tela e vice-versa.
 */
@Injectable({ providedIn: 'root' })
export class EmbarqueStore {
  private readonly api = inject(ApiService);
  private readonly embarque = inject(EmbarqueApiService);
  private readonly fala = inject(SpeechService);
  private readonly status = inject(StatusService);
  private readonly win: Livre = inject(DOCUMENT).defaultView;

  readonly modoForcado = signal<Modo | null>(null);
  /** Demonstração quando a página pede (?modo=demo) ou quando o servidor não tem acesso à SPTrans. */
  readonly modo = computed<Modo>(() => this.modoForcado() ?? (this.status.demo() ? 'demo' : 'auto'));

  // ---------- ponto ----------
  readonly ponto = signal<PontoEscolhido | null>(null);
  readonly pontoConfirmado = signal(false);
  readonly opcoesPonto = signal<Ponto[]>([]);
  readonly avisoBusca = signal('');
  readonly buscando = signal(false);
  readonly localizando = signal(false);

  // ---------- linhas ----------
  readonly linhas = signal<OpcaoLinha[]>([]);
  readonly avisoLinhas = signal('');
  readonly carregandoLinhas = signal(false);
  readonly escolhidas = signal<LinhaEscolhida[]>([]);

  // ---------- acompanhamento ----------
  readonly sessao = signal<SessaoEmbarque | null>(null);
  readonly situacao = signal<SituacaoEmbarque | null>(null);
  readonly falhando = signal(false);
  readonly erro = signal('');
  readonly iniciando = signal(false);
  readonly ultimoAviso = signal<Anuncio | null>(null);
  /** Texto para a região viva (leitores de tela recebem os mesmos avisos que a voz). */
  readonly avisoVivo = signal('');
  readonly avisoUrgente = signal('');
  readonly vozAtiva = signal<boolean>(lerJson<boolean>(CHAVE_VOZ) ?? true);
  readonly telaAcesa = signal(false);

  // ---------- favoritos ----------
  readonly favoritos = signal<TrajetoFavorito[]>(lerJson<TrajetoFavorito[]>(CHAVE_CACHE) ?? []);
  readonly favoritosCarregados = signal(false);
  readonly erroFavoritos = signal('');

  readonly etapa = computed<Etapa>(() => (this.sessao() ? 'acompanhando' : this.ponto() && this.pontoConfirmado() ? 'linha' : 'ponto'));
  readonly favoritoAtual = computed(() => {
    const s = this.sessao();
    const p = s ? { codigo: s.ponto } : this.ponto();
    const l = s ? s.linhas[0] : this.escolhidas()[0];
    if (!p || !l) return null;
    return this.favoritos().find((f) => f.ponto === p.codigo && f.linha === l.letreiro && (f.sentido ?? null) === (l.sentido ?? null)) ?? null;
  });

  private readonly anunciador = new AnunciadorEmbarque();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private pedido = 0;
  private wakeLock: Livre = null;

  constructor() {
    const doc = this.win?.document;
    doc?.addEventListener?.('visibilitychange', () => {
      if (doc.hidden || !this.sessao()) return;
      void this.manterTelaAcesa();
      void this.atualizar();
    });
  }

  // ===================== favoritos =====================

  async carregarFavoritos(): Promise<void> {
    try {
      const lista = await firstValueFrom(this.embarque.favoritos());
      this.favoritos.set(lista);
      gravarJson(CHAVE_CACHE, lista);
      this.erroFavoritos.set('');
    } catch (e) {
      this.erroFavoritos.set(this.favoritos().length
        ? 'Mostrando os trajetos salvos neste aparelho. Não consegui atualizar com o servidor.'
        : mensagem(e));
    } finally {
      this.favoritosCarregados.set(true);
    }
  }

  async salvarFavoritoAtual(apelido?: string | null): Promise<TrajetoFavorito> {
    const s = this.sessao();
    const ponto = s ? { codigo: s.ponto, nome: s.ponto_nome } : this.ponto();
    const linha = s ? s.linhas[0] : this.escolhidas()[0];
    if (!ponto || !linha) throw new ErroApi(400, 'Escolha o ponto e a linha antes de salvar o trajeto.');
    const destino = linha.destino ?? this.linhas().find((l) => l.letreiro === linha.letreiro && l.sentido === linha.sentido)?.destino ?? null;
    const salvo = await firstValueFrom(this.embarque.salvarFavorito({
      ponto: ponto.codigo, ponto_nome: ponto.nome, linha: linha.letreiro, sentido: linha.sentido ?? null, destino,
      apelido: apelido?.trim() || null, simulado: (s?.simulado ?? this.modo() === 'demo'),
    }));
    this.favoritos.update((l) => [...l.filter((f) => f.id !== salvo.id), salvo]);
    gravarJson(CHAVE_CACHE, this.favoritos());
    return salvo;
  }

  async renomearFavorito(f: TrajetoFavorito, apelido: string): Promise<void> {
    const novo = await firstValueFrom(this.embarque.renomearFavorito(f.id, apelido.trim() || null));
    this.favoritos.update((l) => l.map((x) => (x.id === novo.id ? novo : x)));
    gravarJson(CHAVE_CACHE, this.favoritos());
  }

  async removerFavorito(f: TrajetoFavorito): Promise<void> {
    await firstValueFrom(this.embarque.removerFavorito(f.id));
    this.favoritos.update((l) => l.filter((x) => x.id !== f.id));
    gravarJson(CHAVE_CACHE, this.favoritos());
  }

  /** Um toque (ou "ir para o trabalho"): já começa a acompanhar o trajeto salvo. */
  async usarFavorito(f: TrajetoFavorito): Promise<void> {
    this.modoForcado.set(f.simulado ? 'demo' : this.modoForcado());
    this.ponto.set({ codigo: f.ponto, nome: f.ponto_nome });
    this.pontoConfirmado.set(true);
    this.escolhidas.set([{ letreiro: f.linha, sentido: f.sentido ?? null, destino: f.destino ?? null }]);
    await this.iniciar();
  }

  // ===================== ponto =====================

  async buscarPontos(termo: string): Promise<Ponto[]> {
    const t = termo.trim();
    if (t.length < 2) {
      this.avisoBusca.set('Digite pelo menos 2 letras do nome do ponto, da rua ou o código.');
      return [];
    }
    this.buscando.set(true);
    this.avisoBusca.set('');
    try {
      const r = await firstValueFrom(this.api.buscarPontos(t, this.modo()));
      this.opcoesPonto.set(r.pontos.slice(0, 8));
      this.avisoBusca.set(r.aviso ?? (r.pontos.length ? '' : `Não encontrei pontos para "${t}". Tente o nome da rua com o número.`));
      return this.opcoesPonto();
    } catch (e) {
      this.opcoesPonto.set([]);
      this.avisoBusca.set(mensagem(e));
      return [];
    } finally {
      this.buscando.set(false);
    }
  }

  /** Pede a localização ao navegador (com permissão). A posição vai só nesta busca e não é guardada. */
  async pontosPerto(): Promise<Ponto[]> {
    const geo = this.win?.navigator?.geolocation;
    if (!geo) {
      this.avisoBusca.set('Este aparelho não oferece localização. Busque pelo nome da rua.');
      return [];
    }
    if (this.modo() === 'demo') {
      this.avisoBusca.set('Na demonstração não há pontos reais perto de você. Busque por "Paulista" para ver o exemplo.');
      return [];
    }
    this.localizando.set(true);
    this.avisoBusca.set('');
    try {
      const pos: Livre = await new Promise((ok, falha) =>
        geo.getCurrentPosition(ok, falha, { enableHighAccuracy: true, timeout: 12_000, maximumAge: 30_000 }));
      const r = await firstValueFrom(this.api.pontosProximos(pos.coords.latitude, pos.coords.longitude, 400));
      this.opcoesPonto.set(r.pontos.slice(0, 8));
      const precisao = Math.round(pos.coords.accuracy ?? 0);
      this.avisoBusca.set(r.aviso ?? (precisao > 80
        ? `A localização tem precisão de cerca de ${precisao} metros. Confira o nome do ponto antes de confirmar.`
        : ''));
      return this.opcoesPonto();
    } catch (e: Livre) {
      this.opcoesPonto.set([]);
      this.avisoBusca.set(e?.code === 1
        ? 'Sem permissão para usar a localização. Você pode liberar nas configurações do navegador ou buscar pelo nome da rua.'
        : e?.code === 3 || e?.code === 2
          ? 'Não consegui descobrir onde você está agora. Tente de novo ao ar livre ou busque pelo nome da rua.'
          : mensagem(e));
      return [];
    } finally {
      this.localizando.set(false);
    }
  }

  escolherPonto(p: PontoEscolhido): void {
    this.ponto.set({ codigo: p.codigo, nome: p.nome, endereco: p.endereco ?? null, distancia_metros: p.distancia_metros ?? null, linhas: p.linhas ?? null });
    this.pontoConfirmado.set(false);
  }

  async confirmarPonto(): Promise<OpcaoLinha[]> {
    if (!this.ponto()) return [];
    this.pontoConfirmado.set(true);
    this.escolhidas.set([]);
    return this.carregarLinhas();
  }

  trocarPonto(): void {
    this.ponto.set(null);
    this.pontoConfirmado.set(false);
    this.linhas.set([]);
    this.escolhidas.set([]);
    this.avisoLinhas.set('');
  }

  /** Linhas do cadastro oficial no ponto + a próxima previsão de cada uma (quando a SPTrans tiver). */
  async carregarLinhas(): Promise<OpcaoLinha[]> {
    const p = this.ponto();
    if (!p) return [];
    this.carregandoLinhas.set(true);
    this.avisoLinhas.set('');
    const modo = this.modo();
    const [cadastro, previsoes] = await Promise.allSettled([
      firstValueFrom(this.embarque.linhasDoPonto(p.codigo, modo)),
      firstValueFrom(this.api.previsoes(p.codigo, modo)),
    ]);
    if (this.ponto()?.codigo !== p.codigo) {
      // A pessoa trocou de ponto enquanto esta consulta estava em andamento: o resultado não vale mais.
      if (!this.ponto()) this.carregandoLinhas.set(false);
      return this.ponto() ? this.linhas() : [];
    }
    const opcoes = new Map<string, OpcaoLinha>();
    const temCadastro = cadastro.status === 'fulfilled' && cadastro.value.linhas.length > 0;
    if (cadastro.status === 'fulfilled') {
      for (const l of cadastro.value.linhas) opcoes.set(`${l.letreiro}|${l.sentido}`, { ...l, proximo_min: null });
    }
    if (previsoes.status === 'fulfilled') {
      const pv = previsoes.value;
      if (pv.ponto?.nome && (!p.nome || /^Ponto \d+$/.test(p.nome))) this.ponto.set({ ...p, nome: pv.ponto.nome, endereco: pv.ponto.endereco ?? p.endereco });
      for (const o of pv.onibus) {
        const k = `${o.letreiro}|${o.sentido ?? ''}`;
        const existente = opcoes.get(k) ?? [...opcoes.values()].find((x) => x.letreiro === o.letreiro && o.sentido == null);
        if (existente) {
          if (existente.proximo_min == null || o.minutos < existente.proximo_min) existente.proximo_min = o.minutos;
        } else if (!temCadastro) {
          // Sem cadastro (demonstração ou ponto fora do GTFS): as linhas vêm das próprias previsões.
          opcoes.set(k, { letreiro: o.letreiro, sentido: o.sentido ?? 0, destino: o.destino, nome_linha: '', proximo_min: o.minutos });
        }
      }
    }
    const lista = [...opcoes.values()].sort((a, b) =>
      (a.proximo_min ?? 999) - (b.proximo_min ?? 999) || a.letreiro.localeCompare(b.letreiro));
    this.linhas.set(lista);
    if (!lista.length) {
      this.avisoLinhas.set(previsoes.status === 'rejected'
        ? mensagem(previsoes.reason)
        : 'Não encontrei linhas para este ponto agora. Confira se é o ponto certo ou tente de novo em instantes.');
    } else if (previsoes.status === 'rejected') {
      this.avisoLinhas.set('As linhas vêm do cadastro da SPTrans; as previsões não responderam agora. O acompanhamento tenta de novo.');
    }
    this.carregandoLinhas.set(false);
    return lista;
  }

  alternarLinha(l: OpcaoLinha): void {
    const k = (x: LinhaEscolhida) => `${x.letreiro}|${x.sentido ?? 0}`;
    const alvo: LinhaEscolhida = { letreiro: l.letreiro, sentido: l.sentido || null, destino: l.destino };
    const atual = this.escolhidas();
    if (atual.some((x) => k(x) === k(alvo))) this.escolhidas.set(atual.filter((x) => k(x) !== k(alvo)));
    else if (atual.length < MAX_LINHAS) this.escolhidas.set([...atual, alvo]);
  }

  linhaEscolhida(l: OpcaoLinha): boolean {
    return this.escolhidas().some((x) => x.letreiro === l.letreiro && (x.sentido ?? 0) === (l.sentido || 0));
  }

  // ===================== acompanhamento =====================

  async iniciar(linhas: LinhaEscolhida[] = this.escolhidas()): Promise<void> {
    const p = this.ponto();
    if (!p || !linhas.length) throw new ErroApi(400, 'Escolha o ponto e pelo menos uma linha.');
    this.iniciando.set(true);
    this.erro.set('');
    try {
      const s = await firstValueFrom(this.embarque.iniciar(p.codigo, p.nome, linhas.slice(0, MAX_LINHAS), this.modo()));
      // O servidor devolve só letreiro e sentido; o destino escolhido continua útil para falar.
      s.linhas = s.linhas.map((l) => ({ ...l, destino: linhas.find((x) => x.letreiro === l.letreiro)?.destino ?? l.destino }));
      this.comecar(s);
    } finally {
      this.iniciando.set(false);
    }
  }

  /** Volta a acompanhar depois de recarregar a página. */
  async retomar(): Promise<boolean> {
    try {
      const s = await firstValueFrom(this.embarque.sessaoAtual());
      if (!s || this.sessao()?.id === s.id) return !!s;
      this.modoForcado.set(s.simulado ? 'demo' : this.modoForcado());
      this.ponto.set({ codigo: s.ponto, nome: s.ponto_nome });
      this.pontoConfirmado.set(true);
      this.escolhidas.set(s.linhas);
      this.comecar(s);
      return true;
    } catch {
      return false;
    }
  }

  private comecar(s: SessaoEmbarque): void {
    this.anunciador.reiniciar();
    this.situacao.set(null);
    this.ultimoAviso.set(null);
    this.falhando.set(false);
    this.sessao.set(s);
    void this.manterTelaAcesa();
    void this.atualizar();
  }

  async atualizar(): Promise<void> {
    const s = this.sessao();
    if (!s) return;
    const pedido = ++this.pedido;
    this.agendar();
    try {
      const sit = await firstValueFrom(this.embarque.situacao(s.id));
      if (pedido !== this.pedido || this.sessao()?.id !== s.id) return;
      this.situacao.set(sit);
      this.falhando.set(false);
      this.erro.set('');
      this.anunciar(this.anunciador.avaliar({ onibus: sit.onibus, simulado: sit.fonte === 'SIMULADO' }, s.linhas.map((l) => l.letreiro)));
    } catch (e) {
      if (pedido !== this.pedido || this.sessao()?.id !== s.id) return;
      if (e instanceof ErroApi && (e.status === 409 || e.status === 404)) {
        this.erro.set(e.message);
        this.finalizarLocal();
        return;
      }
      this.falhando.set(true);
      this.erro.set(mensagem(e));
      this.anunciar(this.anunciador.falhou());
    }
  }

  async encerrar(desfecho: 'EMBARQUEI' | 'DESISTI'): Promise<void> {
    const s = this.sessao();
    if (!s) return;
    this.finalizarLocal();
    try {
      await firstValueFrom(this.embarque.encerrar(s.id, desfecho));
    } catch {
      /* o servidor expira o acompanhamento sozinho; a tela já parou */
    }
    const texto = desfecho === 'EMBARQUEI' ? 'Boa viagem! Acompanhamento encerrado.' : 'Acompanhamento encerrado.';
    this.anunciar({ tipo: 'inicio', texto, urgente: false }, true);
    if (desfecho === 'EMBARQUEI') {
      // A pessoa já está no ônibus: a tela volta ao começo (favoritos e busca de ponto).
      this.trocarPonto();
    } else {
      // Continua no mesmo ponto, podendo escolher outra linha: atualiza as previsões da lista.
      this.escolhidas.set([]);
      void this.carregarLinhas();
    }
  }

  private finalizarLocal(): void {
    this.pedido++;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.sessao.set(null);
    this.situacao.set(null);
    this.falhando.set(false);
    void this.liberarTela();
  }

  private agendar(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.atualizar(), INTERVALO_ACOMPANHAMENTO_MS);
  }

  /** Repete o último aviso; sem aviso ainda, fala a situação atual. */
  repetir(): string {
    const texto = this.anunciador.ultimo || this.situacao()?.frase_falada || '';
    if (texto) this.dizer(texto, true);
    return texto;
  }

  situacaoFalada(): string {
    const s = this.situacao();
    if (!this.sessao()) return 'Você ainda não está acompanhando um ônibus. Escolha o ponto e a linha.';
    if (!s) return 'Estou consultando as previsões da SPTrans.';
    const atraso = this.falhando() ? ' Atenção: não consegui atualizar na última tentativa.' : '';
    return s.frase_falada + atraso;
  }

  alternarVoz(ativa = !this.vozAtiva()): void {
    this.vozAtiva.set(ativa);
    gravarJson(CHAVE_VOZ, ativa);
    if (!ativa) this.fala.parar();
  }

  async apagarDados(): Promise<void> {
    await firstValueFrom(this.embarque.apagarDados());
    this.finalizarLocal();
    this.favoritos.set([]);
    gravarJson(CHAVE_CACHE, []);
    trocarIdentificador();
  }

  /** Fala (se a voz estiver ligada) e publica na região viva para leitores de tela. */
  dizer(texto: string, forcarVoz = false): void {
    if ((this.vozAtiva() || forcarVoz) && this.fala.suportaSintese) this.fala.falar(texto);
  }

  private anunciar(a: Anuncio | null, semRegistro = false): void {
    if (!a) return;
    if (!semRegistro) this.ultimoAviso.set(a);
    if (a.urgente) {
      this.avisoUrgente.set('');
      queueMicrotask(() => this.avisoUrgente.set(a.texto));
      try {
        this.win?.navigator?.vibrate?.([350, 150, 350]);
      } catch {
        /* sem vibração */
      }
    } else {
      this.avisoVivo.set(a.texto);
    }
    this.dizer(a.texto);
  }

  private async manterTelaAcesa(): Promise<void> {
    try {
      if (this.wakeLock || !this.win?.navigator?.wakeLock) return;
      this.wakeLock = await this.win.navigator.wakeLock.request('screen');
      this.telaAcesa.set(true);
      this.wakeLock.addEventListener?.('release', () => {
        this.wakeLock = null;
        this.telaAcesa.set(false);
      });
    } catch {
      this.telaAcesa.set(false);
    }
  }

  private async liberarTela(): Promise<void> {
    try {
      await this.wakeLock?.release?.();
    } catch {
      /* ignora */
    }
    this.wakeLock = null;
    this.telaAcesa.set(false);
  }
}

function mensagem(e: unknown): string {
  return e instanceof ErroApi ? e.message : 'Algo deu errado. Tente de novo.';
}
