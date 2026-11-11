"""Gera os 4 notebooks (código + texto). Depois execute-os com:

    jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb --ExecutePreprocessor.timeout=-1
"""
from pathlib import Path

import nbformat as nbf

PASTA = Path(__file__).resolve().parents[1] / "notebooks"
PASTA.mkdir(exist_ok=True)

SETUP = """import sys, json, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
RAIZ = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
sys.path.insert(0, str(RAIZ / 'src'))
import pandas as pd
pd.set_option('display.max_colwidth', 120)"""


def nb(nome: str, celulas: list[tuple[str, str]]) -> None:
    n = nbf.v4.new_notebook()
    n.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    n.cells = [nbf.v4.new_markdown_cell(c) if t == "md" else nbf.v4.new_code_cell(c) for t, c in celulas]
    nbf.write(n, PASTA / nome)


nb("01_base_conhecimento.ipynb", [
    ("md", "# 01 · Base de conhecimento em trechos\n\n**Tarefa da IA:** responder dúvidas de passageiros de ônibus de São Paulo (idosos, pessoas com deficiência, estudantes) sobre gratuidade, Bilhete Único, integração, tarifas e direitos no transporte, **citando a fonte** e **recusando** quando a base não tem a resposta.\n\nFontes: só documentos públicos oficiais (SPTrans e leis federais). As leis vêm do portal da Câmara dos Deputados porque o site do Planalto não respondeu a requisições automáticas durante a coleta (ver `scripts/baixar_leis.py`)."),
    ("code", SETUP),
    ("code", "fontes = pd.read_csv(RAIZ / 'base' / 'fontes.csv')\nfontes[['id', 'orgao', 'formato', 'licenca', 'data_acesso']]"),
    ("md", "## Divisão em trechos\n- **Leis:** um trecho por artigo (unidade natural de citação); artigos longos são quebrados por parágrafo mantendo o rótulo `Art. X (cont.)`.\n- **Perguntas e Respostas da SPTrans:** um trecho por par pergunta + resposta (cada FAQ já responde uma dúvida completa).\n- **Tabela de tarifas:** cada célula vira uma frase (`Tarifa ...: R$ 5,30.`) sem alterar nenhum valor.\n- Limite de ~700 caracteres por trecho: cabe no contexto do modelo de 3B junto com outros 3 trechos."),
    ("code", "from pf_genai import trechos\nT = trechos.gerar_trechos()\ntrechos.salvar(T)\nprint(len(T), 'trechos gerados')"),
    ("code", "df = pd.DataFrame([t.__dict__ for t in T])\ntabela = (df.groupby('documento_id').agg(trechos=('trecho_id', 'count'), caracteres_medios=('texto', lambda s: int(s.str.len().mean())))\n          .join(fontes.set_index('id')[['titulo', 'formato', 'licenca']]))\ntabela"),
    ("code", "tabela[['titulo', 'formato', 'licenca', 'trechos']].to_csv(RAIZ / 'base' / 'tabela_base.csv')\nprint(tabela['trechos'].sum(), 'trechos no total')"),
    ("md", "## Exemplos de trechos"),
    ("code", "for tid in ['lei-10741-transporte-002', 'sptrans-gratuidade-60-64-025', 'sptrans-tarifas-003']:\n    t = next(x for x in T if x.trecho_id == tid)\n    print(f'[{t.trecho_id}] ({t.documento})\\n{t.texto}\\n')"),
])

