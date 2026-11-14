import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { afterEach, expect, it } from 'vitest';
import { Assistente } from '../app/features/assistente/assistente';
import { LinhaPage } from '../app/features/linha/linha';
import { ConversaService } from '../app/core/conversa.service';

const providers = () => [provideHttpClient(), provideHttpClientTesting(), provideRouter([])];
afterEach(() => TestBed.resetTestingModule());

it('envia contexto devolvido pelo servidor, mantém histórico na navegação e limpa ambos', async () => {
  TestBed.configureTestingModule({ imports: [Assistente], providers: providers() });
  const f = TestBed.createComponent(Assistente); f.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.match('/api/status').forEach(r => r.flush({ sptrans: 'REAL', assistente: 'DISPONIVEL' }));
  const c = f.componentInstance as any;
  c.texto = '5317-10'; const primeira = c.enviar();
  http.expectOne('/api/chat').flush({ resposta: 'Escolha o sentido.', fontes: [], confianca: 'alta', nao_consta: false, disponivel: true, origem: 'CADASTRO', contexto: { linha: '5317-10', sentido: 1 } });
  await primeira;
  c.texto = 'e o próximo?'; const segunda = c.enviar();
  const req = http.expectOne('/api/chat');
  expect(req.request.body.contexto).toEqual({ linha: '5317-10', sentido: 1 });
  req.flush({ resposta: 'Qual ponto?', fontes: [], confianca: 'alta', nao_consta: false, disponivel: true, contexto: { linha: '5317-10', pendencia: 'PONTO_PREVISAO' } });
  await segunda; f.destroy();
  const nova = TestBed.createComponent(Assistente); nova.detectChanges();
  expect(nova.nativeElement.textContent).toContain('Qual ponto?');
  (nova.componentInstance as any).limpar();
  expect(TestBed.inject(ConversaService).contexto()).toBeNull();
  expect(TestBed.inject(ConversaService).mensagens()).toEqual([]);
});

it('ações de sentido contrário e próximo ônibus enviam o contexto atualizado sem o ponto da ida', async () => {
  TestBed.configureTestingModule({ imports: [Assistente], providers: providers() });
  const f = TestBed.createComponent(Assistente); f.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.match('/api/status').forEach(r => r.flush({ sptrans: 'REAL', assistente: 'DISPONIVEL' }));
  const memoria = TestBed.inject(ConversaService);
  memoria.contexto.set({ ponto: 160015580, linha: '5317-10', sentido: 1 });
  const c = f.componentInstance as any;
  c.texto = 'e no sentido contrário?'; const volta = c.enviar();
  http.expectOne('/api/chat').flush({ resposta: 'Escolha uma parada da volta.', fontes: [], confianca: 'alta', nao_consta: false, disponivel: true, origem: 'CADASTRO', contexto: { ponto: null, linha: '5317-10', sentido: 2 }, acoes: [{ titulo: 'Próximo ônibus', pergunta: 'e o próximo?' }] });
  await volta; f.detectChanges();
  const botao = Array.from(f.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>).find(b => b.textContent?.trim() === 'Próximo ônibus')!;
  botao.click(); f.detectChanges();
  const req = http.expectOne('/api/chat');
  expect(req.request.body).toEqual({ pergunta: 'e o próximo?', contexto: { ponto: null, linha: '5317-10', sentido: 2 } });
  expect(f.nativeElement.querySelector('button[type=submit]').disabled).toBe(true);
  req.flush({ resposta: 'Qual ponto da volta?', fontes: [], confianca: 'alta', nao_consta: false, disponivel: true, contexto: { ponto: null, linha: '5317-10', sentido: 2, pendencia: 'PONTO_PREVISAO' } });
  await f.whenStable(); f.detectChanges();
  expect(f.nativeElement.textContent).toContain('Qual ponto da volta?');
  expect(f.nativeElement.querySelector('.compositor__contexto').textContent).not.toContain('160015580');
});

