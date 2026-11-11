"""Especialização por AGENTE (configuração C do placar).

Por que agente e não LoRA: ver README. Em resumo, o agente ataca diretamente as causas
de erro do RAG simples observadas no notebook 03 e roda no mesmo modelo local.

Passos (cada um fica registrado em Resultado.passos, para explicar a decisão):
 1. TRIAGEM + REESCRITA: o LLM diz se a pergunta é do escopo (transporte público em SP,
    tarifa, gratuidade, Bilhete Único, direitos) e reescreve a pergunta com os termos das
    fontes oficiais ("velhinho" -> "pessoa idosa", "passe livre" -> "gratuidade").
 2. BUSCA DUPLA: busca com a pergunta original e com a reescrita; junta pelo maior score.
 3. LIMIAR: nenhum trecho acima do limiar -> recusa ("não consta").
 4. GERAÇÃO RESTRITA: o JSON Schema só aceita trecho_id entre os recuperados
    (impossível citar fonte inexistente) e o campo "documento" é preenchido pelo sistema.
 5. VERIFICAÇÃO: (a) números da resposta precisam aparecer nos trechos citados;
    (b) o LLM confere se os trechos sustentam a resposta. Falhou -> 1 nova tentativa com
    o aviso; falhou de novo -> recusa com confiança baixa.
"""
from __future__ import annotations

import json
import re
import time

from . import llm
from .esquemas import Fonte, RespostaIA, recusa
from .gerador import LIMIAR, REGRAS_ESTILO, Resultado, formatar_contexto
from .indice import Indice

SISTEMA_TRIAGEM = (
    "Você classifica perguntas de passageiros de ônibus da cidade de São Paulo. "
    "no_escopo = true se a pergunta for sobre transporte público municipal: tarifa, gratuidade, "
    "Bilhete Único, integração, cartões, direitos de pessoas idosas, com deficiência ou mobilidade "
    "reduzida no transporte, acessibilidade nos ônibus. Caso contrário false. "
    "Em 'consulta', reescreva a pergunta como busca, usando termos formais de leis e da SPTrans "
    "(ex.: 'pessoa idosa', 'pessoa com deficiência', 'gratuidade', 'Bilhete Único Especial', "
    "'integração', 'tarifa', 'acompanhante'), sem inventar informação.\n"
    "Exemplos:\n"
    "'Tenho 66 anos, pago ônibus?' -> {\"no_escopo\": true, \"consulta\": \"gratuidade pessoa idosa 65 anos ônibus\"}\n"
    "'Quantos ônibus pego com uma passagem?' -> {\"no_escopo\": true, \"consulta\": \"tarifa Bilhete Único quantidade de embarques integração ônibus\"}\n"
    "'Meu filho é cadeirante, ele paga?' -> {\"no_escopo\": true, \"consulta\": \"gratuidade pessoa com deficiência Bilhete Único Especial\"}\n"
    "'Vai chover amanhã?' -> {\"no_escopo\": false, \"consulta\": \"previsão do tempo\"}\n"
    "'Qual a capital da França?' -> {\"no_escopo\": false, \"consulta\": \"capital da França\"}"
)
SCHEMA_TRIAGEM = {
    "type": "object",
    "properties": {"no_escopo": {"type": "boolean"}, "consulta": {"type": "string"}},
    "required": ["no_escopo", "consulta"],
}

SISTEMA_RESPOSTA = (
    "Você é o assistente do Ponto Falante para passageiros de ônibus de São Paulo. "
    "Responda usando SOMENTE os trechos do CONTEXTO. Copie números, idades, valores e prazos "
    "exatamente como aparecem nos trechos. Você pode fazer comparações simples com o que a pessoa "
    "disse (ex.: quem tem 66 anos tem mais de 65). Se algum trecho responde à pergunta, responda e "
    "liste em trechos_usados o(s) trecho_id usados. Se o assunto é parecido mas a informação pedida não está "
    "nos trechos, use nao_consta=true. " + REGRAS_ESTILO
)

