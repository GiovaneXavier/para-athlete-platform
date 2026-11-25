# Modo educação (K2): nota de desenho

**Estado:** nota aprovada (PR #4) e implementada no ramo `feature/k2-education` (Passo 2). A seção "Como ficou a implementação", no fim, lista o que mudou em relação à nota.

**O que é:** um modo de estudo em português. O usuário recebe um caso clínico **fictício** (perfil sintético, determinístico por semente), escolhe uma resposta e só então vê o veredito do motor com o **rastro dos critérios**. Há três níveis de dificuldade e um quiz. Nada é guardado: nem no servidor, nem no navegador entre visitas.

**Escopo fixo (D28):** `visual` (11 a 13), `short_stature` (40 e 41), `limb_prosthesis` (61 a 64) e `limb_standing` (42 a 47) **só por nível de amputação**. Fora, e recusados pela API e ausentes da web: `intellectual` (classe 20), `neuro_seated`, `neuro_standing`, `frame_runner` e `wheelchair`.

**Aviso fixo, em toda tela e em toda resposta da API** (constante única `NOTICE` em `education/scope.py`):

> Material de estudo, com dados fictícios. Não ensina a classificar oficialmente. Regras do livreto do CPB (2024) em leitura nossa, ainda a validar com a especialista.

**Marca de conteúdo:** todo caso e toda explicação levam `review_status` = `draft` (padrão) ou `reviewed`. Nada é `reviewed` até a especialista rever; a tela mostra "Rascunho" enquanto for `draft`.

## O que já verifiquei antes de escrever (sem commitar código)

- `sample_true_profiles(n, [grupo], semente)` é determinístico e **independe dos outros grupos**: sortear `visual` sozinho dá os mesmos perfis que sortear junto com outros. Gerar 210 perfis de 4 grupos leva 0,1 s.
- Num protótipo descartável, reconstruí o veredito **só a partir dos `criteria` do `classes.yaml`** para `visual` e `short_stature` e comparei com o motor: **0 divergências em 2.000 perfis visuais e 1.200 de baixa estatura**.
- **Achado importante:** `limb_standing` e `limb_prosthesis` **não têm `criteria` numéricos** no `classes.yaml`; a lógica é uma tabela de níveis de amputação em `rules/evaluators/limb.py`. O rastro desses dois grupos exige uma **tabela nova na camada de leitura** que repete a tabela do motor. É o risco de duplicação que o brief apontou; a defesa é um teste de consistência **exaustivo** (ver 2).
- `limb_standing` mistura 70% de perfis por amputação e 30% pela via de força, amplitude e diferença de perna. A classe 44 vem muito dessa segunda via (numa amostra de 80 perfis, só 2 dos 10 da classe 44 eram por amputação). Filtrar só amputação é possível sem tocar no gerador, mas exige amostrar **mais** perfis por rótulo (ver 3).
- Para os perfis com campos escondidos: em baixa estatura, esconder qualquer um dos três campos faz o motor devolver `insufficient_data` em todas as classes. Em visual, esconder uma medida dá resultados mistos (classe com ressalva, limítrofe ou insuficiente), então só uso as máscaras que resultam em "dados insuficientes" em todas as classes.

## 1. Formato do caso e como cada grupo apresenta o perfil

Idioma: português do Brasil. Unidades sempre escritas. Decimais com vírgula (formatação feita no servidor, para o teste ver o texto final). Sem nome, idade inventada, foto ou história pessoal: o caso é "Atleta fictício".

Um caso (`CaseOut`) tem: `case_id`, `group`, `difficulty`, `review_status`, `notice`, `presentation` e `options`. **Não tem** classe, veredito, rastro nem qualquer campo de resposta. `presentation` tem uma frase-resumo e uma lista de fatos `{label, value}` (a tela mostra como lista de definição).

| Grupo | Fatos mostrados | Exemplo (resumo) |
|---|---|---|
| Visual | Acuidade do melhor olho, com a melhor correção (logMAR, 2 casas); campo visual (graus) | "Atleta com deficiência visual. No melhor olho, com a melhor correção, a acuidade é de 1,20 logMAR; o campo visual é de 35 graus." |
| Baixa estatura | Sexo; estatura (cm); comprimento do braço mais longo, do acrômio à ponta do dedo mais longo (cm). A soma **não** é mostrada (é parte do raciocínio) | "Atleta do sexo feminino, com 128,0 cm de estatura e braço mais longo de 55,5 cm." |
| Membros em pé | Posição de competição ("em pé, sem prótese"); nível em cada um dos quatro membros: perna esquerda/direita (nenhuma, parte do pé, abaixo do joelho, através ou acima do joelho) e braço esquerdo/direito (nenhuma, nível do punho, cotovelo ou acima) | "Atleta com amputação, que compete em pé e sem prótese. Perna esquerda: abaixo do joelho. Perna direita: sem amputação. Braços: sem amputação." |
| Prótese | Igual ao anterior, com "compete com prótese de corrida" | idem |

Campos que o perfil tem e **não** aparecem: tudo o que não é do grupo (por exemplo, QI, força, amplitude, distribuição neurológica). Os casos de `limb_standing` são só os de perfil por amputação (`impairments == {limb_deficiency}`), então força, amplitude e diferença de perna nunca aparecem.

**Opções de resposta** (as mesmas em todos os níveis de um grupo, para o nível não vazar pela lista): uma por classe do grupo, rotulada só com o número e os códigos do catálogo (por exemplo, "Classe 44 (T44/F44)"), mais **"Nenhuma classe"**, **"Caso limítrofe ou que exige especialista"** (junta os rótulos `-1`, como o brief pede) e **"Faltam dados para decidir"** (ver pergunta 1 abaixo). O **nome** da classe (`name_pt`) só aparece depois de responder, porque nos grupos de amputação ele descreve o próprio padrão e entregaria a resposta.

Provas e equipamentos **não** são mostrados em nenhum lugar do K2 (não estão validados).

## 2. Como o rastro é montado e como o teste de consistência funciona

**Camada nova, só de leitura:** `src/para_triage/education/trace.py`. Ela lê o perfil e os `criteria` do catálogo carregado e devolve uma lista de **passos**; não altera nem chama nada em `rules/` além de ler o catálogo e avaliar o motor. As razões em inglês do motor (`Verdict.reasons`) **nunca** chegam ao usuário (o modelo de resposta nem tem esse campo; há teste).

Cada passo (`TraceStep`) tem: `criterion` (o que se verifica, em português), `reference` (o limite e a comparação, por exemplo "classe 13: de 1,00 a 1,40 logMAR"), `value` (o valor do caso com unidade), `result` (`atende`, `não atende` ou `não avaliado`) e `explanation` (uma frase nossa). O rastro termina com uma `conclusion` e a referência `Cartilha do CPB (2024), p. <source_page>` do catálogo, **só como referência**.

**Por grupo:**

- **Visual** (`criteria` do YAML). Passos da acuidade: contra o intervalo de cada classe (11: pior que 2,60; 12: de 1,50 a 2,60; 13: de 1,00 a 1,40). Passos do campo: contra o limite de cada classe (12: abaixo de 10 graus; 13: abaixo de 40 graus). Passo final: "vale a classe mais comprometida entre as que o caso atende". Caso limítrofe: acuidade entre 1,40 e 1,50, faixa que o livreto deixa sem classe. Ausência de uma medida: passo `não avaliado`.
- **Baixa estatura** (`criteria` do YAML, por sexo). Para a classe 40 e depois a 41: três passos (estatura ≤ limite, braço ≤ limite, soma ≤ limite, com a soma calculada à vista) e um passo "as três condições valem ao mesmo tempo". Passo final: as classes são aninhadas, vale a mais comprometida que o caso atende.
- **Membros em pé** e **prótese** (**tabela nova**, sem `criteria` no YAML). Passos: o nível de cada membro; o par ordenado dos níveis de cada par de membros (maior, menor); a linha da tabela que casa, com o texto nosso (por exemplo, "os dois membros inferiores amputados abaixo do joelho: classe 43"). Casos que o motor manda para especialista (membro superior e inferior juntos em pé; pé parcial; combinações acima e abaixo do joelho com prótese) viram uma conclusão "exige especialista" com a razão em português.

**Resposta certa vs. rastro.** O **gabarito vem sempre do motor** (`RuleEngine.evaluate`), nunca do rastro. O rastro é uma explicação e chega a uma conclusão própria; o teste confere as duas.

**Mapa do motor para a resposta** (mesmo critério do gerador, `label_of`): uma classe `meets` única → essa classe; nenhuma classe e nenhum status especial → "Nenhuma classe"; `borderline` ou `needs_review` → "Caso limítrofe ou que exige especialista"; todas `insufficient_data` → "Faltam dados". Qualquer outra combinação (por exemplo, duas classes `meets`) **não é oferecida**.

**Teste de consistência:**

1. **Numéricos (visual, baixa estatura):** para 200 perfis amostrados por grupo e nível (`sample_true_profiles`), mais uma varredura de valores em volta de cada limiar (limiar ± 0,01, ± 0,05, igual), a conclusão do rastro tem de coincidir com a resposta do motor. Também para as versões com campo escondido.
2. **Amputação (membros em pé, prótese):** teste **exaustivo**: todas as 4 × 4 × 3 × 3 = 144 combinações de níveis, nas duas posições. É mais forte que amostrar, e é o que protege a tabela duplicada.
3. **Descartes:** em tempo de execução, antes de oferecer um caso, a API confere a coincidência; se divergir, o caso é descartado e o próximo candidato é usado. O teste relata quantos foram descartados por grupo. **Meta e limite:** esperado **0**; o teste **falha** se passar de 1% em qualquer grupo (tolerância só para arredondamento de limiar), e eu paro e aviso a arquitetura, como o brief pede.
4. Um teste de que **nenhuma frase em inglês do motor** aparece na resposta.

## 3. Níveis de dificuldade e como são gerados

**Geração.** Para cada par (grupo, semente) a API monta, uma vez, um **banco** com `sample_true_profiles(n_por_rótulo, [grupo], semente)` e guarda em cache (`lru_cache`). O banco é determinístico (mesma semente, mesmos perfis, mesma ordem). `n_por_rótulo` é 40 para visual, baixa estatura e prótese, e **120 para membros em pé** (para sobrar casos de amputação da classe 44 depois do filtro). Cada perfil recebe um nível por uma função pura; o banco de um nível é embaralhado de forma determinística (`default_rng([semente, grupo, nível])`) e o caso de índice *i* é o *i*-ésimo (volta ao início se faltar). **Não uso `natural_ranges()`**: ele muda uma variável global do módulo de amostragem e não é seguro com várias requisições em paralelo; o nível fácil sai por **margem em relação aos limiares**, calculada na camada nova.

| Nível | Visual | Baixa estatura | Membros em pé / prótese |
|---|---|---|---|
| **Fácil** | Resposta é uma classe ou "nenhuma"; acuidade ≥ 0,25 logMAR e campo ≥ 10 graus longe de **todos** os limiares | Resposta é uma classe ou "nenhuma"; as três medidas e a soma a ≥ 8% de cada limite | Um só membro afetado, ou os dois do mesmo nível; sem pé parcial; resposta é uma classe |
| **Médio** | Resposta é uma classe ou "nenhuma", mas algum valor está perto de um limiar | Idem, com alguma medida a menos de 8% de um limite | Padrões que pedem ler os dois lados (bilateral, níveis diferentes sem ser limítrofe) e "nenhuma classe" (sem amputação registrada) |
| **Difícil** | Faixa entre 1,40 e 1,50 (limítrofe) **ou** uma medida escondida de modo que todas as classes fiquem "dados insuficientes" | Um dos três campos escondido ("faltam dados") | Casos limítrofes ou de especialista (pé parcial, membro superior e inferior juntos em pé, acima e abaixo do joelho com prótese) **ou** um nível escondido ("faltam dados") |

Os limiares (0,25 logMAR, 10 graus, 8%) são **valores iniciais**; calibro na implementação com a distribuição real do banco e registro os valores finais em `education/scope.py`. Um perfil pertence a **um** nível. O **quiz "misto"** pede 40% fácil, 40% médio, 20% difícil (arredondamento por maior resto, determinístico).

**Campos escondidos (nível difícil).** A máscara é decidida por semente e índice; o gabarito é o **motor aplicado ao perfil já mascarado** (que devolve "dados insuficientes"). O rastro mostra o passo `não avaliado` e diz qual medida precisa ser feita.

## 4. API e web

### API (novo router `education`, modelos em `api/education_schemas.py`)

Os modelos ficam num arquivo próprio, e não em `api/schemas.py`, para não aumentar o ponto quente de conflito que o plano 15 aponta.

| Rota | Entrada | Saída |
|---|---|---|
| `GET /api/education/scope` | nenhuma | Aviso fixo, e os 4 grupos do escopo: id, nome, classes, aviso do grupo (por exemplo, o dos membros em pé), níveis, opções de resposta |
| `GET /api/education/case` | `group`, `difficulty`, `seed`, `index` | `CaseOut` (sem resposta) |
| `GET /api/education/quiz` | `seed`, `size` (5, 10 ou 15), `groups` (opcional), `difficulty` (`easy`, `medium`, `hard` ou `mixed`) | Lista de `CaseOut` e o aviso |
| `POST /api/education/answer` | `{case_id, choice}` com `choice` = id de uma opção ou `null` ("ver a resposta") | `AnswerOut`: `correct`, `answer` (id e rótulo), `class_name_pt`, `trace`, `limits`, `review_status`, `notice` |

**Recusa dos grupos fora do escopo.** `group` e `groups` são validados contra a lista dos quatro (`Literal`), e qualquer outro valor (inclusive `intellectual`, `neuro_*`, `frame_runner`, `wheelchair`) dá **422**; um `case_id` com grupo fora do escopo dá **404**. O OpenAPI só lista os quatro. **Testes:** um por grupo recusado em cada rota; um que confere que o conjunto permitido é exatamente os quatro; um que varre as respostas de `scope` e dos casos procurando os nomes dos grupos e das classes excluídas (20, 31 a 38, 51 a 57, 71 e 72); e um que procura esses ids no código fonte da web.

**Como o gabarito é protegido.** `case_id` tem a forma `k2.v1.<grupo>.<nível>.<semente>.<índice>`. Ele **não codifica a resposta**: é só a receita para o servidor **refazer o caso** (o gerador é determinístico). O servidor não guarda nada entre as chamadas. `GET case` e `GET quiz` nunca calculam nem enviam a resposta; ela só sai em `POST answer`. Testes: nenhuma chave de resposta (`answer`, `correct`, `trace`, `label`, `class_id`, `verdict`) nas respostas de `case` e `quiz`; o texto do caso não contém o número nem o nome da classe certa; a resposta de `case` é idêntica para o mesmo `case_id` em chamadas repetidas.

**Risco residual, aceito e dito aqui:** como é verificação no servidor sem estado, quem chamar `POST answer` uma vez para cada opção descobre a resposta. Isso não vaza nada que o modo de estudo proteja (não há nota, ranking nem avaliação oficial), mas significa que o quiz mede estudo, não prova. A pontuação é calculada no navegador.

### Web (rotas novas; a navegação entre elas fica simples, com links)

| Rota | O que mostra |
|---|---|
| `/educacao` | Aviso fixo, explicação curta, os quatro grupos (cartões com aviso próprio), escolha de nível, botões "Praticar" e "Fazer um quiz" |
| `/educacao/praticar?grupo=&nivel=&semente=&caso=` | Um caso por vez; "Próximo caso" soma 1 em `caso` (o link recarrega o mesmo caso) |
| `/educacao/quiz?semente=&tamanho=&grupos=&nivel=` | O quiz (ver 5) |

**Fluxo de um caso:** aviso fixo e selo "Rascunho" → caso (lista de definição) → opções (`fieldset` com `legend`, botões de rádio nativos) → "Responder" e "Ver a resposta" → região de resultado → rastro → "Próximo caso".

**Acessibilidade (WCAG 2.2 AA), desde o primeiro componente:**

- Foco visível, ordem do teclado igual à ordem visual, nenhuma armadilha de teclado; controles nativos.
- Rótulos programáticos em todos os controles; `legend` na pergunta; mensagem de erro textual ("Escolha uma opção") ligada ao grupo.
- **Anúncio do resultado:** a região de resultado é `role="status"` com `aria-live="polite"`; ao responder, o foco vai para o título do resultado (`tabIndex={-1}`), que diz "Você acertou" ou "Não foi dessa vez. A resposta era: …".
- Nada só por cor: acerto e erro têm ícone e texto; o estado do passo do rastro (`atende`, `não atende`, `não avaliado`) é texto.
- Contraste medido no navegador, como fiz no K11 (meta: mínimo 4,5:1 em texto normal e 3:1 em controles); alvos de toque de pelo menos 24 px; sem rolagem horizontal em 320 px; tabelas do rastro com `caption` e `th scope`.
- Sem limite de tempo, sem animação essencial, sem som.
- Não verificado com leitor de tela no K11; o K2 repete essa lacuna e a registra, a menos que a arquitetura queira um teste manual.

## 5. Quiz

- **Tamanho:** 5, 10 (padrão) ou 15 questões, de 1 a 4 grupos (padrão: os quatro) e um nível (`easy`, `medium`, `hard` ou `mixed`, padrão `mixed`).
- **Sorteio:** determinístico pela semente da URL (se não vier semente, o navegador sorteia uma e a põe na URL, para o quiz poder ser refeito ou compartilhado). Os grupos entram em rodízio, sem repetir `case_id`.
- **Pontuação:** **acertos** (1 por resposta certa; "Ver a resposta" e erro valem 0). A tela final mostra "acertos X de Y", por grupo e por nível, e a lista dos casos com o rastro de cada um. A palavra proibida para desempenho do usuário não é usada.
- **O que se guarda:** **nada persiste**. As respostas ficam no estado da página (memória), sem `localStorage`, `sessionStorage`, cookies, banco nem log de respostas no servidor. Fechar ou recarregar perde o andamento; só a semente na URL permite refazer. A API do quiz é sem estado.

## 6. O que o rastro não consegue dizer, e como a tela avisa

Cada resposta traz uma lista `limits` (texto nosso, em português), mostrada num bloco "O que este rastro não cobre" **antes** do botão "Próximo caso":

| Grupo | O que não cobre |
|---|---|
| Visual | O exame real tem mais do que dois números; o caso reduz a acuidade e o campo a valores prontos. O livreto escreve o limite da classe 11 como "menor que 2,60" e lemos como pior que 2,60 (o valor 2,60 cai na classe 12). A faixa entre 1,40 e 1,50 o livreto deixa sem classe |
| Baixa estatura | O caso dá os números prontos; a medição real segue protocolo próprio, que o rastro não ensina |
| Membros em pé | **Força, amplitude de movimento e a diferença de 7 cm entre as pernas (T44) não entram** (os casos são só por nível de amputação, e o motor cobre essas medidas só em parte). O pé parcial (Lisfranc) é lido como caso limítrofe sem confirmação. Força e amplitude dos membros superiores não estão implementadas |
| Prótese | Pé parcial junto com prótese e a combinação acima e abaixo do joelho vão para especialista; o rastro diz isso e não escolhe |
| Todos | Provas e equipamentos não aparecem e não estão validados; a leitura das regras é nossa e está por validar com a especialista |

Além do bloco, o aviso do grupo aparece **no cartão do grupo** e **acima do caso**, e o aviso fixo e a marca "Rascunho" estão em toda tela.

## 7. Texto

- Todas as explicações, razões e avisos são **nossos**, escritos em português, num único módulo reviável (`education/texts_pt.py`), com um identificador por modelo de frase. Nenhuma frase é copiada da cartilha do CPB nem da LEXI; nenhuma ilustração.
- O catálogo fornece **só** o número da classe, os códigos (T e F), o `name_pt` (que já é nosso, e só é mostrado depois da resposta) e o `source_page`, que aparece como "Cartilha do CPB (2024), p. N", **referência**, não citação.
- `review_status`: um arquivo `education/review_status.json` com listas de `case_id` e de modelos de texto `reviewed`, **vazio no início**. Tudo o que não está lá é `draft`. Só a especialista (via a sessão de arquitetura ou o usuário) pode mover algo para `reviewed`.
- **Banco revisável:** um comando `python -m para_triage.education.review_sheet --seed 0` gera um documento com 10 casos por grupo (semente 0), com resposta, rastro e limites, para a especialista rever em lote.
- A checagem de "texto copiado" é de **revisão humana na PR** (não há teste que a detecte); o módulo único de textos existe para tornar essa revisão curta.

## Estrutura de arquivos prevista (Passo 2)

```
src/para_triage/education/
  scope.py            grupos permitidos, aviso fixo, níveis e limiares
  presentation.py     perfil -> frase-resumo e fatos em português
  trace.py            critérios -> passos do rastro; tabela de amputação
  cases.py            banco por (grupo, semente), níveis, case_id, gabarito do motor
  texts_pt.py         todos os textos nossos
  review_status.json  vazio
  review_sheet.py     folha de revisão para a especialista
src/para_triage/api/education_schemas.py
src/para_triage/api/routers/education.py
web/src/app/educacao/{page.tsx, praticar/page.tsx, quiz/page.tsx}
web/src/components/education/…
web/src/lib/education-api.ts
tests/test_education_*.py
```

Nada em `rules/`, `data/`, `models/` ou `experiments/` muda. O código novo só **importa** `RuleEngine`, `load_catalog`, `sample_true_profiles`, `label_of` e `SAMPLERS`.

## Testes previstos (critérios de pronto do brief)

Determinismo (mesma semente, mesmos casos e mesmos `case_id`); consistência do rastro com a fração de descartes relatada (e o teste exaustivo da tabela de amputação); gabarito não vaza; aviso fixo e marca "Rascunho" procurados no texto das respostas e no código da web; nenhum grupo fora do escopo alcançável (API e web); nenhuma razão em inglês do motor na resposta; o termo "acurácia" não liga ao desempenho do usuário nos arquivos do K2 (use "acertos"); nenhum `localStorage`, `sessionStorage`, cookie ou `fetch` de escrita fora de `POST answer` no código do K2; os 219 testes atuais e o diff vazio nas pastas do núcleo.

## Decisões que preciso da arquitetura

1. **Quarta resposta "Faltam dados para decidir".** O brief fala em três (classe, nenhuma, especialista). Proponho a quarta no nível difícil porque o brief também pede "campos faltantes" e, sem ela, o gabarito de um caso com campo escondido não tem resposta honesta. Alternativa: tirar os campos escondidos e deixar o difícil só com limítrofes. **Recomendo a quarta opção.**
2. **Tabela de amputação duplicada na camada de leitura**, protegida pelo teste exaustivo das 144 combinações. Alternativa: mostrar para esses dois grupos só o padrão e a conclusão do motor, sem rastro por critério. **Recomendo a tabela com o teste exaustivo.**
3. **Nome da classe só depois de responder** (não nas opções). Alternativa: mostrar o nome nas opções do nível fácil.
4. **Não usar `natural_ranges()`** (estado global não seguro em paralelo) e fazer o nível fácil por margem. Pede só o seu OK.
5. **Modelos da API em `api/education_schemas.py`**, não em `api/schemas.py`.
6. **Risco residual de "chutar todas as opções"**, aceito por não haver nota nem ranking. Se o quiz um dia valer como avaliação, o desenho muda (token assinado, tentativa única no servidor).
7. **Limite de descartes de 1%** (esperado 0).
8. **Banco de 120 perfis por rótulo em membros em pé**, só para compensar o filtro de amputação; não exige mudança no gerador.

Se algum destes for "não", ajusto a nota antes de implementar.

## Como ficou a implementação

A nota foi seguida, com estes ajustes e acréscimos:

- **Teste de fixação (golden), pedido na revisão.** `tests/test_education_golden.py` compara com `tests/fixtures/education_golden.json` o hash dos 5 primeiros casos de cada grupo e nível (semente 0), o `CASE_VERSION` e o id das regras. Falha se o gerador, as regras, a receita dos casos ou os **textos** mudarem. Para atualizar quando for intencional: `python tests/fixtures/make_education_golden.py`, revisar o diff e pensar em subir `CASE_VERSION` em `education/scope.py`.
- **`GET /api/education/scope` traz `rules_version`** (id do livro de regras) e `case_version`.
- **Casos distintos nos grupos de amputação.** Os níveis de amputação são discretos, então o banco de `limb_standing` tem, para a semente 0, 8 casos fáceis, 4 médios e 38 difíceis distintos (e 4, 2 e 27 em `limb_prosthesis`). O banco é deduplicado; o quiz **nunca repete** um caso e, quando o nível pedido acaba num grupo, usa o próximo nível do mesmo grupo (o `case_id` e o selo de nível mostram o nível de fato). No modo praticar o índice volta ao início depois do último caso do nível.
- **Semente fixa 0 nos links de praticar**, o mesmo banco da folha de revisão (gerada por `python -m para_triage.education.review_sheet`; a folha não está neste repositório). O quiz sorteia uma semente nova a cada começo e a põe no endereço.
- **`size` do quiz** é validado à mão (5, 10 ou 15; outro valor dá 422), porque o validador de `Literal[int]` não aceita o número vindo na query string.
- **Descartes:** 0 em todas as sementes e grupos testados (0, 1, 2 no teste do banco). O teste de consistência falha se passar de 1%.
- **"Responder" sem opção** mostra o erro e não revela nada (um bug assim foi achado e corrigido no teste manual no navegador).
- **Textos:** todos em `src/para_triage/education/texts_pt.py`; a lista completa vai na folha de revisão, no fim.
- **Acessibilidade medida no navegador:** contraste mínimo 6,3:1, sem rolagem horizontal em 320 px, foco movido para o título do resultado, anúncio por `role="status"`. **Não verificado:** leitor de tela e tema escuro.
