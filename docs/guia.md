# Guia de classes (K18): nota de desenho

**Estado:** nota aprovada (PR #6) e implementada no ramo `feature/k18-guide` (Passo 2). A seção "Como ficou a implementação", no fim, lista o que mudou em relação à nota.

**O que é:** um guia de estudo, em português, para entender as classes do atletismo paralímpico por grupo e por classe, com texto nosso, glossário, ilustrações originais em SVG e ligações com o modo educação (K2) e com o painel de transparência (K11). É **conteúdo**: não calcula nada do usuário, não recebe dado dele e não guarda nada.

**Escopo (leitura adotada no brief):** os mesmos quatro grupos do K2: `visual` (11 a 13), `short_stature` (40 e 41), `limb_standing` (42 a 47) e `limb_prosthesis` (61 a 64). São 15 classes. Ficam de fora a classe 20, neuro (31 a 38), Petra (71 e 72) e cadeira (51 a 57). "Validado" aqui quer dizer "implementado e já usado no K2", **não** revisado por classificador; a palavra "validado" não aparece nas páginas (o guia diz "implementado" e "em leitura nossa").

**Aviso fixo, em toda página** (constante única `NOTICE` em `guide/scope.py`):

> Guia de estudo, em leitura nossa do livreto do CPB (2024). Não é classificação oficial e ainda está por validar com a especialista.

**Marca de conteúdo:** toda página mostra "Rascunho" enquanto `review_status` for `draft`. O status vem de `guide/review_status.json` (lista de páginas `reviewed` e um indicador `texts_reviewed`), **vazio no início**, como no K2.

## O que verifiquei antes de escrever (sem commitar código)

- O catálogo dá, para as 15 classes, número, códigos (T e F), `name_pt`, grupo e `source_page`. **Só visual e baixa estatura têm `criteria` numéricos**; os grupos de amputação são uma tabela de níveis em `limb.py` (a mesma situação do K2).
- O K2 já tem, para a semente 0, **ao menos um caso de nível fácil ou médio com resposta em cada uma das 15 classes**. Dá para cada página de classe ter um **exemplo fictício** vindo do K2, sem inventar perfil novo.
- A web não tem navegação: cada página (`/`, `/transparencia`, `/educacao`…) monta o seu próprio cabeçalho. O `layout.tsx` raiz só tem o `<body>`. `/transparencia` tem um link "pular para o conteúdo" próprio e `id="conteudo"` no `main`; a home e o `StudyPage` do K2 não têm `id` no `main`.

## 1. Arquitetura de informação

```
/guia                                   início
/guia/visual                            grupo
/guia/visual/classe-11                  classe (11, 12, 13)
/guia/baixa-estatura                    grupo
/guia/baixa-estatura/classe-40          classe (40, 41)
/guia/amputacao-em-pe                   grupo
/guia/amputacao-em-pe/classe-42         classe (42 a 47)
/guia/amputacao-com-protese             grupo
/guia/amputacao-com-protese/classe-61   classe (61 a 64)
/guia/glossario                         glossário
```

São **21 páginas**, todas estáticas (geradas no build). Os endereços usam nomes em português (`baixa-estatura`), não os ids do catálogo; o mapa entre os dois vive em `guide/scope.py`, e um teste confere que os quatro grupos são exatamente os de `education.scope.ALLOWED_GROUPS`. Qualquer outro endereço dá a página 404 do Next.

| Página | Conteúdo | Liga com |
|---|---|---|
| **Início** | O que é o guia e para quem; como ler os códigos T e F; os quatro grupos em cartões (uma frase de cada); aviso de que há outros grupos "em validação" e fora do guia; versão das regras e data de geração | K2 (`/educacao`), K11 (`/transparencia#regras`), glossário |
| **Grupo** | O que decide a classe neste grupo; as classes lado a lado; como as classes vizinhas se diferenciam; ilustração do grupo; o que o guia não cobre; termos da página | K2 (praticar o grupo), as classes do grupo |
| **Classe** | A classe em uma frase; o que a regra pede (gerado dos dados); como se diferencia das vizinhas; ilustração; um exemplo fictício do K2; o que não cobre; referência de página do livreto; termos da página | K2 (praticar o grupo), grupo, classes vizinhas, K11 |
| **Glossário** | Todos os termos, em ordem alfabética, com âncora por termo | todas |

**Ligação com o K2.** Cada página de grupo e de classe tem "Praticar casos deste grupo", para `/educacao/praticar?grupo=<id>&nivel=easy&semente=0&caso=0`. O K2 hoje sorteia por grupo e nível, não por classe, então o link é **por grupo**. Uma ligação por classe pediria um filtro novo na API do K2 (ver as dúvidas). **Ligação com o K11:** o rodapé de toda página aponta para `/transparencia#regras` (versão e estado dos grupos).

**Trilha de navegação** (migalhas) em toda página interna: `Guia > Grupo > Classe`, em `<nav aria-label="Trilha">` com lista ordenada e `aria-current="page"` no último item.

## 2. Estrutura do texto e geração a partir do catálogo

### Bloco por página de classe, na ordem

1. **Título e códigos:** "Classe 44 (T44/F44)" e o `name_pt` do catálogo. Os códigos T e F **vêm do catálogo** (campo `events`, que o catálogo diz estar por validar); uma nota curta diz isso.
2. **Em uma frase** (texto nosso): a ideia da classe, sem número.
3. **O que a regra pede** (**gerado**): visual e baixa estatura, os critérios numéricos do catálogo, formatados (por exemplo, "acuidade do melhor olho de 1,50 a 2,60 logMAR, ou campo visual abaixo de 10 graus"); amputação, a **lista dos padrões** de nível por membro que resultam nesta classe, **enumerados executando o motor** nas 144 combinações de níveis.
4. **Como se diferencia das vizinhas** (**gerado**, com moldura de texto nosso): compara com a classe anterior e a seguinte do grupo, usando só os mesmos dados. Exemplo para baixa estatura: uma tabela por sexo com os três limites da 40 e da 41, e a frase "as duas classes são aninhadas: vale a mais comprometida que o caso atende".
5. **Ilustração** (ver 3).
6. **Exemplo fictício** (do K2, semente 0): o resumo e os fatos do caso, e a conclusão do rastro. Marcado como "Caso fictício do modo educação".
7. **O que o guia não cobre** (texto nosso, igual aos `limits` do K2 para o grupo, para dizer a mesma coisa nos dois lugares).
8. **Referência:** "Cartilha do CPB (2024), p. N" do `source_page`, **só como referência**, mais "Termos desta página".

A **página de grupo** tem os mesmos blocos 2, 4, 5, 7 e 8, mais a tabela "classes lado a lado" (número, códigos, o que a regra pede em uma linha) no lugar dos blocos 3 e 6.

### Como o texto nasce, sem duplicar a lógica das regras

Há **duas camadas** em `src/para_triage/guide/`:

- **Prosa nossa** (`texts_pt.py`, módulo único e reviável, como o do K2): as frases explicativas e as molduras. **Regra do projeto: a prosa não tem número de limiar.** Todo número que a página mostra é **gerado** a partir do catálogo ou do motor e entra no texto por um espaço reservado (por exemplo, `{logmar_min_12}`). Um teste varre a prosa e **falha se achar um número** que não seja número de classe, "2024" ou "T/F". Assim, quando a WPA ou o catálogo mudarem um limite, nenhuma frase fica com o número velho.
- **Dados gerados** (`build.py`): lê `load_catalog()` (critérios e metadados) e **executa o motor** (`RuleEngine.evaluate`) para os padrões de amputação. Não reimplementa nenhuma regra. A única lógica de apresentação é ordenar e agrupar padrões (por exemplo, juntar "esquerda" e "direita" em "um dos membros").

### Como o teste protege contra divergir do motor

1. **Afirmações verificáveis.** Cada página gerada carrega uma lista `claims`: perfis fictícios e a resposta que a página implica (um dentro do critério, um no limite, um logo fora; para amputação, um por padrão listado). O teste roda `engine_answer` (o mesmo do K2) em cada um e **falha se divergir**. É o teste de contrato do guia: se o motor mudar e a página não, o teste acusa.
2. **Amputação por enumeração.** Os padrões da página vêm do próprio motor; o teste ainda confere que o conjunto de padrões por classe é o da tabela do K2 (`education/trace.py`), que já é conferida nas 144 combinações.
3. **Prosa sem número** (acima) e **teste de conteúdo velho** (ver 7).
4. Os exemplos fictícios usam o K2; o golden do K2 já fixa esses casos, então mexer no gerador também chama atenção aqui.

## 3. Ilustrações

Todas **originais**, em SVG, desenhadas por nós a partir de formas simples. **Nenhuma imagem da LEXI nem da cartilha**, e nenhuma foto. A geometria é **gerada de dados** (os mesmos números do texto), para o desenho não divergir da frase.

| # | Figura | Onde | O que mostra |
|---|---|---|---|
| F1 | Escala de acuidade (logMAR) | Visual (grupo e classes) | Uma barra horizontal de 0 a 3 com as faixas da 13, da faixa sem classe, da 12 e da 11, com marcas e rótulos numéricos nos limites |
| F2 | Campo visual | Visual | Dois círculos concêntricos em escala, com os limites de 10 e 40 graus rotulados |
| F3 | Medidas da baixa estatura | Baixa estatura | Uma figura de bonecos de traço, de frente, com a estatura (linha vertical) e o braço mais longo (do ombro à ponta do dedo) marcados e rotulados, sem números de classe |
| F4 | Níveis de amputação, membro inferior | Amputação (grupos e classes) | Uma perna esquemática com três marcas horizontais rotuladas: parte do pé, abaixo do joelho, através ou acima do joelho |
| F5 | Níveis de amputação, membro superior | Amputação em pé | Um braço esquemático com duas marcas: punho e cotovelo |
| F6 | **Pictograma do padrão** (uma por classe de amputação) | Páginas das classes 42 a 47 e 61 a 64 | Um boneco de traço com os quatro membros; cada membro afetado mostra o nível de amputação por um recorte e um rótulo de texto; gerado **a partir do padrão** do motor |

**Como são desenhadas.** Componentes React que desenham SVG a partir de dados tipados (`web/src/components/guide/figures/`), com `viewBox` fixo e `width: 100%`, texto em SVG com pelo menos 12 unidades (legível em 320 px), traço e preenchimentos com `currentColor` e variáveis de cor do tema (claro e escuro). Os dados vêm do JSON gerado.

**Acessibilidade das figuras.**

- Cada figura é `<figure>` com `<figcaption>` visível e `role="img"` com `aria-labelledby` (título) e `aria-describedby` (descrição longa). A **descrição longa é gerada junto com a figura**, a partir dos mesmos dados: ela diz todos os números e rótulos desenhados. Teste: toda figura tem título e descrição, e **todo número desenhado aparece na descrição**.
- **Nada só por cor:** cada faixa e cada membro afetado tem **padrão** (hachura, pontilhado, traço) **e rótulo de texto**; a cor é reforço. Os padrões distinguem as faixas em tons de cinza.
- **Contraste:** paleta fixa no código, com razão de contraste calculada em teste (mínimo 4,5:1 para texto e 3:1 para traços e preenchimentos significativos, contra o fundo claro e o escuro). Em modo de cores forçadas, o traço usa `currentColor` para continuar visível.
- **Daltonismo:** o teste simula protanopia, deuteranopia e tritanopia sobre a paleta e confere que as faixas vizinhas continuam diferentes **pelo padrão** (a cor sozinha pode não bastar, e por isso não é o único canal).
- **320 px:** conferido no navegador, sem rolagem horizontal, e pelo axe (ver 6).

**Quem revisa:** a especialista, quanto ao conteúdo (o que cada desenho afirma sobre níveis e medidas); e, para acessibilidade, uma pessoa que use leitor de tela no dia a dia, **ainda a definir** (dúvida 6).

## 4. Glossário

**Mecanismo.** Página `/guia/glossario` com uma lista de definição (`<dl>`), em ordem alfabética, com `id` por termo. **Sem pop-up por hover.** Na prosa, o termo é um **link** para `/guia/glossario#termo` (sublinhado, foco visível). Cada página de grupo e de classe termina com **"Termos desta página"**: as definições curtas dos termos usados ali, em texto corrido, sem recolher nem abrir, para ler sem sair da página. Quem usa teclado ou leitor de tela só precisa de links e texto.

**Termos** (definições curtas nossas, uma a duas frases cada): classe esportiva; classificação (oficial); classificador; grupo de deficiência; deficiência elegível; critério mínimo de deficiência; livreto do CPB; códigos T e F (pista e saltos, lançamentos e arremessos, como o catálogo os atribui); logMAR; acuidade visual; melhor olho, com a melhor correção; campo visual; baixa estatura; acrômio; comprimento do braço (do acrômio à ponta do dedo mais longo); soma de estatura e braço; classes aninhadas; amputação; nível de amputação; através do joelho; acima do joelho; abaixo do joelho; pé parcial (nível de Lisfranc); punho; cotovelo; prótese de corrida; compete em pé, sem prótese; caso limítrofe; rastro dos critérios; leitura nossa. São **30 termos**.

**Como ficam consistentes.** A prosa marca o termo com um espaço reservado (`{{termo:acromio|acrômio}}`); o gerador resolve em segmentos de texto e de link. Teste: todo termo citado existe no glossário, todo termo do glossário é citado em ao menos uma página, e nenhum termo do glossário tem número de limiar.

## 5. Shell de navegação

**Estrutura.** Um componente `SiteNav` no `layout.tsx` raiz, acima do conteúdo:

```
<a href="#conteudo">Pular para o conteúdo</a>        (primeiro foco da página)
<header>
  <nav aria-label="Principal">
    <ul>  Triagem (/) · Educação (/educacao) · Guia (/guia) · Transparência (/transparencia)  </ul>
  </nav>
</header>
```

- Lista simples de links, **sem menu recolhível e sem JavaScript para abrir**: em 320 px os itens quebram em linhas. O item da página atual leva `aria-current="page"` (e um sublinhado mais grosso, não só cor). O componente é cliente só para ler `usePathname`.
- Alvos de pelo menos 24 px de altura, foco visível, ordem do teclado igual à visual.
- **Fica oculto na impressão** (`print:hidden`), porque a home imprime o relatório.

**Como entra nas páginas existentes sem quebrá-las.**

1. O `layout.tsx` ganha o `SiteNav` antes de `{children}`; nada mais muda no layout.
2. O link "pular para o conteúdo" passa a ser **um só**, no shell. Para ele funcionar, cada `<main>` precisa de `id="conteudo"`: a home e o `StudyPage` do K2 ganham o atributo; `/transparencia` já o tem e **perde o link duplicado** que tem hoje (senão haveria dois).
3. Os links soltos que já existem na home ("Transparência", "Modo educação") e os "Voltar à triagem" **ficam**: são redundantes, mas inofensivos, e tirá-los não é necessário para o K18.
4. Testes de regressão: os testes atuais que procuram texto nas páginas (K2 e K11) continuam passando, e um teste novo confere que cada página tem exatamente um `id="conteudo"` e um `<main>`.

## 6. Plano de teste de acessibilidade

**Automatizado, no CI (proposta):** um job `a11y` que sobe `next start` e, com **Playwright** e **`@axe-core/playwright`**, percorre todas as páginas do guia (21), a home, `/educacao`, `/educacao/praticar` com um caso e `/transparencia`. Para cada uma, roda o axe com as regras WCAG 2.0 A/AA, 2.1 AA e 2.2 AA mais as boas práticas (`heading-order`, `region`, `landmark-*`), em **tema claro e escuro** (`colorScheme` do Playwright) e em **320 px e 1280 px**, e confere que não há rolagem horizontal. Falha com qualquer violação. O axe mede **contraste real** no navegador, o que o teste de paleta em Python não alcança. Os pacotes são instalados no job com `npm install --no-save` (sem mexer no `package.json` nem no lock; ver a issue #3 sobre o lock no Linux). As páginas do guia são estáticas e **não precisam da API**; as de K2 e K11 precisam do servidor da API ou entram só se a API de teste subir no job (dúvida 3).

**Automatizado, em Python (sem navegador):** alt e descrição longa de toda figura; todo número desenhado na descrição; contraste da paleta nos dois temas; simulação de daltonismo; hierarquia de títulos do JSON (um `h1`, sem salto); âncoras de glossário resolvidas; links internos resolvidos (toda rota citada existe).

**Manual, com lista** (`docs/guia_checklist_acessibilidade.md`, criada no Passo 2): só teclado em todas as páginas; zoom de 200% e 400%; espaçamento de texto aumentado; modo de cores forçadas; leitura de uma página de cada tipo.

**O que continua sem verificação (e fica dito na PR do Passo 2):** **leitor de tela** (NVDA e VoiceOver) e **aspectos cognitivos** (leitura fácil é do K8, e a Libras também). O tema escuro fica coberto pelo axe, mas **não** por uma leitura humana.

## 7. Obsolescência

**Conteúdo gerado e commitado.** `python -m para_triage.guide.export` grava `web/src/content/guide.json` (as páginas, as figuras, o glossário, as afirmações verificáveis). As páginas leem esse arquivo **no build**; a web e a API **não executam o motor nem leem o catálogo em tempo de execução**. O JSON leva `rules_id` (de `rules_version()`), `catalog_pages` (`source_page` usados) e `generated_on` (data da geração, em ISO).

**Cada página mostra:** o id de versão das regras e a data da última geração (rodapé, com link para `/transparencia#regras`).

**Testes que falham se o conteúdo ficar velho:**

1. `guide.json.rules_id == rules_version().id` (mudou uma regra, o catálogo ou o motor: regere).
2. O JSON **regerado em memória** é igual ao commitado, **ignorando `generated_on`** (pega mudança no catálogo, na prosa ou no K2 sem regerar, mesmo quando o id das regras não mudou).
3. As afirmações verificáveis (seção 2) batem com o motor.

A mensagem do teste diz o comando para regerar e que o diff do JSON deve ser revisado.

**Aviso em tempo de execução (opcional, progressivo).** Um pequeno componente cliente consulta `GET /api/transparency` e, **se a API responder** e o `live.rules_id` for diferente do `rules_id` da página, mostra um aviso de que o guia foi gerado com outra versão das regras. Sem API, não mostra nada (o guia não depende dela).

**Quando regerar:** quando o catálogo, o motor, os textos do guia ou o banco do K2 mudarem. É o mesmo hábito do K11 (`docs/transparencia.md`).

## 8. O que não cobre, riscos e dúvidas

**Não cobre:**

- A classe 20, neuro (31 a 38), Petra (71 e 72) e cadeira (51 a 57). O início do guia diz que há outros grupos fora dele "por estarem em validação", sem listar regras provisórias.
- **Provas e equipamentos** (a validar), idade, sexo além do que as regras usam, exemplos de pessoas reais, fotos.
- **Leitura fácil** (K8), **Libras**, outros idiomas, busca, impressão formatada e uso offline. A estrutura (blocos curtos, frases simples, texto separado da apresentação) **não impede** uma versão em leitura fácil depois.
- Os grupos de amputação em pé cobrem **só o nível de amputação** (como no K2). Força, amplitude de movimento e a diferença de 7 cm entre as pernas (classe 44) ficam fora e **a página diz isso**.

**Riscos:**

| Risco | Mitigação |
|---|---|
| A prosa ensinar um número que mudou | Prosa sem número; todo número é gerado; teste varre a prosa |
| O guia divergir do motor | Afirmações verificáveis rodadas no motor; padrões de amputação enumerados do motor |
| O guia parecer classificação oficial | Aviso fixo em toda página, "Rascunho", e nenhum cálculo do usuário |
| Copiar a cartilha ou a LEXI | Texto nosso num só módulo, revisão humana na PR (nenhum teste detecta cópia); nenhuma imagem de terceiros |
| Desenho simplificar demais e induzir erro | A especialista revisa o que cada figura afirma; a descrição longa diz o que é esquema |
| Os códigos T e F dependerem de provas não validadas | Nota nas páginas; ou omitir os códigos (dúvida 5) |
| Conteúdo envelhecer sem aviso | Testes de obsolescência e aviso em tempo de execução |
| O shell de navegação mexer nas páginas existentes | Mudança mínima (`id` no `main`, um link duplicado removido) e testes de regressão |

**Dúvidas para a arquitetura:**

1. **Endereços em português** (`baixa-estatura`, `amputacao-em-pe`) em vez dos ids do catálogo. Recomendo em português.
2. **Praticar por classe.** Hoje o K2 só filtra por grupo e nível. Posso **só ligar por grupo**, ou acrescentar ao K2 um parâmetro de leitura (por exemplo, `answer=class:44`) em `GET /api/education/case`, o que mexe numa PR já mesclada. Recomendo **ligar por grupo** agora.
3. **axe no CI** com Playwright instalado por `npm install --no-save`, sem mudar `package.json`. As páginas de K2 e K11 pedem a API; proponho **testar no job só o guia, a home estática e a página `/transparencia`** (que importa o JSON no build), e deixar K2 para a checagem manual. Aceita?
4. **Conteúdo gerado e commitado** (`guide.json`) em vez de ler o catálogo na hora. Recomendo o commitado, pelo teste de obsolescência pedido no brief.
5. **Mostrar os códigos T e F** (vêm de `events`, "a validar") com uma nota, ou omiti-los? Recomendo mostrar com a nota, já que o K2 os mostra.
6. **Quem revisa as figuras** quanto à acessibilidade: a especialista cobre o conteúdo, mas não sei quem usa leitor de tela. Pode ser alguém do grupo, ou fica registrado como "não verificado".
7. **Exemplo fictício do K2 em cada classe.** Recomendo, por reaproveitar casos já testados; depende de o K2 continuar estável (o golden protege).
8. **Shell de navegação no layout raiz**, com `id="conteudo"` nas páginas existentes e a remoção do link duplicado de `/transparencia`. Pede seu OK, porque mexe em páginas já mescladas.
9. **`generated_on`** fica no JSON (pedido do brief), então regerar sem mudança de conteúdo muda o arquivo. Aceito, com os testes ignorando esse campo.
10. **Aviso em tempo de execução** (a página compara o id das regras com a API): vale o pequeno custo, ou fica só o teste de CI?

## Estrutura de arquivos prevista (Passo 2)

```
src/para_triage/guide/
  scope.py            grupos, mapa de endereços, aviso fixo
  texts_pt.py         toda a prosa nossa (sem número de limiar) e o glossário
  build.py            catálogo + motor -> páginas, figuras e afirmações
  export.py           grava web/src/content/guide.json
  review_status.json  vazio
  review_sheet.py     folha de revisão para a especialista
web/src/content/guide.json
web/src/app/guia/{page.tsx, [grupo]/page.tsx, [grupo]/[classe]/page.tsx, glossario/page.tsx}
web/src/components/guide/…       páginas, figuras SVG, glossário, aviso de versão
web/src/components/site/site-nav.tsx
tests/test_guide_*.py
docs/guia_checklist_acessibilidade.md
```

Nada em `rules/`, `data/`, `models/` ou `experiments/` muda. O código novo só **importa** `RuleEngine`, `load_catalog`, `rules_version` e o que o K2 já expõe (`education.cases`, `education.scope`).

## Como ficou a implementação

A nota foi seguida, com os acréscimos da revisão e estes ajustes:

- **Tom e desenho neutros e respeitosos** (acréscimo 1): a prosa evita pena, superação e "falta" (um teste varre uma lista de palavras); o nível de amputação é descrito como característica; os bonecos são esquemas de traços, com nota na legenda de que não são pessoas. A folha de revisão pede à especialista que avalie o tom e registra que o ideal é uma revisão também por atleta com deficiência (ainda não identificada).
- **Job `a11y` estável** (acréscimo 2): versões fixas (`@playwright/test` 1.55.0, `@axe-core/playwright` 4.10.2), instaladas com `--no-save`; cache do Chromium; os passos e as mensagens separam `INFRA:` (navegador, servidor, rede; código de saída 2) de `A11Y:` (violações reais; código 1).
- **Figuras monocromáticas** (só `currentColor`, mais padrão e rótulo escrito), no lugar do teste de paleta e de simulação de daltonismo da nota: sem cor para carregar significado, o contraste segue o do texto do tema e é medido pelo axe no navegador. Um teste confere que o código das figuras não tem cor literal.
- **Sem tema escuro alcançável.** O app não tem alternância de tema (o `.dark` só existe nos tokens), então o job testa o tema claro. O axe com `A11Y_DARK=1` acusa falhas de contraste de botões e selos já existentes no tema escuro; ficam como informação (ver `docs/guia_checklist_acessibilidade.md`).
- **Problemas achados pelo axe nas páginas existentes e corrigidos** (a home entra no job): texto de descrição do seletor de grupo com contraste baixo (`text-muted-foreground` em fundo selecionado) e títulos de seção do formulário (`h3`) logo depois do `h1`, que viraram `h2`.
- **Problemas achados nas páginas novas e corrigidos:** botões-link com texto longo estouravam 320 px (`whitespace-nowrap`), duas regiões de tabela com o mesmo nome e duas tabelas iguais na página de classe de baixa estatura.
- **Páginas não existentes** (`/guia/qualquer-coisa`) mostram a página "não encontrada" com `noindex`, mas o Next responde com status 200 nesse modo (`cacheComponents` não aceita `dynamicParams`).
- **Aviso em tempo de execução** (`Freshness`): consulta `/api/transparency`; só aparece se a API responder com outra versão das regras; nunca falha nem bloqueia.
- **Folha de revisão:** gerada por `python -m para_triage.guide.review_sheet` (a folha não está neste repositório), com todas as páginas, as descrições das figuras e o glossário.
