# Roteiro de teste com leitor de tela (NVDA e VoiceOver)

**Rascunho v0, de 24/10/2026.** Para quem vai testar as páginas novas (guia, modo educação, transparência) com leitor de tela. O axe do CI acha **falhas técnicas** (rótulo ausente, contraste, estrutura), mas **não** diz se a página **faz sentido ao ser ouvida**. Isso só uma pessoa descobre. **Um teste feito por quem não usa leitor de tela todo dia é indicativo, não definitivo**: ele pega problemas grosseiros, mas não substitui uma pessoa que usa o leitor há anos. O resultado deve ser registrado como "testado por [nome], usuário [novato ou experiente]".

Os atalhos abaixo são os **padrão** do NVDA e do VoiceOver; versões e configurações mudam, então confira na documentação do seu leitor se algum não responder.

## 1. Preparar

### NVDA (Windows, com Firefox ou Chrome)

- **Iniciar:** Ctrl+Alt+N (se estiver instalado com o atalho padrão) ou pelo menu Iniciar.
- **Tecla NVDA:** Insert (ou CapsLock, conforme a configuração).
- **Parar a fala:** Ctrl. **Ler tudo a partir daqui:** NVDA+Seta para baixo.
- **Modo de navegação e modo de foco:** NVDA+Espaço alterna. Nas páginas de leitura, fique no **modo de navegação** (o que permite as teclas de atalho abaixo); em campos de formulário, o NVDA entra no modo de foco sozinho.
- **Visualizador de fala** (útil para **registrar o que foi dito**): menu do NVDA, Ferramentas, Visualizador de fala.
- **Atalhos no modo de navegação:** **H** (próximo título; Shift+H volta; 1 a 6 vão a títulos de cada nível), **D** (próximo marco, como navegação e conteúdo principal), **K** (próximo link), **T** (próxima tabela), **G** (próximo gráfico), **B** (próximo botão), **F** (próximo campo de formulário), **Tab** (próximo item que recebe foco).
- **Lista de elementos:** NVDA+F7 mostra uma lista de **links, títulos, marcos e botões**: bom para ver a **estrutura inteira** e se os nomes fazem sentido sozinhos.
- **Título da página:** NVDA+T.

### VoiceOver (Mac, com Safari)

- **Ligar e desligar:** Cmd+F5.
- **VO:** Control+Option.
- **Navegar:** VO+Seta para a direita ou esquerda. **Ler tudo:** VO+A. **Parar:** Control.
- **Rotor** (lista de títulos, links, marcos, campos de formulário): VO+U, depois as setas.
- **Próximo título:** VO+Cmd+H. **Próximo link:** VO+Cmd+L.
- **Ativar:** VO+Espaço.

### VoiceOver (iPhone, com Safari)

- **Ligar:** Ajustes, Acessibilidade, VoiceOver.
- **Navegar:** deslizar para a direita ou esquerda. **Ativar:** toque duplo. **Rotor:** girar dois dedos (títulos, links, marcos).
- **Ler tudo:** deslizar para cima com dois dedos.

## 2. Como testar uma página

Para **cada** página abaixo, nesta ordem, anote **o que foi lido** e se **fez sentido sem ver a tela**:

1. **Título da página** (NVDA+T) está claro e diz onde você está?
2. **Primeiro Tab:** o primeiro foco é "Pular para o conteúdo"? Ao ativá-lo, o foco vai para o conteúdo principal?
3. **Marcos:** (D) há navegação, conteúdo principal e rodapé? Os nomes dos marcos fazem sentido?
4. **Títulos:** (lista de elementos ou H) a **hierarquia** faz sentido? Há **um só título de nível 1**? Algum título é "vazio" ou repetido sem contexto?
5. **Links:** (K ou lista de elementos) **cada link faz sentido fora do contexto** ("Classe 44", "Praticar casos deste grupo") ou há "clique aqui" ou "saiba mais" soltos?
6. **O que foi lido que parece estranho?** Palavras cortadas, siglas lidas letra por letra de modo confuso, símbolos, repetição.
7. **Dá para fazer o que a página propõe só com o teclado?** Sem armadilha, sem perder o foco.
8. **O que você **não** conseguiu saber** sem ver a tela?

