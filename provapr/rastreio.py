"""Critério → função → teste e o veredito (seção 3 da arquitetura)."""
from dataclasses import dataclass, field

PROVADO, FRACO, SEM_TESTE = "PROVADO", "FRACO", "SEM_TESTE"
NAO_RASTREADO, SUITE_VERMELHA = "NAO_RASTREADO", "SUITE_VERMELHA"
LIBERADO, BLOQUEADO = "LIBERADO", "BLOQUEADO"


@dataclass
class Criterio:
    id: str
    descricao: str
    funcoes: list
    exemplos: list = field(default_factory=list)
    mutantes: list = field(default_factory=list)
    status: str = ""

    @property
    def mortos(self):
        return sum(m.morto for m in self.mutantes)

    @property
    def testes_ligados(self):
        nomes = {t.split("(")[0].rsplit(".", 1)[-1] for m in self.mutantes for t in m.cobridores}
        return sorted(nomes)


def status(funcoes, mutantes, equivalentes=()):
    if not funcoes:
        return NAO_RASTREADO
    considerados = [m for m in mutantes if m not in equivalentes]
    if all(m.morto for m in considerados):
        return PROVADO
    if all(m.status == "NO_COVERAGE" for m in considerados):
        return SEM_TESTE
    return FRACO


def rastrear(criterios, mutantes, equivalentes=()):
    """criterios: dicts da IA. Devolve [Criterio] com mutantes e status."""
    saida = []
    for c in criterios:
        ms = [m for m in mutantes if m.funcao in c["funcoes"]]
        crit = Criterio(c["id"], c["descricao"], list(c["funcoes"]), list(c["exemplos"]), ms)
        crit.status = status(crit.funcoes, ms, equivalentes)
        saida.append(crit)
    return saida


def veredito(statuses):
    statuses = list(statuses)
    return LIBERADO if statuses and all(s == PROVADO for s in statuses) else BLOQUEADO
