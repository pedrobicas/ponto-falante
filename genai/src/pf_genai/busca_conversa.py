"""Recuperação candidata para DEV. Não é o índice usado pelo modo agente em produção.

Expansão lexical conservadora, fusão por id e exclusão de subtipos de cartão
quando não foram pedidos. Mantém o verificador v1 e seu limiar sem alterações.
"""
import re
import unicodedata


def normalizar(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')


def consultas(pergunta: str) -> list[str]:
    t = normalizar(pergunta)
    saida = [pergunta]
    formal = re.sub(r"\b(busao|buzao)\b", "ônibus", pergunta, flags=re.I)
    formal = re.sub(r"\bcart[aã]o comum\b", "Bilhete Único Comum", formal, flags=re.I)
    if formal != pergunta:
        saida.append(formal)
    if re.search(r"cadeira de rodas|cadeirante|acessibilidade", t) and not re.search(r"paga|pago|gratis|gratuidade|bilhete|cartao", t):
        saida.append("Os veículos de transporte coletivo devem ser acessíveis para pessoas com deficiência e mobilidade reduzida. " + pergunta)
    if "acompanhante" in t and not re.search(r"estudante|escola|ensino|cadastrado", t):
        saida.append("Bilhete Único Especial pessoa com deficiência benefício com direito a acompanhante presença do acompanhante. " + pergunta)
    return list(dict.fromkeys(saida))


class IndiceConversa:
    def __init__(self, indice, pergunta):
        self.indice = indice
        self.pergunta = normalizar(pergunta)

    def buscar(self, consulta, k):
        achados = {}
        acompanhante_geral = "acompanhante" in self.pergunta and not re.search(r"estudante|escola|ensino|cadastrado", self.pergunta)
        for q in consultas(consulta):
            for a in self.indice.buscar(q, max(k, 12)):
                titulo = normalizar(a.trecho.texto.splitlines()[0])
                if acompanhante_geral and ("acompanhante cadastrado" in titulo or "instituicao de ensino" in titulo):
                    continue
                tid = a.trecho.trecho_id
                if tid not in achados or achados[tid].score < a.score:
                    achados[tid] = a
        return sorted(achados.values(), key=lambda a: (-a.score, a.trecho.trecho_id))[:k]
