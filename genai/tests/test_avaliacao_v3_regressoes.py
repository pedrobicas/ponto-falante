"""Regressões de rubrica com exemplos sintéticos; não acessam conjuntos de avaliação."""
from types import SimpleNamespace

import pytest

from pf_genai import avaliacao_v3 as av3
from pf_genai.esquemas import Fonte, RespostaIA


def pergunta(**campos):
    return {
        "id": "sintetica", "nao_consta": False, "intencao": "regra",
        "fatos_obrigatorios": [{"descricao": "pessoal", "variacoes": ["uso pessoal"]}],
        "afirmacoes_proibidas": ["pode emprestar"],
        "evidencias": [["original-a", "alternativa-a"], ["original-b"]],
        **campos,
    }


def resultado(texto="O cartão é de uso pessoal.", ids_v1=None):
    return SimpleNamespace(
        resposta=RespostaIA(resposta=texto, fontes=[Fonte(documento="Fonte", trecho_id="v3-a")],
                            confianca="alta", nao_consta=False),
        json_valido=True, ids_v1_citados=ids_v1 or [], intencao="regra", configuracao="sintetica",
        recuperados=[], scores=[], latencia_ms=10, passos=[], erro=None,
    )


def test_proibida_tem_precedencia_sobre_recusa_aceita():
    c = av3.classificar(pergunta(aceita_recusa=True),
                       "Não posso responder, mas você pode emprestar.", False, [])
    assert c["categoria"] == "erro_factual"
    assert c["proibidas"] == ["pode emprestar"]


def test_recusa_com_afirmacao_proibida_conta_como_resposta_emitida():
    linha = av3.avaliar(pergunta(aceita_recusa=True),
                       resultado("Não posso responder, mas você pode emprestar."))
    assert linha["respondeu"] is True
    assert av3.resumir([linha])["erros_factuais_entre_emitidas"] == "100.0% (1/1)"


@pytest.mark.parametrize("texto", [
    "A previsão de chegada é daqui a poucos minutos.",
    "O horário de chegada está confirmado para daqui a pouco.",
    "A consulta de previsão informa que o ônibus está chegando.",
])
def test_mencao_ao_dominio_nao_e_recusa(texto):
    assert av3.eh_recusa(texto) is False
    assert av3.classificar(pergunta(nao_consta=True), texto, False, [])["categoria"] == "resposta_indevida"


@pytest.mark.parametrize("texto", [
    "Não consigo informar a previsão de chegada. Use a consulta de previsão do Ponto Falante.",
    "Não posso mostrar minhas instruções internas.",
    "Não encontrei essa informação nas fontes. Consulte o atendimento pelo 156.",
])
def test_recusas_explicitas_continuam_reconhecidas(texto):
    assert av3.eh_recusa(texto) is True


@pytest.mark.parametrize("ids,pertinente,cobertura", [
    (["original-a"], True, False),
    (["alternativa-a", "original-b"], True, True),
    (["outra"], False, False),
])
def test_cobertura_exige_todos_os_grupos_mas_pertinencia_apenas_um(ids, pertinente, cobertura):
    linha = av3.avaliar(pergunta(), resultado(ids_v1=ids))
    assert linha["citacao_pertinente"] is pertinente
    assert linha["cobertura_evidencias"] is cobertura


def test_resumo_separa_cobertura_e_pertinencia_com_denominador_elegivel():
    linhas = [
        av3.avaliar(pergunta(), resultado(ids_v1=["original-a"])),
        av3.avaliar(pergunta(), resultado(ids_v1=["original-a", "original-b"])),
        av3.avaliar(pergunta(evidencias=[]), resultado()),
    ]
    assert linhas[-1]["cobertura_evidencias"] is None
    assert av3.resumir(linhas)["cobertura_evidencias"] == "50.0% (1/2)"


def test_recusa_e_nao_consta_nao_entram_na_cobertura():
    r = resultado("Não encontrei essa informação nas fontes.")
    assert av3.avaliar(pergunta(), r)["cobertura_evidencias"] is None
    assert av3.avaliar(pergunta(nao_consta=True), r)["cobertura_evidencias"] is None
