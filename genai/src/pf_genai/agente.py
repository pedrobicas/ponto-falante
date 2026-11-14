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
import os
import re
import time
import unicodedata
from dataclasses import replace

from . import llm
from .esquemas import Fonte, RespostaIA, recusa
from .gerador import LIMIAR, REGRAS_ESTILO, Resultado, formatar_contexto
from .indice import Indice, Resultado as Achado

SISTEMA_TRIAGEM = (
    "Você classifica perguntas de passageiros de ônibus da cidade de São Paulo. "
    "no_escopo = true se a pergunta for sobre transporte público municipal: tarifa, gratuidade, "
    "Bilhete Único, integração, cartões, direitos de pessoas idosas, com deficiência ou mobilidade "
    "reduzida no transporte, acessibilidade nos ônibus. Caso contrário false. "
    "Em 'consulta', reescreva a pergunta como busca, usando termos formais de leis e da SPTrans "
    "(ex.: 'pessoa idosa', 'pessoa com deficiência', 'gratuidade', 'Bilhete Único Especial', "
    "'integração', 'tarifa', 'acompanhante'), sem inventar informação. Preserve a idade, o público e o tipo de cartão declarados.\n"
    "Exemplos:\n"
    "'Tenho 66 anos, pago ônibus?' -> {\"no_escopo\": true, \"consulta\": \"gratuidade pessoa idosa 66 anos ônibus\"}\n"
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
MARGEM_REPARO = 0.02  # reparo de recusa só quando o 1º trecho passa do limiar com folga (medido no DEV em 14/11)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _texto_normalizado(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')


def fonte_compativel(pergunta: str, trecho) -> bool:
    """Benefícios específicos só sustentam respostas para o público declarado."""
    q = _texto_normalizado(pergunta)
    titulo = _texto_normalizado(trecho.texto.splitlines()[0])
    publicos = set()
    idades = _idades(q)
    for idade in idades:
        if 60 <= idade <= 64:
            publicos.add('sptrans-gratuidade-60-64')
        elif 65 <= idade <= 120:
            publicos.add('sptrans-gratuidade-65-mais')
    if not idades and re.search(r'\b(idos[oa]|avo)\b', q):
        publicos.update(('sptrans-gratuidade-60-64', 'sptrans-gratuidade-65-mais'))
    if re.search(r'deficien|\bpcd\b|cadeirante|cadeira de rodas|autis', q):
        publicos.add('sptrans-bilhete-pcd')
    if re.search(r'estudante|escola|ensino|faculdade', q):
        publicos.add('sptrans-bilhete-estudante')
    especificos = {'sptrans-gratuidade-60-64', 'sptrans-gratuidade-65-mais', 'sptrans-bilhete-pcd', 'sptrans-bilhete-estudante'}
    comum = bool(re.search(r'(cartao|bilhete(?: unico)?) comum', q))
    if trecho.documento_id in especificos and (publicos or comum) and trecho.documento_id not in publicos:
        return False
    if ('acompanhante' in q and not re.search(r'estudante|escola|ensino|cadastrado', q)
            and re.search(r'acompanhante cadastrado|instituicao de ensino', titulo)):
        return False
    return True


def _idades(texto: str) -> list[int]:
    return [int(a or b) for a, b in re.findall(
        r'\b(\d{1,3})\s+anos\b|\b(?:tenho|fez|completei|completar|perto dos|aos)\s+(\d{1,3})\b', texto)]


def _trecho_para_publico(pergunta: str, trecho):
    """Retira só o aviso 60–64 repetido no rodapé da FAQ 65+, sem alterar o corpus."""
    idades = _idades(_texto_normalizado(pergunta))
    if trecho.documento_id == 'sptrans-gratuidade-65-mais' and idades and all(65 <= i <= 120 for i in idades):
        texto = '\n'.join(l for l in trecho.texto.splitlines()
                          if not re.match(r'pessoas com 60 a 64 anos\b', _texto_normalizado(l).strip()))
        return replace(trecho, texto=texto)
    return trecho


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
    base = " ".join(textos)
    norm = lambda s: s.replace(",", ".")
    disponiveis = {norm(n) for n in _NUM.findall(base)}
    sem_suporte = []
    for m in _NUM.finditer(resposta):
        n = m.group()
        if norm(n) in disponiveis:
            continue
        # Só a idade declarada pode ser retomada como dado da pessoa. Preço, prazo ou regra
        # sugeridos na pergunta não são evidência; nem uma idade autoriza inventar um limiar.
        idade_pergunta = re.search(rf"\b{re.escape(n)}\s+anos\b", pergunta, re.I)
        referencias = re.finditer(rf"\b(?:com|aos|você tem|quem tem|pessoa de)\s+{re.escape(n)}\s+anos\b", resposta, re.I)
        referencia_idade = n.isdigit() and 0 <= int(n) <= 120 and idade_pergunta and any(r.start() <= m.start() < r.end() for r in referencias)
        if not referencia_idade:
            sem_suporte.append(n)
    return sem_suporte


def responder(pergunta: str, indice: Indice, k: int = 4, limiar: float = LIMIAR) -> Resultado:
    # Equivalência lexical, sem inferir idade, benefício ou elegibilidade.
    pergunta = re.sub(r'\bRG\b', 'documento de identidade', pergunta, flags=re.I)
    t0 = time.perf_counter()
    passos: list[str] = []
    ms = lambda: int((time.perf_counter() - t0) * 1000)

    # 1. Triagem + reescrita
    try:
        tri = llm.gerar_json(SISTEMA_TRIAGEM, pergunta, SCHEMA_TRIAGEM, num_predict=120)
        if not isinstance(tri, dict) or type(tri.get("no_escopo")) is not bool or not isinstance(tri.get("consulta"), str):
            raise ValueError("triagem fora do contrato")
        if len(tri["consulta"]) > 500:
            tri["consulta"] = pergunta
        # A reescrita não pode trocar a idade nem introduzir um limiar inventado.
        if set(_NUM.findall(tri['consulta'])) != set(_NUM.findall(pergunta)):
            tri['consulta'] = pergunta
            passos.append('reescrita alterou números; usando a pergunta original')
    except (json.JSONDecodeError, ValueError):
        tri = {"no_escopo": True, "consulta": pergunta}
        passos.append("triagem falhou; seguindo com a pergunta original")
    passos.append(f"triagem: no_escopo={tri['no_escopo']} consulta='{tri['consulta']}'")

    # 2. Busca dupla (roda mesmo fora do escopo: se a base tiver algo forte, não descartamos)
    achados = {}
    for consulta in dict.fromkeys([pergunta, tri.get("consulta") or pergunta]):
        for a in indice.buscar(consulta, max(k, 12)):
            if not fonte_compativel(pergunta, a.trecho):
                continue
            # Não modificar resultados compartilhados pelo índice/cache.
            a = Achado(_trecho_para_publico(pergunta, a.trecho), a.score)
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
    q = _texto_normalizado(pergunta)
    # A fonte recuperada descreve um benefício condicionado, não uma gratuidade universal.
    # Sem saber se o cartão inclui esse direito, esclarecer é mais útil que negar ou inventar.
    if ('acompanhante' in q and re.search(r'gratuidade|gratis|paga|pago', q)
            and re.search(r'deficien|\bpcd\b|cadeirante', q)
            and not re.search(r'estudante|escola|ensino|cadastrado|(?:tenho|tem|possuo) (?:o |um |o meu |meu )?(?:beneficio|cartao).*direito a acompanhante', q)):
        fonte = next((a.trecho for a in relevantes if a.trecho.documento_id == 'sptrans-bilhete-pcd'
                      and 'beneficio com direito a acompanhante' in _texto_normalizado(a.trecho.texto)), None)
        if fonte:
            resp = RespostaIA(resposta='A SPTrans prevê benefício com direito a acompanhante. Confirme se esse direito está incluído no seu cartão antes da viagem.',
                              fontes=[Fonte(documento=fonte.documento, trecho_id=fonte.trecho_id, url=fonte.url)],
                              confianca='media', nao_consta=False)
            passos.append('benefício condicionado: esclarecimento com fonte, sem conceder nem negar gratuidade')
            return Resultado('agente', resp, None, True, None, ids, scores, ms(), passos)
    contexto = formatar_contexto(relevantes)
    aviso = ""
    for tentativa in (1, 2):
        # 4. Geração com citações restritas
        usuario = f"CONTEXTO:\n{contexto}\n\nPERGUNTA: {pergunta}{aviso}"
        try:
            g = llm.gerar_json(SISTEMA_RESPOSTA, usuario, _schema_resposta(list(mapa)))
            if (not isinstance(g, dict) or type(g.get("nao_consta")) is not bool
                    or not isinstance(g.get("resposta"), str)
                    or not isinstance(g.get("trechos_usados"), list)
                    or not all(isinstance(i, str) for i in g["trechos_usados"])):
                raise ValueError("resposta fora do contrato")
        except (json.JSONDecodeError, ValueError):
            passos.append(f"tentativa {tentativa}: JSON inválido")
            continue
        if g.get("nao_consta"):
            # Reparo de recusa (PF_REPARO_RECUSA=1, medido só no DEV): com um trecho forte em 1º lugar, o modelo
            # recusa perguntas abertas ("como funciona o Bilhete Único?") que o trecho responde. A nova tentativa
            # usa só esse trecho e continua passando pela auditoria de números e pelo verificador.
            if (tentativa == 1 and os.environ.get("PF_REPARO_RECUSA", "0") == "1"
                    and relevantes[0].score >= limiar + MARGEM_REPARO):
                passos.append("tentativa 1: não consta com trecho forte; nova tentativa só com o 1º trecho")
                contexto = formatar_contexto(relevantes[:1])
                aviso = ("\n\nO trecho acima é o mais próximo da pergunta. Se ele trata do assunto perguntado, responda "
                         "só com o que ele diz, mesmo que a resposta seja parcial, e cite o id. Indique que não consta "
                         "apenas se o trecho não tratar do assunto.")
                continue
            passos.append(f"tentativa {tentativa}: o modelo indicou que não consta")
            return Resultado("agente", recusa("media"), g, True, None, ids, scores, ms(), passos)
        # 4b. Forma da resposta: o 3B às vezes cola o contexto inteiro (com ids) em "resposta".
        g["resposta"] = re.sub(r"\s{2,}", " ", _ID_TRECHO.sub(" ", g["resposta"])).strip()
        if len(g["resposta"]) > 600 or not g["resposta"]:
            passos.append(f"tentativa {tentativa}: resposta copiou o contexto ({len(g['resposta'])} caracteres)")
            aviso = "\n\nATENÇÃO: não copie os trechos nem os ids. Responda em até 3 frases curtas."
            continue
        usados = [i for i in dict.fromkeys(g.get("trechos_usados") or []) if i in mapa]
        if not usados or any(i not in mapa for i in g["trechos_usados"]):
            passos.append(f"tentativa {tentativa}: citação ausente ou desconhecida")
            aviso = "\nCite somente os ids dos trechos que sustentam a resposta ou indique que não consta."
            continue
        textos = [f"{mapa[i].documento}. {mapa[i].texto}" for i in usados]

        # 5a. Verificação determinística de números
        sem_suporte = numeros_sem_suporte(g["resposta"], [mapa[i].texto for i in usados], pergunta)
        if sem_suporte:
            passos.append(f"tentativa {tentativa}: números sem suporte {sem_suporte}")
            aviso = (f"\n\nATENÇÃO: os números {sem_suporte} não aparecem no corpo dos trechos que você citou. "
                     "Se houver suporte em outro trecho do CONTEXTO, cite esse trecho também. "
                     "Caso contrário, reescreva sem detalhes numéricos desnecessários, preservando as condições da regra. "
                     "Não recuse toda a pergunta apenas por uma referência de lei ou detalhe que pode ser omitido.")
            continue
        # 5b. Verificação de fundamentação pelo LLM
        try:
            v = llm.gerar_json(SISTEMA_VERIFICACAO,
                               f"TRECHOS:\n{chr(10).join(textos)}\n\nPERGUNTA: {pergunta}\nRESPOSTA: {g['resposta']}",
                               SCHEMA_VERIFICACAO, num_predict=100)
            if not isinstance(v, dict) or type(v.get("suportada")) is not bool or not isinstance(v.get("problema"), str):
                raise ValueError("verificação fora do contrato")
        except (json.JSONDecodeError, ValueError):
            v = {"suportada": False, "problema": "verificação indisponível"}
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
                          fontes=[Fonte(documento=mapa[i].documento, trecho_id=i, url=mapa[i].url) for i in usados],
                          confianca=confianca, nao_consta=False)
        passos.append(f"tentativa {tentativa}: aprovada ({confianca})")
        return Resultado("agente", resp, g, True, None, ids, scores, ms(), passos)

    passos.append("duas tentativas sem fundamentação: recusa com confiança baixa")
    return Resultado("agente", recusa("baixa"), None, True, None, ids, scores, ms(), passos)
