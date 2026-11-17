"""Ponta a ponta da conferência do letreiro no navegador: câmera -> Spring -> serviço de visão (modelo real).

A câmera do navegador é simulada com uma foto real de ônibus (Chromium --use-file-for-fake-video-capture); todo o
resto é real: a tela do Embarque Assistido, o backend, o serviço visao/servico com YOLO + EasyOCR.

Requisitos: app rodando com a visão conectada (PF_VISAO_URL ou túnel registrado), `pip install playwright`, ffmpeg.
Uso:
    python scripts/integracao/validar_visao.py [--base http://127.0.0.1:8080] [--foto visao/amostras/imagens/demo/01_647P-10.jpg]
        [--chromium /caminho/do/chrome]

Cobre: escolher ponto e linha (modo demonstração), abrir a câmera, conferir, resultado vindo do modelo (nome
pf-visao), frase falada, acessibilidade (axe) e captura em output/playwright/.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
AXE = RAIZ / "frontend/node_modules/axe-core/axe.min.js"
SAIDA = RAIZ / "output/playwright"
GRAVA_FALAS = """
(() => {
  window.__falas = [];
  if (!window.speechSynthesis) return;
  window.speechSynthesis.speak = (fala) => { window.__falas.push(fala.text); };
})();
"""


def video_da_foto(foto: Path, destino: Path) -> None:
    """Converte a foto num vídeo Y4M curto (o Chromium repete o arquivo como se fosse a câmera)."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", str(foto), "-t", "2", "-r", "5",
                    "-vf", "scale=1280:-2", "-pix_fmt", "yuv420p", str(destino)], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--foto", default=str(RAIZ / "visao/amostras/imagens/demo/01_647P-10.jpg"))
    ap.add_argument("--chromium", default=None, help="executável do Chromium/Chrome (padrão: o do Playwright)")
    args = ap.parse_args()
    r: dict = {"base": args.base, "foto": Path(args.foto).name}

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        video = Path(tmp) / "camera.y4m"
        video_da_foto(Path(args.foto), video)
        navegador = pw.chromium.launch(executable_path=args.chromium, args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-video-capture={video}"])
        contexto = navegador.new_context(permissions=["camera"], locale="pt-BR", viewport={"width": 1280, "height": 900},
                                          bypass_csp=True)  # só para injetar axe e ler as falas
        contexto.add_init_script(GRAVA_FALAS)
        page = contexto.new_page()

        page.goto(f"{args.base}/embarque?modo=demo")
        page.get_by_label("Ou digite o nome do ponto").fill("Paulista")
        page.get_by_role("search", name="Buscar ponto").get_by_role("button", name="Buscar").click()
        page.locator(".opcao-ponto").first.click()
        page.get_by_role("button", name="Sim, é este ponto").click()
        primeira = page.locator(".opcao-linha input[type=checkbox]").first
        expect(primeira).to_be_visible(timeout=15000)
        primeira.check()
        page.get_by_role("button", name="Começar a acompanhar").click()
        expect(page.get_by_role("heading", name="Acompanhando")).to_be_visible(timeout=15000)

        page.get_by_role("button", name="Conferir o letreiro pela câmera").click()
        page.get_by_role("button", name="Abrir a câmera").click(timeout=15000)
        page.wait_for_function("document.querySelector('.camera__video')?.videoWidth > 0", timeout=15000)
        antes = len(page.evaluate("window.__falas"))
        page.get_by_role("button", name="Conferir letreiro").click()
        resultado = page.locator(".camera__resultado")
        expect(resultado).to_be_visible(timeout=60000)
        r["resultado"] = resultado.get_attribute("data-resultado")
        r["texto"] = resultado.inner_text()
        if "pf-visao" not in r["texto"]:
            raise AssertionError(f"O resultado não veio do modelo da equipe: {r['texto']}")
        page.wait_for_function(f"window.__falas.length > {antes}", timeout=5000)
        r["falado"] = page.evaluate("window.__falas")[-1]

        page.add_script_tag(path=str(AXE))
        falhas = page.evaluate("""async () => (await axe.run(document.querySelector('.camera'),
            { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } })).violations.map(v => v.id)""")
        r["acessibilidade"] = falhas
        SAIDA.mkdir(parents=True, exist_ok=True)
        page.locator(".camera").screenshot(path=str(SAIDA / "visao-conferencia-desktop.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator(".camera").scroll_into_view_if_needed()
        page.screenshot(path=str(SAIDA / "visao-conferencia-celular.png"))
        navegador.close()

    print(json.dumps(r, ensure_ascii=False, indent=2))
    if falhas:
        print("Falhas de acessibilidade:", falhas, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
