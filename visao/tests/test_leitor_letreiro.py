from leitor_letreiro import extrair_candidatos, ler_linha, similaridade

LINHAS = ["8000-10", "875A-10", "6450-10", "N101-11"]


def test_extrai_linha_com_destino():
    assert extrair_candidatos("8000-10 TERM. LAPA") == ["8000-10"]


def test_ignora_palavras_sem_numero():
    assert extrair_candidatos("TERM LAPA") == []


def test_letreiro_so_com_codigo_casa_pela_parte_principal():
    assert similaridade("875A", "875A-10") == 1.0


def test_corrige_confusao_de_ocr_O_por_zero():
    leitura = ler_linha([("8OOO-1O LAPA", 0.9)], LINHAS)
    assert leitura.linha == "8000-10"
    assert leitura.confianca > 0.8


def test_nao_inventa_linha_que_nao_passa_no_ponto():
    leitura = ler_linha([("9999-10", 0.95)], LINHAS)
    assert leitura.linha is None


def test_sem_lista_da_api_aceita_padrao_com_confianca_reduzida():
    leitura = ler_linha([("6450-10 PQ. D. PEDRO", 0.9)], None)
    assert leitura.linha == "6450-10"
    assert leitura.confianca < 0.9


def test_ocr_vazio():
    leitura = ler_linha([], LINHAS)
    assert leitura.linha is None and leitura.confianca == 0.0


# --- regras extras usadas pela conferência pelo celular (servico/) ---

def test_sem_sufixo_no_letreiro_nao_inventa_sufixo():
    r = ler_linha([("875A JD. ANGELA", 0.9)], ["875A-10", "875A-21"], rejeitar_ambiguas=True)
    assert r.linha == "875A-10"           # casa com a primeira variante da lista...
    assert r.texto_confirmado() == "875A"  # ...mas só afirma o que o letreiro mostrou


def test_com_sufixo_confirma_linha_completa():
    r = ler_linha([("875A-21 METRO", 0.9)], ["875A-10", "875A-21"], rejeitar_ambiguas=True)
    assert r.texto_confirmado() == "875A-21"


def test_leitura_ambigua_entre_numeros_diferentes_e_recusada():
    # "8750" fica igualmente perto de 875A e 875C: na dúvida, não afirma nenhuma das duas.
    linhas = ["875A-10", "875C-10"]
    assert ler_linha([("8750-10", 0.9)], linhas, rejeitar_ambiguas=True).linha is None
    # o comportamento original (usado na avaliação do relatório) continua igual
    assert ler_linha([("8750-10", 0.9)], linhas).linha == "875A-10"


def test_leitura_exata_nunca_e_ambigua():
    r = ler_linha([("875C-10", 0.9)], ["875A-10", "875C-10"], rejeitar_ambiguas=True)
    assert r.linha == "875C-10" and r.texto_confirmado() == "875C-10"
