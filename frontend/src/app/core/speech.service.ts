import { DOCUMENT } from '@angular/common';
import { Injectable, inject, signal } from '@angular/core';
import { PreferencesService } from './preferences.service';

export class ErroVoz extends Error {
  constructor(readonly codigo: 'nao-suportado' | 'sem-permissao' | 'nada-ouvido' | 'falha') {
    super(codigo);
  }
}

export interface VozDisponivel {
  uri: string;
  nome: string;
  idioma: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Livre = any;

/** Envolve speechSynthesis e SpeechRecognition com segurança (tudo é opcional no navegador). */
@Injectable({ providedIn: 'root' })
export class SpeechService {
  private readonly win: Livre = inject(DOCUMENT).defaultView;
  private readonly prefs = inject(PreferencesService);

  readonly falando = signal(false);
  readonly ouvindo = signal(false);
  /** Vozes em português disponíveis no aparelho (carregam de forma assíncrona em alguns navegadores). */
  readonly vozes = signal<VozDisponivel[]>([]);
  private reconhecimento: Livre = null;

  constructor() {
    this.carregarVozes();
    try {
      this.win?.speechSynthesis?.addEventListener?.('voiceschanged', () => this.carregarVozes());
    } catch {
      /* ignora */
    }
  }

  private carregarVozes(): void {
    try {
      const todas: Livre[] = this.win?.speechSynthesis?.getVoices?.() ?? [];
      this.vozes.set(
        todas
          .filter((v) => v.lang?.toLowerCase().startsWith('pt'))
          .map((v) => ({ uri: String(v.voiceURI ?? v.name), nome: String(v.name ?? v.voiceURI), idioma: String(v.lang) })),
      );
    } catch {
      this.vozes.set([]);
    }
  }

  get suportaSintese(): boolean {
    return !!this.win?.speechSynthesis && typeof this.win.SpeechSynthesisUtterance === 'function';
  }

  get suportaReconhecimento(): boolean {
    return !!(this.win?.SpeechRecognition || this.win?.webkitSpeechRecognition);
  }

  /** Fala o texto em pt-BR. Devolve false se não houver suporte ou texto. */
  falar(texto: string, velocidade?: number): boolean {
    const limpo = (texto ?? '').trim();
    if (!this.suportaSintese || !limpo) return false;
    const sintese = this.win.speechSynthesis;
    try {
      sintese.cancel();
      const fala = new this.win.SpeechSynthesisUtterance(limpo);
      fala.lang = 'pt-BR';
      fala.rate = velocidade ?? this.prefs.prefs().velocidadeVoz;
      const voz = this.escolherVoz();
      if (voz) fala.voice = voz;
      fala.onstart = () => this.falando.set(true);
      fala.onend = () => this.falando.set(false);
      fala.onerror = () => this.falando.set(false);
      this.falando.set(true);
      sintese.speak(fala);
      return true;
    } catch {
      this.falando.set(false);
      return false;
    }
  }

  parar(): void {
    try {
      this.win?.speechSynthesis?.cancel();
    } catch {
      /* ignora */
    }
    this.falando.set(false);
  }

  private escolherVoz(): Livre {
    try {
      const vozes: Livre[] = this.win.speechSynthesis.getVoices?.() ?? [];
      const escolhida = this.prefs.prefs().voz;
      return (
        (escolhida ? vozes.find((v) => (v.voiceURI ?? v.name) === escolhida) : null) ??
        vozes.find((v) => v.lang?.toLowerCase().replace('_', '-') === 'pt-br') ??
        vozes.find((v) => v.lang?.toLowerCase().startsWith('pt')) ??
        null
      );
    } catch {
      return null;
    }
  }

  /** Escuta uma frase e devolve o texto reconhecido. */
  escutar(): Promise<string> {
    const Reconhecedor = this.win?.SpeechRecognition || this.win?.webkitSpeechRecognition;
    if (!Reconhecedor) return Promise.reject(new ErroVoz('nao-suportado'));
    return new Promise<string>((resolve, reject) => {
      let texto = '';
      const r = new Reconhecedor();
      this.reconhecimento = r;
      r.lang = 'pt-BR';
      r.interimResults = false;
      r.maxAlternatives = 1;
      r.onresult = (e: Livre) => {
        texto = e.results?.[0]?.[0]?.transcript ?? '';
      };
      r.onerror = (e: Livre) => {
        this.ouvindo.set(false);
        const erro = e?.error;
        reject(
          new ErroVoz(
            erro === 'not-allowed' || erro === 'service-not-allowed'
              ? 'sem-permissao'
              : erro === 'no-speech'
                ? 'nada-ouvido'
                : 'falha',
          ),
        );
      };
      r.onend = () => {
        this.ouvindo.set(false);
        this.reconhecimento = null;
        if (texto) resolve(texto);
        else reject(new ErroVoz('nada-ouvido'));
      };
      try {
        this.ouvindo.set(true);
        r.start();
      } catch {
        this.ouvindo.set(false);
        reject(new ErroVoz('falha'));
      }
    });
  }

  pararEscuta(): void {
    try {
      this.reconhecimento?.stop();
    } catch {
      /* ignora */
    }
  }
}
