import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { afterEach, expect, it } from 'vitest';
import { routes } from '../app/app.routes';
import { FavoritosService } from '../app/core/favoritos.service';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PontoPage } from '../app/features/ponto/ponto';
import { App } from '../app/app';
import { StatusService } from '../app/core/status.service';

afterEach(() => TestBed.resetTestingModule());

it('navegação preserva somente modo demo, sem carregar busca antiga entre destinos', async () => {
  TestBed.configureTestingModule({ imports: [App], providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()] });
  const fixture = TestBed.createComponent(App); fixture.detectChanges();
  TestBed.inject(HttpTestingController).match('/api/status').forEach(r => r.flush({sptrans:'REAL',assistente:'INDISPONIVEL'}));
  await TestBed.inject(Router).navigateByUrl('/favoritos?modo=demo&q=Paulista');
  fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  expect(el.querySelector('nav a')?.getAttribute('href')).toBe('/?modo=demo');
  fixture.destroy();
});

it('favoritos têm destino próprio e permitem remover um ponto sem abrir a previsão', async () => {
  const route = routes.find(r => r.path === 'favoritos');
  expect(route, 'Favoritos precisam estar disponíveis pela navegação').toBeDefined();
  const component = await route!.loadComponent!() as any;
  TestBed.configureTestingModule({ imports: [component], providers: [provideRouter([])] });
  const store = TestBed.inject(FavoritosService);
  if (!store.eFavorito(987654)) store.alternar({ codigo: 987654, nome: 'Ponto de teste' });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  expect(el.querySelector('a[href="/ponto/987654"]')).toBeTruthy();
  const remove = el.querySelector('button[aria-label="Remover Ponto de teste dos favoritos"]') as HTMLButtonElement;
  expect(remove).toBeTruthy();
  remove.focus();
  remove.click(); fixture.detectChanges();
  expect(store.eFavorito(987654)).toBe(false);
  expect(el.querySelector('[role="status"]')?.textContent).toContain('removido');
  expect(document.activeElement).toBe(el.querySelector('h1'));
  fixture.destroy();
});

it('previsões mostram primeiro seis ônibus e permitem filtrar uma linha sem perder os demais', async () => {
  TestBed.configureTestingModule({ imports: [PontoPage], providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
  const fixture = TestBed.createComponent(PontoPage);
  fixture.componentRef.setInput('codigo', '123'); fixture.detectChanges();
  TestBed.inject(HttpTestingController).expectOne(r => r.url.includes('/previsoes')).flush({
    ponto: {codigo: 123, nome: 'Ponto', fonte: 'SIMULADO'}, fonte: 'SIMULADO', tipo: 'PREVISAO', consultado_em: '2026-11-12T12:00:00-03:00', frase_falada: 'Previsões simuladas',
    onibus: Array.from({length: 9}, (_,i) => ({letreiro: i % 2 ? '8000-10' : '7000-10', destino:'Centro', minutos:i+1, previsto_em:'12:10', acessivel:true, veiculo:String(i)})),
  });
  await fixture.whenStable(); fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  expect(el.querySelectorAll('.partida')).toHaveLength(6);
  (el.querySelector('.quadro__mais button') as HTMLButtonElement).click(); fixture.detectChanges();
  expect(el.querySelectorAll('.partida')).toHaveLength(9);
  const select = el.querySelector('#filtro-linha') as HTMLSelectElement;
  select.value = '8000-10'; select.dispatchEvent(new Event('change')); fixture.detectChanges();
  expect(el.querySelectorAll('.partida')).toHaveLength(4);
  expect(el.querySelector('.quadro__lista')?.textContent).not.toContain('7000-10');
  select.value = ''; select.dispatchEvent(new Event('change')); fixture.detectChanges();
  expect(el.querySelectorAll('.partida')).toHaveLength(6);
  fixture.destroy();
});


it('filtro avisa quando uma linha deixa de ter previsões após atualização e permite voltar', async () => {
  TestBed.configureTestingModule({ imports: [PontoPage], providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
  const fixture = TestBed.createComponent(PontoPage);
  fixture.componentRef.setInput('codigo', '123'); fixture.detectChanges();
  const resposta = {
    ponto: { codigo: 123, nome: 'Ponto', fonte: 'SIMULADO' as const },
    fonte: 'SIMULADO' as const, tipo: 'PREVISAO' as const,
    consultado_em: '2026-11-12T12:00:00-03:00', frase_falada: 'Previsões simuladas',
    onibus: [
      { letreiro: '7000-10', destino: 'Centro', minutos: 3, previsto_em: '12:03', acessivel: true },
      { letreiro: '8000-10', destino: 'Lapa', minutos: 5, previsto_em: '12:05', acessivel: true },
    ],
  };
  TestBed.inject(HttpTestingController).expectOne(r => r.url.includes('/previsoes')).flush(resposta);
  await fixture.whenStable(); fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  const filtro = el.querySelector('#filtro-linha') as HTMLSelectElement;
  filtro.value = '8000-10'; filtro.dispatchEvent(new Event('change')); fixture.detectChanges();
  expect(el.querySelectorAll('.partida')).toHaveLength(1);

  // Atualização ao vivo: a linha 8000 deixou de aparecer no ponto.
  (fixture.componentInstance as any).dados.set({ ...resposta, onibus: [resposta.onibus[0]] });
  fixture.detectChanges();
  expect(el.querySelector('.quadro__sem-linha')?.textContent).toContain('Nenhum ônibus da linha 8000-10');
  expect(el.querySelectorAll('.partida')).toHaveLength(0);
  const restaurar = Array.from(el.querySelectorAll('button')).find(b => b.textContent?.includes('Mostrar todas as linhas'))!;
  restaurar.click(); fixture.detectChanges();
  expect(el.querySelectorAll('.partida')).toHaveLength(1);
  fixture.destroy();
});

it('a falha da checagem recente não anuncia assistente antigo como disponível', () => {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  const status = TestBed.inject(StatusService);
  status.status.set({ sptrans: 'REAL', assistente: 'DISPONIVEL', assistente_tempo_real: true });
  expect(status.assistente()).toBe('disponivel');
  status.falhou.set(true);
  expect(status.assistente()).toBe('indisponivel');
});
