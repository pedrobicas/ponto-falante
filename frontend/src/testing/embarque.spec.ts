import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import axe from 'axe-core';
import { afterEach, describe, expect, it } from 'vitest';
import { AnunciadorEmbarque } from '../app/core/anunciador-embarque';
import { acharFavorito, extrairLinha, interpretar } from '../app/core/comandos-embarque';
import { AssistenteEmbarque } from '../app/core/assistente-embarque.service';
import { EmbarqueStore } from '../app/core/embarque.store';
import { OnibusPrevisto } from '../app/core/models';
import { EmbarquePage } from '../app/features/embarque/embarque';
import { ConferirLetreiro } from '../app/features/embarque/conferir-letreiro';

afterEach(() => TestBed.resetTestingModule());
const providers = () => [provideHttpClient(), provideHttpClientTesting(), provideRouter([])];
const axeOpcoes = { rules: { 'color-contrast': { enabled: false }, region: { enabled: false } } };

function bus(minutos: number, veiculo = 'A', letreiro = '8000-10'): OnibusPrevisto {
  return { letreiro, destino: 'Lapa', previsto_em: '2026-11-16T10:00:00-03:00', minutos, acessivel: true, veiculo };
}

describe('avisos por voz do acompanhamento', () => {
  it('fala no início, nos marcos de 10, 5 e 3 minutos e ao chegar, sem repetir', () => {
    const a = new AnunciadorEmbarque();
    const linhas = ['8000-10'];
    const falas = [12, 11, 10, 9, 8, 6, 5, 4, 3, 2, 1, 1, 0].map((m) => a.avaliar({ onibus: [bus(m)], simulado: false }, linhas));
    const tipos = falas.map((f) => f?.tipo ?? null);
    expect(tipos).toEqual(['inicio', null, 'marco', null, null, null, 'marco', null, 'marco', null, 'chegando', null, null]);
    expect(falas[0]!.texto).toContain('em 12 minutos');
    expect(falas[10]!.urgente).toBe(true);
    expect(falas[10]!.texto).toContain('confirme a linha com o motorista');
  });

  it('não anuncia marcos acima da previsão inicial e avisa atraso relevante', () => {
    const a = new AnunciadorEmbarque();
    expect(a.avaliar({ onibus: [bus(7)], simulado: false }, ['8000-10'])?.tipo).toBe('inicio');
    expect(a.avaliar({ onibus: [bus(6)], simulado: false }, ['8000-10'])).toBeNull();
    expect(a.avaliar({ onibus: [bus(5)], simulado: false }, ['8000-10'])?.tipo).toBe('marco');
    const atraso = a.avaliar({ onibus: [bus(9)], simulado: false }, ['8000-10']);
    expect(atraso?.tipo).toBe('atraso');
    expect(atraso?.texto).toContain('em 9 minutos');
    // Depois do atraso, o marco de 5 minutos volta a valer.
    expect(a.avaliar({ onibus: [bus(5)], simulado: false }, ['8000-10'])?.tipo).toBe('marco');
  });

  it('avisa que o ônibus que chegava pode ter passado quando some da previsão', () => {
    const a = new AnunciadorEmbarque();
    a.avaliar({ onibus: [bus(2, 'A')], simulado: false }, ['8000-10']);
    a.avaliar({ onibus: [bus(1, 'A')], simulado: false }, ['8000-10']);
    const troca = a.avaliar({ onibus: [bus(14, 'B')], simulado: false }, ['8000-10']);
    expect(troca?.tipo).toBe('troca');
    expect(troca?.urgente).toBe(true);
    expect(troca?.texto).toContain('pode ter passado');
  });

  it('sem previsão fala uma vez; falhas só depois de duas seguidas e avisa quando volta', () => {
    const a = new AnunciadorEmbarque();
    const sem = a.avaliar({ onibus: [], simulado: true }, ['8000-10']);
    expect(sem?.tipo).toBe('sem-previsao');
    expect(sem?.texto.startsWith('Demonstração com horários simulados.')).toBe(true);
    expect(a.avaliar({ onibus: [], simulado: true }, ['8000-10'])).toBeNull();
    expect(a.falhou()).toBeNull();
    expect(a.falhou()?.tipo).toBe('falha');
    expect(a.falhou()).toBeNull();
    expect(a.avaliar({ onibus: [bus(8)], simulado: true }, ['8000-10'])?.tipo).toBe('troca');
    expect(a.ultimo).toContain('Apareceu uma previsão');
  });

  it('nunca inventa horário: o texto usa só os minutos recebidos', () => {
    const a = new AnunciadorEmbarque();
    const f = a.avaliar({ onibus: [bus(17)], simulado: false }, ['8000-10'])!;
    expect(f.texto.match(/\d+ minutos?/g)).toEqual(['17 minutos']);
  });
});

