# ProvaPR

CLI que transforma "o CI está verde" em "cada critério da issue tem um teste que detecta mudança".
A IA (via `claude -p`) propõe critérios, ligações e testes; compilador, JUnit, PIT e um humano decidem.
Só biblioteca padrão do Python (≥ 3.10), sobre projetos Maven com pitest-maven.

> A IA propõe, o PIT decide, um humano aprova.

## Como reproduzir em 3 comandos

Requisitos: Python ≥ 3.10, JDK ≥ 8 e Maven 3 (o Maven baixa o pitest-maven 1.15.8 e o JUnit 4.13.1 na 1ª execução).
Não precisa de conta do Claude: o modo replay usa as respostas gravadas em `replay/demo.jsonl`.

```bash
git clone https://github.com/pedrinndias/provapr.git && cd provapr
```
```bash
python3 -m provapr run --projeto exemplos/calculadora --issue exemplos/calculadora/issue-2.md --replay replay/demo.jsonl
```
Responda `s` às 3 perguntas `Aprovar este teste?`. Resultado esperado: `BLOQUEADO → LIBERADO`, `exit 0`, e `provapr-relatorio.md` com
CA1 2/2, CA2 0/2 → 2/2, CA3 5/9 → 9/9. Os testes aprovados ficam como mudança não commitada em `exemplos/calculadora/src/test`
(a CLI nunca faz commit). Para voltar ao início:
```bash
git clean -f exemplos/calculadora/src/test
```

Outros cenários:
- Responder `n` a tudo → `BLOQUEADO`, `exit 1`, nenhum `ProvaPR*Test.java` sobra.
- Com o bug (`cd exemplos/calculadora && git apply bug.patch`) → `BLOQUEADO (SUITE_VERMELHA)` em segundos, sem chamar a IA.
  Desfaça com `git apply -R bug.patch`.
- Testes da própria CLI: `python3 -m unittest -v` (os de integração rodam o Maven e o PIT de verdade, ~3 min).

## Modo ao vivo

Precisa do `claude` CLI logado (assinatura). `--gravar` grava cada resposta para reprodução depois:

```bash
python3 -m provapr run --projeto exemplos/calculadora --issue exemplos/calculadora/issue-2.md --modelo haiku --gravar replay/meu.jsonl
```
`--replay X --gravar X` (o mesmo arquivo) responde do que já está gravado e só chama ao vivo o que falta.
`--max-tentativas N` (padrão 3), `--saida PASTA` (relatório MD + JSON), `--mvn CAMINHO`.

## O que acontece numa execução

1. `mvn test`. Vermelho → `BLOQUEADO (SUITE_VERMELHA)`, sem IA e sem PIT.
2. IA extrai os critérios da issue e liga cada um a métodos públicos (lista fechada, `enum` no JSON Schema).
3. PIT nas classes; cada critério recebe PROVADO, FRACO, SEM_TESTE ou NAO_RASTREADO (veredito "antes").
4. Para cada mutante vivo (pula os já mortos por um teste aprovado), até 3 tentativas:
   IA propõe um método `@Test` → filtro estático → **compila** → **passa no código original** → **PIT confirma que mata o alvo**.
5. Só então o humano vê o teste, os mutantes que ele mata e o score do critério, e responde `s`/`n`.
   Esgotou as tentativas: `e` (equivalente, sai do denominador) ou `m` (fica vivo).
6. PIT final, veredito "depois" e `provapr-relatorio.md` + `.json`. Tudo que não foi aprovado é revertido (inclusive no Ctrl-C).

Saída: `0` LIBERADO, `1` BLOQUEADO, `2` erro (por exemplo, replay sem resposta gravada).

## Estrutura

| Caminho | Papel |
|---|---|
| `provapr/cli.py` | `run`, veredito antes/depois, relatório MD + JSON |
| `provapr/laco.py` | laço de geração, 3 portões, aprovação humana, reversão |
| `provapr/modelo.py` | `ProvedorModelo` (Strategy): `ClaudeCLI`, `Replay`, `Gravador` (Decorator), `Completar` |
| `provapr/mutacao.py` | `ExecutorMutacao` → `PitMaven` (Adapter do `mutations.xml`) |
| `provapr/projeto.py` | `mvn test`, surefire, métodos públicos, portões de compilação e teste |
| `provapr/rastreio.py` | critério → função → teste e veredito |
| `provapr/esquemas.py` | JSON Schemas das 2 chamadas e validador mínimo |
| `prompts/` | prompts versionados |
| `exemplos/calculadora/` | projeto Maven da demo, `issue-2.md`, `bug.patch` |
| `replay/` | respostas gravadas ao vivo com haiku |
| `avaliacao/` | scripts de medição e `resultados.md` |

O exemplo `calculadora` deriva do material da disciplina de Engenharia de Software do DCC/UFMG (ver `exemplos/calculadora/LICENSE`).
