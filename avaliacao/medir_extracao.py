"""Q3: fidelidade da extração de critérios contra avaliacao/gabarito.md (plano-poc.md, D7).

Etapa 1, extrair: cada entrada × N execuções independentes da chamada `extrair_criterios`.
  python3 avaliacao/medir_extracao.py extrair --repeticoes 3 --modelo haiku --gravar replay/aval_extracao.jsonl
  python3 avaliacao/medir_extracao.py extrair --repeticoes 3 --replay replay/aval_extracao.jsonl
Etapa 2, medir: lê avaliacao/casamento.json (qual critério da IA casa com qual do gabarito, decidido à mão)
e calcula precisão, revocação e estabilidade.
  python3 avaliacao/medir_extracao.py medir
"""
import argparse
import json
import sys
import time
from datetime import datetime
from itertools import combinations
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from provapr.cli import montar_prompt  # noqa: E402
from provapr.esquemas import esquema_criterios  # noqa: E402
from provapr.modelo import ClaudeCLI, Gravador, Replay  # noqa: E402
from provapr.projeto import metodos_publicos  # noqa: E402

AVAL = RAIZ / "avaliacao"
CALC = RAIZ / "exemplos" / "calculadora"
# (id, arquivo da issue, projeto cujos métodos entram no enum; None = sem código)
ENTRADAS = [
    ("E1", CALC / "issue-2.md", CALC),
    ("E2", AVAL / "entradas" / "us-01.md", None),
    ("E3", AVAL / "entradas" / "us-02.md", None),
    ("E4", AVAL / "entradas" / "us-03.md", None),
    ("E5", AVAL / "entradas" / "us-04.md", None),
]
# nº de critérios do gabarito por entrada (avaliacao/gabarito.md)
GABARITO = {"E1": 3, "E2": 4, "E3": 4, "E4": 4, "E5": 5}


def extrair(args):
    inicio = time.monotonic()
    prov = (Replay(args.replay, args.modelo, RAIZ) if args.replay
            else Gravador(ClaudeCLI(args.modelo), args.gravar, RAIZ))
    saida = []
    for eid, issue, proj in ENTRADAS:
        metodos = metodos_publicos(proj) if proj else []
        prompt = montar_prompt(metodos, issue.read_text(encoding="utf-8"))
        for rep in range(1, args.repeticoes + 1):
            resp = prov.responder("extrair_criterios", prompt, esquema_criterios(metodos))
            print(f"{eid} rep {rep}: {len(resp['criterios'])} critérios")
            saida.append({"entrada": eid, "repeticao": rep, "criterios": resp["criterios"]})
    if args.replay:  # só confere contra a medição ao vivo, sem sobrescrever
        gravado = json.loads((AVAL / "extracao.json").read_text(encoding="utf-8"))["execucoes"]
        print("replay igual ao extracao.json" if gravado == saida else "replay DIFERE do extracao.json")
        return 0 if gravado == saida else 1
    dur = [d for d in prov.duracoes_ms if d]
    dados = {"data": datetime.now().astimezone().isoformat(timespec="seconds"),
             "modelo": args.modelo, "repeticoes": args.repeticoes,
             "chamadas_ia": len(prov.duracoes_ms),
             "duracao_ia_ms_media": round(sum(dur) / len(dur)) if dur else None,
             "duracao_total_s": round(time.monotonic() - inicio, 1), "execucoes": saida}
    (AVAL / "extracao.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    return 0


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def medir(_args):
    ext = json.loads((AVAL / "extracao.json").read_text(encoding="utf-8"))
    cas = json.loads((AVAL / "casamento.json").read_text(encoding="utf-8"))["casamento"]
    linhas, tot = [], {"ia": 0, "ia_ok": 0, "gab": 0, "gab_ok": 0}
    for eid, _, _ in ENTRADAS:
        execs = [e for e in ext["execucoes"] if e["entrada"] == eid]
        n_ia, cobertos = [], []
        ia_ok = 0
        for e in execs:
            mapa = cas[eid][str(e["repeticao"])]
            ids = [c["id"] for c in e["criterios"]]
            assert set(mapa) == set(ids), f"{eid} rep {e['repeticao']}: casamento incompleto"
            # valor: id do gabarito, lista de ids (critério composto) ou null (não casa)
            listas = [[v] if isinstance(v, str) else (v or []) for v in mapa.values()]
            ia_ok += sum(1 for li in listas if li)
            n_ia.append(len(ids))
            cobertos.append({g for li in listas for g in li})
        g = GABARITO[eid]
        gab_ok = sum(len(c) for c in cobertos)
        estab = (sum(jaccard(a, b) for a, b in combinations(cobertos, 2))
                 / max(1, len(list(combinations(cobertos, 2)))))
        linhas.append({"entrada": eid, "criterios_ia": n_ia, "gabarito": g,
                       "precisao": round(100 * ia_ok / sum(n_ia), 1),
                       "revocacao": round(100 * gab_ok / (g * len(execs)), 1),
                       "estabilidade_jaccard": round(estab, 2),
                       "cobertos_por_execucao": [sorted(c) for c in cobertos]})
        tot["ia"] += sum(n_ia)
        tot["ia_ok"] += ia_ok
        tot["gab"] += g * len(execs)
        tot["gab_ok"] += gab_ok
    for li in linhas:
        print(f"{li['entrada']}: IA {li['criterios_ia']} vs gabarito {li['gabarito']} · "
              f"precisão {li['precisao']}% · revocação {li['revocacao']}% · "
              f"estabilidade {li['estabilidade_jaccard']}")
    print(f"Total: precisão {100 * tot['ia_ok'] / tot['ia']:.1f}% · "
          f"revocação {100 * tot['gab_ok'] / tot['gab']:.1f}%")
    (AVAL / "extracao_metricas.json").write_text(
        json.dumps({"por_entrada": linhas, "total": tot}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extrair")
    e.add_argument("--repeticoes", type=int, default=3)
    e.add_argument("--modelo", default="haiku")
    g = e.add_mutually_exclusive_group(required=True)
    g.add_argument("--gravar")
    g.add_argument("--replay")
    sub.add_parser("medir")
    args = p.parse_args(argv)
    return extrair(args) if args.cmd == "extrair" else medir(args)


if __name__ == "__main__":
    sys.exit(main())
