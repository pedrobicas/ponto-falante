import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, expect, it } from 'vitest';
import { FavoritosService } from '../app/core/favoritos.service';
import { RecentesService } from '../app/core/recentes.service';
import { erroHttpInterceptor } from '../app/core/erro.interceptor';
import { Favoritos } from '../app/features/favoritos/favoritos';
import { BoletimPage } from '../app/features/boletim/boletim';

beforeEach(() => {
  localStorage.removeItem('pf.favoritos');
  localStorage.removeItem('pf.recentes');
});
afterEach(() => {
  TestBed.resetTestingModule();
  localStorage.removeItem('pf.favoritos');
  localStorage.removeItem('pf.recentes');
});

it('preserva favoritos antigos e não descarta o primeiro ao salvar o décimo terceiro', () => {
  localStorage.setItem('pf.favoritos', JSON.stringify([{ codigo: 1, nome: 'Legado' }]));
  const store = TestBed.inject(FavoritosService);
  for (let codigo = 2; codigo <= 13; codigo++) store.alternar({ codigo, nome: 'Ponto ' + codigo });
  expect(store.lista()).toHaveLength(13);
  expect(store.eFavorito(1)).toBe(true);
  TestBed.resetTestingModule();
  expect(TestBed.inject(FavoritosService).lista()).toHaveLength(13);
});

it('mantém favoritos reais e simulados separados mesmo com o mesmo código', () => {
  const store = TestBed.inject(FavoritosService);
  store.alternar({ codigo: 123, nome: 'Real', modo: 'auto' });
  store.alternar({ codigo: 123, nome: 'Simulado', modo: 'demo' });
  expect(store.lista()).toHaveLength(2);
  store.alternar({ codigo: 123, nome: 'Simulado', modo: 'demo' });
  expect(store.eFavorito(123)).toBe(true);
  expect(store.eFavorito(123, 'demo')).toBe(false);
});

it('recentes persistem a origem e não substituem o ponto real por seu exemplo simulado', () => {
  const store = TestBed.inject(RecentesService);
  store.adicionar({ codigo: 123, nome: 'Real', modo: 'auto' });
  store.adicionar({ codigo: 123, nome: 'Simulado', modo: 'demo' });
  TestBed.resetTestingModule();
  expect(TestBed.inject(RecentesService).lista().map(p => p.modo)).toEqual(['demo', 'auto']);
});

it('favoritos usam o modo do item, independente do modo da página', () => {
  TestBed.configureTestingModule({ imports: [Favoritos], providers: [provideRouter([])] });
  const store = TestBed.inject(FavoritosService);
  store.alternar({ codigo: 123, nome: 'Real', modo: 'auto' });
  store.alternar({ codigo: 123, nome: 'Simulado', modo: 'demo' });
  const fixture = TestBed.createComponent(Favoritos);
  fixture.componentRef.setInput('modo', 'demo');
  fixture.detectChanges();
  const links = [...fixture.nativeElement.querySelectorAll('.parada__link')] as HTMLAnchorElement[];
  expect(links.map(a => a.getAttribute('href'))).toEqual(['/ponto/123', '/ponto/123?modo=demo']);
  expect(links[1].textContent).toContain('SIMULADO');
  fixture.destroy();
});

const boletim = {
  data_referencia: '2026-11-11', gerado_em: '2026-11-12T06:00:00-03:00',
  dados_simulados: true, desatualizado: false, natureza_dados: 'ESTIMADO', resumo_falado: 'Resumo.',
  linhas: [
    { linha: '8000-10', status: 'CRITICA', classificacao: 'ESTIMADO', espera_tipica_min: 22,
      maior_espera_prevista_min: 38, amostras: 2, frase: 'Espera estimada.' },
    { linha: '9000-10', status: 'CRITICA', classificacao: 'SIMULADO', atraso_medio_min: 7,
      intervalo_max_min: 12, passagens: 4, rotulo: 'Atraso simulado', frase: 'Exemplo simulado.' },
  ],
};

