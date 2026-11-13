"""Gera docs/fluxo.bpmn (BPMN 2.0 com diagrama) do robô: coletor de amostras reais + boletim diário.

Uso: python docs/gerar_fluxo_bpmn.py  (depois abra docs/fluxo.html ou https://demo.bpmn.io)
O layout é calculado aqui para o arquivo continuar editável em qualquer modelador BPMN.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

TAM = {"start": (36, 36), "end": (36, 36), "task": (150, 80), "gw": (50, 50), "store": (50, 50)}


class Proc:
    def __init__(self, pid, nome, participante, y0, altura):
        self.pid, self.nome, self.participante, self.y0, self.altura = pid, nome, participante, y0, altura
        self.nos, self.fluxos, self.stores = [], [], []

    def no(self, tipo, nid, nome, x, y, **extra):
        w, h = TAM[tipo]
        self.nos.append({"tipo": tipo, "id": nid, "nome": nome, "x": x, "y": self.y0 + y - h // 2, "w": w, "h": h, **extra})

    def f(self, fid, a, b, nome="", pontos=None):
        self.fluxos.append((fid, a, b, nome, pontos))

    def pos(self, nid):
        return next(n for n in self.nos if n["id"] == nid)


def centro_dir(n):
    return n["x"] + n["w"], n["y"] + n["h"] // 2


def centro_esq(n):
    return n["x"], n["y"] + n["h"] // 2


def topo(n):
    return n["x"] + n["w"] // 2, n["y"]


def base(n):
    return n["x"] + n["w"] // 2, n["y"] + n["h"]


def rota(p: Proc, a, b, modo):
    na, nb = p.pos(a), p.pos(b)
    if modo == "reta":
        return [centro_dir(na), centro_esq(nb)]
    if modo == "desce":  # sai por baixo e entra pela esquerda
        x1, y1 = base(na)
        x2, y2 = centro_esq(nb)
        return [(x1, y1), (x1, y2), (x2, y2)]
    if modo == "sobe":
        x1, y1 = topo(na)
        x2, y2 = centro_esq(nb)
        return [(x1, y1), (x1, y2), (x2, y2)]
    if modo == "volta_baixo":  # sai pela direita e entra por baixo
        x1, y1 = centro_dir(na)
        x2, y2 = base(nb)
        return [(x1, y1), (x2, y1), (x2, y2)]
    if modo == "volta_cima":
        x1, y1 = centro_dir(na)
        x2, y2 = topo(nb)
        return [(x1, y1), (x2, y1), (x2, y2)]
    raise ValueError(modo)


# ---------------- Coletor ----------------
C = Proc("Processo_Coletor", "Coletor de amostras reais", "Part_Coletor", 0, 300)
y = 130
C.no("start", "C_Inicio", "8 vezes por dia (07h às 21h)", 230, y, timer=True)
C.no("task", "C_Config", "Ler pontos do YAML e lotes pendentes", 310, y)
C.no("task", "C_Consultar", "Para cada ponto: GET previsões (3 tentativas)", 500, y, loop=True)
C.no("gw", "C_GwReal", "Fonte OLHO_VIVO?", 700, y)
C.no("task", "C_Amostra", "Guardar amostra (consultado_em, ônibus previstos)", 800, y - 70)
C.no("task", "C_Descartar", "Descartar e registrar motivo (demo ou fora do contrato)", 800, y + 70)
C.no("task", "C_Enviar", "POST /rpa/amostras com X-API-Key", 1010, y)
C.no("gw", "C_GwGravou", "MVP gravou?", 1210, y)
C.no("task", "C_Pendente", "Guardar lote em saida/pendentes para reenvio", 1310, y + 70)
C.no("task", "C_Auditar", "Gravar log e auditoria da coleta", 1310, y - 70)
C.no("end", "C_Fim", "Amostras reais no PostgreSQL", 1530, y)
C.f("c1", "C_Inicio", "C_Config", pontos="reta")
C.f("c2", "C_Config", "C_Consultar", pontos="reta")
C.f("c3", "C_Consultar", "C_GwReal", pontos="reta")
C.f("c4", "C_GwReal", "C_Amostra", "sim", "sobe")
C.f("c5", "C_GwReal", "C_Descartar", "não", "desce")
C.f("c6", "C_Amostra", "C_Enviar", pontos="volta_cima")
C.f("c7", "C_Descartar", "C_Enviar", pontos="volta_baixo")
C.f("c8", "C_Enviar", "C_GwGravou", pontos="reta")
C.f("c9", "C_GwGravou", "C_Auditar", "sim", "sobe")
C.f("c10", "C_GwGravou", "C_Pendente", "não", "desce")
C.f("c11", "C_Auditar", "C_Fim", pontos="volta_cima")
C.f("c12", "C_Pendente", "C_Fim", pontos="volta_baixo")

# ---------------- Boletim ----------------
B = Proc("Processo_Boletim", "Robô do boletim diário", "Part_Boletim", 340, 520)
y = 250
B.no("start", "B_Inicio", "Todo dia 06:00", 230, y, timer=True)
B.no("task", "B_Ler", "GET /rpa/amostras do dia anterior (3 tentativas, backoff)", 310, y)
B.no("gw", "B_GwMvp", "MVP respondeu?", 510, y)
B.no("task", "B_Desatualizado", "Republicar último boletim como DESATUALIZADO", 610, y + 175)
B.no("task", "B_Validar", "Para cada amostra: validar, deduplicar e separar sentidos", 610, y)
B.no("gw", "B_GwReal", "Há amostra real válida?", 810, y)
B.no("task", "B_Estimar", "Para cada linha: estimar espera prevista (ESTIMADO)", 910, y - 130, loop=True)
B.no("task", "B_Classificar", "Classificar: CRÍTICA, ATENÇÃO, OK ou SEM DADOS (limites do YAML)", 1130, y - 130)
B.no("gw", "B_GwDemo", "MVP em modo demonstração?", 910, y + 60)
B.no("task", "B_Simulado", "Histórico SIMULADO da rede fictícia, rotulado", 1010, y)
B.no("task", "B_Indisponivel", "Boletim INDISPONÍVEL (sem números)", 1010, y + 110)
B.no("task", "B_Gerar", "Gerar boletim JSON + HTML com fonte e categoria", 1420, y)
B.no("task", "B_Publicar", "POST /boletim com X-API-Key", 1620, y)
B.no("gw", "B_GwPublicou", "Publicou?", 1820, y)
B.no("task", "B_Falha", "Salvar cópia local e registrar falha", 1920, y + 110)
B.no("task", "B_Auditar", "Gravar log e auditoria", 1920, y - 110)
B.no("end", "B_Fim", "Boletim em GET /boletim (lido em voz alta)", 2140, y)
B.f("b1", "B_Inicio", "B_Ler", pontos="reta")
B.f("b2", "B_Ler", "B_GwMvp", pontos="reta")
B.f("b3", "B_GwMvp", "B_Validar", "sim", "reta")
B.f("b4", "B_GwMvp", "B_Desatualizado", "não", "desce")
B.f("b5", "B_Validar", "B_GwReal", pontos="reta")
B.f("b6", "B_GwReal", "B_Estimar", "sim", "sobe")
B.f("b7", "B_GwReal", "B_GwDemo", "não", "desce")
B.f("b8", "B_Estimar", "B_Classificar", pontos="reta")
B.f("b10", "B_Classificar", "B_Gerar", pontos="volta_cima")
B.f("b11", "B_GwDemo", "B_Simulado", "sim", "sobe")
B.f("b12", "B_GwDemo", "B_Indisponivel", "não", "desce")
B.f("b13", "B_Simulado", "B_Gerar", pontos="reta")
B.f("b14", "B_Indisponivel", "B_Gerar", pontos="volta_baixo")
B.f("b15", "B_Gerar", "B_Publicar", pontos="reta")
B.f("b16", "B_Publicar", "B_GwPublicou", pontos="reta")
B.f("b17", "B_GwPublicou", "B_Auditar", "sim", "sobe")
B.f("b18", "B_GwPublicou", "B_Falha", "não", "desce")
B.f("b19", "B_Auditar", "B_Fim", pontos="volta_cima")
B.f("b20", "B_Falha", "B_Fim", pontos="volta_baixo")
B.f("b21", "B_Desatualizado", "B_Publicar", pontos="volta_baixo")

TAG = {"start": "startEvent", "end": "endEvent", "task": "task", "gw": "exclusiveGateway"}


def xml_processo(p: Proc) -> str:
    entradas = {n["id"]: [] for n in p.nos}
    saidas = {n["id"]: [] for n in p.nos}
    for fid, a, b, _, _ in p.fluxos:
        saidas[a].append(fid)
        entradas[b].append(fid)
    linhas = [f'  <bpmn:process id="{p.pid}" name="{escape(p.nome)}" isExecutable="false">']
    for n in p.nos:
        tag = TAG[n["tipo"]]
        corpo = [f"      <bpmn:incoming>{i}</bpmn:incoming>" for i in entradas[n["id"]]]
        corpo += [f"      <bpmn:outgoing>{o}</bpmn:outgoing>" for o in saidas[n["id"]]]
        if n.get("timer"):
            corpo.append('      <bpmn:timerEventDefinition id="%s_timer" />' % n["id"])
        if n.get("loop"):
            corpo.append('      <bpmn:standardLoopCharacteristics />')
        linhas.append(f'    <bpmn:{tag} id="{n["id"]}" name="{escape(n["nome"], {chr(34): "&quot;"})}">')
        linhas += corpo
        linhas.append(f"    </bpmn:{tag}>")
    for fid, a, b, nome, _ in p.fluxos:
        rot = f' name="{escape(nome)}"' if nome else ""
        linhas.append(f'    <bpmn:sequenceFlow id="{fid}"{rot} sourceRef="{a}" targetRef="{b}" />')
    linhas.append("  </bpmn:process>")
    return "\n".join(linhas)


def xml_di(p: Proc) -> str:
    out = [f'      <bpmndi:BPMNShape id="{p.participante}_di" bpmnElement="{p.participante}" isHorizontal="true">',
           f'        <dc:Bounds x="160" y="{p.y0}" width="{2160 if p is B else 1560}" height="{p.altura}" />',
           "      </bpmndi:BPMNShape>"]
    for n in p.nos:
        extra = ' isMarkerVisible="true"' if n["tipo"] == "gw" else ""
        out.append(f'      <bpmndi:BPMNShape id="{n["id"]}_di" bpmnElement="{n["id"]}"{extra}>')
        out.append(f'        <dc:Bounds x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" />')
        if n["tipo"] != "task":
            if n["id"] == "B_GwDemo":  # abaixo e à esquerda: área livre do diagrama
                lx, ly, lw = n["x"] - 120, n["y"] + 40, 110
            elif n["tipo"] == "gw":    # acima e à esquerda: longe das saídas "sim" (sobe) e "não" (desce)
                lx, ly, lw = n["x"] - 95, n["y"] - 30, 100
            elif n["tipo"] == "end":   # à direita: a entrada chega por cima
                lx, ly, lw = n["x"] + 44, n["y"] + 2, 120
            else:
                lx, ly, lw = n["x"] - 30, n["y"] + n["h"] + 6, n["w"] + 60
            out.append(f'        <bpmndi:BPMNLabel><dc:Bounds x="{lx}" y="{ly}" width="{lw}" height="28" /></bpmndi:BPMNLabel>')
        out.append("      </bpmndi:BPMNShape>")
    for fid, a, b, nome, modo in p.fluxos:
        pts = rota(p, a, b, modo or "reta")
        out.append(f'      <bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">')
        out += [f'        <di:waypoint x="{x}" y="{yy}" />' for x, yy in pts]
        if nome:
            x, yy = pts[1] if len(pts) > 2 else pts[0]
            out.append(f'        <bpmndi:BPMNLabel><dc:Bounds x="{x + 6}" y="{yy - 22}" width="90" height="14" /></bpmndi:BPMNLabel>')
        out.append("      </bpmndi:BPMNEdge>")
    return "\n".join(out)


def gerar() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Gerado por docs/gerar_fluxo_bpmn.py. Coletor de amostras reais da SPTrans e boletim diário ESTIMADO. -->
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definicoes_PontoFalante_RPA"
  targetNamespace="https://github.com/pedrobicas/ponto-falante/rpa">
  <bpmn:collaboration id="Colaboracao_RPA">
    <bpmn:participant id="Part_Coletor" name="Coletor (GitHub Actions, 8 por dia)" processRef="Processo_Coletor" />
    <bpmn:participant id="Part_Boletim" name="Boletim (GitHub Actions, diário)" processRef="Processo_Boletim" />
  </bpmn:collaboration>
{xml_processo(C)}
{xml_processo(B)}
  <bpmndi:BPMNDiagram id="Diagrama_RPA">
    <bpmndi:BPMNPlane id="Plano_RPA" bpmnElement="Colaboracao_RPA">
{xml_di(C)}
{xml_di(B)}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
'''


if __name__ == "__main__":
    destino = Path(__file__).with_name("fluxo.bpmn")
    destino.write_text(gerar(), encoding="utf-8", newline="\n")
    print(f"gerado {destino}")
