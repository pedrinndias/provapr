import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from provapr import laco as L
from provapr.esquemas import ESQUEMA_TESTE
from provapr.modelo import Completar, ErroModelo, Gravador, ProvedorModelo, Replay, SemRespostaGravada
from provapr.mutacao import Mutante
from provapr.rastreio import Criterio

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "calculadora"
CLASSE = "br.ufmg.dcc.Calendario"


def mutante(linha, mutador, status="SURVIVED", matadores=()):
    return Mutante(CLASSE, "ehBissexto", linha, mutador, status, tuple(matadores),
                   tuple(matadores), f"desc {mutador}")


def resp(nome):
    return {"nome_teste": nome, "corpo_metodo": "assertTrue(new Calendario().ehBissexto(400));",
            "entrada": "400", "saida_esperada": "true", "justificativa": "x"}


class Prov(ProvedorModelo):
    def __init__(self, respostas):
        super().__init__()
        self.respostas = list(respostas)

    def responder(self, chamada, prompt, schema):
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        self.duracoes_ms.append(1)
        return r


class PitFalso:
    """Devolve os alvos mortos pelo teste de nome dado (com o formato do PIT)."""

    def __init__(self, mortos):
        self.mortos = mortos

    def executar(self, projeto, classe=None):
        saida = []
        for m in self.mortos:
            tid = f"{CLASSE.rsplit('.', 1)[0]}.ProvaPRCalendarioTest.{m[2]}({CLASSE}Test)"
            saida.append(mutante(m[0], m[1], "KILLED", [tid]))
        return saida


