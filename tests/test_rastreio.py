import unittest
from pathlib import Path

from provapr import rastreio
from provapr.mutacao import Mutante, ler_xml

FIXTURE = Path(__file__).parent / "fixtures" / "mutations_baseline.xml"


def m(status):
    return Mutante("br.ufmg.dcc.X", "f", 1, "M", status, (), ())


class TestStatus(unittest.TestCase):
    def test_os_4_status(self):
        self.assertEqual(rastreio.status([], [m("KILLED")]), rastreio.NAO_RASTREADO)
        self.assertEqual(rastreio.status(["X#f"], [m("NO_COVERAGE")] * 2), rastreio.SEM_TESTE)
        self.assertEqual(rastreio.status(["X#f"], [m("KILLED"), m("SURVIVED")]), rastreio.FRACO)
        self.assertEqual(rastreio.status(["X#f"], [m("KILLED"), m("TIMED_OUT")]), rastreio.PROVADO)

    def test_equivalente_sai_do_denominador(self):
        vivo = m("SURVIVED")
        self.assertEqual(rastreio.status(["X#f"], [m("KILLED"), vivo], [vivo]), rastreio.PROVADO)

    def test_veredito(self):
        self.assertEqual(rastreio.veredito([rastreio.PROVADO] * 2), rastreio.LIBERADO)
        self.assertEqual(rastreio.veredito([rastreio.PROVADO, rastreio.FRACO]), rastreio.BLOQUEADO)
        self.assertEqual(rastreio.veredito([]), rastreio.BLOQUEADO)

    def test_fixture_baseline(self):
        crits = [{"id": f"CA{i}", "descricao": "", "funcoes": [f], "exemplos": []}
                 for i, f in enumerate(["Calculadora#soma", "Calculadora#subtrai",
                                        "Calendario#ehBissexto"], 1)]
        r = rastreio.rastrear(crits, ler_xml(FIXTURE))
        self.assertEqual([c.status for c in r], ["PROVADO", "SEM_TESTE", "FRACO"])
        self.assertEqual((r[2].mortos, len(r[2].mutantes)), (5, 9))
        self.assertEqual(r[0].testes_ligados, ["testeSoma1", "testeSoma2"])