nb("02_indice_recall_limiar.ipynb", [
    ("md", "# 02 · Busca vetorial: recall@1, recall@3 e limiar de similaridade\n\nÍndice FAISS (`IndexFlatIP` com vetores normalizados = similaridade de cosseno).\n\n**Separação desenvolvimento × teste (sem contaminação):**\n- `avaliacao/perguntas_dev.jsonl` (30 perguntas: 20 respondíveis + 10 \"não consta\"): usado para **todas as escolhas** (modelo de embeddings, limiar, ajustes do agente).\n- `avaliacao/perguntas.jsonl` (40 perguntas: 30 + 10): **teste final**, só medido no fim, sem ajustar nada depois.\n- Os dois conjuntos não compartilham nenhum trecho esperado.\n\nUma primeira rodada exploratória usou o conjunto de teste para escolher o limiar; ela foi descartada e está guardada em `avaliacao/exploratorio_descartado/` só para transparência."),
    ("code", SETUP),
    ("code", "from pf_genai import trechos, avaliacao as av\nfrom pf_genai.indice import Indice\nDEV = av.carregar_perguntas('dev')\nTESTE = av.carregar_perguntas('teste')\nT = trechos.carregar()\nfor nome, P in [('dev', DEV), ('teste', TESTE)]:\n    print(nome, len(P), 'perguntas;', sum(not p['nao_consta'] for p in P), 'respondíveis;', sum(p['nao_consta'] for p in P), '\"não consta\"')\nesp = lambda P: {t for p in P for t in p['trechos_esperados']}\nprint('trechos esperados em comum entre dev e teste:', len(esp(DEV) & esp(TESTE)))"),
    ("md", "## Escolha do modelo de embeddings (no DEV)"),
    ("code", "modelos = ['sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',\n           'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',\n           'intfloat/multilingual-e5-large']\nindices, linhas = {}, []\nfor m in modelos:\n    idx = Indice(T, m)\n    indices[m] = idx\n    r = av.recall_at_k(idx, DEV, (1, 3, 5))\n    c = pd.DataFrame(av.curva_limiar(idx, DEV, [round(0.30 + 0.005 * i, 3) for i in range(140)]))\n    best = c.loc[c['acuracia_balanceada'].idxmax()]\n    linhas.append({'modelo': m.split('/')[1], **{k: v for k, v in r.items() if k != 'detalhes'},\n                   'melhor_limiar_dev': best['limiar'], 'acuracia_balanceada_dev': best['acuracia_balanceada']})\nrecall_dev = pd.DataFrame(linhas)\nrecall_dev.to_csv(RAIZ / 'avaliacao' / 'recall_dev.csv', index=False)\nrecall_dev"),
    ("md", "**Escolha:** `multilingual-e5-large`. Ele foi treinado para busca (pares pergunta/passagem com prefixos `query:`/`passage:`); os modelos *paraphrase* foram treinados para similaridade entre frases parecidas. Custo: ~2 GB de disco e alguns minutos para indexar a base em CPU, uma única vez."),
    ("code", "idx = indices['intfloat/multilingual-e5-large']\nidx.salvar()"),
    ("md", "## Limiar de similaridade (no DEV)\nSe o trecho mais parecido tiver similaridade abaixo do limiar, o sistema **recusa** (\"não consta\") sem chamar o LLM. Queremos deixar passar as respondíveis e barrar as \"não consta\"."),
    ("code", "curva = pd.DataFrame(av.curva_limiar(idx, DEV, [round(0.80 + 0.005 * i, 3) for i in range(25)]))\ncurva.to_csv(RAIZ / 'avaliacao' / 'curva_limiar_dev.csv', index=False)\nimport matplotlib.pyplot as plt\nax = curva.plot(x='limiar', y=['respondiveis_passam', 'nao_consta_barradas', 'acuracia_balanceada'], figsize=(9, 4), grid=True)\nax.set_ylabel('proporção'); ax.set_title('Escolha do limiar no conjunto DEV (e5-large)')\nplt.savefig(RAIZ / 'avaliacao' / 'curva_limiar_dev.png', dpi=120, bbox_inches='tight')\ncurva[(curva.limiar >= 0.84) & (curva.limiar <= 0.89)]"),
    ("code", "melhor = curva[curva.acuracia_balanceada == curva.acuracia_balanceada.max()].iloc[0]\nprint('Menor limiar com a maior acurácia balanceada no DEV:', melhor.to_dict())"),
    ("md", "**Justificativa do limiar 0,86 (escolhido no DEV):** é o menor limiar com a maior acurácia balanceada sem perder nenhuma pergunta respondível. Subir mais barra mais \"não consta\", mas começa a negar respostas a quem precisa; as \"não consta\" que passam do limiar ainda enfrentam a instrução de recusa e, no agente, as verificações. As que passam são justamente as armadilhas do mesmo assunto (ex.: horário de um posto de atendimento), que a busca sozinha não separa."),
    ("md", "## Medida final no TESTE (nenhuma escolha é feita aqui)"),
    ("code", "r_teste = av.recall_at_k(idx, TESTE, (1, 3, 5))\nc_teste = pd.DataFrame(av.curva_limiar(idx, TESTE, [0.86]))\nfinal = pd.DataFrame([{'conjunto': 'teste (final)', **{k: v for k, v in r_teste.items() if k != 'detalhes'}, **c_teste.iloc[0].to_dict()}])\nfinal.to_csv(RAIZ / 'avaliacao' / 'recall_teste_final.csv', index=False)\nfinal"),
    ("code", "det = pd.DataFrame(r_teste['detalhes'])\ndet['acertou_top3'] = det.apply(lambda d: bool(set(d['top'][:3]) & set(d['esperados'])), axis=1)\nprint('Perguntas do teste em que o trecho certo não veio no top-3 (só registro, não usado para ajustar):')\ndet[~det['acertou_top3']]"),
])

