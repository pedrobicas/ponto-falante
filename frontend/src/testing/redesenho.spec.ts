import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import axe from 'axe-core';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { origemDaResposta, RespostaChat } from '../app/core/models';
import { Assistente, respostaSimulada } from '../app/features/assistente/assistente';
import { naturezaDaLinha } from '../app/features/boletim/boletim';
import { Busca } from '../app/features/busca/busca';
import { Inicio } from '../app/features/inicio/inicio';
import { PontoPage, fraseOnibus } from '../app/features/ponto/ponto';

const AXE = { rules: { 'color-contrast': { enabled: false }, region: { enabled: false } } };

function provedores() {
  return [provideHttpClient(), provideHttpClientTesting(), provideRouter([])];
}

beforeEach(() => {
  try {
    localStorage.clear();
  } catch {
    /* sem armazenamento */
  }
});

describe('Origem das respostas do assistente', () => {
  it('sem o campo origem, vale BASE_OFICIAL quando disponível e INDISPONIVEL quando não', () => {
    expect(origemDaResposta({ disponivel: true })).toBe('BASE_OFICIAL');
    expect(origemDaResposta({ disponivel: false })).toBe('INDISPONIVEL');
    expect(origemDaResposta({ disponivel: true, origem: 'TEMPO_REAL' })).toBe('TEMPO_REAL');
  });

  it('tempo real com dados de demonstração é marcado como simulado', () => {
    const r: RespostaChat = {
      resposta: 'x', fontes: [{ documento: 'Dados simulados (demonstração)', trecho_id: '' }], confianca: 'alta',
      nao_consta: false, disponivel: true, origem: 'TEMPO_REAL',
    };
    expect(respostaSimulada(r, false)).toBe(true);
    expect(respostaSimulada({ ...r, fontes: [] }, true)).toBe(true);
    expect(respostaSimulada({ ...r, fontes: [] }, false)).toBe(false);
    expect(respostaSimulada({ ...r, origem: 'BASE_OFICIAL' }, true)).toBe(false);
  });
});

