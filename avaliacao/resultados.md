# Resultados da avaliação (GQM, decisão D7)

Medido em 26/11/2026, MacBook Intel, JDK 21, Maven 3.9, `claude` CLI com haiku. As respostas da IA estão gravadas em `replay/`,
então os números podem ser reconferidos sem chamar o modelo.

**Meta:** analisar a suíte de testes de um PR para decidir se "verde" significa "cada critério da issue tem teste que detecta mudança",
do ponto de vista do revisor, no exemplo `calculadora`.

## Q1. A suíte detecta mudança em cada critério?

Comando: `printf 's\ns\ns\n' | python3 -m provapr run --projeto exemplos/calculadora --issue exemplos/calculadora/issue-2.md --replay replay/demo.jsonl`
(lido de `provapr-relatorio.json`; cobertura de linha lida do `target/pit-reports/index.html`).

| Critério | Mutantes mortos antes | Depois | Status |
|---|---|---|---|
| CA1 Somar | 2/2 | 2/2 | PROVADO |
| CA2 Subtrair | 0/2 | 2/2 | SEM_TESTE → PROVADO |
| CA3 Ano bissexto | 5/9 | 9/9 | FRACO → PROVADO |
| **Projeto** | **7/13 (54%)** | **13/13 (100%)** | BLOQUEADO → LIBERADO |

Cobertura de linha: **86% (6/7) → 100% (7/7)**. Antes do ProvaPR, a cobertura de linha já parecia boa (86%), mas só 54% dos mutantes morriam
e o CA2 não tinha nenhum teste. As duas métricas contam histórias diferentes.
(O plano previa 67% de cobertura de linha no baseline; o PIT mede 86%. A contagem 13/7 bate.)

## Q2. A IA fecha lacunas sem trazer lixo?

Comando: `python3 avaliacao/medir_geracao.py --repeticoes 5 --modelo haiku --gravar replay/aval_geracao.jsonl`
(detalhe por caso em `avaliacao/geracao.json`). Os 6 mutantes vivos do baseline × 5 repetições independentes, cada uma partindo do baseline.

| Funil da 1ª tentativa (n = 30) | n | % |
|---|---|---|
| Compila | 30 | 100% |
| Passa no código original | 30 | 100% |
| Mata o mutante alvo (PIT) | 29 | 96,7% |
| **Mutantes mortos em até 3 tentativas** | **30/30** | **100%** |

Total: 31 tentativas (1 caso precisou de 2: `Calendario L5 % → *`, cuja 1ª tentativa compilou e passou, mas não matou o alvo).

Aprovação humana: medida só nas execuções da demo. Caminho `s`: 3 de 3 testes aprovados; caminho `n`: 6 de 6 rejeitados e revertidos (AC2).
Nessas execuções, as respostas `s`/`n` vieram por pipe (cenário de aceite), não de um revisor julgando cada teste.

Comparação (ilustrativa, porque a classe é trivial): no 2601.09695, cerca de 80% dos testes gerados compilam e cerca de 57% passam (VI-C1);
o MutGen chega a 89,5% de mutation score no HumanEval-Java. Aqui os portões descartam o que não serve antes de chegar ao humano.

## Q3. A extração é fiel à issue?

**Pendente.** Depende de `avaliacao/gabarito.md`, escrito por Pedro **antes** de rodar `medir_extracao.py`
(issue-2.md + US-01 a US-04 do A5 × 3 execuções). Evidência parcial, sem gabarito: nas 3 extrações ao vivo da `issue-2.md` gravadas no repositório
(`replay/dia2.jsonl`, `replay/demo.jsonl`, `replay/aval_geracao.jsonl`), sempre saíram 3 critérios e o mesmo mapeamento (CA1 → `Calculadora#soma`, CA2 → `Calculadora#subtrai`,
CA3 → `Calendario#ehBissexto`); o texto das descrições variou.

## Q4. Cabe no fluxo de um PR?

| Execução | Tempo total | Chamadas de IA | `duration_ms` médio |
|---|---|---|---|
| Demo ao vivo, caminho `s` (`--gravar`) | 1 min 45 s | 4 | 6.972 ms |
| Demo em replay (AC1) | 43 s (62 s num clone limpo) | 4 (0 ao vivo) | — |
| Suíte vermelha (AC3) | 3,8 s | 0 | — |
| Medição da geração (30 casos) | 12 min 38 s | 32 | 6.100 ms |

Alvo do plano: demo ≤ 2 min ao vivo. **Cumprido** (1 min 45 s). O custo é dominado pelo Maven e pelo PIT (3 portões por tentativa), não pela IA.

## O que não foi medido

Repositório grande, outras linguagens, mutantes equivalentes reais em código de produção e comparação estatística.