it.each(['SIMULADO', 'INDISPONIVEL'])('boletim %s no chat não recebe selo de estimativa oficial', async (natureza) => {
  TestBed.configureTestingModule({ imports: [Assistente], providers: providers() });
  const f = TestBed.createComponent(Assistente); f.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.match('/api/status').forEach(r => r.flush({ sptrans: 'REAL', assistente: 'PARCIAL' }));
  const c = f.componentInstance as any;
  c.texto = 'O que diz o boletim?'; const p = c.enviar();
  http.expectOne('/api/chat').flush({ resposta: 'Boletim do robô.', fontes: [], confianca: 'baixa', nao_consta: false, disponivel: true, origem: 'BOLETIM', natureza_dados: natureza });
  await p; f.detectChanges();
  const selo = f.nativeElement.querySelector('.fala--assistente pf-origem').textContent;
  expect(selo).toContain(natureza === 'SIMULADO' ? 'SIMULADO' : 'Indisponível');
  expect(selo).not.toContain('estimativa do robô');
});

async function linha() {
  TestBed.configureTestingModule({ imports: [LinhaPage], providers: providers() });
  const f = TestBed.createComponent(LinhaPage); f.componentRef.setInput('letreiro', '5317-10'); f.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  const paradas = Array.from({ length: 73 }, (_, i) => ({ codigo: 160000000 + i, nome: i === 30 ? 'Paulista, 1000' : `Rua ${i}`, fonte: 'GTFS_SPTRANS' }));
  http.expectOne('/api/linhas/5317-10/paradas').flush({ fonte: 'GTFS_SPTRANS', letreiro: '5317-10', sentidos: [{ sentido: 1, destino: 'Praça do Correio', nome_linha: 'Linha', paradas }, { sentido: 2, destino: 'Bairro', nome_linha: 'Linha', paradas: paradas.slice().reverse() }] });
  await f.whenStable(); f.detectChanges();
  return { f, http, c: f.componentInstance as any };
}

it('filtra todas as 73 paradas sem acentos, conserva posição e oferece expansão', async () => {
  const { f, c } = await linha();
  expect(f.nativeElement.querySelectorAll('.parada').length).toBe(15);
  c.filtrar('Paulista, 1000'); f.detectChanges();
  expect(f.nativeElement.querySelectorAll('.parada').length).toBe(1);
  expect(f.nativeElement.querySelector('.parada__ordem').textContent).toBe('31');
  c.filtrar('inexistente'); f.detectChanges();
  expect(f.nativeElement.textContent).toContain('Nenhuma parada encontrada');
  c.filtrar(''); c.limite.set(30); f.detectChanges();
  expect(f.nativeElement.querySelectorAll('.parada').length).toBe(30);
});

it('seleção consulta previsões e ignora resposta atrasada de outro sentido', async () => {
  const { f, c, http } = await linha();
  const promessa = c.selecionar(c.atual().paradas[0]);
  const req = http.expectOne('/api/pontos/160000000/previsoes');
  c.escolher(2);
  req.flush({ onibus: [{ letreiro: '5317-10', sentido: 1, minutos: 1 }], fonte: 'OLHO_VIVO' });
  await promessa; f.detectChanges();
  expect(c.selecionada()).toBeNull(); expect(c.previsao()).toBeNull();
  expect(f.nativeElement.querySelector('.linha__selecionada')).toBeNull();
});

it('previsões mostram só a linha e sentido selecionados e distinguem falha de ausência', async () => {
  const { f, c, http } = await linha();
  const promessa = c.selecionar(c.atual().paradas[0]);
  http.expectOne('/api/pontos/160000000/previsoes').flush({ onibus: [{ letreiro: '5317-10', sentido: 1, minutos: 5 }, { letreiro: '5317-10', sentido: 2, minutos: 1 }], fonte: 'OLHO_VIVO', horario_referencia: '10:30' });
  await promessa; f.detectChanges(); expect(c.onibus()).toHaveLength(1);
  const atualizar = c.selecionar(c.selecionada());
  http.expectOne('/api/pontos/160000000/previsoes').flush({}, { status: 503, statusText: 'Indisponível' });
  await atualizar; f.detectChanges();
  expect(f.nativeElement.textContent).toContain('A SPTrans não respondeu');
  expect(f.nativeElement.textContent).not.toContain('Sem previsão');
});
