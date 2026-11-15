import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { RespostaChat, tipoDaResposta } from '../app/core/models';
import { Assistente, situacaoEmPalavras } from '../app/features/assistente/assistente';

/** Regressão da auditoria de 15/11: recusa com "confiança alta" e pergunta de outra cidade mandada ao 156. */

const base: RespostaChat = { resposta: 'x', fontes: [], confianca: 'alta', nao_consta: false, disponivel: true };

beforeEach(() => {
  try { localStorage.clear(); } catch { /* sem armazenamento */ }
});

describe('Tipo da resposta', () => {
  it('recusa com confiança alta da GenAI vira RECUSA e não diz "confiança alta"', () => {
    const r = { ...base, nao_consta: true, origem: 'BASE_OFICIAL' as const };
    expect(tipoDaResposta(r)).toBe('RECUSA');
    expect(situacaoEmPalavras(r)).not.toMatch(/confiança alta|está nas fontes/i);
  });

  it('distingue fundamentada, consulta, insuficiente, fora da área e indisponível', () => {
    const fonte = [{ documento: 'Lei 10.741', trecho_id: 'lei-1' }];
    expect(tipoDaResposta({ ...base, fontes: fonte, origem: 'BASE_OFICIAL' })).toBe('FUNDAMENTADA');
    expect(tipoDaResposta({ ...base, origem: 'BASE_OFICIAL' })).toBe('INSUFICIENTE');
    expect(tipoDaResposta({ ...base, fontes: fonte, confianca: 'baixa', origem: 'BASE_OFICIAL' })).toBe('INSUFICIENTE');
    expect(tipoDaResposta({ ...base, origem: 'TEMPO_REAL' })).toBe('CONSULTA');
    expect(tipoDaResposta({ ...base, nao_consta: true, origem: 'FORA_DA_AREA' })).toBe('FORA_DA_AREA');
    expect(tipoDaResposta({ ...base, disponivel: false })).toBe('INDISPONIVEL');
    expect(tipoDaResposta({ ...base, tipo_resposta: 'RECUSA' })).toBe('RECUSA');
  });

  it('previsão da SPTrans é descrita como consulta, não como chegada', () => {
    expect(situacaoEmPalavras({ ...base, origem: 'TEMPO_REAL' })).toContain('Previsão não é chegada confirmada');
  });

  it('resposta antiga de tempo real indisponível vira INDISPONIVEL, como no backend', () => {
    expect(tipoDaResposta({ ...base, origem: 'TEMPO_REAL', disponivel: false })).toBe('INDISPONIVEL');
  });

  it('consulta simulada não é descrita como dado da SPTrans', () => {
    const texto = situacaoEmPalavras({ ...base, origem: 'CADASTRO' }, true);
    expect(texto).toMatch(/simulados/);
    expect(texto).not.toMatch(/SPTrans/);
  });

  it('consulta sem dados (confiança baixa) não aparece como confiável', () => {
    const texto = situacaoEmPalavras({ ...base, origem: 'BOLETIM', confianca: 'baixa' });
    expect(texto).toMatch(/sem dados suficientes/);
  });
});

describe('Assistente: recusa e fora da área', () => {
  let http: HttpTestingController;
  afterEach(() => TestBed.resetTestingModule());

  async function perguntar(pergunta: string, resposta: object) {
    TestBed.configureTestingModule({
      imports: [Assistente], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(Assistente);
    fixture.detectChanges();
    http = TestBed.inject(HttpTestingController);
    http.match('/api/status').forEach((r) => r.flush({ sptrans: 'REAL', assistente: 'DISPONIVEL', assistente_tempo_real: true }));
    await fixture.whenStable();
    const c = fixture.componentInstance as unknown as { texto: string; enviar(): Promise<void> };
    c.texto = pergunta;
    const envio = c.enviar();
    fixture.detectChanges();
    http.expectOne('/api/chat').flush(resposta);
    await envio;
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('recusa da base oficial mostra o aviso de "não consta" e nunca confiança alta', async () => {
    const el = await perguntar('Posso levar bicicleta?', {
      resposta: 'Não encontrei essa informação nas fontes oficiais.', fontes: [], confianca: 'alta', nao_consta: true,
      disponivel: true, origem: 'BASE_OFICIAL', tipo_resposta: 'RECUSA',
    });
    expect(el.textContent).toContain('Não consta nas fontes oficiais consultadas');
    expect(el.textContent).not.toMatch(/Confiança alta/);
    expect(el.querySelector('.confianca')?.getAttribute('data-tipo')).toBe('RECUSA');
    expect(el.querySelector('.confianca--alta')).toBeNull();
  });

  it('pergunta sobre Curitiba mostra a limitação de área, sem 156 nem SPTrans no aviso', async () => {
    const el = await perguntar('Posso levar meu cachorro no ônibus em Curitiba?', {
      resposta: 'O Ponto Falante atende só o transporte público municipal da cidade de São Paulo e não tem informações '
        + 'oficiais sobre Curitiba. Para saber as regras de lá, consulte o órgão ou a empresa responsável pelo transporte público de Curitiba.',
      fontes: [], confianca: 'baixa', nao_consta: true, disponivel: true, origem: 'FORA_DA_AREA', tipo_resposta: 'FORA_DA_AREA',
    });
    const aviso = el.querySelector('.nao-consta')?.textContent ?? '';
    expect(aviso).toContain('Fora da área atendida');
    expect(aviso).not.toContain('156');
    expect(aviso).not.toContain('SPTrans');
    expect(el.textContent).not.toContain('Não consta nas fontes oficiais consultadas');
  });
});