nb("03_geracao_fundamentada.ipynb", [
    ("md", "# 03 · Geração fundamentada: JSON válido, citação e recusa\n\nModelo local: **qwen2.5:3b** via Ollama (temperatura 0, semente 42). Saída estruturada com JSON Schema do próprio Ollama e validação com **pydantic** no formato do contrato:\n```json\n{\"resposta\": str, \"fontes\": [{\"documento\": str, \"trecho_id\": str}], \"confianca\": \"alta|media|baixa\", \"nao_consta\": bool}\n```\nRegras de validação: confiança só com 3 valores; resposta afirmativa precisa citar pelo menos uma fonte; recusa não cita fonte."),
    ("code", SETUP),
    ("code", "from pf_genai import gerador, llm\nfrom pf_genai.esquemas import RespostaIA\nfrom pf_genai.indice import Indice\nidx = Indice.carregar()\nprint('LLM:', llm.MODELO, '| limiar:', gerador.LIMIAR)"),
    ("code", "def mostrar(r):\n    print(f'[{r.configuracao}] {r.latencia_ms} ms | JSON válido: {r.json_valido} | recuperados: {list(zip(r.recuperados, r.scores))}')\n    print(json.dumps(r.resposta.model_dump() if r.resposta else {'erro': r.erro}, ensure_ascii=False, indent=2))\n\nmostrar(gerador.rag('Tenho 67 anos. Preciso pagar a passagem do ônibus em São Paulo?', idx))"),
    ("md", "## Recusa quando não há base\nPerguntas fora da base são barradas pelo limiar (sem chamar o LLM) ou pela instrução de recusa."),
    ("code", "mostrar(gerador.rag('Qual o horário do último ônibus da linha 875C-10?', idx))\nmostrar(gerador.rag('Vai chover amanhã em São Paulo?', idx))"),
    ("md", "## Validação pydantic barrando saídas fora do contrato"),
    ("code", "for bruto in [{'resposta': 'É grátis.', 'fontes': [], 'confianca': 'alta', 'nao_consta': False},\n              {'resposta': 'É grátis.', 'fontes': [{'documento': 'Lei', 'trecho_id': 'x'}], 'confianca': 'certeza', 'nao_consta': False}]:\n    print(gerador._validar(bruto)[1])"),
    ("md", "## O mesmo modelo sem contexto\nPara comparação: sem a base, o modelo responde com o que \"lembra\" do treino, e cita fontes que não existem."),
    ("code", "mostrar(gerador.sem_contexto('Tenho 67 anos. Preciso pagar a passagem do ônibus em São Paulo?'))\nmostrar(gerador.sem_contexto('Qual o horário do último ônibus da linha 875C-10?'))"),
])

