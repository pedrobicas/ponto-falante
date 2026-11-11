import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { expect, it } from 'vitest';
import { PontoPage } from '../app/features/ponto/ponto';

it('apresenta horario estimado sem afirmar chegada ou atribuir simulacao a SPTrans', async () => {
  TestBed.configureTestingModule({ imports: [PontoPage], providers: [
    provideHttpClient(), provideHttpClientTesting(), provideRouter([]),
  ] });
  const fixture = TestBed.createComponent(PontoPage);
  fixture.componentRef.setInput('codigo', '700001234');
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne(r => r.url.includes('/previsoes')).flush({
    ponto: { codigo: 700001234, nome: 'Paulista', fonte: 'SIMULADO' },
    fonte: 'SIMULADO', tipo: 'PREVISAO', consultado_em: '2026-11-11T12:00:00-03:00',
    onibus: [{ letreiro: '8000-10', destino: 'Lapa', previsto_em: '12:00', minutos: 0, acessivel: true }],
    frase_falada: 'Demonstracao. Onibus previsto para agora.',
  });
  await fixture.whenStable();
  fixture.detectChanges();
  const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
  fixture.destroy();
  http.verify();
  expect(texto).toContain('Previsto agora');
  expect(texto).not.toContain('Chegando');
  expect(texto).toContain('horários simulados');
});
