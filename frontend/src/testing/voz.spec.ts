import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SpeechService } from '../app/core/speech.service';
import { PreferencesService } from '../app/core/preferences.service';

class Fala {
  lang = ''; rate = 1; voice: unknown;
  onstart?: () => void; onend?: () => void; onerror?: () => void;
  constructor(public text: string) {}
}

describe('Contrato de reproducao por voz', () => {
  let win: Record<string, unknown>;
  beforeEach(() => {
    win = {};
    TestBed.configureTestingModule({ providers: [
      { provide: DOCUMENT, useValue: { defaultView: win } },
      { provide: PreferencesService, useValue: { prefs: () => ({ velocidadeVoz: 0.8 }) } },
    ] });
  });

  it('degrada sem voz disponivel e mantem estado parado', () => {
    const voz = TestBed.inject(SpeechService);
    expect(voz.falar('Previsao de onibus.')).toBe(false);
    expect(voz.falando()).toBe(false);
  });

  it('usa pt-BR, preferencia de velocidade e encerra o estado ao terminar', () => {
    const speak = vi.fn();
    win['speechSynthesis'] = { speak, cancel: vi.fn(), getVoices: () => [{ lang: 'en-US' }, { lang: 'pt-BR' }] };
    win['SpeechSynthesisUtterance'] = Fala;
    const voz = TestBed.inject(SpeechService);
    expect(voz.falar('  Previsao em tres minutos.  ')).toBe(true);
    const fala = speak.mock.calls[0][0] as Fala;
    expect(fala.text).toBe('Previsao em tres minutos.');
    expect(fala.lang).toBe('pt-BR');
    expect(fala.rate).toBe(0.8);
    expect(fala.voice).toEqual({ lang: 'pt-BR' });
    expect(voz.falando()).toBe(true);
    fala.onend?.();
    expect(voz.falando()).toBe(false);
  });

  it('falha do sintetizador libera controles sem lancar erro', () => {
    win['speechSynthesis'] = { speak: () => { throw new Error('dispositivo'); }, cancel: vi.fn() };
    win['SpeechSynthesisUtterance'] = Fala;
    const voz = TestBed.inject(SpeechService);
    expect(voz.falar('Previsao.')).toBe(false);
    expect(voz.falando()).toBe(false);
  });

  it('reconhecimento sem permissao devolve erro tratavel pela interface', async () => {
    win['SpeechRecognition'] = class {
      onerror?: (e: { error: string }) => void;
      start() { this.onerror?.({ error: 'not-allowed' }); }
    };
    const voz = TestBed.inject(SpeechService);
    await expect(voz.escutar()).rejects.toMatchObject({ codigo: 'sem-permissao' });
    expect(voz.ouvindo()).toBe(false);
  });
});