class TestLaco(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        shutil.copytree(EXEMPLO / "src", self.dir / "src")
        self.arq = self.dir / "src/test/java/br/ufmg/dcc/ProvaPRCalendarioTest.java"
        self.m5 = mutante(5, "MathMutator")
        self.b5 = mutante(5, "BooleanFalseReturnValsMutator", "NO_COVERAGE")
        self.crit = Criterio("CA3", "bissexto", ["Calendario#ehBissexto"], ["400 -> true"],
                             [self.m5, self.b5])

    def tearDown(self):
        shutil.rmtree(self.dir)

    def laco(self, prov, respostas, pit):
        entrada = iter(respostas)
        return L.Laco(self.dir, prov, entrada=lambda _: next(entrada), pit=pit)

    def portoes_ok(self):
        return mock.patch.multiple(L, compilar_testes=lambda *a: (True, ""),
                                   testar_metodo=lambda *a: (True, ""))

    def test_filtro_estatico(self):
        self.assertIn("System.exit", L.filtro_estatico("System.exit(0);", "testeX", set()))
        self.assertIn("Random", L.filtro_estatico("new java.util.Random();", "testeX", set()))
        self.assertIn("já existe", L.filtro_estatico("assertTrue(true);", "testeX", {"testeX"}))
        self.assertIsNone(L.filtro_estatico("assertTrue(true);", "testeX", {"testeY"}))

    def test_limpar_erro(self):
        raiz = self.dir.resolve()
        saida = (f"[ERROR] COMPILATION ERROR : \n[ERROR] {raiz}/src/test/A.java:[4,34] cannot find symbol\n"
                 "  symbol:   method x()\n[ERROR] Failed to execute goal ...\n[ERROR] depois")
        self.assertEqual(L.limpar_erro(saida, self.dir),
                         "[ERROR] src/test/A.java cannot find symbol\nsymbol:   method x()")

    def test_aprovado_mata_e_pula_o_segundo(self):
        pit = PitFalso([(5, "MathMutator", "testeA"), (5, "BooleanFalseReturnValsMutator", "testeA")])
        lc = self.laco(Prov([resp("testeA")]), ["s"], pit)
        with self.portoes_ok():
            lc.executar([self.crit])
        self.assertEqual(lc.aprovados, ["testeA"])
        self.assertEqual(len(lc.tentativas), 1)  # o 2º alvo foi pulado
        self.assertIn("public void testeA()", self.arq.read_text())

    def test_rejeitado_some_do_disco(self):
        # alvos em ordem de mutador: BooleanFalse… (testeA) antes de Math… (testeB)
        pit = PitFalso([(5, "BooleanFalseReturnValsMutator", "testeA"), (5, "MathMutator", "testeB")])
        lc = self.laco(Prov([resp("testeA"), resp("testeB")]), ["n", "n"], pit)
        with self.portoes_ok():
            lc.executar([self.crit])
        self.assertEqual(lc.aprovados, [])
        self.assertEqual([t.humano for t in lc.tentativas], ["rejeitado pelo humano"] * 2)
        self.assertFalse(self.arq.exists())

    def test_nao_matou_esgota_e_declara_equivalente(self):
        pit = PitFalso([])
        crit = Criterio("CA3", "b", ["Calendario#ehBissexto"], [], [self.m5])
        lc = self.laco(Prov([resp("testeA"), resp("testeB"), ErroModelo("ruim")]), ["e"], pit)
        with self.portoes_ok():
            lc.executar([crit])
        self.assertEqual(len(lc.tentativas), 3)
        self.assertEqual(lc.equivalentes, {L.chave_mutante(self.m5)})
        self.assertEqual(lc.tentativas[-1].humano, "declarado equivalente")
        self.assertFalse(self.arq.exists())

    def test_eof_na_pergunta_vale_nao(self):
        def fim(_):
            raise EOFError
        self.assertEqual(L.perguntar("?", fim), "")

    def test_ctrl_c_reverte(self):
        def interrompe(*a):
            self.assertTrue(self.arq.exists())  # candidato estava no disco
            raise KeyboardInterrupt
        lc = self.laco(Prov([resp("testeA")]), [], PitFalso([]))
        with mock.patch.object(L, "compilar_testes", interrompe):
            with self.assertRaises(KeyboardInterrupt):
                lc.executar([self.crit])
        self.assertFalse(self.arq.exists())

    def test_sem_resposta_gravada_propaga(self):
        lc = self.laco(Prov([SemRespostaGravada("sem resposta gravada")]), [], PitFalso([]))
        with self.assertRaises(SemRespostaGravada):
            lc.executar([self.crit])

    def test_arquivo_existente_volta_igual(self):
        original = "package br.ufmg.dcc;\npublic class ProvaPRCalendarioTest {\n}\n"
        self.arq.write_text(original)
        lc = self.laco(Prov([resp("testeA")]), ["n"], PitFalso([(5, "MathMutator", "testeA")]))
        crit = Criterio("CA3", "b", ["Calendario#ehBissexto"], [], [self.m5])
        with self.portoes_ok():
            lc.executar([crit])
        self.assertEqual(self.arq.read_text(), original)


class TestGravacaoDeErro(unittest.TestCase):
    def test_erro_gravado_volta_no_replay(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "r.jsonl"
            g = Gravador(Prov([ErroModelo("is_error: x"), resp("testeA")]), arq)
            with self.assertRaises(ErroModelo):
                g.responder("gerar_teste", "p", ESQUEMA_TESTE)
            g.responder("gerar_teste", "p2", ESQUEMA_TESTE)
            self.assertEqual(json.loads(arq.read_text().splitlines()[0])["erro"], "is_error: x")
            r = Replay(arq, g.modelo)
            with self.assertRaises(ErroModelo):
                r.responder("gerar_teste", "p", ESQUEMA_TESTE)
            self.assertEqual(r.responder("gerar_teste", "p2", ESQUEMA_TESTE)["nome_teste"], "testeA")
            with self.assertRaises(SemRespostaGravada):
                r.responder("gerar_teste", "p3", ESQUEMA_TESTE)

    def test_completar_so_chama_o_que_falta(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "r.jsonl"
            Gravador(Prov([resp("testeA")]), arq).responder("gerar_teste", "p", ESQUEMA_TESTE)
            vivo = Prov([resp("testeB")])
            vivo.modelo, vivo.chamadas_ao_vivo = "?", 0
            c = Completar(vivo, arq)
            self.assertEqual(c.responder("gerar_teste", "p", ESQUEMA_TESTE)["nome_teste"], "testeA")
            self.assertEqual(c.responder("gerar_teste", "q", ESQUEMA_TESTE)["nome_teste"], "testeB")
            self.assertEqual(len(arq.read_text().splitlines()), 2)
            self.assertEqual(len(c.duracoes_ms), 2)
            r = Replay(arq, "?")
            self.assertEqual(r.responder("gerar_teste", "p", ESQUEMA_TESTE)["nome_teste"], "testeA")
            self.assertEqual(r.responder("gerar_teste", "q", ESQUEMA_TESTE)["nome_teste"], "testeB")


if __name__ == "__main__":
    unittest.main()
