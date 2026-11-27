"""Q2/Q4: funil da geração de testes (plano-poc.md, D7).

Os mutantes vivos do baseline × N repetições independentes, cada uma partindo do baseline
(sem testes aprovados), numa cópia temporária do exemplo. Mede a 1ª tentativa (compila,
passa no original, mata o alvo) e o % de mutantes mortos em até 3 tentativas.
Nada é aprovado nem fica no disco: a aprovação humana é medida nas execuções da demo.

  python3 avaliacao/medir_geracao.py --repeticoes 5 --modelo haiku --gravar replay/aval_geracao.jsonl
  python3 avaliacao/medir_geracao.py --repeticoes 5 --replay replay/aval_geracao.jsonl

Em replay, só confere o funil contra avaliacao/geracao.json (não sobrescreve o registro ao vivo),
a menos que --saida seja dado.
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from provapr import rastreio  # noqa: E402
from provapr.cli import montar_prompt  # noqa: E402
from provapr.esquemas import esquema_criterios  # noqa: E402
from provapr.laco import Laco, rotulo  # noqa: E402
from provapr.modelo import ClaudeCLI, Gravador, Replay  # noqa: E402
from provapr.mutacao import PitMaven  # noqa: E402
from provapr.projeto import metodos_publicos  # noqa: E402

EXEMPLO = RAIZ / "exemplos" / "calculadora"


def pct(a, b):
    return round(100 * a / b, 1) if b else 0.0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--repeticoes", type=int, default=5)
    p.add_argument("--modelo", default="haiku")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--gravar")
    g.add_argument("--replay")
    p.add_argument("--saida", help="padrão: avaliacao/geracao.json ao gravar; em replay, só confere")
    args = p.parse_args(argv)

    inicio = time.monotonic()
    tmp = Path(tempfile.mkdtemp())
    proj = tmp / "calculadora"
    shutil.copytree(EXEMPLO, proj, ignore=shutil.ignore_patterns("target"))
    try:
        prov = (Replay(args.replay, args.modelo, proj) if args.replay
                else Gravador(ClaudeCLI(args.modelo), args.gravar, proj))
        issue = (proj / "issue-2.md").read_text(encoding="utf-8")
        metodos = metodos_publicos(proj)
        resp = prov.responder("extrair_criterios", montar_prompt(metodos, issue),
                              esquema_criterios(metodos))
        pit = PitMaven()
        criterios = rastreio.rastrear(resp["criterios"], pit.executar(proj))
        alvos = Laco(proj, prov, pit=pit).alvos(criterios)
        print(f"{len(alvos)} mutantes vivos × {args.repeticoes} repetições")

        casos = []
        for rep in range(1, args.repeticoes + 1):
            for c, m in alvos:
                laco = Laco(proj, prov, pit=pit, entrada=lambda _: "")
                arq = laco.arquivo(m.classe)
                print(f"\n[rep {rep}] {c.id} {rotulo(m)}")
                try:
                    achado = laco.gerar(c, m, arq)
                finally:
                    arq.escrever([])  # nada é aprovado
                casos.append({"repeticao": rep, "criterio": c.id, "mutante": rotulo(m),
                              "matou_em_ate_3": bool(achado),
                              "tentativas": [t.como_dict() for t in laco.tentativas]})
    finally:
        shutil.rmtree(tmp)

    primeiras = [c["tentativas"][0] for c in casos]
    todas = [t for c in casos for t in c["tentativas"]]
    n = len(primeiras)
    funil = {k: sum(t[k] for t in primeiras) for k in ("compilou", "passou", "matou")}
    dur = [d for d in prov.duracoes_ms if d]
    dados = {
        "data": datetime.now().astimezone().isoformat(timespec="seconds"),
        "comando": "python3 avaliacao/medir_geracao.py " + " ".join(argv or sys.argv[1:]),
        "modelo": args.modelo, "repeticoes": args.repeticoes, "mutantes_vivos": len(alvos),
        "primeiras_tentativas": n,
        "funil_1a_tentativa": {k: {"n": v, "pct": pct(v, n)} for k, v in funil.items()},
        "tentativas_totais": len(todas),
        "mortos_em_ate_3": {"n": sum(c["matou_em_ate_3"] for c in casos), "de": len(casos),
                            "pct": pct(sum(c["matou_em_ate_3"] for c in casos), len(casos))},
        "chamadas_ia": len(prov.duracoes_ms),
        "duracao_ia_ms_media": round(sum(dur) / len(dur)) if dur else None,
        "duracao_total_s": round(time.monotonic() - inicio, 1),
        "casos": casos,
    }
    registro = RAIZ / "avaliacao" / "geracao.json"
    if args.saida or not args.replay:
        Path(args.saida or registro).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    elif registro.exists():
        gravado = json.loads(registro.read_text(encoding="utf-8"))
        chaves = ("funil_1a_tentativa", "tentativas_totais", "mortos_em_ate_3")
        igual = all(gravado.get(k) == dados[k] for k in chaves)
        print("replay igual ao geracao.json" if igual else "replay DIFERE do geracao.json")
    print(f"\n1ª tentativa (n={n}): compila {funil['compilou']} ({pct(funil['compilou'], n)}%), "
          f"passa {funil['passou']} ({pct(funil['passou'], n)}%), "
          f"mata {funil['matou']} ({pct(funil['matou'], n)}%)")
    print(f"mortos em até 3 tentativas: {dados['mortos_em_ate_3']['n']}/{len(casos)} "
          f"({dados['mortos_em_ate_3']['pct']}%) · {len(todas)} tentativas · "
          f"{dados['chamadas_ia']} chamadas · média {dados['duracao_ia_ms_media']} ms · "
          f"{dados['duracao_total_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