nb("04_agente_e_placar.ipynb", [
    ("md", "# 04 · Especialização por agente e placar das 3 configurações\n\n**Por que agente e não LoRA:** treinar LoRA de um modelo de 3B exige GPU NVIDIA (CUDA) e centenas de pares revisados. Temos GPU AMD no Windows e 8 dias. O agente roda no mesmo modelo local, é avaliável no mesmo placar e ataca as causas de erro do RAG simples:\n\n| Erro do RAG simples | Passo do agente que corrige |\n|---|---|\n| Pergunta coloquial busca o trecho errado | Triagem + **reescrita** da consulta com termos oficiais, busca dupla |\n| Cita `trecho_id` mal formatado ou inexistente | **Geração restrita**: o JSON Schema só aceita ids recuperados; o sistema preenche `documento` |\n| Inventa número/prazo | **Verificação determinística**: todo número da resposta precisa estar no trecho citado |\n| Afirma algo que o trecho não diz | **Verificação pelo LLM** + 1 nova tentativa, senão recusa |\n| Cola o contexto inteiro na resposta | Remoção de ids e limite de tamanho, com nova tentativa |\n\nCada decisão fica registrada em `passos` (explicabilidade)."),
    ("code", SETUP),
    ("code", "from pf_genai import agente, gerador, avaliacao as av\nfrom pf_genai.indice import Indice\nidx = Indice.carregar()\nprint('LLM:', gerador.llm.MODELO, '| limiar:', gerador.LIMIAR, '| verificador bloqueia:', agente.VERIFICADOR_BLOQUEIA)\nr = agente.responder('Meu pai tem 62 anos. Ele precisa pagar ônibus? Como faz?', idx)\nprint(json.dumps(r.resposta.model_dump(), ensure_ascii=False, indent=2))\nfor p in r.passos: print(' -', p)"),
    ("md", "## Condições equivalentes\nAs 3 configurações usam o **mesmo** modelo (qwen2.5:3b), temperatura 0, semente 42, o mesmo índice e5-large, o mesmo limiar (0,86) e as mesmas perguntas. Só muda a estratégia. O placar é gerado por `python scripts/rodar_placar.py --conjunto dev|teste` e este notebook **lê** os resultados gravados (rodar de novo aqui poderia gerar uma segunda medição do teste).\n\n**Métricas** (determinísticas, `src/pf_genai/avaliacao.py`):\n- **acerto**: respondível com todos os fatos do gabarito, ou \"não consta\" recusada;\n- **recusa correta (não consta)**: % das perguntas sem resposta na base que foram recusadas;\n- **alucinação**: respondeu algo errado ou respondeu o que não consta;\n- **recusa indevida**: % das respondíveis que foram recusadas;\n- **sem fundamentação**: resposta afirmativa sem citação válida ou com número que não está nos trechos citados;\n- **precisão das citações**: das citações feitas nas respondíveis, % que são trechos do gabarito; **citações válidas**: % que existem na base;\n- recusa é julgada pelo texto que seria **falado**, não só pela flag `nao_consta`."),
    ("md", "## Desenvolvimento: histórico de ajustes no DEV\nCada iteração mudou uma coisa e foi medida só no DEV (`avaliacao/historico_dev/`)."),
    ("code", "hist = []\nfor f in sorted((RAIZ / 'avaliacao' / 'historico_dev').glob('placar_dev_iter*.csv')):\n    d = pd.read_csv(f)\n    d = d[d.configuracao == 'agente'].assign(iteracao=f.stem.replace('placar_dev_', ''))\n    hist.append(d)\nhist = pd.concat(hist).set_index('iteracao')\nhist['mudanca'] = ['versão inicial', 'checagem de números ignora ids; verificador menos rígido; sem veto da triagem',\n                   'verificador só rebaixa a confiança', 'exige evidência literal copiada do trecho', 'FINAL: volta a bloquear pelo verificador'][:len(hist)]\nhist[['mudanca', 'acerto_total_%', 'recusa_correta_nao_consta_%', 'alucinacao_%', 'recusa_indevida_%', 'sem_fundamentacao_%', 'precisao_citacoes_%']]"),
    ("md", "**Escolha no DEV:** o verificador LLM do 3B é pouco discriminativo: aponta \"problema\" até em respostas certas. Bloquear custa recusas indevidas; não bloquear deixa passar respostas para perguntas que não constam (ex.: inventar o horário de um posto). Para um assistente lido em voz alta para idosos e pessoas com deficiência visual, escolhemos **bloquear**: \"não encontrei, ligue 156\" é melhor do que uma informação errada."),
    ("code", "placar_dev = pd.read_csv(RAIZ / 'avaliacao' / 'placar_dev.csv').set_index('configuracao')\nplacar_dev"),
    ("md", "## Avaliação final no TESTE (rodada uma vez, depois de congelar o agente)"),
    ("code", "placar = pd.read_csv(RAIZ / 'avaliacao' / 'placar_teste.csv').set_index('configuracao')\ncols = ['acerto_total_%', 'acerto_respondiveis_%', 'recusa_correta_nao_consta_%', 'alucinacao_%', 'recusa_indevida_%',\n        'sem_fundamentacao_%', 'citacao_correta_%', 'precisao_citacoes_%', 'citacoes_validas_%', 'json_valido_%', 'nao_consta_incoerente_%', 'latencia_media_s']\nplacar[cols]"),
    ("code", "import matplotlib.pyplot as plt\nax = placar[['acerto_total_%', 'recusa_correta_nao_consta_%', 'alucinacao_%', 'recusa_indevida_%', 'sem_fundamentacao_%', 'precisao_citacoes_%']].plot.bar(figsize=(11, 4), rot=0, grid=True)\nax.set_ylabel('%'); ax.set_title('Teste final: 40 perguntas × 3 configurações (qwen2.5:3b local)')\nax.legend(loc='upper left', bbox_to_anchor=(1, 1))\nplt.savefig(RAIZ / 'avaliacao' / 'placar_teste.png', dpi=120, bbox_inches='tight')"),
    ("code", "todas = pd.concat([pd.read_json(RAIZ / 'avaliacao' / f'resultados_teste_{c}.jsonl', lines=True) for c in ['sem_contexto', 'rag', 'agente']])\npd.crosstab(todas['categoria'], todas['configuracao'], values=todas['acerto'], aggfunc='mean').round(2)"),
    ("md", "## Erros do agente no teste (matéria-prima dos 5 erros reais, ver `avaliacao/erros.md`)"),
    ("code", "erros = todas[(todas.configuracao == 'agente') & (~todas.acerto)]\nerros[['id', 'categoria', 'nao_consta_esperado', 'resposta', 'fontes', 'recuperados', 'passos']]"),
])
print("notebooks gerados em", PASTA)
