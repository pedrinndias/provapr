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

Comando: `python3 avaliacao/medir_extracao.py extrair --repeticoes 3 --modelo haiku --gravar replay/aval_extracao.jsonl`, depois
`python3 avaliacao/medir_extracao.py medir` (dados em `avaliacao/extracao.json`, casamento em `avaliacao/casamento.json`, números em
`avaliacao/extracao_metricas.json`). 5 entradas × 3 execuções independentes = 15 chamadas, média de 5.984 ms, 2 min 53 s.
Entradas: `issue-2.md` (critérios escritos) e US-01 a US-04 de `pedrinndias/study` (só a frase da história, **sem critérios escritos**).

**Quem julgou:** a pedido de Pedro, o gabarito (`avaliacao/gabarito.md`) e o casamento foram escritos pelo Claude (Opus 5.5), com o gabarito
escrito antes da extração. Nas histórias, então, isto mede a concordância entre dois modelos, não a de um revisor humano. Na `issue-2.md`
o gabarito é cópia literal da issue, e o resultado não depende de quem escreveu.

| Entrada | Critérios da IA (3 execuções) | Gabarito | Precisão | Revocação | Estabilidade (Jaccard) |
|---|---|---|---|---|---|
| E1 `issue-2.md` | 3, 3, 3 | 3 | 100% | 100% | 1,00 |
| E2 US-01 login institucional | 1, 1, 1 | 4 | 100% | 50% | 1,00 |
| E3 US-02 perfil | 2, 1, 4 | 4 | 100% | 50% | 1,00 |
| E4 US-03 amigos | 1, 1, 1 | 4 | 100% | 25% | 1,00 |
| E5 US-04 grupo de estudos | 2, 2, 1 | 5 | 100% | 40% | 1,00 |
| **Total** | | | **100%** | **50%** | |

Precisão = critérios da IA que casam com algum do gabarito; revocação = critérios do gabarito cobertos, somados nas 3 execuções;
estabilidade = Jaccard médio, entre pares de execuções, do conjunto de critérios do gabarito cobertos.

Leitura:
- **Issue com critérios escritos:** extração literal e estável. 3 de 3 nas 3 execuções, mesmo mapeamento (CA1 → `Calculadora#soma`,
  CA2 → `Calculadora#subtrai`, CA3 → `Calendario#ehBissexto`); só a redação variou (como nas gravações `dia2`, `demo` e `aval_geracao`).
- **História sem critérios:** a IA não inventa. Devolve só o que a frase afirma (o caminho feliz e o objetivo do "de modo que"), quase sempre
  avisando "critério inferido; a issue não traz critérios explícitos". Por isso a precisão fica em 100% e a revocação em 50%: os casos de erro
  e de borda do gabarito (credencial inválida, pedido repetido, campo obrigatório, sair do grupo) não aparecem.
- O número de critérios varia entre execuções (E3: 2, 1, 4), mas o conjunto coberto não muda (Jaccard 1,00): a IA ora junta, ora separa
  os mesmos comportamentos.
- **Consequência para o ProvaPR:** "LIBERADO" vale para os critérios escritos na issue. Numa história sem critérios, a ferramenta provaria
  só o caminho feliz; o que falta escrever é trabalho do time, não da IA. Isso reforça a decisão de a IA *extrair* e não *inventar* critérios.

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
Gabarito do Q3 escrito por um revisor humano (aqui foi o Claude, a pedido de Pedro) e extração em histórias que tenham critérios escritos.
