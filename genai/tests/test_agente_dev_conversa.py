"""Novos testes DEV de fundamentação/contrato; nenhum item de avaliação final é lido."""
from types import SimpleNamespace

import numpy as np
import pytest

from pf_genai import agente, indice
from pf_genai.trechos import Trecho


@pytest.fixture
def base():
    t = Trecho("dev-001", "dev", "Fonte de desenvolvimento", "https://www.sptrans.com.br/", "O veículo possui rampa de acesso.")
    return SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=t, score=0.95)])


def executar(monkeypatch, base, tri=None, geracao=None, verificacao=None):
    def gerar(sistema, *args, **kwargs):
        if sistema == agente.SISTEMA_TRIAGEM:
            return tri if tri is not None else {"no_escopo": True, "consulta": "rampa de acesso"}
        if sistema == agente.SISTEMA_VERIFICACAO:
            return verificacao if verificacao is not None else {"suportada": True, "problema": ""}
        return geracao if geracao is not None else {"resposta": "O veículo possui rampa de acesso.", "trechos_usados": ["dev-001"], "nao_consta": False}
    monkeypatch.setattr(agente.llm, "gerar_json", gerar)
    return agente.responder("Tem rampa?", base).resposta


@pytest.mark.parametrize("tri", [{}, [], {"no_escopo": "false", "consulta": None}])
def test_triagem_malformada_continua_com_consulta_original(monkeypatch, base, tri):
    assert not executar(monkeypatch, base, tri=tri).nao_consta


@pytest.mark.parametrize("verificacao", [{}, [], {"suportada": "true", "problema": ""}, {"suportada": False, "problema": "não comprovado"}])
def test_verificacao_invalida_nunca_aprova(monkeypatch, base, verificacao):
    assert executar(monkeypatch, base, verificacao=verificacao).nao_consta


@pytest.mark.parametrize("citacoes", [[], ["inventada"], ["dev-001", "inventada"], [123]])
def test_citacao_ausente_ou_invalida_nao_recebe_fonte_automatica(monkeypatch, base, citacoes):
    r = executar(monkeypatch, base, geracao={"resposta": "Há rampa.", "nao_consta": False, "trechos_usados": citacoes})
    assert r.nao_consta and not r.fontes


def test_url_vem_do_cadastro_do_trecho(monkeypatch, base):
    assert executar(monkeypatch, base).fontes[0].url == "https://www.sptrans.com.br/"


def test_sigla_rg_nao_causa_recusa_por_diferenca_de_vocabulario(monkeypatch):
    t = Trecho('dev-001', 'dev', 'Fonte', '', 'Apresente documento pessoal que comprove a idade.')
    base = SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=t, score=.95)])
    def gerar(sistema, usuario, *args, **kwargs):
        if sistema == agente.SISTEMA_TRIAGEM:
            return {'no_escopo': True, 'consulta': usuario}
        if sistema == agente.SISTEMA_VERIFICACAO:
            return {'suportada': True, 'problema': ''}
        if ' RG' in usuario:
            return {'resposta': 'Não consta.', 'nao_consta': True, 'trechos_usados': []}
        return {'resposta': 'Apresente um documento de identidade que comprove a idade.', 'nao_consta': False, 'trechos_usados': ['dev-001']}
    monkeypatch.setattr(agente.llm, 'gerar_json', gerar)
    assert not agente.responder('Posso apresentar meu RG?', base).resposta.nao_consta


def test_numero_do_titulo_nao_sustenta_valor_da_resposta(monkeypatch):
    t = Trecho('dev-001', 'dev', 'Cartão 65+', '', 'A segunda via é gratuita.')
    base = SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=t, score=.95)])
    r = executar(monkeypatch, base, geracao={'resposta': 'Custa 65 reais.', 'nao_consta': False, 'trechos_usados': ['dev-001']})
    assert r.nao_consta and not r.fontes


