import os
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from provapr.mutacao import ErroMutacao, Mutante, PitMaven, ler_xml

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / "tests" / "fixtures" / "mutations_baseline.xml"
EXEMPLO = RAIZ / "exemplos" / "calculadora"
TESTE = "br.ufmg.dcc.CalendarioTest.testeBissextoComum(br.ufmg.dcc.CalendarioTest)"


def conferir_baseline(caso, mutantes):
    caso.assertEqual(len(mutantes), 13)
    caso.assertEqual(sum(m.morto for m in mutantes), 7)
    cal = Counter(m.status for m in mutantes if m.funcao == "Calendario#ehBissexto")
    caso.assertEqual(sum(cal.values()), 9)
    caso.assertEqual(cal["SURVIVED"], 2)
    caso.assertEqual(cal["NO_COVERAGE"], 2)
    soma = [m for m in mutantes if m.funcao == "Calculadora#soma"]
    caso.assertEqual((len(soma), sum(m.morto for m in soma)), (2, 2))
    sub = [m.status for m in mutantes if m.funcao == "Calculadora#subtrai"]
    caso.assertEqual(sub, ["NO_COVERAGE", "NO_COVERAGE"])


class TestLeituraXml(unittest.TestCase):
    def setUp(self):
        self.mutantes = ler_xml(FIXTURE)

    def test_baseline(self):
        conferir_baseline(self, self.mutantes)

    def test_campos_de_um_sobrevivente(self):
        m = next(m for m in self.mutantes if m.status == "SURVIVED")
        self.assertEqual(m.classe, "br.ufmg.dcc.Calendario")
        self.assertEqual(m.metodo, "ehBissexto")
        self.assertEqual(m.mutador, "MathMutator")
        self.assertEqual(m.matadores, ())
        self.assertEqual(m.cobridores, (TESTE,))
        self.assertFalse(m.morto)

    def test_morto_tem_matador(self):
        for m in self.mutantes:
            if m.morto:
                self.assertTrue(m.matadores, m)

    def test_sem_cobertura_nao_tem_cobridor(self):
        for m in self.mutantes:
            if m.status == "NO_COVERAGE":
                self.assertEqual(m.cobridores, ())

    def test_varios_testes_separados_por_barra(self):
        xml = ("<mutations><mutation detected='true' status='TIMED_OUT'>"
               "<mutatedClass>a.B</mutatedClass><mutatedMethod>m</mutatedMethod>"
               "<lineNumber>3</lineNumber><mutator>x.y.Neg</mutator>"
               "<killingTests>a.T.t1(a.T)|a.T.t2(a.T)</killingTests>"
               "<succeedingTests>a.T.t3(a.T)</succeedingTests></mutation></mutations>")
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
            f.write(xml)
        try:
            m = ler_xml(f.name)[0]
        finally:
            os.unlink(f.name)
        self.assertEqual(m.matadores, ("a.T.t1(a.T)", "a.T.t2(a.T)"))
        self.assertEqual(len(m.cobridores), 3)
        self.assertTrue(m.morto)
        self.assertEqual(m.funcao, "B#m")


@unittest.skipUnless(shutil.which("mvn"), "mvn ausente")
class TestIntegracaoPit(unittest.TestCase):
    def test_pit_real_no_exemplo(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "calc"
            shutil.copytree(EXEMPLO, dest, ignore=shutil.ignore_patterns("target"))
            conferir_baseline(self, PitMaven().executar(dest))

    def test_pom_sem_xml_e_erro_claro(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "calc"
            shutil.copytree(EXEMPLO, dest, ignore=shutil.ignore_patterns("target"))
            pom = dest / "pom.xml"
            pom.write_text(pom.read_text().replace("<param>XML</param>", "").replace(
                "<fullMutationMatrix>true</fullMutationMatrix>", ""))  # só HTML, padrão do PIT
            with self.assertRaisesRegex(ErroMutacao, "mutations.xml"):
                PitMaven().executar(dest)

    def test_pom_sem_matriz_completa_e_erro_claro(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "calc"
            shutil.copytree(EXEMPLO, dest, ignore=shutil.ignore_patterns("target"))
            pom = dest / "pom.xml"
            pom.write_text(pom.read_text().replace(
                "<fullMutationMatrix>true</fullMutationMatrix>", ""))
            with self.assertRaisesRegex(ErroMutacao, "fullMutationMatrix"):
                PitMaven().executar(dest)


if __name__ == "__main__":
    unittest.main()
