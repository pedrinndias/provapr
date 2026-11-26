# ProvaPR
CLI que transforma "o CI está verde" em "cada critério da issue tem um teste que detecta mudança".
A IA (via `claude -p`) propõe critérios, ligações e testes; compilador, JUnit, PIT e um humano decidem.
Só biblioteca padrão do Python (≥ 3.10) sobre projetos Maven com pitest-maven.
Testes: `python3 -m unittest discover -v`. Exemplo da demo em `exemplos/calculadora`.
