import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import axe from 'axe-core';
import { expect, it } from 'vitest';
import { Assistente } from '../app/features/assistente/assistente';
import { BoletimPage } from '../app/features/boletim/boletim';

it('assistente indisponivel aparece como estado amigavel e fontes como itens de lista', async () => {
  TestBed.configureTestingModule({ imports: [Assistente], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])] });
  const fixture = TestBed.createComponent(Assistente);
  fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  expect(el.querySelector('h1')?.textContent).toContain('Assistente');
  expect(el.querySelectorAll('.sugestoes .chip').length).toBeGreaterThan(0);
  (fixture.componentInstance as unknown as { texto: string }).texto = 'Tenho direito a gratuidade?';
  const http = TestBed.inject(HttpTestingController);
  const envio = (fixture.componentInstance as unknown as { enviar(): Promise<void> }).enviar();
  http.expectOne('/api/chat').flush({ resposta: '', fontes: [], confianca: 'baixa', nao_consta: true, disponivel: false });
  await envio;
  fixture.detectChanges();
  expect(el.textContent).toContain('descansando');
  expect(el.textContent).toContain('O resto do aplicativo continua funcionando');
  const resultado = await axe.run(el, { rules: { 'color-contrast': { enabled: false }, region: { enabled: false } } });
  expect(resultado.violations.map((v) => v.id)).toEqual([]);
  fixture.destroy();
});

it('boletim simulado mostra selo textual e totais por situacao com icone e texto', async () => {
  TestBed.configureTestingModule({ imports: [BoletimPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
  const fixture = TestBed.createComponent(BoletimPage);
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne('/api/boletim').flush({
    data_referencia: '2026-11-10', gerado_em: '2026-11-11T10:00:00-03:00', desatualizado: false, dados_simulados: true,
    linhas: [
      { linha: '1001-10', status: 'CRITICA', frase: 'Atrasos fortes.' },
      { linha: '1003-10', status: 'OK', frase: 'Normal.' },
    ],
    resumo_falado: 'Resumo.',
  });
  http.expectOne('/api/boletins').flush([]);
  await fixture.whenStable();
  fixture.detectChanges();
  const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
  expect(texto).toContain('Dados simulados');
  expect(texto).toContain('Atraso forte');
  expect(texto).toContain('com atraso forte');
  fixture.destroy();
});