SISTEMA_VERIFICACAO = (
    "Você é um verificador. Diga se a RESPOSTA é sustentada pelos TRECHOS. "
    "suportada=false SOMENTE se a resposta afirmar algo que não está nos trechos ou que os contradiz "
    "(valor, prazo, idade, regra ou documento diferente). Resposta incompleta, resumida, sem citar "
    "artigo de lei ou com comparação simples (ex.: 66 anos é mais de 65) continua suportada. "
    "Responda JSON com suportada (true/false) e problema (frase curta, vazia se suportada)."
)
SCHEMA_VERIFICACAO = {
    "type": "object",
    "properties": {"suportada": {"type": "boolean"}, "problema": {"type": "string"}},
    "required": ["suportada", "problema"],
}

# Histórico de ajustes no DEV (avaliacao/historico_dev/):
#  iter2  verificador bloqueia ............ acerto 70%, alucinação 0%,  recusa indevida 45%
#  iter3  verificador só rebaixa confiança  acerto 70%, alucinação 27%, recusa indevida 5%
#  iter4  + evidência literal ............. acerto 60%, alucinação 40%, recusa indevida 0%
# Escolha: bloquear. Para quem depende da voz do Ponto Falante, uma informação errada (ex.: "o
# posto abre até as 22h") custa mais caro do que "não encontrei, ligue 156".
VERIFICADOR_BLOQUEIA = True
MARGEM_ESCOPO = 0.0   # ajustado no DEV: a triagem do 3B marcava perguntas do escopo como fora (d03, d19)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _schema_resposta(ids: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "resposta": {"type": "string"},
            "trechos_usados": {"type": "array", "items": {"type": "string", "enum": ids}},
            "nao_consta": {"type": "boolean"},
        },
        "required": ["resposta", "trechos_usados", "nao_consta"],
    }


_ID_TRECHO = re.compile(r"\[?[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}\]?")


def numeros_sem_suporte(resposta: str, textos: list[str], pergunta: str) -> list[str]:
    """Números da resposta que não aparecem nos trechos (nem no nome do documento, nem na pergunta).
    Ids de trecho escritos na resposta (ex.: sptrans-bilhete-pcd-009) não contam como números."""
    resposta = _ID_TRECHO.sub(" ", resposta)
    base = " ".join(textos) + " " + pergunta
    norm = lambda s: s.replace(",", ".")
    disponiveis = {norm(n) for n in _NUM.findall(base)}
    return [n for n in _NUM.findall(resposta) if norm(n) not in disponiveis]


