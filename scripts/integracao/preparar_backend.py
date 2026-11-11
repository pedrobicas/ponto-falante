"""Cria uma copia de validacao do backend; nunca altera o componente original."""
import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NS = "http://maven.apache.org/POM/4.0.0"


def preparar(origem: Path, destino: Path) -> None:
    origem, destino = origem.resolve(), destino.resolve()
    area = (RAIZ / ".validation").resolve()
    if not destino.is_relative_to(area) or destino == area:
        raise ValueError("Destino deve ficar dentro de .validation/.")
    if (origem.is_relative_to(destino) or destino.is_relative_to(origem)
            or not (origem / "pom.xml").is_file()):
        raise ValueError("Backend de origem invalido; informe a pasta que contem pom.xml.")
    # Caminhos absolutos resolvidos e limitados a .validation antes de qualquer limpeza.
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True, exist_ok=True)
    # Copia apenas o que o Maven precisa; nenhum .env, target ou arquivo de outra tarefa.
    for nome in ("pom.xml", "mvnw", "mvnw.cmd"):
        if (origem / nome).exists():
            shutil.copy2(origem / nome, destino / nome)
    for nome in ("src", ".mvn"):
        if (origem / nome).is_dir():
            shutil.copytree(origem / nome, destino / nome, dirs_exist_ok=True)
    testes = destino / "src/test/java"
    testes.mkdir(parents=True, exist_ok=True)
    shutil.copytree(RAIZ / "tests/backend", testes, dirs_exist_ok=True)
    overlay = RAIZ / "backend/src/main"
    if overlay.is_dir() and not origem.is_relative_to(RAIZ / "backend"):
        shutil.copytree(overlay, destino / "src/main", dirs_exist_ok=True)
    ET.register_namespace("", NS)
    tree = ET.parse(destino / "pom.xml")
    dependencias = tree.getroot().find(f"{{{NS}}}dependencies")
    if dependencias is None:
        raise ValueError("POM sem dependencies.")
    if not any(d.findtext(f"{{{NS}}}artifactId") == "embedded-postgres" for d in dependencias):
        dep = ET.SubElement(dependencias, f"{{{NS}}}dependency")
        for chave, valor in (("groupId", "io.zonky.test"), ("artifactId", "embedded-postgres"),
                             ("version", "2.2.2"), ("scope", "test")):
            ET.SubElement(dep, f"{{{NS}}}{chave}").text = valor
    tree.write(destino / "pom.xml", encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=RAIZ / "backend")
    parser.add_argument("--destination", type=Path, default=RAIZ / ".validation/backend")
    args = parser.parse_args()
    preparar(args.source, args.destination)
    print("Backend preparado em .validation; arquivos originais preservados.")
