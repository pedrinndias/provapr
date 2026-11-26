"""Projeto Maven: mvn test, leitura do surefire e métodos públicos por regex."""
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

RE_CLASSE = re.compile(r"\bpublic\s+(?:final\s+|abstract\s+)*class\s+(\w+)")
RE_METODO = re.compile(
    r"^\s*public\s+(?!class\b)(?:static\s+|final\s+|synchronized\s+)*"
    r"[\w.<>\[\], ]+?\s+(\w+)\s*\(", re.M)


@dataclass
class ResultadoTestes:
    codigo: int
    falhas: list = field(default_factory=list)  # (teste, mensagem)
    saida: str = ""

    @property
    def verde(self):
        return self.codigo == 0


def metodos_publicos(projeto):
    """Devolve {'Classe#metodo'} dos fontes em src/main/java."""
    achados = set()
    for arq in sorted(Path(projeto, "src", "main", "java").rglob("*.java")):
        texto = arq.read_text(encoding="utf-8")
        mc = RE_CLASSE.search(texto)
        if not mc:
            continue
        classe = mc.group(1)
        for nome in RE_METODO.findall(texto):
            if nome != classe:  # construtor
                achados.add(f"{classe}#{nome}")
    return achados


def ler_surefire(pasta):
    falhas = []
    for arq in sorted(Path(pasta).glob("TEST-*.xml")):
        for caso in ET.parse(arq).getroot().iter("testcase"):
            for tag in ("failure", "error"):
                el = caso.find(tag)
                if el is not None:
                    nome = f"{caso.get('classname')}.{caso.get('name')}"
                    falhas.append((nome, el.get("message") or ""))
    return falhas


def rodar_testes(projeto, mvn="mvn"):
    r = subprocess.run([mvn, "-q", "-B", "test"], cwd=projeto, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True)
    falhas = ler_surefire(Path(projeto, "target", "surefire-reports"))
    return ResultadoTestes(r.returncode, falhas, r.stdout + r.stderr)


def compilar_testes(projeto, mvn="mvn"):
    """Portão 1: test-compile. Devolve (ok, saída)."""
    r = subprocess.run([mvn, "-q", "-B", "test-compile"], cwd=projeto,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr


def testar_metodo(projeto, classe_teste, metodo, mvn="mvn"):
    """Portão 2: roda só o método novo no código original. Devolve (ok, mensagem)."""
    pasta = Path(projeto, "target", "surefire-reports")
    for arq in pasta.glob(f"TEST-*.{classe_teste}.xml"):
        arq.unlink()
    r = subprocess.run([mvn, "-q", "-B", "test", f"-Dtest={classe_teste}#{metodo}"],
                       cwd=projeto, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if r.returncode == 0:
        return True, ""
    falhas = [msg for nome, msg in ler_surefire(pasta) if nome.endswith(f"{classe_teste}.{metodo}")]
    return False, (falhas[0] if falhas else (r.stdout + r.stderr)[-300:]).strip()[:300]
