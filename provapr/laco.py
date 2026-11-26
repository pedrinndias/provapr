"""Laço de geração (D4): até 3 tentativas, filtro estático, 3 portões e aprovação humana.

Antes do laço guarda cada ProvaPR<Classe>Test.java (conteúdo ou ausência); no finally,
cobrindo Ctrl-C, deixa só os testes aprovados. A CLI nunca faz commit.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from .esquemas import ESQUEMA_TESTE
from .modelo import ErroModelo, SemRespostaGravada
from .mutacao import ErroMutacao, PitMaven
from .projeto import compilar_testes, testar_metodo

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
MAX_TENTATIVAS = 3
PROIBIDOS = ["System.exit", "java.io", "java.net", "Thread", "reflect", "Random"]
VIVOS = {"SURVIVED", "NO_COVERAGE"}


def chave_mutante(m):
    return (m.classe, m.metodo, m.linha, m.mutador, m.descricao)


def rotulo(m):
    return f"{m.classe.rsplit('.', 1)[-1]} L{m.linha} {m.descricao.split(' for ')[0]}"


def filtro_estatico(corpo, nome, nomes_usados):
    for p in PROIBIDOS:
        if p in corpo:
            return f"recusado pelo filtro estático: o corpo usa {p}"
    if nome in nomes_usados:
        return f"recusado pelo filtro estático: o nome {nome} já existe"
    return None


def limpar_erro(saida, raiz):
    """Primeiras 20 linhas do erro de compilação, sem caminho absoluto nem [linha,col]."""
    raiz = str(Path(raiz).resolve()) + "/"
    linhas = []
    for linha in saida.splitlines():
        if "Failed to execute goal" in linha or "-> [Help" in linha:
            break
        if "COMPILATION ERROR" in linha or not linha.strip():
            continue
        linha = re.sub(r":\[\d+,\d+\]", "", linha.replace(raiz, ""))
        linhas.append(linha.strip())
    return "\n".join(linhas[:20]) or saida.strip()[-500:]


def perguntar(texto, entrada=input):
    try:
        return entrada(texto).strip().lower()
    except EOFError:
        print()
        return ""


@dataclass
class Tentativa:
    mutante: str
    n: int
    compilou: bool = False
    passou: bool = False
    matou: bool = False
    humano: str = "—"
    nome: str = ""
    extras: list = field(default_factory=list)

    def como_dict(self):
        return {"mutante": self.mutante, "n": self.n, "compilou": self.compilou,
                "passou": self.passou, "matou": self.matou, "humano": self.humano,
                "nome_teste": self.nome, "tambem_matou": self.extras}


class ArquivoProvaPR:
    """ProvaPR<Classe>Test.java: original (ou ausência) + métodos aprovados + candidato."""

    def __init__(self, projeto, classe):
        pacote, simples = classe.rsplit(".", 1)
        self.pacote = pacote
        self.nome_classe = f"ProvaPR{simples}Test"
        self.caminho = Path(projeto, "src", "test", "java", *pacote.split("."),
                            f"{self.nome_classe}.java")
        self.original = (self.caminho.read_text(encoding="utf-8")
                         if self.caminho.exists() else None)
        self.aprovados = []  # textos dos métodos

    def nomes(self):
        texto = self.renderizar(self.aprovados) or ""
        return set(re.findall(r"void\s+(\w+)\s*\(", texto))

    def renderizar(self, metodos):
        if not metodos:
            return self.original
        corpo = "\n".join(metodos)
        if self.original is not None:
            fim = self.original.rstrip().rfind("}")
            return self.original[:fim] + corpo + "}\n"
        return (f"package {self.pacote};\n\n"
                "import org.junit.Test;\n"
                "import static org.junit.Assert.assertEquals;\n"
                "import static org.junit.Assert.assertFalse;\n"
                "import static org.junit.Assert.assertTrue;\n\n"
                f"public class {self.nome_classe} {{\n{corpo}}}\n")

    def escrever(self, metodos):
        texto = self.renderizar(metodos)
        if texto is None:
            self.caminho.unlink(missing_ok=True)
        else:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.caminho.write_text(texto, encoding="utf-8")

    def restaurar(self):
        """Deixa só o original + aprovados (chamado no finally)."""
        self.escrever(self.aprovados)


def metodo_java(m, resp):
    corpo = "\n".join("    " + l for l in resp["corpo_metodo"].strip().splitlines())
    return (f"  // Gerado pelo ProvaPR — mutante {rotulo(m)}\n"
            f"  @Test\n  public void {resp['nome_teste']}() {{\n{corpo}\n  }}\n")


class Laco:
    def __init__(self, projeto, prov, mvn="mvn", entrada=input, pit=None):
        self.projeto = Path(projeto)
        self.prov = prov
        self.mvn = mvn
        self.entrada = entrada
        self.pit = pit or PitMaven(mvn)
        self.tentativas = []
        self.equivalentes = set()   # chaves
        self.aprovados = []         # nomes de teste aprovados
        self.arquivos = {}

    # --- prompt -----------------------------------------------------------
    def prompt(self, m, criterio, feedback):
        rel = Path("src", "main", "java", *m.classe.split(".")).with_suffix(".java")
        fonte = (self.projeto / rel).read_text(encoding="utf-8").strip()
        cobridores = sorted({t.split("(")[0].rsplit(".", 1)[-1] for t in m.cobridores})
        trocas = {
            "<<CLASSE>>": m.classe.rsplit(".", 1)[-1], "<<ARQUIVO>>": str(rel),
            "<<FONTE>>": fonte, "<<STATUS>>": m.status, "<<METODO>>": m.metodo,
            "<<LINHA>>": str(m.linha), "<<MUTADOR>>": m.mutador, "<<DESCRICAO>>": m.descricao,
            "<<COBRIDORES>>": ", ".join(cobridores) or "nenhum (sem cobertura)",
            "<<CRITERIO>>": f"{criterio.id} {criterio.descricao}",
            "<<EXEMPLOS>>": "; ".join(criterio.exemplos) or "nenhum",
            "<<FEEDBACK>>": "\n".join(f"- tentativa {i}: {f}" for i, f in enumerate(feedback, 1))
                            or "nenhuma (primeira tentativa)",
        }
        texto = (PROMPTS / "gerar_teste.txt").read_text(encoding="utf-8")
        for k, v in trocas.items():
            texto = texto.replace(k, v)
        return texto

    # --- laço -------------------------------------------------------------
    def alvos(self, criterios):
        vistos, saida = set(), []
        for c in criterios:
            for m in sorted(c.mutantes, key=lambda m: (m.classe, m.linha, m.mutador, m.descricao)):
                k = chave_mutante(m)
                if m.status in VIVOS and k not in vistos:
                    vistos.add(k)
                    saida.append((c, m))
        return saida

    def executar(self, criterios):
        """Roda o laço. Levanta SemRespostaGravada/ErroMutacao/KeyboardInterrupt após reverter."""
        mortos = set()  # chaves mortas por testes aprovados
        try:
            for c, m in self.alvos(criterios):
                k = chave_mutante(m)
                if k in mortos:
                    print(f"\n[{c.id}] {rotulo(m)}: já morto por teste aprovado, pulando")
                    continue
                self.ciclo(c, m, criterios, mortos)
        finally:
            for arq in self.arquivos.values():
                arq.restaurar()

    def arquivo(self, classe):
        if classe not in self.arquivos:
            self.arquivos[classe] = ArquivoProvaPR(self.projeto, classe)
        return self.arquivos[classe]

    def ciclo(self, c, m, criterios, mortos):
        print(f"\n[{c.id}] alvo: {rotulo(m)} ({m.status})")
        arq = self.arquivo(m.classe)
        feedback = []
        for n in range(1, MAX_TENTATIVAS + 1):
            t = Tentativa(rotulo(m), n)
            self.tentativas.append(t)
            try:
                resp = self.prov.responder("gerar_teste", self.prompt(m, c, feedback), ESQUEMA_TESTE)
            except SemRespostaGravada:
                raise
            except ErroModelo as e:
                feedback.append(f"resposta inválida do modelo: {str(e)[:300]}")
                print(f"  tentativa {n}: {feedback[-1]}")
                continue
            t.nome = resp["nome_teste"]
            motivo = filtro_estatico(resp["corpo_metodo"], t.nome, arq.nomes())
            if motivo:
                feedback.append(motivo)
                print(f"  tentativa {n}: {motivo}")
                continue
            metodo = metodo_java(m, resp)
            arq.escrever(arq.aprovados + [metodo])

            ok, saida = compilar_testes(self.projeto, self.mvn)
            if not ok:
                feedback.append("não compilou:\n" + limpar_erro(saida, self.projeto))
                print(f"  tentativa {n}: {t.nome} não compilou")
                arq.escrever(arq.aprovados)
                continue
            t.compilou = True

            ok, msg = testar_metodo(self.projeto, arq.nome_classe, t.nome, self.mvn)
            if not ok:
                feedback.append(f"falhou no código original (oráculo errado): {msg}")
                print(f"  tentativa {n}: {t.nome} falhou no código original")
                arq.escrever(arq.aprovados)
                continue
            t.passou = True

            resultado = self.pit.executar(self.projeto, m.classe)
            marca = f".{arq.nome_classe}.{t.nome}("
            matou = [x for x in resultado if x.morto and any(marca in mt for mt in x.matadores)]
            if chave_mutante(m) not in {chave_mutante(x) for x in matou}:
                feedback.append("não matou: o teste passou, mas o mutante alvo continuou vivo")
                print(f"  tentativa {n}: {t.nome} não matou o alvo")
                arq.escrever(arq.aprovados)
                continue
            t.matou = True
            t.extras = [rotulo(x) for x in matou if chave_mutante(x) != chave_mutante(m)]

            if self.aprovar(c, m, metodo, matou, mortos, t):
                arq.aprovados.append(metodo)
                self.aprovados.append(t.nome)
                mortos.update(chave_mutante(x) for x in matou)
            arq.escrever(arq.aprovados)
            return

        print(f"  esgotou {MAX_TENTATIVAS} tentativas para {rotulo(m)}")
        r = perguntar("Mutante equivalente? [e]quivalente / [m]anter vivo ", self.entrada)
        if r == "e":
            self.equivalentes.add(chave_mutante(m))
            self.tentativas[-1].humano = "declarado equivalente"
        else:
            self.tentativas[-1].humano = "mantido vivo"

    def aprovar(self, c, m, metodo, matou, mortos, t):
        chaves_c = [chave_mutante(x) for x in c.mutantes]
        antes = sum(1 for x in c.mutantes if x.morto or chave_mutante(x) in mortos)
        novos = {chave_mutante(x) for x in matou}
        depois = sum(1 for x in c.mutantes
                     if x.morto or chave_mutante(x) in mortos or chave_mutante(x) in novos)
        print(f"  passou nos 3 portões (compila, passa no original, mata o alvo) — tentativa {t.n}")
        print("  " + "-" * 60)
        print(metodo.rstrip())
        print("  " + "-" * 60)
        print("  mutantes mortos por este teste: " + "; ".join(rotulo(x) for x in matou))
        print(f"  score de {c.id}: {antes}/{len(chaves_c)} → {depois}/{len(chaves_c)}")
        r = perguntar("Aprovar este teste? [s]im / [n]ão ", self.entrada)
        t.humano = "aprovado" if r == "s" else "rejeitado pelo humano"
        return r == "s"
