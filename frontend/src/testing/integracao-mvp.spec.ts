import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import axe from 'axe-core';
import { App } from '../app/app';
import { ApiService } from '../app/core/api.service';
import { erroHttpInterceptor } from '../app/core/erro.interceptor';

describe('Contratos HTTP do MVP', () => {
  let api: ApiService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [
      provideHttpClient(withInterceptors([erroHttpInterceptor])), provideHttpClientTesting(),
    ] });
    api = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('busca pontos na mesma origem e preserva o modo demonstrativo', async () => {
    const resposta = firstValueFrom(api.buscarPontos('Afonso Braz', 'demo'));
    const req = http.expectOne(r => r.url === '/api/pontos');
    expect(req.request.params.get('busca')).toBe('Afonso Braz');
    expect(req.request.params.get('modo')).toBe('demo');
    req.flush({ fonte: 'SIMULADO', pontos: [] });
    expect((await resposta).fonte).toBe('SIMULADO');
  });

  it('modo automatico permite ao backend escolher a SPTrans', async () => {
    const resposta = firstValueFrom(api.buscarPontos('Afonso', 'auto'));
    const req = http.expectOne(r => r.url === '/api/pontos');
    expect(req.request.params.has('modo')).toBe(false);
    req.flush({ fonte: 'OLHO_VIVO', pontos: [] });
    expect((await resposta).fonte).toBe('OLHO_VIVO');
  });

  it('envia ao Spring apenas a pergunta do assistente', async () => {
    const resposta = firstValueFrom(api.perguntar('Tenho direito a gratuidade?'));
    const req = http.expectOne('/api/chat');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ pergunta: 'Tenho direito a gratuidade?' });
    expect(req.request.headers.has('X-API-Key')).toBe(false);
    req.flush({ resposta: 'Indisponivel.', fontes: [], confianca: 'baixa', nao_consta: true, disponivel: false });
    expect((await resposta).disponivel).toBe(false);
  });

  it('traduz falha SPTrans preservando o codigo publico', async () => {
    const resposta = firstValueFrom(api.buscarPontos('Afonso'));
    const resultado = expect(resposta).rejects.toMatchObject({ status: 503, codigo: 'SPTRANS_INDISPONIVEL' });
    http.expectOne(r => r.url === '/api/pontos').flush(
      { mensagem: 'Servico temporariamente indisponivel.', codigo: 'SPTRANS_INDISPONIVEL' },
      { status: 503, statusText: 'Service Unavailable' },
    );
    await resultado;
  });

  it('consulta o boletim por data sob /api', async () => {
    const resposta = firstValueFrom(api.boletimDaData('2026-11-10'));
    http.expectOne('/api/boletim/2026-11-10').flush({ data_referencia: '2026-11-10', linhas: [] });
    expect((await resposta).data_referencia).toBe('2026-11-10');
  });
});

describe('Estrutura acessivel do aplicativo', () => {
  it('oferece landmarks, navegacao rotulada e link para pular ao conteudo', async () => {
    TestBed.configureTestingModule({ imports: [App], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('nav[aria-label="Principal"]')).not.toBeNull();
    expect(el.querySelector('a[href="#conteudo"]')).not.toBeNull();
    expect(el.querySelector('main#conteudo')).not.toBeNull();
    const resultado = await axe.run(el, { rules: { 'color-contrast': { enabled: false } } });
    expect(resultado.violations.map(v => v.id)).toEqual([]);
    fixture.destroy();
  });
});
