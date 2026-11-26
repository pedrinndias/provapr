"""Porta ProvedorModelo (Strategy) com ClaudeCLI, Gravador (Decorator) e Replay."""
import hashlib
import json
import subprocess
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from .esquemas import ErroEsquema, validar

PAPEL = ("Você é um analista de testes. Responda só com o JSON pedido, "
         "sem ler arquivos e sem inventar funções fora da lista.")
TIMEOUT_S = 90


class ErroModelo(RuntimeError):
    """Tentativa falha: is_error, timeout, JSON inválido ou fora do esquema."""


def normalizar(prompt, raiz=None):
    texto = prompt.replace("\r\n", "\n")
    if raiz:
        texto = texto.replace(str(Path(raiz).resolve()) + "/", "")
    return texto


def chave(chamada, modelo, schema, prompt, raiz=None):
    canon = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    base = "\n".join([chamada, modelo, canon, normalizar(prompt, raiz)])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class ProvedorModelo:
    modelo = "?"
    chamadas_ao_vivo = 0

    def __init__(self):
        self.duracoes_ms = []

    def responder(self, chamada, prompt, schema):
        raise NotImplementedError


class ClaudeCLI(ProvedorModelo):
    def __init__(self, modelo="haiku", executavel="claude"):
        super().__init__()
        self.modelo = modelo
        self.executavel = executavel
        self.chamadas_ao_vivo = 0

    def responder(self, chamada, prompt, schema):
        cmd = [self.executavel, "-p", "--model", self.modelo, "--tools", "",
               "--no-session-persistence", "--output-format", "json",
               "--system-prompt", PAPEL,
               "--json-schema", json.dumps(schema, ensure_ascii=False), prompt]
        self.chamadas_ao_vivo += 1
        inicio = time.monotonic()
        try:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise ErroModelo(f"timeout de {TIMEOUT_S} s")
        try:
            saida = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise ErroModelo(f"saída não é JSON (exit {r.returncode}): {r.stderr[-300:]}")
        if saida.get("is_error") or "structured_output" not in saida:
            raise ErroModelo(f"is_error: {str(saida.get('result'))[:300]}")
        self.duracoes_ms.append(saida.get("duration_ms")
                                or int((time.monotonic() - inicio) * 1000))
        try:
            return validar(saida["structured_output"], schema)
        except ErroEsquema as e:
            raise ErroModelo(f"fora do esquema: {e}")


class Gravador(ProvedorModelo):
    """Envolve outro provedor e anexa cada resposta válida ao .jsonl."""

    def __init__(self, interno, caminho, raiz=None):
        super().__init__()
        self.interno = interno
        self.caminho = Path(caminho)
        self.raiz = raiz
        self.modelo = interno.modelo
        self.duracoes_ms = interno.duracoes_ms
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text("", encoding="utf-8")

    @property
    def chamadas_ao_vivo(self):
        return self.interno.chamadas_ao_vivo

    def responder(self, chamada, prompt, schema):
        resposta = self.interno.responder(chamada, prompt, schema)
        linha = {"versao": 1, "chamada": chamada,
                 "chave": chave(chamada, self.modelo, schema, prompt, self.raiz),
                 "modelo": self.modelo,
                 "gravado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                 "duracao_ms": self.duracoes_ms[-1] if self.duracoes_ms else None,
                 "resposta": resposta}
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        return resposta


class Replay(ProvedorModelo):
    """Só lê o .jsonl; chaves repetidas saem na ordem de gravação."""

    def __init__(self, caminho, modelo="haiku", raiz=None):
        super().__init__()
        self.modelo = modelo
        self.raiz = raiz
        self.chamadas_ao_vivo = 0
        self.filas = defaultdict(deque)
        for texto in Path(caminho).read_text(encoding="utf-8").splitlines():
            if texto.strip():
                linha = json.loads(texto)
                self.filas[linha["chave"]].append(linha)

    def responder(self, chamada, prompt, schema):
        fila = self.filas.get(chave(chamada, self.modelo, schema, prompt, self.raiz))
        if not fila:
            raise ErroModelo(f"replay sem resposta gravada para '{chamada}'")
        linha = fila.popleft()
        self.duracoes_ms.append(linha.get("duracao_ms"))
        try:
            return validar(linha["resposta"], schema)
        except ErroEsquema as e:
            raise ErroModelo(f"replay fora do esquema: {e}")
