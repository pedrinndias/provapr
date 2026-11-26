"""Adapter ExecutorMutacao -> PitMaven: roda o PIT e traduz mutations.xml em Mutante."""
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

DETECTADOS = {"KILLED", "TIMED_OUT", "MEMORY_ERROR"}


@dataclass(frozen=True)
class Mutante:
    classe: str
    metodo: str
    linha: int
    mutador: str
    status: str
    matadores: tuple
    cobridores: tuple
    descricao: str = ""

    @property
    def morto(self):
        return self.status in DETECTADOS

    @property
    def funcao(self):
        return f"{self.classe.rsplit('.', 1)[-1]}#{self.metodo}"


class ErroMutacao(RuntimeError):
    pass


class ExecutorMutacao:
    """Porta: qualquer ferramenta de mutação devolve uma lista de Mutante."""

    def executar(self, projeto, classe=None):
        raise NotImplementedError


def _testes(texto):
    return tuple(t for t in (texto or "").split("|") if t)


def ler_xml(caminho):
    raiz = ET.parse(caminho).getroot()
    mutantes = []
    for m in raiz.iter("mutation"):
        matadores = _testes(m.findtext("killingTests"))
        sobreviventes = _testes(m.findtext("succeedingTests"))
        mutantes.append(Mutante(
            classe=m.findtext("mutatedClass"),
            metodo=m.findtext("mutatedMethod"),
            linha=int(m.findtext("lineNumber")),
            mutador=m.findtext("mutator").rsplit(".", 1)[-1],
            status=m.get("status"),
            matadores=matadores,
            cobridores=matadores + sobreviventes,
            descricao=m.findtext("description") or "",
        ))
    return mutantes


class PitMaven(ExecutorMutacao):
    def __init__(self, mvn="mvn"):
        self.mvn = mvn

    def executar(self, projeto, classe=None):
        projeto = Path(projeto)
        cmd = [self.mvn, "-q", "-B", "test-compile",
               "org.pitest:pitest-maven:mutationCoverage"]
        if classe:
            cmd.append(f"-DtargetClasses={classe}")
        r = subprocess.run(cmd, cwd=projeto, capture_output=True, text=True)
        if r.returncode != 0:
            raise ErroMutacao((r.stdout + r.stderr)[-2000:])
        return ler_xml(projeto / "target" / "pit-reports" / "mutations.xml")
