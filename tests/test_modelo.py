import json
import tempfile
import unittest
from pathlib import Path

from provapr.esquemas import ESQUEMA_TESTE
from provapr.modelo import ErroModelo, Gravador, ProvedorModelo, Replay, chave

RESP = {"nome_teste": "testeX", "corpo_metodo": "assertTrue(true);", "entrada": "",
        "saida_esperada": "", "justificativa": ""}


class Falso(ProvedorModelo):
    modelo = "haiku"

    def __init__(self, respostas):
        super().__init__()
        self.respostas = list(respostas)
        self.chamadas_ao_vivo = 0

    def responder(self, chamada, prompt, schema):
        self.chamadas_ao_vivo += 1
        self.duracoes_ms.append(10)
        return self.respostas.pop(0)


class TestModelo(unittest.TestCase):
    def test_chave_estavel_e_normalizada(self):
        a = chave("c", "haiku", {"b": 1, "a": 2}, "linha\r\n/raiz/x/A.java", "/raiz/x")
        b = chave("c", "haiku", {"a": 2, "b": 1}, "linha\nA.java", None)
        self.assertEqual(a, b)
        self.assertNotEqual(a, chave("c", "sonnet", {"a": 2, "b": 1}, "linha\nA.java"))

    def test_grava_e_reproduz_em_ordem(self):
        outra = dict(RESP, nome_teste="testeY")
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "r.jsonl"
            g = Gravador(Falso([RESP, outra]), arq)
            g.responder("gerar_teste", "p", ESQUEMA_TESTE)
            g.responder("gerar_teste", "p", ESQUEMA_TESTE)
            self.assertEqual(g.chamadas_ao_vivo, 2)
            self.assertEqual(json.loads(arq.read_text().splitlines()[0])["versao"], 1)
            r = Replay(arq)
            self.assertEqual(r.responder("gerar_teste", "p", ESQUEMA_TESTE)["nome_teste"], "testeX")
            self.assertEqual(r.responder("gerar_teste", "p", ESQUEMA_TESTE)["nome_teste"], "testeY")
            self.assertEqual(r.chamadas_ao_vivo, 0)
            with self.assertRaises(ErroModelo):
                r.responder("gerar_teste", "p", ESQUEMA_TESTE)

    def test_replay_revalida(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "r.jsonl"
            linha = {"versao": 1, "chamada": "g", "chave": chave("g", "haiku", ESQUEMA_TESTE, "p"),
                     "modelo": "haiku", "resposta": dict(RESP, extra=1)}
            arq.write_text(json.dumps(linha) + "\n")
            with self.assertRaises(ErroModelo):
                Replay(arq).responder("g", "p", ESQUEMA_TESTE)
