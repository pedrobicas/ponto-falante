import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { afterEach, expect, it, vi } from 'vitest';
import { BoletimPage, naturezaDaLinha } from '../app/features/boletim/boletim';
import { PontoPage } from '../app/features/ponto/ponto';
import { Assistente } from '../app/features/assistente/assistente';
import { SpeechService } from '../app/core/speech.service';
import { PreferencesService } from '../app/core/preferences.service';

afterEach(() => TestBed.resetTestingModule());
const providers = () => [provideHttpClient(), provideHttpClientTesting(), provideRouter([])];

it('previsões SPTrans não viram passagens reais e origem ausente não vira real', () => {
  expect(naturezaDaLinha({ linha: '8000', status: 'OK', frase: '', fontes: ['olhovivo'] }, false)).toBe('estimado');
  expect(naturezaDaLinha({ linha: '8000', status: 'OK', frase: '' }, false)).toBe('indisponivel');
});

it('boletim apresenta medidas de espera, período observado e cobertura de consultas', async () => {
  TestBed.configureTestingModule({ imports: [BoletimPage], providers: providers() });
  const fixture = TestBed.createComponent(BoletimPage);
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne('/api/boletim').flush({
    data_referencia: '2026-11-11', gerado_em: '2026-11-12T06:00:00-03:00', desatualizado: false,
    natureza_dados: 'ESTIMADO', dados_simulados: false, fonte_dados: { olhovivo: 2 },
    periodo_referencia: { inicio: '07:00', fim: '13:00', fuso: 'America/Sao_Paulo' },
    amostragem: { consultas_validas: 2, consultas_esperadas: 8, cobertura_pct: 25 },
    linhas: [{ linha: '8000-10', status: 'CRITICA', classificacao: 'ESTIMADO', atraso_medio_min: null,
      espera_tipica_min: 22, maior_espera_prevista_min: 38, amostras: 2, frase: 'Espera longa prevista.' }],
    resumo_falado: 'Estimativas de espera.',
  });
  http.expectOne('/api/boletins').flush([]);
  await fixture.whenStable(); fixture.detectChanges();
  const text = (fixture.nativeElement as HTMLElement).textContent!;
  expect(text).toContain('Espera típica');
  expect(text).toContain('22 min');
  expect(text).toContain('07:00'); expect(text).toContain('13:00');
  expect(text).toContain('25%');
  expect(text).not.toContain('dia inteiro');
  expect(text).not.toContain('Atraso médio');
  expect(text).not.toContain('passagens');
  expect(text).toContain('Espera longa');
  fixture.destroy();
});

it('previsão atrasada da rota anterior não substitui o novo ponto', async () => {
  TestBed.configureTestingModule({ imports: [PontoPage], providers: providers() });
  const fixture = TestBed.createComponent(PontoPage);
  const http = TestBed.inject(HttpTestingController);
  fixture.componentRef.setInput('codigo', '1'); fixture.detectChanges();
  const old = http.expectOne(r => r.url.includes('/pontos/1/'));
  fixture.componentRef.setInput('codigo', '2'); fixture.detectChanges();
  const current = http.expectOne(r => r.url.includes('/pontos/2/'));
  const payload = (codigo: number) => ({ ponto: { codigo, nome: `Ponto ${codigo}`, fonte: 'OLHO_VIVO' },
    fonte: 'OLHO_VIVO', tipo: 'PREVISAO', consultado_em: '2026-11-11T12:34:00-03:00', onibus: [], frase_falada: '' });
  current.flush(payload(2)); await fixture.whenStable();
  old.flush(payload(1)); await fixture.whenStable(); fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('h1').textContent).toBe('Ponto 2');
  expect(fixture.nativeElement.textContent).toContain('12:34');
  fixture.destroy();
});

it('limpar conversa pendente impede leitura de uma resposta removida', async () => {
  TestBed.configureTestingModule({ imports: [Assistente], providers: providers() });
  const fixture = TestBed.createComponent(Assistente); fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.match('/api/status').forEach(r => r.flush({ sptrans: 'REAL', assistente: 'DISPONIVEL' }));
  const speak = vi.spyOn(TestBed.inject(SpeechService), 'falar');
  const c = fixture.componentInstance as any;
  TestBed.inject(PreferencesService).atualizar({ lerRespostaAuto: true }); c.texto = 'Como funciona?';
  const sent = c.enviar(); c.limpar();
  http.expectOne('/api/chat').flush({ resposta: 'Resposta removida', fontes: [], confianca: 'alta', nao_consta: false, disponivel: true });
  await sent;
  expect(speak).not.toHaveBeenCalled();
  fixture.destroy();
});
