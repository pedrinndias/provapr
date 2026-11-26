import unittest

from provapr.esquemas import ESQUEMA_TESTE, ErroEsquema, esquema_criterios, validar

METODOS = {"Calculadora#soma", "Calendario#ehBissexto"}


def criterio(**k):
    base = {"id": "CA1", "descricao": "soma", "funcoes": ["Calculadora#soma"], "exemplos": []}
    base.update(k)
    return {"criterios": [base]}


class TestEsquemas(unittest.TestCase):
    def test_valido(self):
        validar(criterio(), esquema_criterios(METODOS))

    def test_enum(self):
        with self.assertRaises(ErroEsquema):
            validar(criterio(funcoes=["Calculadora#divide"]), esquema_criterios(METODOS))

    def test_pattern(self):
        with self.assertRaises(ErroEsquema):
            validar(criterio(id="C1"), esquema_criterios(METODOS))

    def test_campo_extra(self):
        with self.assertRaises(ErroEsquema):
            validar(criterio(extra=1), esquema_criterios(METODOS))

    def test_falta_campo(self):
        with self.assertRaises(ErroEsquema):
            validar({"nome_teste": "testeX"}, ESQUEMA_TESTE)

    def test_sem_metodos_funcoes_vazia(self):
        esq = esquema_criterios(set())
        validar(criterio(funcoes=[]), esq)
        with self.assertRaises(ErroEsquema):
            validar(criterio(), esq)

    def test_lista_vazia_de_criterios(self):
        with self.assertRaises(ErroEsquema):
            validar({"criterios": []}, esquema_criterios(METODOS))
