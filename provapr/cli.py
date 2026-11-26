"""CLI do ProvaPR: `run` com veredito antes, laço de geração e veredito depois (0 LIBERADO, 1 BLOQUEADO, 2 erro)."""
import argparse
import json
import sys
import time
from pathlib import Path

from . import rastreio
from .esquemas import esquema_criterios
from .laco import Laco, chave_mutante
from .modelo import ClaudeCLI, Completar, ErroModelo, Gravador, Replay, SemRespostaGravada
from .mutacao import ErroMutacao, PitMaven
from .projeto import metodos_publicos, rodar_testes

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def montar_prompt(metodos, issue):
    modelo = (PROMPTS / "extrair_criterios.txt").read_text(encoding="utf-8")
    lista = "\n".join(f"- {m}" for m in sorted(metodos)) or "(nenhum)"
    return modelo.replace("<<METODOS>>", lista).replace("<<ISSUE>>", issue.strip())


def provedor(args, raiz):
    if args.replay and args.gravar:
        if Path(args.replay).resolve() != Path(args.gravar).resolve():
            raise SystemExit("--replay e --gravar juntos só com o mesmo arquivo (completar)")
        return Completar(ClaudeCLI(args.modelo), args.gravar, raiz)
    if args.replay:
        return Replay(args.replay, args.modelo, raiz)
    vivo = ClaudeCLI(args.modelo)
    return Gravador(vivo, args.gravar, raiz) if args.gravar else vivo


def _tempo(s):
    return f"{int(s // 60)} min {int(s % 60):02d} s"


def _ligados(c, ia):
    return ", ".join(n + ("*" if n in ia else "") for n in c.testes_ligados) or "—"


def relatorio_md(args, antes, depois, laco, final_antes, final, modo, dados):
    titulo = final if final_antes == final else f"{final_antes} → {final}"
    ia = set(laco.aprovados) if laco else set()
    linhas = [f"## ProvaPR — {titulo}",
              f"Issue: {Path(args.issue).name} · Projeto: {args.projeto} · "
              f"Modelo: {args.modelo} ({modo}) · {_tempo(dados['duracao_total_s'])} · "
              f"{dados['chamadas_ia']} chamadas de IA", ""]
    if not antes:
        linhas += ["**SUITE_VERMELHA**: `mvn test` falhou antes de tudo; sem IA e sem PIT.", ""]
        linhas += [f"- `{n}`: {m}" for n, m in dados.get("falhas", [])]
        linhas += ["", "> A IA propõe, o PIT decide, um humano aprova."]
        return "\n".join(linhas) + "\n"
    linhas += ["| Critério | Funções | Testes ligados | Mutantes mortos (antes → depois) | Status |",
               "|---|---|---|---|---|"]
    for a, d in zip(antes, depois):
        st = a.status if a.status == d.status else f"{a.status} → {d.status}"
        lig = _ligados(a, ia) if a.testes_ligados == d.testes_ligados else \
            f"{_ligados(a, ia)} → {_ligados(d, ia)}"
        linhas.append(f"| {a.id} {a.descricao} | {', '.join(a.funcoes) or '—'} | {lig} | "
                      f"{a.mortos}/{len(a.mutantes)} → {d.mortos}/{len(d.mutantes) - _neq(d, laco)} | {st} |")
    if ia:
        linhas += ["", "\\* proposto pela IA, verificado pelo PIT, aprovado por humano."]
    if laco and laco.tentativas:
        linhas += ["", "### Testes propostos",
                   "| Mutante | Tentativas | Compilou | Passou | Matou | Humano |",
                   "|---|---|---|---|---|---|"]
        finais = {}
        for t in laco.tentativas:
            finais[t.mutante] = t
        sn = {True: "sim", False: "não"}
        for t in finais.values():
            matou = sn[t.matou] + (f" (+{', '.join(e.split(' ', 2)[1] for e in t.extras)})"
                                   if t.extras else "")
            linhas.append(f"| {t.mutante} | {t.n} | {sn[t.compilou]} | {sn[t.passou]} | "
                          f"{matou} | {t.humano} |")
    if laco and laco.equivalentes:
        linhas += ["", f"{len(laco.equivalentes)} mutante(s) declarado(s) equivalente(s) por humano."]
    linhas += ["", "> A IA propõe, o PIT decide, um humano aprova."]
    return "\n".join(linhas) + "\n"


def _neq(c, laco):
    if not laco:
        return 0
    return sum(chave_mutante(m) in laco.equivalentes for m in c.mutantes)