def test_reescrita_nao_substitui_idade_da_pessoa(monkeypatch):
    certo = Trecho('dev-063', 'dev', 'Fonte', '', 'A pessoa com 60 a 64 anos usa o cartão comum.')
    errado = Trecho('dev-065', 'dev', 'Fonte', '', 'A pessoa com 65 anos pode usar documento de identidade.')
    pergunta = 'Tenho 63 e quero gratuidade no ônibus.'
    base = SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=certo if q == pergunta else errado, score=.95)])
    def gerar(sistema, usuario, *args, **kwargs):
        if sistema == agente.SISTEMA_TRIAGEM:
            return {'no_escopo': True, 'consulta': 'gratuidade pessoa com 65 anos'}
        if sistema == agente.SISTEMA_VERIFICACAO:
            return {'suportada': True, 'problema': ''}
        if 'dev-065' in usuario:
            return {'resposta': 'Pode usar documento de identidade.', 'nao_consta': False, 'trechos_usados': ['dev-065']}
        return {'resposta': 'Use o cartão comum.', 'nao_consta': False, 'trechos_usados': ['dev-063']}
    monkeypatch.setattr(agente.llm, 'gerar_json', gerar)
    r = agente.responder(pergunta, base).resposta
    assert [f.trecho_id for f in r.fontes] == ['dev-063']


def test_subtipo_escolar_nao_sustenta_negacao_geral_de_acompanhante(monkeypatch):
    t = Trecho('dev-001', 'sptrans-bilhete-pcd', 'Pessoa com deficiência', '',
               'O que é o cartão com Acompanhante Cadastrado?\nPermite ao responsável do estudante viajar sem o titular para a instituição de ensino.')
    base = SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=t, score=.95)])
    monkeypatch.setattr(agente.llm, 'gerar_json', lambda sistema, *args, **kwargs:
                        {'no_escopo': True, 'consulta': 'gratuidade acompanhante'} if sistema == agente.SISTEMA_TRIAGEM else
                        {'suportada': True, 'problema': ''} if sistema == agente.SISTEMA_VERIFICACAO else
                        {'resposta': 'O acompanhante não tem gratuidade.', 'nao_consta': False, 'trechos_usados': ['dev-001']})
    r = agente.responder('O acompanhante da pessoa com deficiência tem gratuidade?', base).resposta
    assert r.nao_consta and not r.fontes


def test_acompanhante_orienta_confirmacao_do_beneficio_sem_negar_direito(monkeypatch):
    t = Trecho('dev-001', 'sptrans-bilhete-pcd', 'Fonte PCD', 'https://www.sptrans.com.br/',
               'Tenho o benefício com direito a acompanhante. Preciso girar a catraca duas vezes?\nA presença do acompanhante é opcional.')
    base = SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=t, score=.95)])
    monkeypatch.setattr(agente.llm, 'gerar_json', lambda sistema, *args, **kwargs:
                        {'no_escopo': True, 'consulta': 'gratuidade acompanhante pessoa com deficiência'} if sistema == agente.SISTEMA_TRIAGEM else
                        {'resposta': 'Não consta.', 'nao_consta': True, 'trechos_usados': []})
    r = agente.responder('O acompanhante da pessoa com deficiência tem gratuidade?', base).resposta
    assert not r.nao_consta
    assert 'direito a acompanhante' in r.resposta and 'confir' in r.resposta.lower()
    assert [f.trecho_id for f in r.fontes] == ['dev-001']


@pytest.mark.parametrize('pergunta,doc', [
    ('Meu cartão comum funciona no metrô?', 'sptrans-bilhete-pcd'),
    ('Tenho 63 e quero gratuidade', 'sptrans-gratuidade-65-mais'),
    ('Tenho 69 anos e quero gratuidade', 'sptrans-gratuidade-60-64'),
    ('Sobre gratuidade para pessoa idosa: e o acompanhante?', 'sptrans-bilhete-pcd'),
])
def test_publico_diferente_nao_e_evidencia(pergunta, doc):
    t = Trecho('dev-001', doc, 'Fonte', '', 'Regras de um benefício específico.')
    assert not agente.fonte_compativel(pergunta, t)


def test_comparacao_entre_publicos_nao_exclui_fontes_pertinentes():
    t = Trecho('dev-001', 'sptrans-bilhete-pcd', 'Fonte', '', 'Regras de um benefício específico.')
    assert agente.fonte_compativel('Sou pessoa com deficiência e tenho 68 anos, qual benefício usar?', t)


def test_transicao_do_cartao_comum_para_beneficio_por_idade_tem_fontes():
    t = Trecho('dev-001', 'sptrans-gratuidade-65-mais', 'Fonte', '', 'Solicite o cartão ao completar 65 anos.')
    assert agente.fonte_compativel('Estou perto dos 65 e uso gratuidade no Bilhete Único comum. O que muda ao completar a idade?', t)