describe('comandos falados ou digitados', () => {
  it.each([
    ['Sim', 'sim'], ['não', 'nao'], ['repete', 'repetir'], ['quanto falta?', 'quanto-falta'],
    ['já embarquei', 'embarquei'], ['parar o acompanhamento', 'parar'], ['desliga a voz', 'silenciar'],
    ['pontos perto de mim', 'perto'], ['conferir o letreiro', 'conferir-camera'], ['quais são meus favoritos', 'listar-favoritos'],
    ['trocar de ponto', 'trocar-ponto'], ['o que você pode fazer?', 'ajuda'],
  ])('"%s" vira %s', (frase, tipo) => {
    expect(interpretar(frase).tipo).toBe(tipo);
  });

  it('entende linhas faladas e códigos de ponto', () => {
    expect(extrairLinha('quero pegar o 875a')).toBe('875A');
    expect(extrairLinha('8000 traco 10')).toBe('8000-10');
    expect(extrairLinha('ponto 990007')).toBeUndefined();
    expect(interpretar('quero pegar o 8000-10 no ponto 990007')).toEqual({ tipo: 'acompanhar', linha: '8000-10', ponto: 990007 });
    expect(interpretar('estou no ponto Avenida Paulista')).toEqual({ tipo: 'buscar-ponto', termo: 'avenida paulista' });
    expect(interpretar('o segundo')).toEqual({ tipo: 'escolher', indice: 2 });
  });

  it('salvar e usar favoritos por apelido', () => {
    expect(interpretar('salvar nos favoritos como trabalho')).toEqual({ tipo: 'salvar-favorito', apelido: 'trabalho' });
    expect(interpretar('ir para o trabalho')).toEqual({ tipo: 'usar-favorito', alvo: 'trabalho' });
    const favs = [
      { apelido: 'Trabalho', linha: '8000-10', ponto_nome: 'Av. Paulista' },
      { apelido: null, linha: '875A-10', ponto_nome: 'Rua da Consolação' },
    ];
    expect(acharFavorito(favs, 'trabalho')).toHaveLength(1);
    expect(acharFavorito(favs, '875a')[0].linha).toBe('875A-10');
    expect(acharFavorito(favs, 'consolacao')).toHaveLength(1);
    expect(acharFavorito(favs, 'praia')).toHaveLength(0);
  });

  it('pergunta livre vai para o assistente geral', () => {
    expect(interpretar('Tenho direito a gratuidade?')).toEqual({ tipo: 'pergunta', texto: 'Tenho direito a gratuidade?' });
  });
});

