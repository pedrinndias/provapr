import shutil
import tempfile
import unittest
from pathlib import Path

from provapr.projeto import ler_surefire, metodos_publicos, rodar_testes

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "exemplos" / "calculadora"


class TestMetodosPublicos(unittest.TestCase):
    def test_exemplo(self):
        self.assertEqual(metodos_publicos(EXEMPLO), {
            "Calculadora#soma", "Calculadora#subtrai", "Calendario#ehBissexto"})

    def test_ignora_privado_e_construtor(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "src", "main", "java", "x")
            p.mkdir(parents=True)
            (p / "A.java").write_text(
                "package x;\npublic class A {\n  public A() {}\n"
                "  private int p() { return 1; }\n"
                "  public static java.util.List<String> lista(int n) { return null; }\n"
                "  public void faz() {}\n}\n")
            self.assertEqual(metodos_publicos(tmp), {"A#lista", "A#faz"})


class TestSurefire(unittest.TestCase):
    def test_le_falha(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "TEST-x.CalcTest.xml").write_text(
                "<testsuite><testcase classname='x.CalcTest' name='ok'/>"
                "<testcase classname='x.CalcTest' name='testeSoma1'>"
                "<failure message='expected:&lt;5&gt; but was:&lt;6&gt;'/></testcase>"
                "</testsuite>")
            self.assertEqual(ler_surefire(tmp),
                             [("x.CalcTest.testeSoma1", "expected:<5> but was:<6>")])


@unittest.skipUnless(shutil.which("mvn"), "mvn ausente")
class TestIntegracaoMvn(unittest.TestCase):
    def test_verde_e_vermelho_com_bug_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "calc"
            shutil.copytree(EXEMPLO, dest, ignore=shutil.ignore_patterns("target"))
            self.assertTrue(rodar_testes(dest).verde)
            fonte = dest / "src/main/java/br/ufmg/dcc/Calculadora.java"
            fonte.write_text(fonte.read_text().replace("x + y;", "x + y + 1;"))
            r = rodar_testes(dest)
            self.assertFalse(r.verde)
            self.assertIn(("br.ufmg.dcc.CalculadoraTest.testeSoma1",
                           "expected:<5> but was:<6>"), r.falhas)


if __name__ == "__main__":
    unittest.main()