describe('Assistente', () => {
  let http: HttpTestingController;
  afterEach(() => TestBed.resetTestingModule());

  async function montar(status: object) {
    TestBed.configureTestingModule({ imports: [Assistente], providers: provedores() });
    const fixture = TestBed.createComponent(Assistente);
    fixture.detectChanges();
    http = TestBed.inject(HttpTestingController);
    http.match('/api/status').forEach((r) => r.flush(status));
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  async function perguntar(fixture: Awaited<ReturnType<typeof montar>>, pergunta: string, resposta: object) {
    const c = fixture.componentInstance as unknown as { texto: string; enviar(): Promise<void> };
    c.texto = pergunta;
    const envio = c.enviar();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Consultando as fontes');
    http.expectOne('/api/chat').flush(resposta);
    await envio;
    fixture.detectChanges();
  }

  it('mostra disponibilidade parcial com clareza', async () => {
    const fixture = await montar({ sptrans: 'DEMO', assistente: 'INDISPONIVEL', assistente_tempo_real: true });
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Responde sobre horários em tempo real; dúvidas gerais indisponíveis no momento');
    fixture.destroy();
  });

  it('resposta de tempo real simulada exibe SIMULADO e a lista de fontes', async () => {
    const fixture = await montar({ sptrans: 'DEMO', assistente: 'INDISPONIVEL', assistente_tempo_real: true });
    await perguntar(fixture, 'Quando passa o ônibus no ponto 990001?', {
      resposta: 'Atenção: dados simulados. Linha 8000-10, previsto em 7 minutos.',
      fontes: [{ documento: 'Dados simulados (demonstração)', trecho_id: '' }],
      confianca: 'alta', nao_consta: false, disponivel: true, latencia_ms: 3, origem: 'TEMPO_REAL',
    });
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.origem--simulado')?.textContent).toContain('SIMULADO');
    expect(el.querySelectorAll('.citacoes__lista li').length).toBe(1);
    const r = await axe.run(el, AXE);
    expect(r.violations.map((v) => v.id)).toEqual([]);
    fixture.destroy();
  });

  it('base oficial com "não consta" mostra o aviso e o selo de origem', async () => {
    const fixture = await montar({ sptrans: 'REAL', assistente: 'DISPONIVEL', assistente_tempo_real: true });
    await perguntar(fixture, 'Posso levar bicicleta?', {
      resposta: 'Não encontrei essa regra.', fontes: [], confianca: 'baixa', nao_consta: true, disponivel: true,
    });
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.origem--base-oficial')).not.toBeNull();
    expect(el.textContent).toContain('Não consta nas fontes oficiais consultadas');
    fixture.destroy();
  });
});

describe('Ponto e busca', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('frase do painel diz "previsto", nunca chegada', () => {
    const f = fraseOnibus({ letreiro: '8000-10', destino: 'Lapa', previsto_em: '12:05', minutos: 5, acessivel: true });
    expect(f).toContain('previsto em 5 minutos');
    expect(f).not.toMatch(/cheg/i);
  });

  it('salvar ponto alterna aria-pressed e passa a aparecer no início', async () => {
    TestBed.configureTestingModule({ imports: [PontoPage], providers: provedores() });
    const fixture = TestBed.createComponent(PontoPage);
    fixture.componentRef.setInput('codigo', '990001');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne((r) => r.url.includes('/previsoes')).flush({
      ponto: { codigo: 990001, nome: 'Paulista', fonte: 'OLHO_VIVO' }, fonte: 'OLHO_VIVO', tipo: 'PREVISAO',
      consultado_em: '2026-11-11T12:00:00-03:00',
      onibus: [{ letreiro: '875A-10', destino: 'Perdizes', previsto_em: '12:03', minutos: 3, acessivel: false }],
      frase_falada: 'Linha 875A-10, previsto em 3 minutos.',
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Dados da SPTrans');
    expect(el.textContent).not.toContain('SIMULADO');
    const botao = el.querySelector<HTMLButtonElement>('.botao--favorito')!;
    expect(botao.getAttribute('aria-pressed')).toBe('false');
    botao.click();
    fixture.detectChanges();
    expect(botao.getAttribute('aria-pressed')).toBe('true');
    const r = await axe.run(el, AXE);
    expect(r.violations.map((v) => v.id)).toEqual([]);
    fixture.destroy();

    const inicio = TestBed.createComponent(Inicio);
    inicio.detectChanges();
    expect((inicio.nativeElement as HTMLElement).querySelector('.paradas--favoritas')?.textContent).toContain('Paulista');
    inicio.destroy();
  });

  it('busca de linhas usa /api/linhas e mostra o letreiro', async () => {
    TestBed.configureTestingModule({ imports: [Busca], providers: provedores() });
    const fixture = TestBed.createComponent(Busca);
    fixture.componentRef.setInput('q', '8000');
    fixture.componentRef.setInput('tipo', 'linhas');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    const req = http.expectOne((r) => r.url === '/api/linhas');
    expect(req.request.params.get('busca')).toBe('8000');
    req.flush({ fonte: 'SIMULADO', linhas: [{ letreiro: '8000-10', terminal_principal: 'Pq. Dom Pedro', terminal_secundario: 'Lapa', destino: 'Lapa', circular: false }] });
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.letreiro')?.textContent).toContain('8000-10');
    expect(el.textContent).toContain('SIMULADO');
    const r = await axe.run(el, AXE);
    expect(r.violations.map((v) => v.id)).toEqual([]);
    fixture.destroy();
  });

  it('busca curta mostra erro de validação sem chamar a API', async () => {
    TestBed.configureTestingModule({ imports: [Busca], providers: provedores() });
    const fixture = TestBed.createComponent(Busca);
    fixture.detectChanges();
    const c = fixture.componentInstance as unknown as { texto: string; enviar(): void };
    c.texto = 'a';
    c.enviar();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('#termo-erro')?.textContent).toContain('pelo menos 2');
    expect(el.querySelector('#termo')?.getAttribute('aria-invalid')).toBe('true');
    TestBed.inject(HttpTestingController).verify();
    fixture.destroy();
  });
});

describe('Boletim: natureza dos dados', () => {
  it('distingue estimativa de previsões, simulado e indisponível', () => {
    // A consulta é real, mas não comprova que o ônibus passou ou atrasou.
    expect(naturezaDaLinha({ linha: 'a', status: 'OK', frase: '', fontes: ['olhovivo'] }, false)).toBe('estimado');
    expect(naturezaDaLinha({ linha: 'a', status: 'OK', frase: '', fontes: ['simulador'] }, false)).toBe('simulado');
    expect(naturezaDaLinha({ linha: 'a', status: 'SEM_DADOS', frase: '', fontes: ['olhovivo'] }, false)).toBe('indisponivel');
    expect(naturezaDaLinha({ linha: 'a', status: 'CRITICA', frase: '' }, true)).toBe('simulado');
  });
});
