# ProvaPR

CLI que transforma "o CI está verde" em "cada critério da issue tem um teste que detecta mudança".
A IA (via `claude -p`) propõe critérios, ligações e testes; compilador, JUnit, PIT e um humano decidem.
Só biblioteca padrão do Python (≥ 3.10), sobre projetos Maven com pitest-maven.

> A IA propõe, o PIT decide, um humano aprova.

## Como reproduzir em 3 comandos

Requisitos: Python ≥ 3.10, JDK ≥ 8 e Maven 3 (o Maven baixa o pitest-maven 1.15.8 e o JUnit 4.13.1 na 1ª execução,
o que leva de 1 a 3 min com internet; depois, a demo em replay leva cerca de 1 min).
Não precisa de conta do Claude: o modo replay usa as respostas gravadas em `replay/demo.jsonl`, sem chamar nenhum modelo.

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
- Testes da própria CLI: `python3 -m unittest -v` (os de integração rodam o Maven e o PIT de verdade, de 3 a 5 min).

Se der errado:
- `exit 2` com `replay sem resposta gravada`: o replay só responde à issue e ao código exatamente como estão no repositório.
  Não edite `issue-2.md` nem os fontes do exemplo; volte com `git checkout -- exemplos && git clean -f exemplos/calculadora/src/test`.
- `Maven não encontrado`: instale o Maven 3 ou passe `--mvn /caminho/do/mvn`.
- Erro do PIT dizendo que falta `mutations.xml` ou `fullMutationMatrix`: o pom precisa da configuração da seção abaixo.

## Usar em outro projeto Maven

O ProvaPR lê o `mutations.xml` do PIT com a matriz completa (quais testes matam e quais cobrem cada mutante).
Copie para o `pom.xml` do projeto o `<plugin>` do pitest de [`exemplos/calculadora/pom.xml`](exemplos/calculadora/pom.xml),
ajustando o pacote em `targetClasses` e `targetTests`. As 3 opções obrigatórias são:
```xml
<outputFormats><param>XML</param><param>HTML</param></outputFormats>
<timestampedReports>false</timestampedReports>
<fullMutationMatrix>true</fullMutationMatrix>
```
Os testes propostos são JUnit 4. Em outro projeto, o modo replay não serve (as respostas gravadas são do exemplo): use o modo ao vivo.

## Modo ao vivo

Precisa do `claude` CLI logado (assinatura). `--gravar` grava cada resposta para reprodução depois:

```bash
python3 -m provapr run --projeto exemplos/calculadora --issue exemplos/calculadora/issue-2.md --modelo haiku --gravar replay/meu.jsonl
```
`--replay X --gravar X` (o mesmo arquivo) responde do que já está gravado e só chama ao vivo o que falta.
`--max-tentativas N` (padrão 3), `--saida PASTA` (relatório MD + JSON), `--mvn CAMINHO`.

## O que acontece numa execução

1. `mvn test`. Vermelho → `BLOQUEADO (SUITE_VERMELHA)`, sem IA e sem PIT.
2. IA extrai os critérios da issue e liga cada um a métodos públicos (lista fechada, `enum` no JSON Schema). O terminal mostra `IA extraiu …`.
3. PIT nas classes; cada critério recebe PROVADO, FRACO, SEM_TESTE, NAO_RASTREADO ou SEM_MUTANTE (veredito "antes").
4. Para cada mutante vivo (pula os já mortos por um teste aprovado), até 3 tentativas:
   IA propõe um método `@Test` → filtro estático → **compila** → **passa no código original** → **PIT confirma que mata o alvo**.
5. Só então o humano vê o teste, os mutantes que ele mata e o score do critério, e responde `s`/`n`.
   Esgotou as tentativas: `e` (equivalente, sai do denominador) ou `m` (fica vivo).
6. PIT final, veredito "depois" e `provapr-relatorio.md` + `.json`. Tudo que não foi aprovado é revertido (inclusive no Ctrl-C).

Status por critério: PROVADO (todo mutante das funções ligadas morre), FRACO (há mutante vivo com teste que o cobre),
SEM_TESTE (nenhum teste cobre), NAO_RASTREADO (a IA não ligou o critério a nenhuma função) e SEM_MUTANTE
(as funções ligadas não geraram mutantes, então nada prova o critério). Só "todos PROVADO" libera.

Saída: `0` LIBERADO, `1` BLOQUEADO, `2` erro (por exemplo, replay sem resposta gravada ou arquivo inexistente).

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

## Limitações e o que é só planejado

Limitações medidas (detalhe em [`avaliacao/resultados.md`](avaliacao/resultados.md)):
- O exemplo é pequeno (2 classes, 13 mutantes) e os números não têm comparação estatística.
- Na avaliação da extração (Q3), o gabarito e o casamento das histórias foram escritos pelo Claude (Opus), a pedido do autor;
  nas histórias, o número mede a concordância entre dois modelos, não a de um revisor humano.
- "LIBERADO" vale para os critérios **escritos** na issue: em história sem critérios, a IA extrai só o caminho feliz (revocação de 50%).
- O teste proposto pela IA roda no Maven antes de o humano vê-lo. O filtro estático (`laco.py`) é por palavra e não é sandbox;
  em uso real, os portões deveriam rodar num contêiner.
- Mutantes equivalentes dependem do julgamento humano (`e`), e a lista de métodos públicos vem de uma regex.

**[planejado]**, não implementado: rodar como GitHub Action no PR, com proteção de branch exigindo o check;
publicar o `provapr-relatorio.md` como comentário do PR; ler a issue do GitHub (`gh issue view`); Stryker para JavaScript
(segundo Adapter de `ExecutorMutacao`).

O exemplo `calculadora` deriva do material da disciplina de Engenharia de Software do DCC/UFMG (ver `exemplos/calculadora/LICENSE`).
