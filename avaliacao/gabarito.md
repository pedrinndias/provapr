# Gabarito da extração (Q3)

Regras:
- Escrito **antes** de rodar `medir_extracao.py` e sem olhar nenhuma saída da IA para as entradas E2 a E5.
- Para cada entrada, os critérios de aceitação que um revisor espera. Uma frase curta por critério,
  descrevendo um comportamento observável ("e-mail repetido mostra erro"), não uma tarefa técnica ("criar tabela").
- Não existe número certo de critérios.

Escrito por: Claude (Opus 5.5), a pedido de Pedro Soares, que delegou o preenchimento · Escrito em: 26/11/2026, 21h12 ·
Revisado por Pedro em: ____/____/2026

**Limite desta medição:** o gabarito não foi escrito por um humano. Nas entradas E2 a E5, o Q3 mede a concordância entre dois modelos
(Opus escreveu o gabarito; haiku faz a extração), não a fidelidade a um revisor humano. Na E1, os critérios estão escritos na própria
issue e o gabarito é cópia literal, então ali a medição não depende de quem escreveu.

---

## E1 — issue-2.md (calculadora)

Texto da entrada:
> 1. Somar dois inteiros devolve a soma deles (ex.: 2 + 3 = 5).
> 2. Subtrair dois inteiros devolve a diferença (ex.: 10 - 4 = 6).
> 3. Dizer se um ano é bissexto: divisível por 4, exceto os divisíveis por 100, que só são bissextos se divisíveis por 400 (2000 é bissexto; 1900 não é).

Critérios esperados:
- CA1: Somar dois inteiros devolve a soma (2 + 3 = 5).
- CA2: Subtrair dois inteiros devolve a diferença (10 - 4 = 6).
- CA3: Um ano é bissexto se divisível por 4, exceto os divisíveis por 100 que não são divisíveis por 400 (2000 sim; 1900 não).

---

## E2 — US-01 (pedrinndias/study#1, 5 pontos)

Texto da entrada:
> Eu, como aluno da PUC, gostaria de entrar no app com minhas credenciais institucionais, de modo que apenas membros reais da universidade façam parte da rede.

Critérios esperados:
- CA1: Aluno com credencial institucional válida da PUC consegue entrar no app.
- CA2: Credencial inválida (senha ou usuário errado) é recusada com mensagem de erro, sem entrar.
- CA3: Quem não tem vínculo com a PUC (conta de e-mail externa ou credencial de outra instituição) não consegue entrar nem se cadastrar.
- CA4: Depois de entrar, o aluno continua logado entre aberturas do app até sair (logout).

---

## E3 — US-02 (pedrinndias/study#2, 3 pontos)

Texto da entrada:
> Eu, como aluno, gostaria de montar meu perfil com curso, período e interesses, de modo que colegas com afinidade consigam me encontrar.

Critérios esperados:
- CA1: O aluno consegue informar e salvar curso, período e interesses no próprio perfil.
- CA2: O perfil não é salvo sem os campos obrigatórios (curso e período), e o app indica o que falta.
- CA3: O aluno consegue editar o perfil depois de salvo, e a mudança aparece para os outros.
- CA4: Outros alunos encontram o perfil ao buscar ou filtrar por curso, período ou interesse em comum.

---

## E4 — US-03 (pedrinndias/study#3, 3 pontos)

Texto da entrada:
> Eu, como aluno, gostaria de adicionar outros alunos à minha lista de amigos, de modo que eu crie uma rede de contatos dentro da universidade.

Critérios esperados:
- CA1: O aluno consegue enviar um pedido de amizade a outro aluno a partir do perfil dele.
- CA2: Quem recebe o pedido pode aceitar ou recusar; só depois de aceito os dois aparecem na lista de amigos um do outro.
- CA3: Não é possível enviar pedido repetido a quem já é amigo ou já tem pedido pendente, nem a si mesmo.
- CA4: O aluno vê a própria lista de amigos e pode remover alguém dela.

---

## E5 — US-04 (pedrinndias/study#4, 8 pontos)

Texto da entrada:
> Eu, como aluno, gostaria de criar um grupo de estudos de uma disciplina, de modo que eu encontre colegas da mesma matéria para revisar antes das provas.

Critérios esperados:
- CA1: O aluno consegue criar um grupo de estudos informando a disciplina (e um nome/descrição); o criador vira membro e administrador do grupo.
- CA2: Não é possível criar o grupo sem informar a disciplina.
- CA3: Outros alunos encontram o grupo ao buscar pela disciplina.
- CA4: Outros alunos conseguem entrar no grupo, e os membros veem quem participa.
- CA5: Membro pode sair do grupo; o criador pode remover membros.