## 3. Páginas e o que esperar

| # | Página | O que conferir em especial | Esperado |
|---|---|---|---|
| 1 | **`/`** (triagem) | Navegação principal; formulário | O menu lista Triagem, Educação, Guia e Transparência, e a página atual é anunciada como "página atual"; o formulário tem rótulos em todos os campos |
| 2 | **`/guia`** (início) | Cartões dos quatro grupos; trilha de navegação | Cada cartão é um link com nome claro; a trilha é uma lista de navegação |
| 3 | **`/guia/visual`** | Tabela "classes lado a lado"; ilustrações | A tabela tem **legenda** e **cabeçalhos de coluna**; cada ilustração tem **título e descrição completa** (G para ir até ela) |
| 4 | **`/guia/visual/classe-11`** | Figura de acuidade (escala logMAR) | A **descrição longa** diz todos os números e rótulos desenhados; nada depende de ver as cores |
| 5 | **`/guia/baixa-estatura/classe-40`** | Tabela por sexo | Ao navegar a tabela célula a célula (NVDA: Ctrl+Alt+setas), o leitor diz o **cabeçalho** (sexo, classe, estatura, braço, soma) com cada valor |
| 6 | **`/guia/amputacao-em-pe/classe-44`** | Pictograma do padrão; lista de padrões | O pictograma tem descrição por texto; a lista de padrões é lida como lista; o aviso de que força e amplitude não entram é encontrado |
| 7 | **`/guia/glossario`** | Lista de definição; âncoras | Cada termo é lido com sua definição; ao seguir um link de termo a partir de uma classe, o foco vai para o termo e o leitor o anuncia |
| 8 | **`/educacao`** | Cartões e aviso fixo | O aviso de "material de estudo, dados fictícios, rascunho" é lido logo no começo |
| 9 | **`/educacao/praticar?...`** (um caso) | **Responder e ouvir o resultado** | Os botões de rádio vêm dentro de um grupo com **legenda** (a pergunta); depois de **Responder**, o leitor **anuncia** "Você acertou" ou "Não foi dessa vez" **sem você ter de procurar**, e o foco vai ao título do resultado; o **rastro** é uma tabela ou lista legível |
| 10 | **`/educacao/quiz`** | Fluxo do quiz, pontuação | A pontuação é falada como "acertos X de Y"; não há palavra "acurácia" |
| 11 | **`/transparencia`** | Tabelas de métricas; "verificação ao vivo" | Tabelas com cabeçalhos; o aviso de nível de evidência N1 é lido junto aos números; a verificação ao vivo diz o resultado em texto |

## 4. Folha de registro

Copie a tabela abaixo para um arquivo e preencha uma linha por página (ou por problema).

| Data | Leitor e versão | Navegador | Quem testou (experiência com leitor de tela) | Página | Resultado (ok, problema leve, problema grave) | O que foi lido | O que deveria ser lido | Observações |
|---|---|---|---|---|---|---|---|---|

**Problema grave** é o que **impede** completar a tarefa (não achar o conteúdo, o resultado do quiz não é anunciado, armadilha de teclado). **Problema leve** é o que **atrapalha** (título repetido, link vago, leitura confusa).

## 5. Depois do teste

1. Mande a folha (e, se puder, o texto do Visualizador de fala) à sessão de arquitetura.
2. Eu **triagio** os problemas, abro **issues** no repositório da plataforma (rótulo `a11y`) e passo as correções à sessão de código.
3. O que for corrigido volta para **novo teste**.
4. O item 1 da `docs/guia_checklist_acessibilidade.md` passa a **"parcial"** (testado por uma pessoa, não usuária habitual) e **só passa a "feito"** com **uma pessoa que use leitor de tela no dia a dia** (de preferência um atleta com deficiência visual).

## 6. O que este roteiro não cobre

- **Tema escuro** e **alto contraste**: ver a lista de verificação.
- **Leitura fácil, Libras e outros idiomas** (K8).
- **Celulares com TalkBack** (Android): fica para depois.
- **Usuário real** de leitor de tela: pendência explícita.