describe('assistente do embarque', () => {
  it('pede confirmação antes de encerrar e não faz nada sem acompanhamento', async () => {
    TestBed.configureTestingModule({ providers: providers() });
    const assistente = TestBed.inject(AssistenteEmbarque);
    const store = TestBed.inject(EmbarqueStore);
    store.alternarVoz(false);
    await assistente.enviar('parar o acompanhamento');
    expect(assistente.mensagens().at(-1)?.texto).toBe('Não há acompanhamento em andamento.');
    await assistente.enviar('sim');
    expect(assistente.mensagens().at(-1)?.texto).toBe('Não há nada esperando confirmação agora.');
    await assistente.enviar('salvar nos favoritos');
    expect(assistente.mensagens().at(-1)?.texto).toContain('Primeiro escolha o ponto e a linha');
    expect(assistente.confirmando()).toBeNull();
  });

  it('busca o ponto, pede confirmação e lista as linhas com previsão real da API', async () => {
    TestBed.configureTestingModule({ providers: providers() });
    const assistente = TestBed.inject(AssistenteEmbarque);
    const store = TestBed.inject(EmbarqueStore);
    store.alternarVoz(false);
    store.modoForcado.set('demo');
    const http = TestBed.inject(HttpTestingController);

    const busca = assistente.enviar('estou no ponto Paulista');
    await Promise.resolve();
    http.expectOne((r) => r.url === '/api/pontos').flush({ fonte: 'SIMULADO', pontos: [
      { codigo: 990001, nome: 'Av. Paulista, 1000', endereco: 'Av. Paulista, 1000', latitude: -23.56, longitude: -46.65, fonte: 'SIMULADO' },
    ] });
    await busca;
    expect(assistente.mensagens().at(-1)?.texto).toContain('É este?');
    expect(store.ponto()?.codigo).toBe(990001);

    const confirma = assistente.enviar('sim');
    for (let i = 0; i < 5; i++) await Promise.resolve();
    http.match((r) => r.url === '/api/pontos/990001/linhas').forEach((r) => r.flush({ codigo: 990001, fonte: 'SIMULADO', linhas: [] }));
    for (let i = 0; i < 5; i++) await Promise.resolve();
    http.match((r) => r.url === '/api/pontos/990001/previsoes').forEach((r) =>
      r.flush({ ponto: { codigo: 990001, nome: 'Av. Paulista, 1000', fonte: 'SIMULADO' }, fonte: 'SIMULADO', consultado_em: '2026-11-16T10:00:00-03:00', horario_referencia: '2026-11-16T10:00:00-03:00',
        onibus: [bus(6)], frase_falada: '' }));
    await confirma;
    const ultima = assistente.mensagens().at(-1)!.texto;
    expect(ultima).toContain('Ponto confirmado');
    expect(ultima).toContain('8000-10 sentido Lapa');
    expect(ultima).toContain('6 minutos');
  });
});

