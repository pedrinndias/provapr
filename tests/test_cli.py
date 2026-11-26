"""Integração (spec, Testing Plan): AC1, AC2, AC3 em replay numa cópia do exemplo; AC5 e AC6."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from provapr import cli
from provapr.esquemas import esquema_criterios
from provapr.modelo import chave
from provapr.projeto import metodos_publicos

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "exemplos" / "calculadora"
DEMO = RAIZ / "replay" / "demo.jsonl"


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.proj = self.dir / "calculadora"
        shutil.copytree(EXEMPLO, self.proj, ignore=shutil.ignore_patterns("target"))
        self.issue = self.proj / "issue-2.md"
        self.testes = self.proj / "src" / "test" / "java" / "br" / "ufmg" / "dcc"

    def tearDown(self):
        shutil.rmtree(self.dir)

    def rodar(self, replay, respostas=""):
        out, err = io.StringIO(), io.StringIO()
        argv = ["run", "--projeto", str(self.proj), "--issue", str(self.issue),
                "--replay", str(replay), "--saida", str(self.dir)]
        with mock.patch("sys.stdin", io.StringIO(respostas)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            codigo = cli.main(argv)
        relatorio = self.dir / "provapr-relatorio.json"
        dados = json.loads(relatorio.read_text()) if relatorio.exists() else None
        return codigo, out.getvalue(), err.getvalue(), dados

    def test_ac1_tudo_s_libera(self):
        codigo, out, _, dados = self.rodar(DEMO, "s\n" * 6)
        self.assertEqual(codigo, 0)
        self.assertEqual(dados["veredito_depois"], "LIBERADO")
        placar = {c["id"]: (c["mutantes"]["mortos"], c["mutantes"]["total"]) for c in dados["criterios"]}
        self.assertEqual(placar, {"CA1": (2, 2), "CA2": (2, 2), "CA3": (9, 9)})
        self.assertEqual(dados["chamadas_ia_ao_vivo"], 0)
        self.assertIn("BLOQUEADO → LIBERADO", (self.dir / "provapr-relatorio.md").read_text())
        self.assertEqual(len(list(self.testes.glob("ProvaPR*Test.java"))), 2)  # aprovados ficam

    def test_ac2_tudo_n_bloqueia_e_reverte(self):
        codigo, _, _, dados = self.rodar(DEMO, "n\n" * 20)
        self.assertEqual(codigo, 1)
        self.assertEqual(dados["veredito_depois"], "BLOQUEADO")
        self.assertEqual(list(self.testes.glob("ProvaPR*Test.java")), [])

    def test_ac3_suite_vermelha_sem_ia(self):
        fonte = self.proj / "src/main/java/br/ufmg/dcc/Calculadora.java"
        fonte.write_text(fonte.read_text().replace("return x + y;", "return x + y + 1;"))
        codigo, out, _, dados = self.rodar(DEMO)
        self.assertEqual(codigo, 1)
        self.assertIn("BLOQUEADO (SUITE_VERMELHA)", out)
        self.assertIn("testeSoma1", out)
        self.assertIn("testeSoma2", out)
        self.assertEqual(dados["chamadas_ia"], 0)

    def test_ac5_funcao_fora_do_enum_e_recusada(self):
        metodos = metodos_publicos(self.proj)
        prompt = cli.montar_prompt(metodos, self.issue.read_text(encoding="utf-8"))
        esquema = esquema_criterios(metodos)
        resposta = {"criterios": [{"id": "CA1", "descricao": "somar", "funcoes": ["soma(a, b)"],
                                   "exemplos": []}]}
        arq = self.dir / "ruim.jsonl"
        arq.write_text(json.dumps({"versao": 1, "chamada": "extrair_criterios",
                                   "chave": chave("extrair_criterios", "haiku", esquema, prompt, self.proj),
                                   "modelo": "haiku", "resposta": resposta}) + "\n")
        codigo, _, err, _ = self.rodar(arq)
        self.assertEqual(codigo, 2)
        self.assertIn("'soma(a, b)' fora do enum", err)
        self.assertNotIn("Traceback", err)

    def test_ac6_chave_ausente_sai_com_2(self):
        arq = self.dir / "vazio.jsonl"
        arq.write_text("")
        codigo, _, err, _ = self.rodar(arq)
        self.assertEqual(codigo, 2)
        self.assertIn("sem resposta gravada", err)


if __name__ == "__main__":
    unittest.main()