def responder(pergunta: str, indice: Indice, k: int = 4, limiar: float = LIMIAR) -> Resultado:
    t0 = time.perf_counter()
    passos: list[str] = []
    ms = lambda: int((time.perf_counter() - t0) * 1000)

    # 1. Triagem + reescrita
    try:
        tri = llm.gerar_json(SISTEMA_TRIAGEM, pergunta, SCHEMA_TRIAGEM, num_predict=120)
    except (json.JSONDecodeError, ValueError):
        tri = {"no_escopo": True, "consulta": pergunta}
        passos.append("triagem falhou; seguindo com a pergunta original")
    passos.append(f"triagem: no_escopo={tri['no_escopo']} consulta='{tri['consulta']}'")

    # 2. Busca dupla (roda mesmo fora do escopo: se a base tiver algo forte, não descartamos)
    achados = {}
    for consulta in {pergunta, tri.get("consulta") or pergunta}:
        for a in indice.buscar(consulta, k):
            if a.trecho.trecho_id not in achados or a.score > achados[a.trecho.trecho_id].score:
                achados[a.trecho.trecho_id] = a
    ordenados = sorted(achados.values(), key=lambda a: -a.score)[:k]
    ids, scores = [a.trecho.trecho_id for a in ordenados], [round(a.score, 4) for a in ordenados]
    passos.append(f"busca: {list(zip(ids, scores))}")

    # 3. Limiar (e escopo)
    relevantes = [a for a in ordenados if a.score >= limiar]
    # Fora do escopo só recusa se a base também não tiver nada forte (o classificador de 3B erra).
    if not relevantes or (not tri["no_escopo"] and relevantes[0].score < limiar + MARGEM_ESCOPO):
        passos.append("nenhum trecho relevante ou pergunta fora do escopo: recusa")
        return Resultado("agente", recusa("alta"), None, True, None, ids, scores, ms(), passos)

    mapa = {a.trecho.trecho_id: a.trecho for a in relevantes}
    contexto = formatar_contexto(relevantes)
    aviso = ""
    for tentativa in (1, 2):
        # 4. Geração com citações restritas
        usuario = f"CONTEXTO:\n{contexto}\n\nPERGUNTA: {pergunta}{aviso}"
        try:
            g = llm.gerar_json(SISTEMA_RESPOSTA, usuario, _schema_resposta(list(mapa)))
        except (json.JSONDecodeError, ValueError):
            passos.append(f"tentativa {tentativa}: JSON inválido")
            continue
        if g.get("nao_consta"):
            passos.append(f"tentativa {tentativa}: o modelo indicou que não consta")
            return Resultado("agente", recusa("media"), g, True, None, ids, scores, ms(), passos)
        # 4b. Forma da resposta: o 3B às vezes cola o contexto inteiro (com ids) em "resposta".
        g["resposta"] = re.sub(r"\s{2,}", " ", _ID_TRECHO.sub(" ", g["resposta"])).strip()
        if len(g["resposta"]) > 600 or not g["resposta"]:
            passos.append(f"tentativa {tentativa}: resposta copiou o contexto ({len(g['resposta'])} caracteres)")
            aviso = "\n\nATENÇÃO: não copie os trechos nem os ids. Responda em até 3 frases curtas."
            continue
        usados = [i for i in dict.fromkeys(g.get("trechos_usados") or []) if i in mapa] or [relevantes[0].trecho.trecho_id]
        textos = [f"{mapa[i].documento}. {mapa[i].texto}" for i in usados]

        # 5a. Verificação determinística de números
        sem_suporte = numeros_sem_suporte(g["resposta"], textos, pergunta)
        if sem_suporte:
            passos.append(f"tentativa {tentativa}: números sem suporte {sem_suporte}")
            aviso = f"\n\nATENÇÃO: os números {sem_suporte} não aparecem nos trechos. Corrija ou responda que não consta."
            continue
        # 5b. Verificação de fundamentação pelo LLM
        try:
            v = llm.gerar_json(SISTEMA_VERIFICACAO,
                               f"TRECHOS:\n{chr(10).join(textos)}\n\nPERGUNTA: {pergunta}\nRESPOSTA: {g['resposta']}",
                               SCHEMA_VERIFICACAO, num_predict=100)
        except (json.JSONDecodeError, ValueError):
            v = {"suportada": True, "problema": "verificação indisponível"}
        alerta_verificador = not v["suportada"]
        if alerta_verificador and VERIFICADOR_BLOQUEIA:
            passos.append(f"tentativa {tentativa}: verificador recusou ({v['problema']})")
            aviso = f"\n\nATENÇÃO: a resposta anterior tinha um problema: {v['problema']}. Use só o que está nos trechos."
            continue
        if alerta_verificador:
            passos.append(f"tentativa {tentativa}: verificador apontou '{v['problema'][:120]}' (só rebaixa a confiança)")
        melhor = max(achados[i].score for i in usados)
        confianca = "alta" if melhor >= limiar + 0.03 and tentativa == 1 and not alerta_verificador else "media"
        resp = RespostaIA(resposta=g["resposta"].strip(),
                          fontes=[Fonte(documento=mapa[i].documento, trecho_id=i) for i in usados],
                          confianca=confianca, nao_consta=False)
        passos.append(f"tentativa {tentativa}: aprovada ({confianca})")
        return Resultado("agente", resp, g, True, None, ids, scores, ms(), passos)

    passos.append("duas tentativas sem fundamentação: recusa com confiança baixa")
    return Resultado("agente", recusa("baixa"), None, True, None, ids, scores, ms(), passos)