describe('tela de embarque', () => {
  it('abre na escolha do ponto com etapas, GPS e busca acessíveis', async () => {
    TestBed.configureTestingModule({ imports: [EmbarquePage], providers: providers() });
    const fixture = TestBed.createComponent(EmbarquePage);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.match('/api/embarque/favoritos').forEach((r) => r.flush([]));
    http.match('/api/embarque/sessoes/atual').forEach((r) => r.flush(null, { status: 204, statusText: 'No Content' }));
    http.match('/api/status').forEach((r) => r.flush({ sptrans: 'DEMO', assistente: 'INDISPONIVEL' }));
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toBeTruthy();
    expect(el.querySelector('[aria-current="step"]')?.textContent).toContain('Ponto');
    expect(el.textContent).toContain('perto de mim');
    expect(el.querySelector('pf-assistente-embarque [role="log"]')).not.toBeNull();
    const resultado = await axe.run(el, axeOpcoes);
    expect(resultado.violations.map((v) => v.id)).toEqual([]);
    fixture.destroy();
  });

  it('câmera não conectada é honesta: não abre a câmera nem mostra resultado inventado', async () => {
    TestBed.configureTestingModule({ imports: [ConferirLetreiro], providers: providers() });
    const fixture = TestBed.createComponent(ConferirLetreiro);
    fixture.componentRef.setInput('linha', '8000-10');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/embarque/visao').flush({ conectada: false, mensagem: 'A conferência do letreiro pela câmera ainda não está conectada.' });
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('ainda não está conectada');
    expect(el.textContent).toContain('Indisponível agora');
    expect(el.querySelector('video:not(.camera__video--oculto)')).toBeNull();
    expect(el.querySelector('.camera__resultado')).toBeNull();
    const resultado = await axe.run(el, axeOpcoes);
    expect(resultado.violations.map((v) => v.id)).toEqual([]);
    fixture.destroy();
  });
  it('conectada: tira outra foto sozinha quando não deu para ler e fala só o resultado final', async () => {
    TestBed.configureTestingModule({ imports: [ConferirLetreiro], providers: providers() });
    const fixture = TestBed.createComponent(ConferirLetreiro);
    fixture.componentRef.setInput('linha', '875A-10');
    fixture.componentRef.setInput('sessao', 's-1');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/embarque/visao').flush({ conectada: true, mensagem: 'Aponte a câmera para o letreiro da frente do ônibus.' });
    await fixture.whenStable();
    fixture.detectChanges();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const c = fixture.componentInstance as any;
    c.esperaEntreFotosMs = 0;
    c.aberta.set(true);
    c.capturar = async () => new Blob(['x'], { type: 'image/jpeg' });
    const video = fixture.nativeElement.querySelector('video') as HTMLVideoElement;
    Object.defineProperty(video, 'videoWidth', { value: 1280 });
    const falas: string[] = [];
    TestBed.inject(EmbarqueStore).dizer = (t: string) => { falas.push(t); };
    const fim = c.conferir();
    const responder = async (corpo: object) => {
      for (let i = 0; i < 20; i++) {
        const pend = http.match('/api/embarque/visao/conferir');
        if (pend.length) { pend[0].flush(corpo); return; }
        await new Promise((ok) => setTimeout(ok, 0));
      }
      throw new Error('a conferência não foi enviada');
    };
    await responder({ resultado: 'INCONCLUSIVO', linha_esperada: '875A-10', linha_lida: null, confianca: null,
      frase_falada: 'Encontrei o letreiro, mas não consegui ler o número da linha.', modelo: 'pf-visao 1.0.0', latencia_ms: 900 });
    await responder({ resultado: 'CONFERE', linha_esperada: '875A-10', linha_lida: '875A-10', confianca: 0.81,
      frase_falada: 'O letreiro parece ser da linha 875A-10, a que você espera. Confirme com o motorista antes de embarcar.',
      modelo: 'pf-visao 1.0.0', latencia_ms: 850 });
    await fim;
    fixture.detectChanges();
    http.verify();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.camera__resultado')?.getAttribute('data-resultado')).toBe('CONFERE');
    expect(el.textContent).toContain('pf-visao 1.0.0');
    expect(falas).toEqual(['O letreiro parece ser da linha 875A-10, a que você espera. Confirme com o motorista antes de embarcar.']);
    const resultado = await axe.run(el, axeOpcoes);
    expect(resultado.violations.map((v) => v.id)).toEqual([]);
    fixture.destroy();
  });
  it('enviar uma foto: reduz no aparelho, confere uma vez só e recusa arquivo que não é imagem', async () => {
    TestBed.configureTestingModule({ imports: [ConferirLetreiro], providers: providers() });
    const fixture = TestBed.createComponent(ConferirLetreiro);
    fixture.componentRef.setInput('linha', '647P-10');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/embarque/visao').flush({ conectada: true, mensagem: 'ok' });
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const botao = [...el.querySelectorAll('button')].find((b) => b.textContent?.includes('Enviar uma foto do letreiro'));
    expect(botao).toBeTruthy();
    expect(el.querySelector('input[type=file]')?.getAttribute('accept')).toContain('image/jpeg');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const c = fixture.componentInstance as any;
    const falas: string[] = [];
    TestBed.inject(EmbarqueStore).dizer = (t: string) => { falas.push(t); };

    await c.conferirArquivo(new Blob(['%PDF'], { type: 'application/pdf' }));
    fixture.detectChanges();
    expect(el.textContent).toContain('Escolha uma foto');
    http.expectNone('/api/embarque/visao/conferir');

    const reduzidas: Blob[] = [];
    c.reduzir = async (b: Blob) => { reduzidas.push(b); return new Blob(['jpeg'], { type: 'image/jpeg' }); };
    const fim = c.conferirArquivo(new Blob(['png'], { type: 'image/png' }));
    let enviadas = 0;
    for (let i = 0; i < 20 && !enviadas; i++) {
      const pend = http.match('/api/embarque/visao/conferir');
      enviadas = pend.length;
      if (enviadas) {
        expect(pend[0].request.body instanceof FormData).toBe(true);
        expect((pend[0].request.body as FormData).get('linha_esperada')).toBe('647P-10');
        pend[0].flush({ resultado: 'INCONCLUSIVO', linha_esperada: '647P-10', linha_lida: null, confianca: null,
          frase_falada: 'Não consegui ler o letreiro com segurança.', modelo: 'pf-visao 1.0.0', latencia_ms: 3200 });
      } else {
        await new Promise((ok) => setTimeout(ok, 0));
      }
    }
    await fim;
    fixture.detectChanges();
    http.verify();
    expect(enviadas).toBe(1);
    expect(reduzidas.length).toBe(1);
    expect(el.querySelector('.camera__resultado')?.getAttribute('data-resultado')).toBe('INCONCLUSIVO');
    expect(falas).toEqual(['Não consegui ler o letreiro com segurança.']);
    const resultado = await axe.run(el, axeOpcoes);
    expect(resultado.violations.map((v) => v.id)).toEqual([]);
    fixture.destroy();
  });
});
