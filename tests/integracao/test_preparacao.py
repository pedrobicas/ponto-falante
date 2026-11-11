import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/integracao"))
import preparar_backend


@pytest.fixture
def area(tmp_path, monkeypatch):
    raiz = tmp_path / "integracao"
    (raiz / "tests/backend").mkdir(parents=True)
    (raiz / "tests/backend/Contrato.java").write_text("class Contrato {}", encoding="utf-8")
    origem = tmp_path / "backend-original"
    (origem / "src/main/java").mkdir(parents=True)
    (origem / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies/></project>', encoding="utf-8")
    (origem / ".env").write_text("SPTRANS_TOKEN=segredo-local", encoding="utf-8")
    monkeypatch.setattr(preparar_backend, "RAIZ", raiz)
    return origem, raiz / ".validation/backend"


def test_prepara_copia_sem_alterar_pom_original_ou_copiar_segredos(area):
    origem, destino = area
    original = (origem / "pom.xml").read_bytes()
    preparar_backend.preparar(origem, destino)
    assert (origem / "pom.xml").read_bytes() == original
    assert not (destino / ".env").exists()
    assert (destino / "src/test/java/Contrato.java").is_file()
    ns = {"m": preparar_backend.NS}
    deps = ET.parse(destino / "pom.xml").findall("m:dependencies/m:dependency", ns)
    assert [d.findtext("m:artifactId", namespaces=ns) for d in deps] == ["embedded-postgres"]


def test_nova_copia_nao_reutiliza_classe_removida(area):
    origem, destino = area
    classe = origem / "src/main/java/Removida.java"
    classe.write_text("class Removida {}", encoding="utf-8")
    preparar_backend.preparar(origem, destino)
    classe.unlink()
    preparar_backend.preparar(origem, destino)
    assert not (destino / "src/main/java/Removida.java").exists()


def test_rejeita_destino_fora_da_area_de_validacao(area):
    origem, destino = area
    with pytest.raises(ValueError, match=".validation"):
        preparar_backend.preparar(origem, origem)
    assert (origem / "pom.xml").is_file()


def test_rejeita_destino_dentro_da_propria_origem(area):
    _, destino = area
    origem = destino.parent / "fonte-temporaria"
    origem.mkdir(parents=True)
    (origem / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies/></project>', encoding="utf-8")
    filho = origem / "filho"
    filho.mkdir()
    marcador = filho / "preservar.txt"
    marcador.write_text("preservado", encoding="utf-8")
    with pytest.raises(ValueError, match="origem"):
        preparar_backend.preparar(origem, filho)
    assert marcador.read_text(encoding="utf-8") == "preservado"