def relatorio_json(antes, depois, laco, final_antes, final, prov, inicio, falhas=()):
    def contagem(c):
        return {"total": len(c.mutantes), "mortos": c.mortos,
                "sobreviventes": sum(m.status == "SURVIVED" for m in c.mutantes),
                "sem_cobertura": sum(m.status == "NO_COVERAGE" for m in c.mutantes),
                "equivalentes": _neq(c, laco)}
    return {"versao": 1, "veredito_antes": final_antes, "veredito_depois": final,
            "criterios": [{"id": a.id, "descricao": a.descricao, "funcoes": a.funcoes,
                           "testes_ligados": d.testes_ligados,
                           "mutantes_antes": contagem(a), "mutantes": contagem(d),
                           "status_antes": a.status, "status_depois": d.status}
                          for a, d in zip(antes, depois)],
            "tentativas": [t.como_dict() for t in laco.tentativas] if laco else [],
            "testes_aprovados": laco.aprovados if laco else [],
            "falhas": [list(f) for f in falhas],
            "chamadas_ia": len(prov.duracoes_ms),
            "chamadas_ia_ao_vivo": prov.chamadas_ao_vivo,
            "duracao_ia_ms": prov.duracoes_ms,
            "duracao_total_s": round(time.monotonic() - inicio, 1)}


def gravar(args, md, dados):
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "provapr-relatorio.md").write_text(md, encoding="utf-8")
    (saida / "provapr-relatorio.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def imprimir(criterios):
    for c in criterios:
        print(f"{c.id} {c.status:<13} {c.mortos}/{len(c.mutantes)} mortos  {', '.join(c.funcoes) or '—'}")


def cmd_run(args):
    inicio = time.monotonic()
    projeto = Path(args.projeto)
    issue = Path(args.issue).read_text(encoding="utf-8")
    modo = "replay" if args.replay and not args.gravar else "ao vivo"
    prov = provedor(args, projeto)

    testes = rodar_testes(projeto, args.mvn)
    if not testes.verde:
        print("SUITE_VERMELHA: mvn test falhou antes de tudo")
        for nome, msg in testes.falhas:
            print(f"  {nome}: {msg}")
        print(f"{rastreio.BLOQUEADO} ({rastreio.SUITE_VERMELHA})")
        dados = relatorio_json([], [], None, rastreio.SUITE_VERMELHA, rastreio.BLOQUEADO,
                               prov, inicio, testes.falhas)
        gravar(args, relatorio_md(args, [], [], None, rastreio.BLOQUEADO, rastreio.BLOQUEADO,
                                  modo, dados), dados)
        print(f"chamadas de IA: {dados['chamadas_ia']}")
        return 1

    metodos = metodos_publicos(projeto)
    try:
        resp = prov.responder("extrair_criterios", montar_prompt(metodos, issue),
                              esquema_criterios(metodos))
    except ErroModelo as e:
        print(f"erro na extração de critérios: {e}", file=sys.stderr)
        return 2
    pit = PitMaven(args.mvn)
    try:
        mutantes = pit.executar(projeto)
    except ErroMutacao as e:
        print(f"erro no PIT: {e}", file=sys.stderr)
        return 2

    antes = rastreio.rastrear(resp["criterios"], mutantes)
    final_antes = rastreio.veredito(c.status for c in antes)
    print("Veredito antes:")
    imprimir(antes)
    print(final_antes)

    laco = Laco(projeto, prov, args.mvn, pit=pit)
    try:
        laco.executar(antes)
        mutantes = pit.executar(projeto)  # PIT final
    except SemRespostaGravada as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except ErroMutacao as e:
        print(f"erro no PIT: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrompido: testes não aprovados foram revertidos", file=sys.stderr)
        return 2

    equivalentes = [m for m in mutantes if chave_mutante(m) in laco.equivalentes]
    depois = rastreio.rastrear(resp["criterios"], mutantes, equivalentes)
    final = rastreio.veredito(c.status for c in depois)
    print("\nVeredito depois:")
    imprimir(depois)
    print(final)

    dados = relatorio_json(antes, depois, laco, final_antes, final, prov, inicio)
    gravar(args, relatorio_md(args, antes, depois, laco, final_antes, final, modo, dados), dados)
    if laco.aprovados:
        print(f"testes aprovados (não commitados): {', '.join(laco.aprovados)}")
    print(f"chamadas de IA: {dados['chamadas_ia']} (ao vivo: {prov.chamadas_ao_vivo})")
    return 0 if final == rastreio.LIBERADO else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="provapr")
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("run", help="rastreia critérios da issue até mutantes mortos")
    r.add_argument("--projeto", required=True)
    r.add_argument("--issue", required=True)
    r.add_argument("--modelo", default="haiku")
    r.add_argument("--gravar", metavar="JSONL")
    r.add_argument("--replay", metavar="JSONL",
                   help="com --gravar no mesmo arquivo: completa o que falta ao vivo")
    r.add_argument("--saida", default=".", help="pasta do relatório MD + JSON")
    r.add_argument("--mvn", default="mvn")
    args = p.parse_args(argv)
    return cmd_run(args)
