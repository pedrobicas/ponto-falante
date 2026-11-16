"""Teste ponta a ponta do Embarque Assistido no navegador (Playwright), em modo demonstração.

Requer `pip install playwright` e Microsoft Edge ou Google Chrome instalado (ou `playwright install chromium`).
Uso (com o app rodando, por exemplo `python scripts/integracao/rodar_mvp_local.py --build`):
    python scripts/integracao/validar_embarque.py [--base http://127.0.0.1:8080] [--canal msedge|chrome|chromium]

Cobre: escolher e confirmar o ponto, escolher a linha, acompanhar com aviso falado, salvar o trajeto,
comandos da assistente com confirmação, retomar após recarregar, usar o favorito, câmera ainda não conectada
(mensagem honesta, sem resultado inventado), "Embarquei", apagar dados, acessibilidade (axe, WCAG 2.1 AA)
em desktop e celular, e ausência de rolagem horizontal no celular. Salva capturas em output/playwright/.
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
AXE = RAIZ / "frontend/node_modules/axe-core/axe.min.js"
SAIDA = RAIZ / "output/playwright"

GRAVA_FALAS = """
(() => {
  window.__falas = [];
  if (!window.speechSynthesis) return;
  window.speechSynthesis.speak = (fala) => { window.__falas.push({ texto: fala.text, idioma: fala.lang }); };
})();
"""


def auditar(page: Page, nome: str, resultados: dict) -> None:
    falhas = page.evaluate(
        """async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }))
             .violations.map(v => ({ id: v.id, impacto: v.impact, alvos: v.nodes.slice(0, 3).map(n => n.target.join(' ')) }))"""
    )
    resultados["acessibilidade"].append({"tela": nome, "falhas": falhas})
    if falhas:
        raise AssertionError(f"Acessibilidade em {nome}: {json.dumps(falhas, ensure_ascii=False)}")


def falas(page: Page) -> list[str]:
    return [f["texto"] for f in page.evaluate("window.__falas || []")]


def assistente(page: Page, texto: str) -> str:
    campo = page.get_by_label("Comando ou pergunta para a assistente")
    antes = page.locator(".assistente-emb__conversa .bolha:not(.bolha--voce)").count()
    campo.fill(texto)
    campo.press("Enter")
    expect(page.locator(".assistente-emb__conversa .bolha:not(.bolha--voce):not(.bolha--pensando)")).to_have_count(antes + 1, timeout=15000)
    return page.locator(".assistente-emb__conversa .bolha:not(.bolha--voce) p").last.inner_text()


def sem_rolagem_horizontal(page: Page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def fluxo_desktop(page: Page, base: str, r: dict) -> None:
    page.goto(f"{base}/embarque?modo=demo")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Do ponto até o ônibus")
    expect(page.locator('[aria-current="step"]')).to_contain_text("Ponto")
    auditar(page, "embarque-ponto", r)

    # 1. Busca e confirmação do ponto.
    page.get_by_label("Ou digite o nome do ponto").fill("Paulista")
    page.get_by_role("search", name="Buscar ponto").get_by_role("button", name="Buscar").click()
    opcao = page.locator(".opcao-ponto").first
    expect(opcao).to_be_visible(timeout=15000)
    nome_ponto = page.locator(".opcao-ponto__nome").first.inner_text()
    opcao.click()
    expect(page.get_by_role("heading", name="É este o seu ponto?")).to_be_visible()
    auditar(page, "embarque-confirmar-ponto", r)
    page.get_by_role("button", name="Sim, é este ponto").click()

    # 2. Escolha da linha (previsões simuladas da demonstração).
    expect(page.get_by_role("heading", name="Qual ônibus você vai pegar?")).to_be_visible()
    primeira = page.locator(".opcao-linha input[type=checkbox]").first
    expect(primeira).to_be_visible(timeout=15000)
    primeira.check()
    auditar(page, "embarque-linha", r)
    page.get_by_role("button", name="Começar a acompanhar").click()

    # 3. Acompanhamento: painel, selo SIMULADO e aviso falado com prefixo de demonstração.
    expect(page.get_by_role("heading", name="Acompanhando")).to_be_visible(timeout=15000)
    expect(page.locator(".painel-emb .quadro__fita")).to_contain_text("SIMULADO")
    expect(page.locator(".painel-emb__proximo, .painel-emb__vazio")).to_be_visible(timeout=15000)
    expect(page.locator(".ultimo-aviso")).to_contain_text("Demonstração com horários simulados")
    ditas = falas(page)
    if not any("Demonstração com horários simulados" in f for f in ditas):
        raise AssertionError(f"O primeiro aviso não foi falado: {ditas}")
    r["fluxo"]["ponto"] = nome_ponto
    r["fluxo"]["primeiro_aviso"] = page.locator(".ultimo-aviso").inner_text()
    auditar(page, "embarque-acompanhando", r)
    SAIDA.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SAIDA / "embarque-acompanhando-desktop.png"), full_page=True)

    # 4. Repetir aviso fala a mesma frase de novo.
    qtd = len(falas(page))
    page.get_by_role("button", name="Repetir aviso").click()
    page.wait_for_function(f"(window.__falas || []).length > {qtd}")

    # 5. Câmera sem modelo conectado: mensagem honesta e nenhum resultado.
    page.get_by_role("button", name="Conferir o letreiro pela câmera").click()
    expect(page.locator(".camera")).to_contain_text("ainda não está conectada", timeout=10000)
    if page.locator(".camera__resultado").count():
        raise AssertionError("A câmera mostrou um resultado sem modelo conectado.")
    auditar(page, "embarque-camera-nao-conectada", r)
    page.get_by_role("button", name="Conferir o letreiro pela câmera").click()

    # 6. Salvar o trajeto como favorito.
    page.get_by_role("button", name="Salvar este trajeto nos favoritos").click()
    page.get_by_label("Apelido do trajeto (opcional)").fill("Trabalho")
    page.get_by_role("button", name="Salvar trajeto").click()
    expect(page.get_by_text('Trajeto salvo como "Trabalho"')).to_be_visible(timeout=10000)

    # 7. Assistente: comandos executam ações; encerrar pede confirmação.
    resposta = assistente(page, "quanto falta?")
    r["fluxo"]["quanto_falta"] = resposta
    if "Demonstração" not in resposta and "minuto" not in resposta and "Nenhum ônibus" not in resposta:
        raise AssertionError(f"Resposta inesperada para 'quanto falta': {resposta}")
    resposta = assistente(page, "parar o acompanhamento")
    if "Encerrar o acompanhamento" not in resposta:
        raise AssertionError(f"Encerrar não pediu confirmação: {resposta}")
    expect(page.get_by_role("group", name="Confirmação pendente")).to_be_visible()
    auditar(page, "embarque-confirmacao", r)
    resposta = assistente(page, "sim")
    # Desistiu, mas continua no mesmo ponto: volta para a escolha da linha.
    expect(page.get_by_role("heading", name="Qual ônibus você vai pegar?")).to_be_visible(timeout=10000)
    page.get_by_role("button", name="Trocar ponto").click()
    expect(page.get_by_role("heading", name="Em qual ponto você está?")).to_be_visible(timeout=10000)

    # 8. Favorito aparece e inicia o acompanhamento de novo; recarregar retoma o acompanhamento.
    favorito = page.locator(".rota-fav__principal").filter(has_text="Trabalho")
    expect(favorito).to_be_visible()
    favorito.click()
    expect(page.get_by_role("heading", name="Acompanhando")).to_be_visible(timeout=15000)
    page.reload()
    expect(page.get_by_role("heading", name="Acompanhando")).to_be_visible(timeout=15000)
    r["fluxo"]["retomou_apos_recarregar"] = True

    # 9. Embarquei encerra e volta ao começo.
    page.get_by_role("button", name="Embarquei").click()
    expect(page.get_by_role("heading", name="Em qual ponto você está?")).to_be_visible(timeout=10000)

    # 10. Assistente por voz/texto: busca por nome e escolha por número.
    resposta = assistente(page, "estou no ponto Paulista")
    if "ponto" not in resposta.lower():
        raise AssertionError(f"Busca pela assistente falhou: {resposta}")
    r["fluxo"]["assistente_busca"] = resposta[:160]


def fluxo_celular(page: Page, base: str, r: dict) -> None:
    page.goto(f"{base}/embarque?modo=demo")
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    if not sem_rolagem_horizontal(page):
        raise AssertionError("Rolagem horizontal na tela de embarque (celular).")
    expect(page.get_by_role("link", name="Embarque")).to_be_visible()
    auditar(page, "celular-embarque-ponto", r)
    favorito = page.locator(".rota-fav__principal").filter(has_text="Trabalho")
    expect(favorito).to_be_visible(timeout=10000)
    favorito.click()
    expect(page.get_by_role("heading", name="Acompanhando")).to_be_visible(timeout=15000)
    expect(page.locator(".painel-emb__proximo, .painel-emb__vazio")).to_be_visible(timeout=15000)
    if not sem_rolagem_horizontal(page):
        raise AssertionError("Rolagem horizontal no acompanhamento (celular).")
    auditar(page, "celular-acompanhando", r)
    page.screenshot(path=str(SAIDA / "embarque-acompanhando-celular.png"), full_page=True)
    page.get_by_role("button", name="Embarquei").click()
    expect(page.get_by_role("heading", name="Em qual ponto você está?")).to_be_visible(timeout=10000)

    # Privacidade: apagar os dados do aparelho remove o favorito.
    page.get_by_role("button", name="Apagar meus dados do embarque").click()
    page.get_by_role("button", name="Apagar tudo").click()
    expect(page.locator(".rota-fav__principal")).to_have_count(0, timeout=10000)
    r["fluxo"]["dados_apagados"] = True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--canal", default="msedge", help="msedge, chrome ou chromium (Playwright)")
    ap.add_argument("--visivel", action="store_true", help="Abre a janela do navegador.")
    args = ap.parse_args()
    r: dict = {"acessibilidade": [], "fluxo": {}}
    with sync_playwright() as p:
        nav = p.chromium.launch(channel=None if args.canal == "chromium" else args.canal, headless=not args.visivel)
        try:
            for nome, opcoes, fluxo in (
                ("desktop", {"viewport": {"width": 1366, "height": 900}}, fluxo_desktop),
                ("celular", {**p.devices["Pixel 7"]}, fluxo_celular),
            ):
                ctx = nav.new_context(locale="pt-BR", **opcoes)
                if nome == "celular":
                    # Mesmo aparelho do fluxo desktop: o identificador fica no armazenamento local.
                    ctx.add_init_script(f"localStorage.setItem('pf.dispositivo', {json.dumps(r['dispositivo'])});")
                ctx.add_init_script(path=str(AXE))
                ctx.add_init_script(GRAVA_FALAS)
                page = ctx.new_page()
                erros: list[str] = []
                page.on("pageerror", lambda e: erros.append(str(e)))
                fluxo(page, args.base, r)
                if nome == "desktop":
                    r["dispositivo"] = page.evaluate("localStorage.getItem('pf.dispositivo')")
                if erros:
                    raise AssertionError(f"Erros de JavaScript ({nome}): {erros}")
                ctx.close()
        finally:
            nav.close()
    r.pop("dispositivo", None)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print("OK: embarque assistido validado em desktop e celular.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