function prepararBoletim() {
  TestBed.configureTestingModule({ imports: [BoletimPage], providers: [
    provideHttpClient(withInterceptors([erroHttpInterceptor])), provideHttpClientTesting(), provideRouter([]),
  ] });
  const fixture = TestBed.createComponent(BoletimPage);
  fixture.detectChanges();
  return { fixture, http: TestBed.inject(HttpTestingController) };
}

it('boletim misto apresenta métricas e rótulos próprios para cada linha', async () => {
  const { fixture, http } = prepararBoletim();
  http.expectOne('/api/boletim').flush(boletim);
  http.expectOne('/api/boletins').flush([]);
  await fixture.whenStable(); fixture.detectChanges();
  const registros = fixture.nativeElement.querySelectorAll('.registro') as NodeListOf<HTMLElement>;
  expect(registros[0].textContent).toContain('Espera típica');
  expect(registros[0].textContent).toContain('22 min');
  expect(registros[1].textContent).toContain('Atraso médio');
  expect(registros[1].textContent).toContain('7 min');
  expect(registros[1].textContent).toContain('Atraso simulado');
  expect(registros[1].textContent).not.toContain('Espera típica');
  expect(fixture.nativeElement.querySelector('.placar__lista').textContent).toContain('em situação crítica');
  expect(fixture.nativeElement.querySelector('.placar__lista').textContent).not.toContain('com espera longa');
  http.verify(); fixture.destroy();
});

it('resumo de boletim somente estimado descreve espera, nunca atraso observado', async () => {
  const { fixture, http } = prepararBoletim();
  http.expectOne('/api/boletim').flush({ ...boletim, dados_simulados: false, linhas: [boletim.linhas[0]] });
  http.expectOne('/api/boletins').flush([]);
  await fixture.whenStable(); fixture.detectChanges();
  const resumo = fixture.nativeElement.querySelector('.placar__lista').textContent;
  expect(resumo).toContain('com espera longa');
  expect(resumo).not.toContain('atraso');
  http.verify(); fixture.destroy();
});

it('falha do histórico não se apresenta como histórico vazio e pode ser repetida', async () => {
  const { fixture, http } = prepararBoletim();
  http.expectOne('/api/boletim').flush(boletim);
  http.expectOne('/api/boletins').flush({}, { status: 503, statusText: 'Unavailable' });
  await fixture.whenStable(); fixture.detectChanges();
  const historico = fixture.nativeElement.querySelector('.anteriores') as HTMLElement;
  expect(historico.textContent).toContain('Não foi possível consultar o histórico');
  expect(historico.textContent).not.toContain('Nenhum boletim anterior');
  historico.querySelector<HTMLButtonElement>('button')!.click();
  http.expectOne('/api/boletins').flush([]);
  await fixture.whenStable(); fixture.detectChanges();
  expect(historico.textContent).toContain('Nenhum boletim anterior');
  http.verify(); fixture.destroy();
});

it('repetir erro de edição histórica consulta a mesma data e distingue 404 de primeira publicação', async () => {
  const { fixture, http } = prepararBoletim();
  http.expectOne('/api/boletim').flush(boletim);
  http.expectOne('/api/boletins').flush([{ data_referencia: '2026-11-10', criticas: 0, atencao: 0 }]);
  await fixture.whenStable(); fixture.detectChanges();
  fixture.nativeElement.querySelector('.anteriores button').click();
  http.expectOne('/api/boletim/2026-11-10').flush({}, { status: 503, statusText: 'Unavailable' });
  await fixture.whenStable(); fixture.detectChanges();
  fixture.nativeElement.querySelector('pf-erro button').click();
  http.expectOne('/api/boletim/2026-11-10').flush({}, { status: 404, statusText: 'Not Found' });
  await fixture.whenStable(); fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('não encontrado');
  expect(fixture.nativeElement.textContent).not.toContain('Nenhum boletim publicado ainda');
  fixture.nativeElement.querySelector('.vazio button').click();
  http.expectOne('/api/boletim').flush(boletim);
  await fixture.whenStable();
  http.verify(); fixture.destroy();
});