def test_beneficio_com_acompanhante_ja_declarado_nao_repergunta(monkeypatch):
    t = Trecho('dev-001', 'sptrans-bilhete-pcd', 'Fonte PCD', '',
               'Tenho o benefício com direito a acompanhante. A presença do acompanhante é opcional.')
    base = SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=t, score=.95)])
    monkeypatch.setattr(agente.llm, 'gerar_json', lambda sistema, *args, **kwargs:
                        {'no_escopo': True, 'consulta': 'benefício PCD acompanhante opcional'} if sistema == agente.SISTEMA_TRIAGEM else
                        {'suportada': True, 'problema': ''} if sistema == agente.SISTEMA_VERIFICACAO else
                        {'resposta': 'A presença do acompanhante é opcional.', 'nao_consta': False, 'trechos_usados': ['dev-001']})
    r = agente.responder('Sou PCD e já tenho benefício com direito a acompanhante. Sem acompanhante ainda tenho gratuidade?', base).resposta
    assert r.resposta == 'A presença do acompanhante é opcional.'


def test_aviso_de_outra_faixa_etaria_nao_e_aplicado_ao_publico_da_pergunta(monkeypatch):
    t = Trecho('dev-001', 'sptrans-gratuidade-65-mais', 'Fonte 65+', '',
               'O cartão especial é usado por pessoas de 65 anos ou mais.\nPessoas com 60 a 64 anos devem carregar o benefício no cartão comum.')
    base = SimpleNamespace(buscar=lambda q, k: [SimpleNamespace(trecho=t, score=.95)])
    def gerar(sistema, usuario, *args, **kwargs):
        if sistema == agente.SISTEMA_TRIAGEM: return {'no_escopo': True, 'consulta': 'gratuidade 68 anos'}
        if sistema == agente.SISTEMA_VERIFICACAO: return {'suportada': True, 'problema': ''}
        return {'resposta': 'Carregue o benefício no cartão comum.' if 'Pessoas com 60 a 64' in usuario else 'O cartão especial é usado por pessoas de 65 anos ou mais.',
                'nao_consta': False, 'trechos_usados': ['dev-001']}
    monkeypatch.setattr(agente.llm, 'gerar_json', gerar)
    r = agente.responder('Tenho 68 anos. Qual benefício uso?', base).resposta
    assert 'cartão comum' not in r.resposta
    assert not r.nao_consta
    # O índice e a fonte original não são alterados para outras perguntas.
    assert 'Pessoas com 60 a 64' in t.texto


def test_numero_sugerido_pelo_usuario_nao_e_fonte():
    assert agente.numeros_sem_suporte("Custa 12 reais.", ["A tarifa é 5 reais."], "Custa 12 reais?") == ["12"]
    assert agente.numeros_sem_suporte("A partir de 62 anos é grátis.", ["Gratuidade aos 65 anos."], "Tenho 62 anos") == ["62"]
    assert agente.numeros_sem_suporte("Com 62 anos, consulte o benefício.", ["Gratuidade aos 65 anos."], "Tenho 62 anos") == []


def test_busca_candidata_expande_somente_topico_pedido():
    from pf_genai.busca_conversa import consultas
    assert any("acessíveis" in q for q in consultas("Uso cadeira de rodas, acesso ao busão?"))
    assert len(consultas("Qual é a chave Pix do fiscal?")) == 1
    assert not any("acessíveis" in q for q in consultas("Uso cadeira de rodas, pago passagem?"))
    assert all("63" in q for q in consultas("Tenho 63, meu cartão comum funciona?"))


def test_cache_recuperacao_preserva_ranking_e_nao_compartilha_objetos_mutaveis(monkeypatch):
    chamadas = []
    def embutir(*args, **kwargs):
        chamadas.append(args[0])
        return np.array([[1, 0]], dtype="float32")
    monkeypatch.setattr(indice, "embutir", embutir)
    trechos = [Trecho("a", "d", "D", "", "A"), Trecho("b", "d", "D", "", "B")]
    i = indice.Indice(trechos, vetores=np.array([[1, 0], [0, 1]], dtype="float32"))
    primeira = i.buscar("Tem rampa?", 2)
    primeira[0].score = -1
    segunda = i.buscar("Tem rampa?", 2)
    assert [x.trecho.trecho_id for x in segunda] == ["a", "b"]
    assert segunda[0].score == 1
    assert len(chamadas) == 1
    i.buscar("Tem rampa?", 1)
    assert len(chamadas) == 2
    i._buscar.cache_clear()
