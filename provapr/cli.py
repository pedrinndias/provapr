"""CLI do ProvaPR. Dia 2: `run` até o veredito "antes" (0 LIBERADO, 1 BLOQUEADO, 2 erro)."""
import argparse
import json
import sys
import time
from pathlib import Path

from . import rastreio
from .esquemas import esquema_criterios
from .modelo import ClaudeCLI, ErroModelo, Gravador, Replay
from .mutacao import ErroMutacao, PitMaven
from .projeto import metodos_publicos, rodar_testes

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def montar_prompt(metodos, issue):
    modelo = (PROMPTS / "extrair_criterios.txt").read_text(encoding="utf-8")
    lista = "\n".join(f"- {m}" for m in sorted(metodos)) or "(nenhum)"
    return modelo.replace("<<METODOS>>", lista).replace("<<ISSUE>>", issue.strip())


def provedor(args, raiz):
    if args.replay:
        return Replay(args.replay, args.modelo, raiz)
    vivo = ClaudeCLI(args.modelo)
    return Gravador(vivo, args.gravar, raiz) if args.gravar else vivo


def relatorio_md(args, criterios, final, modo, n_chamadas):
    linhas = [f"## ProvaPR — {final}",
              f"Issue: {Path(args.issue).name} · Projeto: {args.projeto} · "
              f"Modelo: {args.modelo} ({modo}) · {n_chamadas} chamadas de IA", "",
              "| Critério | Funções | Testes ligados | Mutantes mortos | Status |",
              "|---|---|---|---|---|"]
    for c in criterios:
        linhas.append(f"| {c.id} {c.descricao} | {', '.join(c.funcoes) or '—'} | "
                      f"{', '.join(c.testes_ligados) or '—'} | {c.mortos}/{len(c.mutantes)} | {c.status} |")
    linhas += ["", "> A IA propõe, o PIT decide, um humano aprova."]
    return "\n".join(linhas) + "\n"


def relatorio_json(criterios, final, prov, inicio):
    def contagem(c):
        return {"total": len(c.mutantes), "mortos": c.mortos,
                "sobreviventes": sum(m.status == "SURVIVED" for m in c.mutantes),
                "sem_cobertura": sum(m.status == "NO_COVERAGE" for m in c.mutantes),
                "equivalentes": 0}
    return {"versao": 1, "veredito_antes": final, "veredito_depois": None,
            "criterios": [{"id": c.id, "descricao": c.descricao, "funcoes": c.funcoes,
                           "testes_ligados": c.testes_ligados, "mutantes": contagem(c),
                           "status_antes": c.status, "status_depois": None}
                          for c in criterios],
            "tentativas": [], "chamadas_ia": len(prov.duracoes_ms),
            "chamadas_ia_ao_vivo": prov.chamadas_ao_vivo,
            "duracao_ia_ms": prov.duracoes_ms,
            "duracao_total_s": round(time.monotonic() - inicio, 1)}


def cmd_run(args):
    inicio = time.monotonic()
    projeto = Path(args.projeto)
    issue = Path(args.issue).read_text(encoding="utf-8")
    prov = provedor(args, projeto)

    testes = rodar_testes(projeto, args.mvn)
    if not testes.verde:
        print("SUITE_VERMELHA: mvn test falhou antes de tudo")
        for nome, msg in testes.falhas:
            print(f"  {nome}: {msg}")
        print(rastreio.BLOQUEADO)
        return 1

    metodos = metodos_publicos(projeto)
    try:
        resp = prov.responder("extrair_criterios", montar_prompt(metodos, issue),
                              esquema_criterios(metodos))
    except ErroModelo as e:
        print(f"erro na extração de critérios: {e}", file=sys.stderr)
        return 2
    try:
        mutantes = PitMaven(args.mvn).executar(projeto)
    except ErroMutacao as e:
        print(f"erro no PIT: {e}", file=sys.stderr)
        return 2

    criterios = rastreio.rastrear(resp["criterios"], mutantes)
    final = rastreio.veredito(c.status for c in criterios)
    for c in criterios:
        print(f"{c.id} {c.status:<13} {c.mortos}/{len(c.mutantes)} mortos  {', '.join(c.funcoes) or '—'}")
    print(final)

    modo = "replay" if args.replay else "ao vivo"
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    dados = relatorio_json(criterios, final, prov, inicio)
    (saida / "provapr-relatorio.md").write_text(
        relatorio_md(args, criterios, final, modo, dados["chamadas_ia"]), encoding="utf-8")
    (saida / "provapr-relatorio.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"chamadas de IA ao vivo: {prov.chamadas_ao_vivo}")
    return 0 if final == rastreio.LIBERADO else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="provapr")
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("run", help="rastreia critérios da issue até mutantes mortos")
    r.add_argument("--projeto", required=True)
    r.add_argument("--issue", required=True)
    r.add_argument("--modelo", default="haiku")
    grupo = r.add_mutually_exclusive_group()
    grupo.add_argument("--gravar", metavar="JSONL")
    grupo.add_argument("--replay", metavar="JSONL")
    r.add_argument("--saida", default=".", help="pasta do relatório MD + JSON")
    r.add_argument("--mvn", default="mvn")
    args = p.parse_args(argv)
    return cmd_run(args)
