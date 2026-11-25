# Livro de regras (adoção, etapas 0 a 2): nota de desenho

**Estado:** nota aprovada e implementada (etapas 0 a 2). A seção "Como ficou a implementação", no fim, lista o que mudou em relação à nota e os números.

**O que é:** um **motor novo, ao lado do atual**, que lê as regras de arquivos YAML (o livro de regras) e devolve o **veredito por classe com os sete estados** e o **rastro por critério**, para os grupos **visual** (11 a 13) e **baixa estatura** (40 e 41). O `RuleEngine` atual **continua sendo o padrão**: a API, o módulo de educação, o guia e a triagem **não mudam**. A troca só vem quando todos os grupos tiverem paridade, em etapa futura.

**Partida:** o protótipo `option_b` do experimento do livro de regras (não incluído neste repositório) (139 linhas de interpretador, 0 divergências em 4.357 perfis do grupo visual). Nada de `spikes/` é importado: o interpretador é **copiado e reescrito** no pacote. `option_a` (OpenFisca) não entra.

## O que verifiquei antes de escrever

- O protótipo B já cobre o visual inteiro com três construções: critério sobre uma medida, flag e lista de regras de decisão. **A baixa estatura pede três coisas novas**: (1) **parâmetros por sexo**; (2) uma **medida derivada** (a soma de estatura e braço); (3) uma **regra de classe** que combina critérios com "todos" (os três limites ao mesmo tempo), e não só "algum" (o visual).
- No motor atual, "a classe mais comprometida que o caso atende" é, nos **dois** grupos, **a de menor número entre as que têm evidência** (visual: `min(hits)`; baixa estatura: itera em ordem crescente e para na primeira). Então um único `pick: most_impaired` serve aos dois.
- Os números dos dois grupos **já existem** em `rules/classes.yaml` (`criteria`). O livro de regras vai repeti-los durante a convivência dos motores; a defesa é um teste que compara os dois (ver 6).
- O rastro do módulo de educação (`education/trace.py`) para esses grupos tem passos por classe e critério com valor e resultado; o do novo interpretador precisa ser **equivalente em conteúdo**, e há uma diferença a tratar: o módulo de educação mostra o limite do campo da classe 13 mesmo quando o da 12 já decidiu (a cadeia "senão" do motor); o interpretador novo vai **manter o resultado bruto** e marcar `superseded_by`, para os dois coincidirem (ver 4).

## 1. Estrutura de pastas

```
src/para_triage/rulebook/
  __init__.py
  interpreter.py        o interpretador (carregar, avaliar, veredito, rastro)  <- as linhas que contam para a regra de parada
  messages.py           texto por código de razão e idioma
  compare.py            regressão lado a lado e diff entre variantes (ferramenta, fora da contagem)
  __main__.py           comandos: test, regress, diff
  data/
    sources.yaml        documentos citáveis
    variants/cpb-2024.yaml
    groups/visual.yaml
    groups/short_stature.yaml
    messages/pt.yaml
    messages/en.yaml
tests/test_rulebook_*.py
```

Os dados ficam **dentro do pacote** (`rulebook/data/`) para viajarem com ele. Isso pede **uma linha** em `[tool.setuptools.package-data]` do `pyproject.toml` (`rulebook = ["data/**/*.yaml"]`): não é dependência nem licença (dúvida 1).

**Regra de parada, medida por teste:** um teste conta as linhas de código (sem brancos nem comentários) de `interpreter.py` e `messages.py` e **falha acima de 500**. Estimativa: **cerca de 300** (carga e parâmetros 90, avaliação de critérios e regras de classe 110, decisão e vereditos 80, rastro e mensagens 50).

## 2. Formato do YAML

### 2.1 `sources.yaml`

```yaml
sources:
  cpb-booklet-2024:
    title: "CPB, Perfil de Classes do Atletismo"
    publisher: CPB
    version: "2024"
    date: 2024-01-01
    pages: {visual: 14, short_stature: [24, 25]}      # só referência de onde ler; o texto não é copiado
```

### 2.2 Critério, parâmetro, regra de classe e decisão (grupo visual, trecho)

```yaml
rulebook: visual
schema: 1
applies_to: [visual]
classes: [11, 12, 13]
measures: [logmar_best_eye, visual_field_deg]

parameters:
  logmar_min_12:
    unit: logMAR
    values: [{from: 2024-01-01, to: null, value: 1.50}]
    source: {doc: cpb-booklet-2024, page: 14}
    status: implemented              # implemented | provisional | contested | reviewed
  boundary_in_class_11:              # uma leitura nossa, não um número do livreto
    values: [{from: 2024-01-01, value: false}]
    source: {doc: cpb-booklet-2024, page: 14, note: "leitura nossa de \"menor que\""}
    status: provisional

criteria:
  acuity_12:
    measure: logmar_best_eye
    test: {op: between, low: logmar_min_12, high: logmar_max_12, high_inclusive: {not: boundary_in_class_11}}
    reason: ACUITY_IN_CLASS_RANGE
    source: {doc: cpb-booklet-2024, page: 14}
    status: implemented
    valid: {from: 2024-01-01, to: null}
  field_13:
    measure: visual_field_deg
    test: {op: lt, value: field_lt_13}
    unless: field_12                 # a cadeia "senão" do campo: o resultado bruto fica no rastro
    reason: FIELD_IN_CLASS_RANGE
    ...
class_rules:                         # quais critérios dão evidência a cada classe
  11: {any_of: [acuity_11]}
  12: {any_of: [acuity_12, field_12]}
  13: {any_of: [acuity_13, field_13]}
flags:
  acuity_gap: {measure: logmar_best_eye, test: {op: between, low: logmar_max_13, high: logmar_min_12, low_inclusive: false, high_inclusive: false}, reason: ACUITY_IN_BOOKLET_GAP}
decision:                            # a primeira regra cujo `when` vale
  - {id: no_measure, when: {all_missing: [logmar_best_eye, visual_field_deg]}, result: {all: insufficient_data}, reason: NO_VISUAL_MEASURE}
  - id: some_class_met
    when: {any_class: true}
    result:
      meets: {pick: most_impaired}
      borderline: [{class: 12, if: {flag: acuity_gap, primary_above: 12}, reason: ACUITY_IN_BOOKLET_GAP}]
      rest: not_met
  - {id: gap, when: {flag: acuity_gap}, result: {borderline: [12, 13], rest: not_met}, reason: ACUITY_IN_BOOKLET_GAP}
  - {id: one_missing, when: {any_missing: [logmar_best_eye, visual_field_deg]}, result: {all: insufficient_data}, reason: MEASURE_MISSING}
  - {id: default, result: {all: not_met}, reason: ABOVE_ELIGIBILITY_LIMITS}
tests: [...]                         # testes como dados (2.4)
```

**Mudança em relação ao protótipo:** o critério deixa de ter `class:`; quem diz a que classe ele dá evidência é a **`class_rules`** (`any_of` ou `all_of`). Isso é o que permite à baixa estatura exigir os três limites juntos sem outro mecanismo.

### 2.3 Baixa estatura (trecho): parâmetros por sexo, medida derivada, `all_of`

```yaml
rulebook: short_stature
schema: 1
applies_to: [short_stature]
classes: [40, 41]
measures: [sex, height_cm, longest_arm_cm]       # nessa ordem: é a ordem de `missing` do motor atual
derived:
  total_cm: {sum: [height_cm, longest_arm_cm]}   # ausente se qualquer parcela estiver ausente

parameters:
  max_height_class_40:
    by: {measure: sex, map: {M: male, F: female}}  # escolhe o valor pelo sexo do perfil
    unit: cm
    values:
      male:   [{from: 2024-01-01, value: 130}]
      female: [{from: 2024-01-01, value: 125}]
    source: {doc: cpb-booklet-2024, page: 24}
    status: implemented
  # max_arm_class_40, max_sum_class_40, max_*_class_41: do mesmo modo

criteria:
  height_40: {measure: height_cm, test: {op: lt, value: max_height_class_40, inclusive: true}, reason: SS_WITHIN_LIMIT, source: {doc: cpb-booklet-2024, page: 24}, status: implemented}
  arm_40:    {measure: longest_arm_cm, test: {op: lt, value: max_arm_class_40, inclusive: true}, reason: SS_WITHIN_LIMIT, ...}
  sum_40:    {measure: total_cm, test: {op: lt, value: max_sum_class_40, inclusive: true}, reason: SS_WITHIN_LIMIT, ...}
  # height_41, arm_41, sum_41
class_rules:
  40: {all_of: [height_40, arm_40, sum_40]}      # os três limites ao mesmo tempo
  41: {all_of: [height_41, arm_41, sum_41]}
decision:
  - {id: measure_missing, when: {any_missing: [sex, height_cm, longest_arm_cm]}, result: {all: insufficient_data}, reason: SS_MEASURE_MISSING}
  - {id: some_class_met, when: {any_class: true}, result: {meets: {pick: most_impaired}, rest: not_met}}
  - {id: default, result: {all: not_met}, reason: SS_LIMITS_EXCEEDED}
```

### 2.4 Variantes, vigência e testes como dados

```yaml
# variants/cpb-2024.yaml
variant: cpb-2024
description: "Leitura nossa do livreto do CPB (2024), a padrão"
reference_date: 2024-10-01       # a data em que se escolhe o valor em vigor
overrides: {}                    # parâmetro -> valor; outra variante troca só o que muda
```

```yaml
# dentro de um grupo
tests:
  - name: exatamente no limite da classe 11 (nossa leitura)
    input: {logmar_best_eye: 2.6, visual_field_deg: 120}
    expect: {11: not_met, 12: meets, 13: not_met}
    criterion: acuity_11
    source: {doc: cpb-booklet-2024, page: 14}
```

## 3. Como cada estado do veredito é produzido

| Estado | Como sai |
|---|---|
| `meets` | `result.meets` (`pick: most_impaired`: a menor classe com evidência) |
| `borderline` | `result.borderline` (lista de classes, com condição opcional): a faixa de 1,40 a 1,50 do visual |
| `insufficient_data` | Regra de decisão com `all_missing` ou `any_missing`; o veredito leva a lista de campos em `missing` |
| `not_met` | `rest` ou regra padrão |
| `not_applicable` | `applies_to` do grupo: se o perfil não declara nenhuma das deficiências, todas as classes saem `not_applicable` antes de qualquer critério |
| `needs_review`, `not_implemented` | O vocabulário das duas é aceito em `result` (`{all: needs_review}`, `{class: 20, status: needs_review}`). **Nenhum dos dois grupos desta fase os usa**, então serão **exercitados por testes do interpretador com livros de regras mínimos escritos no próprio teste**, para não repetir a lacuna do experimento |

Todo veredito tem `class_id`, `status`, `reasons` (códigos) e `missing` (campos), como o `Verdict` atual, mais o **rastro** (seção 4).

## 4. Rastro e mensagens

Cada avaliação devolve `trace`: uma lista de passos `{criterion, class_id, measure, value, test, result, reason, source}`, mais, quando houver, `superseded_by` e os valores resolvidos dos parâmetros (`reference`). `result` é `met`, `not_met`, `not_assessed` (medida faltando), `skipped` (fora da vigência) ou, para uma regra de classe, o resultado de `any_of` ou `all_of`. O **último passo** é a regra de decisão que valeu.

`messages.py` devolve o texto de um código em um idioma: `messages/pt.yaml` e `en.yaml` mapeiam `ACUITY_IN_CLASS_RANGE` para um modelo com `{value}`, `{limit}`, `{measure}`. **Espanhol fica para depois.** Falta de tradução em um idioma cai para o inglês, e um teste falha se um código usado nos grupos não existir em `pt` e `en`.

## 5. Como a regressão lado a lado é executada

`python -m para_triage.rulebook regress [--group visual|short_stature|all]` (e o mesmo dentro do `pytest`):

1. **Perfis:** a **amostra do módulo de educação** do grupo (`sample_true_profiles`, 200 perfis por semente, sementes 0 a 4), cada um completo e com **cada medida escondida** (e com todas); uma **varredura em volta de cada limiar**, **gerada a partir dos parâmetros do próprio YAML** (limite −0,01, igual, +0,01, +0,05; para a baixa estatura, por sexo, nas três medidas e na soma; a faixa de 1,40 a 1,50 inteira); e perfis de **outras deficiências** (`not_applicable`).
2. **Referência:** `RuleEngine.evaluate` sobre o mesmo `Profile`.
3. **Novo:** o interpretador, com um adaptador `Profile -> medidas` (`sex` vira "M" ou "F"; campos ausentes ficam ausentes).
4. **Igualdade:** `status` e `missing` por classe. **Meta: 0 divergências.** Divergências saem com o perfil, a classe e os dois vereditos; o comando termina com código 1.
5. **Paridade dos números:** um teste compara os parâmetros do YAML com os `criteria` de `rules/classes.yaml`, para as duas cópias não se separarem.

## 6. Variantes e vigência

- **Variante:** `load(group, variant="cpb-2024")` ou um arquivo `.yaml`; `overrides` troca valores de parâmetros por nome (por exemplo, `boundary_in_class_11: true`). Linha de comando: `--set nome=valor`.
- **Vigência:** cada valor de parâmetro tem `from` e `to` (`to: null` = em aberto). `evaluate(..., on=<data>)` escolhe o valor em vigor nessa data; sem `on`, vale o `reference_date` da variante (**nunca "hoje"**, para o resultado não depender do relógio). Um critério com `valid` fora da data de referência sai `skipped` no rastro. Data sem nenhum valor em vigor é **erro explícito** (`NoValueInForce`), não um valor qualquer.
- **Diff entre variantes (R-6):** `python -m para_triage.rulebook diff --group visual --a cpb-2024 --b cpb-2024 --set boundary_in_class_11=true` roda as duas sobre a amostra e imprime, de forma legível: quantos perfis mudam, **a tabela de transições** (classe, status antes e depois, quantidade) e **três exemplos** com o valor da medida. É a função `diff_variants(group, a, b, cases)` do `compare.py`; o protótipo já fez isso (234 e 29 perfis).

## 6.1 Reconstituição do rastro do módulo de educação e do guia (só um teste)

`tests/test_rulebook_trace_equivalence.py`: para os grupos visual e baixa estatura, sobre perfis da amostra do módulo de educação, compara o rastro do novo interpretador com `education/trace.py`: **mesmo critério** (por classe e medida), **mesmo valor** (o número extraído do texto do módulo de educação e o valor bruto do novo) e **mesmo resultado** (`met` e `not_met`). **Não troca** o módulo de educação nem o guia de rastro.

## 7. Plano de testes

| # | Teste | Etapa |
|---|---|---|
| 1 | Interpretador com **livros de regras mínimos no próprio teste**: cada um dos sete estados, `any_of` e `all_of`, `unless`, medida derivada, parâmetro por sexo, `pick: most_impaired` | 0 |
| 2 | **Vigência**: valor por data, `to` aberto, fronteira de `from` e `to`, data sem valor (`NoValueInForce`), critério fora da vigência (`skipped`) | 0 |
| 3 | **Variantes**: `overrides` por nome, `--set`, variante inexistente e parâmetro inexistente dão erro claro | 0 |
| 4 | **Mensagens**: todo código usado nos YAML existe em `pt` e `en`; fallback para `en` | 0 |
| 5 | **Testes como dados** dos YAML (os blocos `tests`) rodam e passam; cada um cita fonte | 0, 1, 2 |
| 6 | **Regressão visual**: 0 divergências (amostra do módulo de educação × 5 sementes × cada máscara, varredura, outras deficiências) | 1 |
| 7 | **Regressão baixa estatura**: 0 divergências (por sexo; soma; ordem; sexo ou medida faltando; limites exatos) | 2 |
| 8 | **Paridade dos números** com `classes.yaml` | 1, 2 |
| 9 | **Equivalência do rastro** com o módulo de educação (6.1) | 1, 2 |
| 10 | **Diff entre variantes** reproduz os números do protótipo (234 e 29 perfis) | 1 |
| 11 | **Regra de parada**: `interpreter.py` e `messages.py` com no máximo 500 linhas de código | 0 |
| 12 | **O motor atual não mudou**: os testes atuais passam, `RuleEngine` continua sendo o padrão e nenhuma rota importa o pacote novo | todas |

## 8. O que não será feito

- Trocar o `RuleEngine`, a API, o módulo de educação, o guia, o guarda do relatório ou a triagem para o motor novo.
- Os grupos de amputação, a classe 20 e os provisórios (etapas 3 a 5, em outra rodada).
- Uma **linguagem de expressões geral**: se uma regra de um desses grupos pedir uma, **paro e aviso**, como a regra de parada manda.
- Espanhol, interface de variantes na web e remoção de `criteria` de `classes.yaml` (só quando houver a troca).
- Dependência nova: o interpretador usa só PyYAML, que já existe.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| **A linguagem crescer** (cada grupo pede um operador) | O teste de 500 linhas; a baixa estatura é justamente o teste de crescimento: se ela pedir mais do que `by`, `derived` e `all_of`, **paro e aviso** |
| **Duas cópias dos números** (YAML do livro e `classes.yaml`) divergirem | Teste de paridade (8); a cópia antiga sai na troca |
| **Interpretador com nome de grupo escondido** (o protótipo cometeu um erro assim com o nome de um flag) | Nada de nomes de grupo no `interpreter.py`; um teste roda o interpretador com livros mínimos de nomes inventados |
| **Rastro diferente do módulo de educação em detalhe** (a cadeia "senão") | `superseded_by` e o teste 9 |
| **Data de referência fixa** esconder uma mudança de vigência | `reference_date` explícita na variante; o diff entre datas mostra o efeito |
| **Adaptador de `Profile` frágil** (nome de campo, enum) | Testado nas duas pontas pela regressão; os nomes das medidas são os do `Profile` |
| **Regressão fraca** | Varredura gerada dos próprios parâmetros, máscara em cada medida e perfis de outras deficiências |

## 10. Dúvidas para a arquitetura

1. **`pyproject.toml`**: uma linha em `package-data` para os YAML irem no pacote. Aceita? (Alternativa: ler os YAML por caminho relativo ao arquivo, que só funciona em instalação editável.)
2. **`rules_version()` (o id das regras)** inclui os arquivos do `rulebook/`? Recomendo **não ainda**: o motor padrão continua sendo o antigo, e incluir agora faria o JSON de transparência, o guia e o golden do módulo de educação mudarem a cada ajuste do livro de regras. Entra na troca.
3. **Data de referência** da variante `cpb-2024`: propõe-se **2024-10-01** (dentro da vigência de todos os valores). Aceita?
4. **Local dos dados**: `rulebook/data/` (proposto) ou `rulebook_data/` ao lado, como o brief permite.
5. **`status` e revisor**: o formato exige `source` e `status` em todo critério e parâmetro; `reviewer` e `reviewed_on` só quando `status: reviewed`. Aceita?
6. **Trace**: `superseded_by` para a cadeia "senão", em vez de `skipped` como no protótipo. Aceita?
7. **Comandos** `python -m para_triage.rulebook test|regress|diff`: aceita como interface, em vez de scripts à parte?
8. **Códigos de razão** com prefixo do grupo só quando o texto muda (`SS_*` para a baixa estatura): aceita?
9. A regressão do `pytest` fica com **cerca de 4 mil perfis por grupo** (estimativa; o protótipo avaliou 4.357 em menos de um segundo, sem contar o motor atual). Se quiser uma amostra maior, vira um comando à parte, fora do CI.

## Como ficou a implementação

**Números** (de `python -m para_triage.rulebook regress`, amostra do módulo de educação de 5 sementes mais a varredura):

| | Visual | Baixa estatura |
|---|---|---|
| Perfis comparados com o `RuleEngine.evaluate` (comando padrão, 5 sementes) | 4.344 | 7.539 |
| **Divergências** (status e campos faltantes, por classe) | **0** | **0** |
| Linhas de código do interpretador (`interpreter.py` + `messages.py`, sem brancos nem comentários) | **258** (237 + 21), contra o limite de 500 | |
| Ferramentas (`compare.py` 153 e `__main__.py` 51), fora da contagem | 204 | |
| YAML do grupo (inclui 12 e 8 testes como dados) | 142 linhas | 123 linhas |

**Construções do formato** (o vocabulário está fechado por um teste: `test_the_format_vocabulary_is_closed_so_the_language_cannot_grow_by_accident`). São **18**:

1. parâmetro com valores por data (`from`, `to`), fonte e status;
2. parâmetro escolhido por uma chave (`by`: o sexo);
3. medida derivada (`derived`: soma);
4. teste de critério (`gt`, `lt`, `between`, com flags de inclusão);
5. flag de inclusão dado por um parâmetro;
6. **negação de um parâmetro** (`{not: ...}`), usada em **um único lugar** (a extremidade superior da classe 12, que depende da leitura do limite da 11); um teste confere que são exatamente uma;
7. critério condicionado a outro (`unless`, a cadeia "senão" do campo);
8. vigência do critério (`valid`);
9. flags (testes que não dão evidência a classe);
10. regra de classe `any_of`;
11. regra de classe `all_of`;
12. regra de decisão com `when` (`all_missing`, `any_missing`, `any_class`, `flag`);
13. resultado `all`;
14. resultado `classes` (um status por classe: `needs_review`, `not_implemented`);
15. resultado `meets` com `pick: most_impaired`;
16. resultado `borderline`, com condição (`flag` e `primary_above`);
17. resultado `rest`;
18. variante (`overrides` e `reference_date`) e testes como dados.

Em relação ao protótipo do experimento, as **novas** são 2 (parâmetro por chave), 3 (soma), 8, 9 com fonte e status, 11, 14 e a validação de fonte, status e revisor. A baixa estatura precisou **só de** `by`, `derived` e `all_of`, como a nota previa: **a regra de parada não foi acionada**, e nenhuma expressão geral foi necessária.

**Ajustes em relação à nota:**

- `package-data` no `pyproject.toml`: uma linha, `"para_triage.rulebook" = ["data/**/*.yaml"]` (a chave do setuptools é o nome do pacote).
- Como a nota previa, o `rules_version()` **não** inclui o `rulebook/` (entra na troca) e a data de referência é 2024-10-01. Um teste confere que o valor começa **exatamente** em 2024-01-01 (31/12/2023 dá `NoValueInForce`).
- O rastro mantém o resultado bruto e marca `superseded_by` (a cadeia "senão" do campo), o que torna o rastro **idêntico em conteúdo** ao do módulo de educação (teste de equivalência).
- **Soma em ponto flutuante** (acréscimo da revisão): a soma usa a mesma adição do Python que o motor atual, e a regressão cobre os limites exatos de cada sexo (cada limite, menos e mais 0,01, e somas que caem no limite), pares em décimos (de 90,0 a 139,9) e 60 pares por limite em passos de 0,1: **0 divergências**.
- O **teste de isolamento** (acréscimo da revisão) é automático: nenhum módulo do pacote fora de `rulebook/` o importa, nenhuma rota nem o OpenAPI o mencionam, e o web não o referencia.
- Comando maior, fora do CI: `python -m para_triage.rulebook regress --seeds 20 --per-label 400`.

---

# Adendo: etapa 3, os grupos de amputação (nota de desenho)

**Estado:** proposta para revisão (só documento). Nada disto está implementado. **Veredito sobre a regra de parada: não acionada no desenho.** A via de força, amplitude e diferença de perna do `limb_standing` **cabe no formato sem uma linguagem de expressões geral**, com 7 construções novas pequenas (seção A4) e uma estimativa de **cerca de 350 linhas** de interpretador (limite 500). A estimativa tem incerteza: a da etapa 0 a 2 foi de 300 e deu 258, mas o `limb_standing` é o primeiro grupo com **dois caminhos que se fundem**, e a fusão é a parte nova mais arriscada.

**Correção ao relatório da etapa 0 a 2:** o comando padrão da baixa estatura compara **7.539** perfis, não 15.495 como constava. O número velho era de antes de reduzirmos os pares de soma da varredura (de cerca de 10 mil para 2.283 casos). As 0 divergências valem nos dois tamanhos. A seção `Como ficou` desta nota foi corrigida.

## A1. O que verifiquei no motor atual (sem alterar nada)

Li `rules/evaluators/limb.py` de novo e **sondei o motor** com perfis de cada ramo para ter certeza do comportamento, em especial dos campos faltantes. Os fatos que o desenho precisa respeitar:

| Fato | Onde importa |
|---|---|
| `limb_prosthesis`: com a posição ausente, tudo é `insufficient_data` com `missing = (posture,)` **só**; com outra posição, tudo é `not_met` com `missing = ()` **mesmo se faltarem níveis**; só depois vêm os níveis ausentes (`insufficient_data`, `missing` = os níveis que faltam), o braço amputado (`needs_review`), a falta de amputação na perna (`not_met`) e a tabela | A **ordem** das regras de decisão e **o que cada regra reporta em `missing`** |
| A tabela de níveis usa o **par ordenado** (maior, menor) por conjunto de membros. Prótese: (3,3)→61, (2,2)→62, (3,0)→63, (2,0)→64, (3,2)→`borderline` 61 e 62, qualquer outro→`needs_review` | A tabela vira linhas de dados |
| `limb_standing` tem **duas vias** (amputação por nível; força, amplitude e diferença de perna), escolhidas pelas **deficiências declaradas** (`limb_deficiency`; `muscle_power`, `rom` ou `leg_length_difference`), **depois de** uma porta comum de posição | Pede o conceito de **via** e uma **fusão** |
| As duas vias se fundem classe a classe pela **melhor situação** (ordem: `meets`, `borderline`, `needs_review`, `insufficient_data`, `not_met`); empate: as razões se somam e vale o `missing` da primeira | A fusão é uma regra fixa, pequena |
| Via funcional: três medidas do tornozelo e da perna (força ≤ 2; arco ≤ 10 graus; diferença de comprimento ≥ 7 cm) dão a classe 44 (`ankle_cmes`); com **dois** lados afetados, tudo `needs_review`; com **um**, 44 `meets`; sem o número de lados (ausente ou fora de 1 e 2), 44 `borderline` com `missing = (lower_limb_sides_affected,)`; o déficit de quadril ou joelho põe a 42 em `borderline`, com ou sem critério atendido | Seis ramos, todos **decididos por comparações simples** |
| Na via funcional, o `missing` do veredito é **escolhido ramo a ramo** (vazio quando a classe é decidida; só os lados no ramo dos lados ausentes; as medidas do tornozelo que faltam nos ramos `insufficient_data` e `not_met`) | O formato precisa **dizer o que cada regra reporta** |

Um achado que **muda** uma regra do formato: na etapa 0 a 2, o `missing` de um veredito era "todas as medidas ausentes do grupo". No `limb_*` isso **não vale**. A regra nova (construção 5, seção A4) é compatível com a antiga: omitido, vale o comportamento de hoje.

## A2. A tabela de níveis como dado: `limb_prosthesis`

**Ideia:** cada linha da tabela vira **uma regra de decisão** com `when: {equals: {...}}`. A tabela inteira é dado, lida de cima para baixo, e as linhas **ganham o `id` da linha do módulo de educação** (`education/trace.py`), o que permite o teste de equivalência do rastro. Não há construção de "tabela" separada.

```yaml
rulebook: limb_prosthesis
schema: 1
applies_to: [limb_deficiency]
classes: [61, 62, 63, 64]
measures: [posture, lower_left, lower_right, upper_left, upper_right]   # a ordem do `missing` do motor atual
domains:                                   # só para as ferramentas (regressão exaustiva); o interpretador ignora
  posture: [standing, prosthesis, seated, frame_runner]
  lower_left: [0, 1, 2, 3]   # (e lower_right; upper_left e upper_right: [0, 1, 2])

derived:                                   # o par ordenado (maior, menor) como medidas numéricas
  lower_hi: {max: [lower_left, lower_right]}
  lower_lo: {min: [lower_left, lower_right]}
  upper_hi: {max: [upper_left, upper_right]}

parameters:
  required_posture: {values: [{from: 2024-01-01, to: null, value: prosthesis}], source: {doc: cpb-booklet-2024, page: 35}, status: implemented}

flags:
  wrong_posture:     {measure: posture, test: {op: ne, value: required_posture}}
  upper_amputation:  {measure: upper_hi, test: {op: gt, value: 0}}
  no_lower:          {measure: lower_hi, test: {op: lt, value: 1}}

decision:                                  # a ordem é a do motor atual
  - {id: posture_missing, when: {any_missing: [posture]}, result: {all: insufficient_data}, report_missing: [posture], reason: LIMB_POSTURE_MISSING}
  - {id: wrong_posture, when: {flag: wrong_posture}, result: {all: not_met}, report_missing: [], reason: LIMB_WRONG_POSTURE}
  - {id: levels_missing, when: {any_missing: [lower_left, lower_right, upper_left, upper_right]}, result: {all: insufficient_data}, report_missing: [lower_left, lower_right, upper_left, upper_right], reason: LIMB_LEVELS_MISSING}
  - {id: upper_with_prosthesis, when: {flag: upper_amputation}, result: {all: needs_review}, reason: LIMB_UPPER_WITH_PROSTHESIS}
  - {id: no_lower, when: {flag: no_lower}, result: {all: not_met}, reason: LIMB_NO_LOWER_AMPUTATION}
  # a tabela de níveis: uma linha por regra (os ids são os do módulo de educação)
  - {id: bilateral_above, when: {equals: {lower_hi: 3, lower_lo: 3}}, result: {classes: {61: meets}, rest: not_met}, reason: LIMB_BILATERAL_ABOVE}
  - {id: bilateral_below, when: {equals: {lower_hi: 2, lower_lo: 2}}, result: {classes: {62: meets}, rest: not_met}, reason: LIMB_BILATERAL_BELOW}
  - {id: unilateral_above, when: {equals: {lower_hi: 3, lower_lo: 0}}, result: {classes: {63: meets}, rest: not_met}, reason: LIMB_UNILATERAL_ABOVE}
  - {id: unilateral_below, when: {equals: {lower_hi: 2, lower_lo: 0}}, result: {classes: {64: meets}, rest: not_met}, reason: LIMB_UNILATERAL_BELOW}
  - {id: above_plus_below, when: {equals: {lower_hi: 3, lower_lo: 2}}, result: {classes: {61: borderline, 62: borderline}, rest: not_met}, reason: LIMB_ABOVE_PLUS_BELOW}
  - {id: foot_involved, result: {all: needs_review}, reason: LIMB_FOOT_INVOLVED_WITH_PROSTHESIS}   # o resto (parte do pé)
```

(Os códigos de razão acima são os nomes propostos; a fonte e o status entram em cada linha na implementação, como já é a regra para critérios.)

**Como cada estado sai:** `insufficient_data` (posição ausente; níveis ausentes), `not_met` (outra posição; sem amputação na perna), `needs_review` (braço amputado; parte do pé), `meets` e `borderline` (as linhas da tabela), `not_applicable` (`applies_to`). **Só o `not_implemented` continua sem uso real.**

## A3. `limb_standing`: duas vias

**Estrutura do arquivo:** porta comum (`gate`), duas **vias** (`pathways`), cada uma com **suas** medidas derivadas, flags e regras de decisão e uma condição de uso (`applies_to`: as deficiências declaradas), e a **fusão** classe a classe pela melhor situação. Os parâmetros ficam compartilhados no topo.

```yaml
rulebook: limb_standing
applies_to: [limb_deficiency, muscle_power, rom, leg_length_difference]
classes: [42, 43, 44, 45, 46, 47]
measures: [posture, lower_left, lower_right, upper_left, upper_right, ankle_pf_mrc, ankle_rom_deg, leg_length_diff_cm, hip_knee_deficit, lower_limb_sides_affected]
parameters:                                  # os três limites da via funcional ficam aqui (não estão no catálogo)
  required_posture: ...                      # standing
  max_plantar_flexion_mrc: {values: [{from: 2024-01-01, to: null, value: 2}], ...}
  max_ankle_arc_deg:       {values: [{..., value: 10}], ...}
  min_leg_length_diff_cm:  {values: [{..., value: 7}], source: {doc: cpb-booklet-2024, note: "o limite de 7 cm vem da F57; a validar para a T44"}, status: provisional}

gate:                                        # termina a avaliação se alguma regra valer
  - {id: posture_missing, when: {any_missing: [posture]}, result: {all: insufficient_data}, report_missing: [posture], reason: LIMB_POSTURE_MISSING}
  - {id: wrong_posture, when: {flag: wrong_posture}, result: {all: not_met}, report_missing: [], reason: LIMB_WRONG_POSTURE}

pathways:
  amputation:                                # só se `limb_deficiency` for declarada
    applies_to: [limb_deficiency]
    measures: [lower_left, lower_right, upper_left, upper_right]
    derived: {lower_hi: ..., lower_lo: ..., upper_hi: ..., upper_lo: ...}
    flags: {lower_any: ..., upper_any: ...}
    decision:
      - {id: levels_missing, ...}
      - {id: lower_and_upper, when: {flags: [lower_any, upper_any]}, result: {all: needs_review}, reason: LIMB_LOWER_AND_UPPER}
      # inferior (hi, lo): as linhas do `_lower_standing`
      - {id: unilateral_above, when: {equals: {lower_hi: 3, lower_lo: 0}}, result: {classes: {42: meets}, rest: not_met}, ...}
      - {id: unilateral_above_plus_foot, when: {equals: {lower_hi: 3, lower_lo: 1}}, result: {classes: {42: borderline}, rest: not_met}, ...}
      - {id: bilateral_with_above, when: {equals: {lower_hi: 3}}, result: {all: needs_review}, ...}      # (3,2) e (3,3)
      - {id: bilateral_below, ...(2,2)->43}, {id: unilateral_below, ...(2,0)->44}
      - {id: below_plus_foot, when: {equals: {lower_hi: 2, lower_lo: 1}}, result: {classes: {43: borderline, 44: borderline}, rest: not_met}, ...}
      - {id: unilateral_foot, ...(1,0)->44 borderline}, {id: bilateral_foot, when: {flag: lower_any}, result: {all: needs_review}, ...}   # o resto: (1,1)
      # superior (hi, lo): as linhas do `_upper_standing`
      - {id: bilateral_elbow, ...(2,2)->45}, {id: unilateral_elbow, ...(2,0)->46}, {id: bilateral_wrist, ...(1,1)->46}
      - {id: elbow_plus_wrist, ...(2,1)->45 e 46 borderline}, {id: unilateral_wrist, when: {flag: upper_any}, result: {classes: {47: meets}, rest: not_met}, ...}
      - {id: no_amputation, result: {all: not_met}, reason: LIMB_NO_AMPUTATION_RECORDED}
  strength_rom:                              # só se `muscle_power`, `rom` ou `leg_length_difference` for declarada
    applies_to: [muscle_power, rom, leg_length_difference]
    flags:
      sides_two:  {measure: lower_limb_sides_affected, test: {op: eq, value: 2}}
      sides_one:  {measure: lower_limb_sides_affected, test: {op: eq, value: 1}}
      hip_knee:   {measure: hip_knee_deficit, test: {op: eq, value: true}}
    criteria:                                # os três critérios de elegibilidade do tornozelo e da perna
      pf_strength: {measure: ankle_pf_mrc, test: {op: lt, value: max_plantar_flexion_mrc, inclusive: true}, ...}
      ankle_arc:   {measure: ankle_rom_deg, test: {op: lt, value: max_ankle_arc_deg, inclusive: true}, ...}
      leg_length:  {measure: leg_length_diff_cm, test: {op: gt, value: min_leg_length_diff_cm, inclusive: true}, ...}
    class_rules: {44: {any_of: [pf_strength, ankle_arc, leg_length]}}
    decision:
      - {id: two_sides, when: {any_class: true, flags: [sides_two]}, result: {all: needs_review}, report_missing: [], reason: LIMB_BILATERAL_INVOLVEMENT}
      - {id: one_side, when: {any_class: true, flags: [sides_one]}, result: {meets: {pick: most_impaired}, borderline: [{class: 42, if: {flag: hip_knee}}], rest: not_met}, report_missing: []}
      - {id: sides_unknown, when: {any_class: true}, result: {borderline: [44, {class: 42, if: {flag: hip_knee}}], rest: not_met}, report_missing: [lower_limb_sides_affected], reason: LIMB_SIDES_NOT_PROVIDED}
      - {id: hip_knee_only, when: {flag: hip_knee}, result: {borderline: [42], rest: not_met}, report_missing: [], reason: LIMB_HIP_KNEE_ASSESSMENT}
      - {id: no_ankle_measure, when: {all_missing: [ankle_pf_mrc, ankle_rom_deg, leg_length_diff_cm]}, result: {all: insufficient_data}, report_missing: [ankle_pf_mrc, ankle_rom_deg, leg_length_diff_cm], reason: LIMB_NO_ANKLE_MEASURE}
      - {id: no_cme, result: {all: not_met}, report_missing: [ankle_pf_mrc, ankle_rom_deg, leg_length_diff_cm], reason: LIMB_NO_CME_MET}
merge: best_status    # meets > borderline > needs_review > insufficient_data > not_met; empate: razões somadas, `missing` da primeira via
```

Os `...` marcam o que a implementação preenche com o mesmo padrão das linhas vizinhas (fonte, status, razão). O esboço mostra a **forma**; os valores exatos das linhas saem do `limb.py`, e a regressão exaustiva é quem confere.

**Por que a via funcional cabe sem expressões gerais:** os seis ramos do motor são **comparações simples sobre medidas** (três limites, um número de lados, um booleano), combinadas por **"e"** (um `when` com várias condições) e escolhidas **por ordem**, que é exatamente o que as regras de decisão já fazem. Não há aritmética nem condicional aninhado: o único "cálculo" é a escolha do `missing`, que vira um campo (`report_missing`). Se, na implementação, algum ramo exigir uma comparação entre **duas medidas** ou uma conta, esse é o sinal de parada, e eu paro e relato.

## A4. Construções novas (cada uma)

| # | Construção | Para quê | Linhas estimadas |
|---|---|---|---|
| 1 | **`derived` com `max` e `min`** (além da `sum`) | O par ordenado (maior, menor) de dois níveis, como duas medidas numéricas (`lower_hi`, `lower_lo`) | +4 |
| 2 | **Testes `eq` e `ne`** (valores categóricos, booleanos e inteiros) | A porta da posição, o número de lados, o déficit de quadril ou joelho | +6 |
| 3 | **`when.equals`** (medidas iguais a valores, também parcial) | Uma linha da tabela de níveis; combinada com a **ordem** das regras dá o "senão" da tabela | +3 |
| 4 | **`when.flag` ou `flags` com lista** (todas verdadeiras) | "Perna **e** braço amputados"; "algum critério **e** dois lados" | +2 |
| 5 | **`report_missing`** por regra de decisão (os campos faltantes que a regra reporta; omitido: todos os ausentes, como hoje) | O `missing` escolhido ramo a ramo do motor atual | +6 |
| 6 | **`gate`** (lista de regras de decisão do grupo, antes das vias; a primeira que vale encerra) | A porta de posição do `limb_standing` | +10 |
| 7 | **`pathways` e `merge: best_status`** (vias com condição de uso e a fusão por melhor situação) | As duas vias do `limb_standing` | +45 |
| (relaxamento) | `borderline` com condição **sem** `primary_above`; `class_rules` opcional | Linhas de tabela não têm classe com evidência | +6 |
| (validação) | Fonte e status também nas linhas e nas vias | Mesma regra de sempre | +10 |

**Soma: +92 linhas, de 258 para cerca de 350** (limite: 500). As ferramentas (`compare.py`) crescem cerca de 80 linhas (a regressão exaustiva), fora da contagem. **Total de construções do formato: 18 hoje, 25 com estas** (7 novas); mais o bloco `domains`, que é **metadado das ferramentas** e o interpretador ignora. **A negação de parâmetro continua em um único lugar.**

## A5. Regressão exaustiva

**Domínios.** Cada grupo declara em `domains` os valores possíveis de cada medida discreta (níveis, posição, lados, déficit, força de 0 a 5); a ferramenta gera o **produto completo mais o valor ausente**. Para os números contínuos, a varredura em volta dos limites vem dos parâmetros, como já é.

| Grupo | O que se cobre | Perfis (estimativa) |
|---|---|---|
| `limb_prosthesis` | Os níveis (4 × 4 × 3 × 3 = **144 combinações**) × **todas as posições** (as duas do brief, em pé e com prótese, mais cadeira, Petra e ausente) × cada nível escondido; deficiências que não são a do grupo | cerca de **3.300** |
| `limb_standing`, via de amputação | As 144 combinações × as posições × cada nível escondido | cerca de **3.300** |
| `limb_standing`, via funcional | Produto de força (0 a 5 e ausente), arco (10 ± 0,01, 0,05 e valores distantes e ausente), diferença de perna (7 ± 0,01, 0,05 e distantes e ausente), lados (ausente, 1, 2 e 3), déficit (ausente, falso e verdadeiro), e as **combinações das três deficiências** (incluindo a presença ou não de `limb_deficiency`) | cerca de **10 a 12 mil** |
| Fusão | Perfis com **as duas vias** ao mesmo tempo (níveis × medidas funcionais), com níveis ausentes, e a amostra do módulo de educação com cada medida escondida | cerca de **3.000** |

**Meta: 0 divergências** de `status` e `missing`, por classe, contra `RuleEngine.evaluate`. No `pytest`, as partes menores inteiras e a funcional **em amostra** (cerca de 4 mil perfis por grupo, como combinado); o produto inteiro roda por um comando à parte, fora do CI: `python -m para_triage.rulebook regress --exhaustive`.

**Outros testes:** a equivalência do rastro com o módulo de educação nas linhas da tabela (o `id` da linha é o `id` do módulo de educação; mesmos níveis e mesma conclusão); `needs_review` e `borderline` agora **exercidos de verdade** pelos grupos; a paridade de que não há duplicata no catálogo (os níveis não têm `criteria` em `classes.yaml`); o isolamento (nada importa o pacote); o teste das 500 linhas; o vocabulário fechado, atualizado com as 7 construções e a regra "uma única negação".

## A6. Estimativa

| | Linhas | Esforço (uma pessoa) |
|---|---|---|
| Interpretador (7 construções, relaxamentos e validação) | +92 (de 258 para cerca de 350) | 1 dia |
| `limb_prosthesis.yaml` | cerca de 90 | 0,5 dia |
| `limb_standing.yaml` | cerca de 190 | 1 dia, com a fusão |
| Mensagens pt e en (cerca de 25 códigos novos cada) | cerca de 60 | 0,5 dia |
| Regressão exaustiva e testes | `compare.py` +80; testes cerca de 250 | 1 dia |
| **Total** | | **3 a 4 dias** (faixa de 2 a 6) |

**Ordem proposta:** `limb_prosthesis` primeiro (só `derived`, `eq/ne`, `equals`, `report_missing`: 4 das 7 construções, e a tabela inteira como dado), **uma etapa**; depois `limb_standing` (porta, vias e fusão), **outra etapa**. Cada uma com a sua regressão.

## A7. O que ficaria de fora

- **O módulo de educação e o guia não trocam** de rastro: só o teste de equivalência nas linhas da tabela. Os casos do módulo de educação continuam só de amputação por nível; **a via funcional não tem rastro no módulo de educação**.
- **Cadeira (51 a 57), neuro e Petra**, a **classe 20** com idade (R12) e os provisórios: etapas 4 e 5.
- **Força e amplitude dos membros superiores**: o motor atual **não as implementa**; o livro de regras também não.
- **Provas e equipamentos**; o espanhol; a troca do `RuleEngine`.
- O **limite de 7 cm** vira parâmetro com `status: provisional` (vem da F57 e é a validar para a T44); isso **não** corrige a regra, só a torna visível.

## A8. Riscos

| Risco | Mitigação |
|---|---|
| **A fusão das vias** reproduzir mal o `merge` do motor (empate, `missing`) | Regressão com as duas vias ao mesmo tempo, níveis ausentes incluídos; a regra de empate escrita no teste |
| **`report_missing` esconder campos** que o motor reporta (ou reportar a mais) | Regressão compara `missing` por classe (já compara); as sondas do motor viram casos de teste nomeados |
| **Tabela como regras** ficar longa e difícil de rever | Uma linha por regra, `id` do módulo de educação, ordem igual à do motor; o teste exaustivo é a rede |
| **A linguagem crescer** (7 construções em um grupo só) | Vocabulário fechado por teste; a regra de parada; as construções são pequenas e **nenhuma é uma expressão** |
| **Três números só no motor** (2, 10, 7) passarem a ter uma cópia no YAML | Eles **não estão no catálogo**, então não há cópia dupla; ficam só no YAML, com fonte e status; a regressão os fixa |
| **Domínios** (`domains`) desatualizados | Um teste confere que os domínios incluem todo valor que o `Profile` aceita para esses campos |
| **Subestimar o `limb_standing`** | A estimativa tem faixa larga (2 a 6 dias) e a ordem proposta deixa o grupo difícil para a segunda etapa |

## A9. Dúvidas para a arquitetura

1. **Linhas da tabela como regras de decisão** (uma construção a menos, o `id` do módulo de educação em cada linha) ou uma construção `table` própria? Recomendo as **regras**.
2. **`report_missing`** como regra de formato (omitido: todos os ausentes). Aceita?
3. **`domains`** no YAML do grupo (metadado só das ferramentas) ou em um arquivo de ferramentas à parte? Recomendo no YAML, perto das medidas.
4. **`merge: best_status`** como valor fixo (única fusão que o motor atual usa). Aceita não generalizar?
5. **Uma etapa por grupo** (prótese, depois em pé) ou uma só? Recomendo duas.
6. Os três limites da via funcional (2, 10 e 7) ficam **só no YAML** (não estão no catálogo). Aceita?
7. **Regressão exaustiva no `pytest`**: as partes menores inteiras e a funcional em amostra (cerca de 4 mil por grupo); o produto inteiro em `regress --exhaustive`, fora do CI. Aceita?

---

## Como ficou a etapa 3a (`limb_prosthesis`)

O adendo foi aprovado; esta é a primeira das duas implementações (a segunda, `limb_standing`, vem depois). O motor atual continua sendo o padrão e nada fora de `rulebook/` importa o pacote.

**O que há:** `data/groups/limb_prosthesis.yaml` (107 linhas, 11 testes como dados), 11 códigos novos em `messages/pt.yaml` e `en.yaml`, `domain_cases` em `compare.py`, a opção `--exhaustive` em `__main__.py` e o grupo em `GROUPS`. A tabela de níveis é **uma regra de decisão por linha**, com o `id` da linha do módulo de educação.

**Construções novas (4 das 7 do adendo, mais 2 pequenas):**

| Construção | Onde | Linhas |
|---|---|---|
| `derived` com `max` e `min` (além de `sum`) | `lower_hi`, `lower_lo`, `upper_hi` | +3 |
| Testes `eq` e `ne` | porta da posição; "há amputação" é `ne 0` e "não há" é `eq 0`, que é como o motor lê o nível (`upper[0]` e `not lower[0]`), e não `gt` e `lt` como o esboço do adendo | +3 |
| `when.equals` | as linhas da tabela | +1 |
| `report_missing` por regra de decisão (os ausentes da lista, na ordem da lista; omitido: todos os ausentes, como antes) | o `missing` de cada ramo | +2 |
| `criteria` e `class_rules` opcionais | um grupo que é só tabela | +3 |
| Linha de tabela (`when.equals`) exige fonte conhecida e status | a mesma regra dos critérios | +4 |

Fora do interpretador, `domains` (metadado do grupo para as ferramentas; o interpretador o ignora). **Total do formato: 22 construções** (18 + 4). Faltam as 3 da 3b (`gate`, `pathways` com `merge: best_status`, flags em lista), mais o relaxamento de `borderline` sem `primary_above`.

**Linhas do interpretador: 269** (`interpreter.py` 248 + `messages.py` 21), contra 258 antes e o limite de 500. O adendo estimava +92 para as 7 construções; a 3a gastou +11.

**Parâmetros:** `required_posture` (fonte p. 35). Duas flags ficam `provisional`: `upper_amputation` (braço amputado com prótese vai para revisão; é política nossa, não texto do livreto) e a linha `above_plus_below` (o classificador decide entre 61 e 62).

**Testes** (445 passam; 24 novos, fora os 11 testes do grupo como dados):

- o produto inteiro dos domínios (posição de 4 valores e ausente, quatro medidas de nível e ausentes) com os quatro conjuntos de deficiências (o grupo, o grupo e outra, só outra, nenhuma): 8.000 perfis, 0 divergências;
- as **144 combinações de níveis nas duas posições** (em pé e com prótese): 288 perfis, 0 divergências;
- a amostra do módulo de educação de 3 sementes com cada medida escondida, e níveis fora do domínio (-1 e 4);
- as sondas do motor viram testes nomeados: posição ausente pede só a posição; outra posição é `not_met` sem pedir nada **mesmo com níveis faltando**; níveis faltantes na ordem dos campos;
- todo estado que o grupo pode dar é dado por algum perfil (só o `not_implemented` fica sem uso real);
- uma linha errada da tabela é detectada (exatamente 2 divergências);
- cada linha é a linha do módulo de educação (mesmo `id`, mesma conclusão, mesmo texto da última etapa);
- os testes do interpretador usam nomes inventados para `max`, `min`, `eq`, `ne`, `equals`, `report_missing` e grupo sem critérios.

**Regressão exaustiva** (`python -m para_triage.rulebook regress --group limb_prosthesis --exhaustive`, 6 minutos): **288.000 perfis, 0 divergências**. São 20 sementes de 400 perfis por classe do módulo de educação (completos, com cada uma das cinco medidas escondida e com todas escondidas: 40.000 perfis em cada uma das sete formas) mais o produto inteiro dos domínios (2.000 com o grupo declarado e 6.000 com outras deficiências). O comando padrão (5 sementes de 40 por classe, mais os 2.000 do produto) leva cerca de 6 segundos: 9.000 perfis, 0 divergências.

---

## Como ficou a etapa 3b (`limb_standing`)

Segunda e última implementação do adendo da etapa 3. O motor atual continua sendo o padrão e nada fora de `rulebook/` importa o pacote.

**O que há:** `data/groups/limb_standing.yaml` (260 linhas, 20 testes como dados), 22 códigos novos em `messages/pt.yaml` e `en.yaml`, e, nas ferramentas, `domain_cases` com produtos por via e com as duas vias juntas (`fusion`). `interpreter.py` passa a avaliar uma "especificação" por vez (`_run`): o arquivo do grupo, ou uma via; um grupo sem vias se comporta como antes (as regressões de `visual`, `short_stature` e `limb_prosthesis` seguem em 0 divergências).

**Construções novas (as 3 que faltavam do adendo, mais 1 relaxamento):**

| Construção | Para quê |
|---|---|
| `gate`: regras de decisão antes das vias; a primeira que vale encerra | a posição |
| `pathways` (cada via com `applies_to`, `measures`, `derived`, `flags`, `criteria`, `class_rules`, `decision`) e `merge: best_status` | amplitude de amputação e força, amplitude e perna |
| `when.flag` com uma lista (todas verdadeiras) | "perna e braço amputados" |
| `borderline` com condição sem `primary_above` | 42 `borderline` por déficit de quadril ou joelho |

Os +26 do interpretador incluem a passagem do avaliador para uma especificação por vez (`_run`). A fusão é fixa: por classe, vale a via de melhor situação (`meets`, `borderline`, `needs_review`, `insufficient_data`, `not_met`); no empate somam-se as razões sem repetir e vale o `missing` da primeira via **do arquivo** (a ordem das vias é a do motor: amputação, depois força). **Total do formato: 25 construções** (18 + 4 da 3a + 3 desta), como previa o adendo, mais `domains` e `fusion`, metadados das ferramentas que o interpretador ignora.

**Linhas do interpretador: 295** (`interpreter.py` 274 + `messages.py` 21), contra 269 depois da 3a, 258 antes da etapa 3 e o limite de 500. O adendo estimava cerca de 350. **A regra de parada não foi acionada**: a via funcional coube em comparações simples, sem expressões, aritmética nem comparação entre duas medidas.

**Os três limites da via funcional** (`max_plantar_flexion_mrc` 2, `max_ankle_arc_deg` 10, `min_leg_length_diff_cm` 7) ficam só no YAML, todos `provisional`, com a nota de que o livreto os dá como exemplo de critério mínimo e que o de 7 cm vem da F57 e está a confirmar para a T44. O mesmo vale para a leitura "déficit de quadril ou joelho" e as linhas da tabela marcadas `provisional` (parte do pé, acima do joelho de um lado com parte do pé do outro, etc.).

**(Fechada na etapa 3c, abaixo.) Uma diferença conhecida, fora do contrato:** com `lower_limb_sides_affected` fora de 1 e 2 (por exemplo 3), o motor atual pede o campo dos lados em `missing`; o livro de regras dá o mesmo **status** mas não pede nada, porque `report_missing` só lista o que de fato falta. A API só aceita 1 ou 2 (`Field(ge=1, le=2)`), então isso não é alcançável por ela. Está num teste nomeado. Corrigir pede uma forma incondicional de `report_missing` (uma construção a mais) e fica como pergunta para a arquitetura.

**Regressão:** os produtos de `domains` por via e das duas vias juntas, a amostra do módulo de educação com cada medida escondida, as 144 combinações de níveis nas duas posições, a varredura dos três limites (7.938 perfis) e a fusão com níveis ausentes. Os números da execução exaustiva estão na seção do grupo.

**Regressão exaustiva** (`python -m para_triage.rulebook regress --group limb_standing --exhaustive`, 22 minutos): **1.012.720 perfis, 0 divergências.** São 20 sementes de 400 perfis por classe do módulo de educação, em 11 formas (completos e com cada uma das dez medidas escondida: 64.000 em cada), mais: a via de amputação sozinha (4.000: o produto de 5 posições e 4 níveis, cada um com seus valores e ausente, com o grupo declarado e com as quatro deficiências), a via funcional sozinha (40.320: posições, força de 0 a 5, uma grade em volta de cada limite do arco e da perna, lados, déficit), as **duas vias juntas** (194.400: os 400 pares de níveis, com ausentes, contra 243 combinações dos valores em volta dos limites, com e sem a terceira deficiência) e outras deficiências (6.000). O comando padrão (cerca de 25 segundos) dá 30.092 perfis, 0 divergências.

---

## Como ficou a etapa 3c (a diferença dos lados, fechada)

A decisão foi **fechar** a diferença conhecida da 3b: com `lower_limb_sides_affected` fora de 1 e 2 (0, 3, -1), o livro de regras de `limb_standing` agora pede o campo dos lados em `missing`, **exatamente como o `RuleEngine.evaluate`**.

**O veredito (status) já era igual.** A diferença era só na lista `missing`: nos perfis com lados fora de 1 e 2, o status de cada classe coincidia com o do motor (44 `borderline`, as demais `not_met`, ou o resultado da fusão com a outra via), e o que divergia era o campo pedido. A 3b tinha um teste que afirmava as duas coisas; agora ele afirma a igualdade completa.

**A construção nova (26ª): `report_always`**, por regra de decisão: a lista de campos que o veredito reporta em `missing`, **como está escrita**, estejam ausentes ou não. `report_missing` continua filtrando pelos ausentes. `sides_unknown` passa a usar `report_always: [lower_limb_sides_affected]`, porque aquele ramo vale tanto para o campo ausente quanto para um valor que o motor não reconhece. Nenhuma outra regra mudou. **Total do formato: 26 construções.**

**Linhas do interpretador: 297** (`interpreter.py` 276 + `messages.py` 21), contra 295 e o limite de 500.

**Cobertura, para a diferença não voltar sem ser vista:**

- `domains` e `fusion` de `limb_standing` listam lados em 1, 2, **0, 3 e -1** (e ausente), então os produtos `domain-strength_rom` e `domain-fusion` os exercitam; um teste confere que as listas e os casos gerados os têm.
- `_product` (em `compare.py`) deixou de tomar "um a cada n" nos produtos grandes, que visitava só alguns valores da última medida (com o passo de 20 e seis valores, só os de índice par); agora toma um subconjunto pseudoaleatório de semente fixa. Sem isso o modo padrão não veria os valores novos.
- Testes nomeados: lados 0, 3 e -1 na via funcional sozinha e nas duas vias juntas (com o déficit de quadril ou joelho), comparando **status e `missing`** com o motor; uma varredura de 324 perfis com lados em {ausente, 0, 1, 2, 3, -1}.
- A regressão detecta o retorno da diferença: um teste troca `report_always` por `report_missing` no arquivo e confere que há divergências.

**Regressão exaustiva** (`regress --group limb_standing --exhaustive`, 17 minutos): **1.247.440 perfis, 0 divergências** (antes, 1.012.720; a via funcional sozinha passou de 40.320 a 80.640 e as duas vias juntas de 194.400 a 388.800, com os lados ampliados). Padrão: 31.261 perfis, 0 divergências. Suíte: 481 testes passam.

---

## Como ficou a etapa 4 (`intellectual`, a classe 20 com a idade de início)

Primeiro grupo cuja variante muda um parâmetro. O motor atual continua sendo o padrão e nada fora de `rulebook/` importa o pacote. **Não mudam** o perfil, a API, a web, os modelos, `rules/` nem o `classes.yaml`: o campo `onset_age` (item R12 do backlog) existe **só no livro de regras**, como medida do grupo.

**O que há:** `data/groups/intellectual.yaml` (10 testes como dados), `data/variants/wpa-2023.yaml`, o documento `wpa-2023` em `sources.yaml`, 5 códigos de razão em pt e en, e, em `compare.py`, o adaptador da idade e o grupo em `GROUPS`.

**Nenhuma construção nova, e o interpretador não mudou: 297 linhas.** O grupo usa três flags (um critério que reprova), regras de decisão em ordem e uma regra final sem `when`, como os demais. A ordem espelha o motor: um critério reprovado dá `not_met` mesmo que outro falte (sem pedir campo nenhum); só depois, medidas ausentes dão `insufficient_data`, que pede as ausentes na ordem do motor (QI, limitação adaptativa, início); senão a classe 20 é atendida. **Contagem de construções do formato: 26**, as mesmas.

**A idade como parâmetro.** `onset_age_limit` vale 22 (como o `classes.yaml`, `onset_before_age`), e a variante `wpa-2023` o troca por 18 (`overrides`, fonte `wpa-2023`, `provisional`). O QI (`iq_max` 75) é o mesmo valor do catálogo; um teste confere os dois números. Da WPA entra **só a idade**: ela não traz limite de QI (remete aos critérios da Virtus, ao questionário TSAL-Q e a uma bateria de testes) e a classe T/F20 é específica da prova. Isso está como nota na fonte, não como critério.

**A fronteira da idade não está confirmada pelo livreto.** O campo do perfil se chama `onset_before_22`, então a leitura natural é **estritamente menor** (`onset_age < 22`; aos 22 completos já não conta). É o que o livro de regras faz, pelo parâmetro `onset_limit_is_late` (verdadeiro: a idade do limite já é tarde; é o `inclusive` da fronteira, escrito do lado em que a comparação reprova, o que evita a negação de parâmetro, que o teste mantém em um único lugar). É `provisional`. Se a fronteira fosse inclusiva, basta o parâmetro valer `false` (por exemplo `--set onset_limit_is_late=false` no `diff`, ou uma variante); **só quem tem o livreto pode confirmar.**

**O adaptador da regressão.** O motor só conhece o booleano `onset_before_22`; o livro de regras lê `onset_age`. Para comparar sem mexer no motor, `compare.py` declara um adaptador: **verdadeiro vira 21, falso vira 22, ausente fica ausente** (nas duas direções: uma idade abaixo de 22 vira verdadeiro), e o campo que o motor lista como faltante, `onset_before_22`, é traduzido de volta para `onset_age` ao comparar o `missing`. **O que a regressão não prova:** as idades entre 18 e 21 e a fronteira, porque o motor não as representa (o adaptador as lê pela própria regra de 22, o que seria circular). Elas têm **testes próprios, com o resultado escrito à mão**, nas duas variantes: com as outras condições atendidas, `cpb-2024` dá `meets` em 17, 18, 19 e 21 e `not_met` em 22 e 23; `wpa-2023` dá `meets` só em 17 e `not_met` de 18 em diante; a idade ausente pede `onset_age` nas duas.

**Regressão:** o produto inteiro dos domínios (QI em 40, 74, 75, 76, 120 e ausente; limitação adaptativa; idade em 21, 22 e ausente), com o grupo declarado e com outras deficiências (`not_applicable`), a amostra do módulo de educação com cada medida escondida, e sondas nomeadas do motor. O grupo dá `meets`, `not_met`, `insufficient_data` e `not_applicable`; **não** dá `borderline`, `needs_review` nem `not_implemented`. Padrão: 2.054 perfis, 0 divergências.

**Regressão exaustiva do grupo** (`regress --group intellectual --exhaustive`): **80.216 perfis, 0 divergências** (20 sementes de 400 perfis por classe do módulo de educação, em cinco formas: 16.000 em cada, mais o produto: 54 com o grupo e 162 com outras deficiências).

**Diff `cpb-2024` contra `wpa-2023`** (`python -m para_triage.rulebook diff --group intellectual --a cpb-2024 --b wpa-2023`). Muda só por causa da idade, e **o número depende da idade que se supõe para quem tem "início antes dos 22"**, que a amostra e o perfil atual não têm:

| Suposição | Perfis completos da amostra que mudam | Sentido |
|---|---|---|
| Todo "antes dos 22" tem início aos 21 (o adaptador) | **todos os que atendem a classe 20 no livreto**: 200 de 400 (5 sementes) e 8.000 de 16.000 (20 sementes); a amostra tem metade de cada rótulo por construção, não é prevalência | `meets` → `not_met` |
| Todo "antes dos 22" tem início aos 17 (antes dos 18) | **nenhum** | |

O número real fica entre os dois e **só um campo de idade (R12) o determina**. Com perfis incompletos, o diff também move `insufficient_data` → `not_met` (a idade 21 reprova na WPA mesmo que outra medida falte): no produto inteiro de 54 perfis, 8 mudam (3 `meets` → `not_met` e 5 `insufficient_data` → `not_met`).

**Os cinco grupos juntos** (`regress --exhaustive`, 27 minutos, depois de tocar o código compartilhado de `compare.py`): visual 160.344, baixa estatura 122.289, `limb_prosthesis` 288.000, `limb_standing` 1.247.440 e `intellectual` 80.216 perfis, **0 divergências em todos**. Padrão dos cinco: 4.344, 7.539, 9.000, 31.261 e 2.054, 0 divergências. Suíte: 496 testes passam.

---

## Como ficou a etapa 5a (`frame_runner`, a Petra: classes 71 e 72)

Primeiro dos três grupos provisórios. O motor atual continua sendo o padrão e nada fora de `rulebook/` importa o pacote. **Nada foi corrigido:** o grupo reproduz `evaluate_frame_runner`, que o próprio motor chama de leitura nossa do livreto (`docs/rules_coverage.md`, itens 15 e 16); a especialista vai substituí-lo.

**O que há:** `data/groups/frame_runner.yaml` (10 testes como dados), 10 códigos de razão em pt e en e, em `compare.py`, a conversão dos campos que o perfil guarda como enums (`ENUMS`: gravidade, distribuição, propulsão, braço, tronco, perna e sexo) e o grupo em `GROUPS`.

**Nenhuma construção nova; o interpretador não mudou (297 linhas, pelo critério do teste das 500 linhas: linhas não vazias e que não são comentário, em `interpreter.py` e `messages.py`; o arquivo `interpreter.py` tem 326 linhas brutas, o número do brief).** O formato segue com 26 construções. O grupo cabe em seis flags (todas `eq` ou `ne` contra um booleano ou `lt` contra um parâmetro) e onze regras de decisão em ordem, uma por ramo do evaluator. A gravidade (`Severity`, `IntEnum`) entra como inteiro de 0 a 3, comparado com o parâmetro `min_severity` (2), sem construção nova.

**Tudo é `provisional`, com `note`:** a postura, a exigência do relatório neurológico, a gravidade mínima e as quatro respostas sobre a transferência, a caminhada e a amarração de tronco. Um teste confere que nada no grupo está como `implemented`.

**O relatório neurológico (`_brain_gate`)** é comum à Petra e ao neuro. O formato não tem reuso entre arquivos, então as duas regras e a flag (`brain_report_missing`, `no_brain_report`) são **repetidas de propósito** em cada arquivo (no `neuro.yaml`, na 5c), com os mesmos códigos de razão.

**Ramos do evaluator:** onze, e os onze são alcançados (um teste confere que as regras vencedoras sobre o produto dos domínios cobrem todas as regras). Nenhum ramo fica de fora.

**Comportamentos do motor que parecem estranhos, reproduzidos e não corrigidos** (cada um tem teste nomeado):

1. `walks_short_distances` e `trunk_straps_needed` **ausentes valem como "não"** e nunca são pedidos em `missing`, mesmo quando decidiriam o veredito (`71 meets` ou `72 meets` em vez de `borderline`).
2. **Gravidade severa vale como moderada**: não há ramo para ela.
3. A **amarração de tronco é ignorada** quando o atleta não se transfere sozinho e não caminha (continua 71).
4. Os **três tipos de deficiência** (hipertonia, ataxia, atetose) **não são distinguidos**: qualquer um torna o grupo aplicável e o resultado é o mesmo.
5. As contradições dão `borderline` nas **duas** classes, sem olhar a gravidade.

**Regressão:** o produto inteiro dos domínios (posição de 4 valores, relatório, gravidade de 0 a 3, transferência, caminhada e amarração, cada um também ausente) com o grupo declarado e com outras deficiências (`not_applicable`); cada um dos três tipos sozinho; a amostra do módulo de educação com cada medida escondida; sondas nomeadas, uma por ramo. Padrão: 8.425 perfis, 0 divergências.

**Regressão exaustiva** (`regress --group frame_runner --exhaustive`, 8 minutos): **264.100 perfis, 0 divergências** (20 sementes de 400 perfis por classe do módulo de educação, em oito formas: 32.000 em cada, mais o produto: 2.025 com o grupo e 6.075 com outras deficiências). Suíte: 513 testes passam.

---

## Como ficou a etapa 5b (`wheelchair`, classes 51 a 57)

Segundo dos três grupos provisórios. O motor atual continua sendo o padrão e nada fora de `rulebook/` o importa. **Nada foi corrigido:** o grupo reproduz `evaluate_seated`, que o próprio motor chama de leitura nossa do livreto (`docs/rules_coverage.md`, itens 17 a 19).

**O que há:** `data/groups/wheelchair.yaml` (14 testes como dados), 14 códigos de razão em pt e en, o grupo em `GROUPS`, e uma construção nova (abaixo). As classes 51 a 57 e as páginas de cada linha são as do catálogo (`source_page` de cada classe; um teste confere).

**Uma construção nova: `same_as`** (a 27ª), num parâmetro: `max_ankle_arc_deg: {same_as: limb_standing}` toma a especificação do parâmetro **do arquivo de outro grupo**, no carregamento, em vez de copiá-la. É como os **três limites do tornozelo** (força 2, arco 10 graus, diferença de perna 7 cm) são compartilhados com o `limb_standing`: o valor, a fonte, o status e a nota vivem **em um só lugar**, e o `wheelchair.yaml` não tem número nenhum para eles. Uma sobreposição por nome (`overrides`, variante, `--set`) vale para os **dois** grupos, porque o nome é o mesmo. Se o outro grupo não tem o parâmetro, é erro (`RulebookError`). Custou **6 linhas** no interpretador (303 de código, 332 brutas; eram 297 e 326), sem nenhuma expressão. O que **não** é compartilhado são as três definições de critério (medida, teste, razão) de classe 57: repetem a forma das do `limb_standing` por serem outro grupo, sem repetir valor.

**O mesmo conjunto de deficiências do `limb_standing`.** O motor avalia os dois grupos para o mesmo perfil, cada um pela sua postura (um perfil sentado só decide as classes 51 a 57; em pé, só as 42 a 47). Um teste conferiu que `applies_to` é o mesmo conjunto e que os dois livros dão, para o mesmo perfil, o que o motor dá: sentado, o `wheelchair` decide e o `limb_standing` dá `not_met` em tudo; em pé, o contrário. O motor também não distingue as quatro deficiências dentro do grupo.

**Formato:** quinze regras de decisão em ordem para os treze ramos do evaluator (a função do braço tem uma linha por valor: 51, 52 e 53), cinco flags de enum (todas `eq`, `ne` ou `between` com literais, sem construção nova), três critérios do tornozelo e a regra da classe 57 (`any_class`, `meets` com `pick`). Os códigos das descrições (0 a 3 para o braço, 0 a 2 para o tronco, 0 a 4 para a perna) são os valores dos enums do perfil, listados em `domains`.

**Tudo é `provisional`, com `note`** (um teste confere que nada está `implemented`): a postura, as funções do braço, do tronco e da perna e as três regras do tornozelo.

**Ramos do evaluator:** os treze são alcançados (um teste confere que as regras vencedoras sobre o produto dos descritores e o produto do tornozelo cobrem as quinze regras). **Nenhum ramo fica de fora.**

**Comportamentos do motor que parecem estranhos, reproduzidos e não corrigidos** (cada um com teste nomeado):

1. **Nível do tornozelo sem nenhuma medida do tornozelo é classe 57 atendida** ("critério do tornozelo não documentado"), e **nada é pedido em `missing`**; basta uma medida que reprove para virar `borderline`. A falta de evidência vale mais que uma evidência que reprova.
2. **Braços preservados sem função de tronco dão 54 sem olhar a perna** (e a perna não é pedida).
3. **Déficit de braço com qualquer função de tronco** (parcial ou total) dá `needs_review` sem olhar a perna.
4. **Tronco parcial e tronco total não se distinguem**, e **perna nenhuma e só flexores do quadril são a mesma classe (55)**.
5. **As quatro deficiências não se distinguem**, e os **níveis de amputação não são lidos**: um amputado sentado é julgado só pela função (item 18 da cobertura: sem campos próprios).
6. Perna **normal** dá `not_met` em tudo, sem pedir nada.

**Regressão:** o produto dos descritores (posição de 4 valores, braço, tronco, perna, cada um também ausente) com o grupo e com outras deficiências, cada uma das quatro deficiências sozinha, o nível do tornozelo por todas as combinações das três medidas em volta dos limites (64), a amostra do módulo de educação com cada medida escondida, e sondas nomeadas, uma por ramo. Padrão: 21.199 perfis, 0 divergências. Uma correção em `compare.py` que esta etapa pediu: o produto de um grupo sem vias passava a usar só as medidas listadas em `domains`; agora as demais (os números comparados com um limite) entram com uma grade em volta do limite, como nos grupos com vias. Os grupos anteriores têm todas as medidas em `domains` e os mesmos totais de perfis de antes.

**Regressão exaustiva** (`regress --group wheelchair --exhaustive`, 42 minutos): **1.723.200 perfis, 0 divergências.** São 20 sementes de 400 perfis por classe do módulo de educação, em nove formas (completos, com cada uma das sete medidas escondida e com todas: 72.000 em cada), mais o produto inteiro dos descritores com a grade do tornozelo: 268.800 com o grupo declarado e 806.400 com as quatro deficiências juntas, uma delas mais outra, outras e nenhuma. Suíte: 537 testes passam.

---

## Como ficou a etapa 5c (`neuro`, classes 31 a 38) e o que falta para trocar o `RuleEngine`

Terceiro e último dos grupos provisórios. O motor atual continua sendo o padrão e nada fora de `rulebook/` o importa. **Nada foi corrigido:** o grupo reproduz `evaluate_neuro` (`docs/rules_coverage.md`, itens 13 a 15), que o próprio motor chama de leitura nossa do livreto. Com ele, **os oito grupos do motor têm paridade** no livro de regras.

**O que há:** `data/groups/neuro.yaml` (19 testes como dados), 23 códigos de razão em pt e en, o grupo em `GROUPS`, e duas construções novas (abaixo). Em `compare.py`: o amostrador do módulo de educação dos dois grupos de postura (`neuro_seated` e `neuro_standing`) e os conjuntos de deficiências do produto (`impairment_sets`).

**Duas construções novas** (a 28ª e a 29ª), as menores que cobrem o que o motor faz:

1. **`impairment_measures`**: as deficiências declaradas entram como **medidas booleanas** `has_<deficiência>` (`has_hypertonia`, `has_ataxia`, `has_athetosis`), nunca ausentes. O motor testa `types == {hipertonia}` (exatamente) e "tem ataxia ou atetose"; com isso, "só hipertonia" é uma lista de flags (tem hipertonia, não tem ataxia, não tem atetose) e "ataxia ou atetose" é uma medida derivada `max` dos dois booleanos, que o formato já tinha. **Uma linha no interpretador.** Outras deficiências declaradas (visual etc.) continuam não contando, como no motor.
2. **`class_groups` e `scope`**: as classes sentadas (31 a 34) e em pé (35 a 38) são decididas por regras diferentes, e o motor devolve para as da outra postura `not_met` **sem pedir campo nenhum**, mesmo quando as da própria postura pedem um (`chair_propulsion`, `cp_distribution`, `neuro_severity`). Uma regra com `scope: seated` decide só as classes desse grupo (`all`, `rest`, `missing` valem para elas), e as demais ficam `not_met` com a razão que o grupo declara (`outside_reason`) e nenhum campo pedido. Um `scope` que não é grupo de classes é erro. **Cerca de nove linhas.** Sem isso o `missing` por classe não se reproduz, porque o formato só tinha um `missing` por regra. Não é uma expressão.

**Pensei em não criar a segunda** e usar `pathways` com `merge`; não serve: a fusão pega o melhor status por classe e, no empate, o `missing` da primeira via, o que não é o que o motor faz aqui.

**Total do formato: 29 construções.** Interpretador: **313 linhas** pelo critério do teste (eram 303) e **342 brutas** (eram 332); limite ~500. Nenhuma expressão geral. Além das duas construções, `impairment_sets` é metadado do grupo para as ferramentas (os dez conjuntos de tipos que o produto percorre: as sete combinações não vazias dos três tipos e três com outra deficiência); o interpretador o ignora.

**Formato do grupo:** vinte e seis regras de decisão em ordem (quatro da porta, dez sentadas e doze em pé), dezoito flags (posturas, gravidade, propulsão, distribuição e os tipos) e uma medida derivada. A gravidade, a propulsão e a distribuição entram como os valores dos enums do perfil (listados em `domains`). **O relatório neurológico** (`_brain_gate`) é a mesma porta da Petra, **repetida de propósito** nos dois arquivos; um teste mantém as duas regras e a flag **iguais** entre `neuro.yaml` e `frame_runner.yaml`.

**Tudo é `provisional`, com `note`.**

**Ramos do evaluator:** todos os ramos são alcançados (um teste confere que as regras vencedoras sobre o produto cobrem as vinte e seis regras do arquivo). **Nenhum ramo fica de fora.**

**Comportamentos do motor que parecem estranhos, reproduzidos e não corrigidos** (cada um com teste nomeado):

1. **Sentado sem gravidade informada** (`neuro_severity` ausente) **é lido como moderado ou mais**: segue para a propulsão e a gravidade **não é pedida**.
2. **A propulsão é pedida antes de olhar a gravidade:** sentado sem propulsão pede a propulsão mesmo que a gravidade seja "nenhuma".
3. **A propulsão decide as classes 31, 32 e 33 sem olhar o tipo de deficiência**; só a classe 34 (propulsão simétrica) olha o conjunto de tipos.
4. **Propulsão simétrica sem distribuição informada** põe a 34 em `borderline` e pede `cp_distribution` **também nas classes 31 a 33** (que ficam `not_met` com o campo pedido); as classes em pé não pedem nada.
5. **Em pé, gravidade grave dá `needs_review` antes de olhar o tipo ou a distribuição.**
6. **Em pé, leve com diplegia só é `borderline` (35 e 38) para hipertonia pura**; hipertonia misturada com ataxia ou atetose com diplegia dá 38 atendida.
7. **Em pé, moderado sem hipertonia é a classe 36 e a distribuição nunca é pedida.**
8. **Quadriplegia ou triplegia em pé e moderado dá `needs_review` mesmo misturada com outros tipos.**
9. O motor trata o conjunto de tipos só pela interseção com os três (hipertonia, ataxia, atetose); as outras deficiências declaradas não contam.

**Regressão:** o produto inteiro dos descritores (posição de 4 valores, relatório, gravidade, propulsão, distribuição, cada um também ausente) para cada um dos dez conjuntos de tipos, mais três conjuntos de outras deficiências; a amostra do módulo de educação das duas posturas com cada medida escondida; uma sonda nomeada por ramo; e a detecção de uma classe errada, de um `scope` removido e de uma ordem trocada. Padrão: 32.750 perfis, 0 divergências.

### O que falta para a troca do `RuleEngine`

Cobertura **por grupo**: completa. Os oito grupos (visual, baixa estatura, `intellectual`, `limb_standing`, `limb_prosthesis`, `neuro`, `frame_runner`, `wheelchair`) dão, para cada perfil das regressões, o mesmo `status` e o mesmo `missing` por classe que `RuleEngine.evaluate`. **Não está pronto** para trocar, e o que falta é de **montagem e de decisão**, não de cobertura de regra:

1. **O motor montado.** Nenhum código reúne os oito livros num `EligibilityResult` (grupo a grupo, na ordem do catálogo, com `candidates`, `primary_class` e `meets` que a geração de dados, a API e o relatório usam). Falta também **comparar o motor inteiro** (todas as classes do perfil de uma vez), não só grupo a grupo.
2. **O perfil como medidas e os veredictos como objetos do motor.** Hoje `compare.py` traduz o `Profile` em medidas (e os enums em inteiros e textos) e o resultado em tuplas. Para a troca é preciso um adaptador **de produção**, e nele a decisão já aberta do **`onset_age`** (R12): o perfil só tem o booleano `onset_before_22`, e a variante `wpa-2023` só faz sentido com a idade.
3. **As razões.** O motor devolve frases em inglês em `Verdict.reasons`; a API, o relatório e sua guarda de fidelidade as consomem. O livro de regras devolve **códigos** (com textos pt e en). É preciso decidir se o texto sai do livro (e a guarda passa a conferir códigos) ou se o motor montado produz as frases do motor atual.
4. **`rules_version()`** não inclui `rulebook/`: na troca ele passa a incluir, e o JSON de transparência e o guia mudam de hash e precisam ser regerados.
5. **Os rastros do módulo de educação e do guia** (`education/trace.py`) são próprios e seguem assim; só as tabelas de níveis têm teste de equivalência. Trocar a fonte do rastro é outra decisão.
6. **Os números duplicados:** visual e baixa estatura têm os limites no livro e em `classes.yaml`; hoje um teste de paridade os mantém iguais. Na troca, a fonte única precisa ser escolhida.
7. **Desempenho e carga:** `Rulebook.load` lê o YAML a cada chamada; um motor montado precisa guardar os livros carregados (a medida de cerca de 1 ms por perfil é do motor mais o livro juntos).
8. **Decisões de conteúdo que a troca herdaria:** a fronteira dos 22 anos (não confirmada), os grupos provisórios (a matriz da especialista os substitui) e os comportamentos estranhos reproduzidos, listados nas seções das etapas 5a, 5b e 5c.

**Regressão exaustiva** (`regress --group neuro --exhaustive`, 16 minutos): **584.375 perfis, 0 divergências.** São 20 sementes de 400 perfis por classe do módulo de educação de cada postura, em sete formas (completos, com cada uma das cinco medidas escondida e com todas: 80.000 em cada), mais o produto inteiro dos descritores: 18.750 com os dez conjuntos de tipos e 5.625 com outras deficiências. Suíte: 566 testes passam.

---

## Como ficou a etapa 6 (o motor montado, em sombra)

Um motor completo no pacote `rulebook/` que reúne os oito livros e responde com a forma do `EligibilityResult`. **Em sombra:** nada o usa em produção, o `RuleEngine` continua sendo o padrão, e nada fora de `rulebook/` o importa nem o nomeia (o teste de isolamento confere os dois). Com isto saem da lista de pendências da troca os itens 1 (o motor montado) e 7 (a carga dos livros).

**O que há (`src/para_triage/rulebook/engine.py`):**

- **`ShadowEngine(variant="cpb-2024", overrides=None, on=None)`** carrega os oito livros **uma vez** (e a variante também: o interpretador recebe a variante já lida, então nenhum arquivo é lido por perfil; um teste proíbe a leitura). `evaluate(profile)` traduz o perfil em medidas, avalia cada livro e reúne os veredictos **ordenados por classe**. Uma sobreposição por nome vai aos livros que têm o parâmetro (a dos limites do tornozelo vale para `limb_standing` e `wheelchair`); nome que nenhum livro tem é erro. Uma classe decidida por dois livros é erro.
- **`ShadowResult`** tem a forma de `EligibilityResult`: `verdicts`, `meets`, `primary_class` (a única atendida, senão nada), `candidates` (atendidas primeiro, depois as limítrofes) e `with_status`. **Não importa o motor atual** (um teste confere): quem importa é a regressão, em `compare.py`.
- **O adaptador de perfil mudou de lugar:** `measures_of` e a ponte da idade de início (`onset_age`, `onset_flag`, 21 e 22) saíram de `compare.py` para `engine.py`, e o `compare.py` os importa. A regressão testa, portanto, **o mesmo adaptador que a produção usaria**. Ficaram em `compare.py` só as traduções que existem por causa da regressão (da medida de volta ao perfil, `ENUMS`, e o nome do campo faltante).

**Três diferenças de forma, de propósito, e como a comparação as trata:**

1. Os `status` são **strings** (`"meets"`) no livro e **`Status`** (enum de `str`) no motor: a comparação usa o `.value`; um teste mostra que `Status.MEETS == "meets"` e que os tipos são mesmo diferentes.
2. As `reasons` são **códigos** (textos em pt e en por `messages.message`), não as frases em inglês do motor. A comparação **não** as compara (ver o relatório abaixo).
3. A idade de início é a do adaptador: **verdadeiro vira 21, falso vira 22, ausente fica ausente.** O campo faltante da classe 20 se chama `onset_age` no motor em sombra e `onset_before_22` no atual; a comparação traduz o nome. **Esta etapa não decide o `onset_age` no perfil (R12).**

**Regressão do motor inteiro** (`python -m para_triage.rulebook regress --engine [--exhaustive]`): para cada perfil, as **33 classes de uma vez** pelos dois motores, comparando a **ordem das classes**, o `status` e o `missing` de cada uma, `meets`, `primary_class` e `candidates`. As entradas: (a) **tudo o que a regressão por grupo gera**, cada caso agora pelo motor inteiro; (b) **perfis com as deficiências de grupos diferentes ao mesmo tempo**, que a regressão por grupo não exerce: para cada uma das 247 combinações de dois a oito grupos, perfis montados juntando medidas e deficiências de casos de cada grupo (10 por combinação no padrão, 200 no exaustivo); (c) a amostra do módulo de educação dos oito grupos com cada medida escondida, que já vem em (a). Padrão: **119.042 perfis, 0 divergências.** Exaustivo (25 minutos): **4.519.364 perfis, 0 divergências**, entre eles 49.400 perfis misturados (dois a oito grupos). Um teste confirma que a regressão vê um motor em sombra errado (um limite deslocado dá divergências).

**Cobertura de classes (teste):** a união das classes dos oito livros é exatamente o conjunto das 33 classes do `classes.yaml`, sem repetição e sem falta, e o grupo de cada classe é o mesmo; o `applies_to` de cada livro é o conjunto de deficiências do grupo no catálogo.

**Interpretador: não cresceu** (313 linhas pelo critério do teste das 500 linhas, 342 brutas, as mesmas da 5c), nenhuma construção nova: **29**. **`rules_version()` idêntico ao da `main`** (`rules-25f1beb46158`, o mesmo `sha256`, calculado a partir dos arquivos de `origin/main`); nenhum arquivo de `rules/`, `api/`, `report/`, `education/`, `guide/`, `web/`, `provenance_info/`, `classes.yaml` nem `pyproject.toml` mudou, então os hashes do módulo de transparência e do guia não mudam.

### O relatório das razões (a decisão do item 3 da troca)

`python -m para_triage.rulebook reasons` pareia, na regressão padrão (119.042 perfis, 3.931.050 veredictos de classe), **cada frase do motor com o código do livro na mesma posição do veredicto**. Resumo:

| | |
|---|---|
| Frases distintas do motor | **2.193** |
| Modelos de frase (os números trocados por `#`) | **124** |
| Códigos distintos do livro | **95** |
| Modelos que carregam um valor (limite, medida, classe) | **43** |
| Modelos com **um** código que também só tem **aquele** modelo (um para um) | **40** |
| Modelos que correspondem a **mais de um** código | **3** |
| Códigos que correspondem a **mais de um** modelo | **51** |
| Veredictos em que o número de razões difere (não dá para parear) | **6.423** de 3.931.050 (0,16%) |

**Não é um para um.** O que se vê:

- **O motor tem frases genéricas por classe; o livro tem o código da decisão.** "criteria not met" (todas as classes não atendidas de um grupo) e "amputation pattern does not match this class" são **um modelo cada um**, e no livro cada um corresponde a **dezenas de códigos**: o livro dá a **todas** as classes a razão **da regra que decidiu** (por exemplo `LIMB_UNILATERAL_BELOW` também nas classes não atendidas), não "não atendida". Os três modelos com mais de um código são esses dois e "classes ## compete seated", que existe em dois grupos (o neuro em pé e a cadeira).
- **Vários modelos do motor correspondem a um código do livro** (51 códigos): o motor **compõe** a frase com as medidas que atenderam (por exemplo "CME met: ankle passive arc of # degrees (<= #); leg length difference of # cm (>= #); number of affected sides not provided", oito combinações para `LIMB_SIDES_NOT_PROVIDED`; "no impairment relevant to 'X' declared", uma por grupo, para `NO_RELEVANT_IMPAIRMENT`; "criterion not met: iq, adaptive_limitation" para `INTELLECTUAL_IQ_ABOVE_LIMIT`). O livro diz **qual regra**, e o rastro (`Step`) diz quais critérios atenderam.
- **Onde a frase carrega um valor que o código não carrega:** em **43 modelos**. As do tornozelo (grau, graus do arco, centímetros e o limite), a acuidade e o campo visual com a classe ("best-eye logMAR # is in the class # range"), a estatura, o braço e a soma com os limites, o QI, as classes entre as quais fica um caso limítrofe. No livro, **o valor está no rastro** (`Step.value`, `Step.test`, `Step.reference`), e os **textos** pt e en têm `{value}` e `{test}`; **o veredicto traz só o código**. Para reproduzir a frase do motor seria preciso que o veredicto carregasse também o valor ou o rastro.
- **Os 6.423 veredictos sem pareamento** (0,16%): uma razão do motor contra **zero** do livro (5.724, quase todos no visual, 3.439 + os misturados, e na baixa estatura, 1.058: o motor diz "visual criteria for this class not met" ou "limits exceeded, or a more impaired class applies" nas classes não atendidas, e a regra do livro que decide quando alguma classe é atendida não tem `reason`, então essas classes ficam sem código); e uma razão do motor contra **duas ou três** do livro (625 e 72, no `limb_standing`): o motor junta numa frase os critérios do tornozelo atendidos ("CME met: plantar flexion strength grade 2 (<= 2); leg length difference of 7 cm (>= 7)"), e o livro lista **um código por critério atendido**.

**O que isto sugere para a decisão (não a tomo):** ou (i) o texto sai do livro (os códigos mais o valor do rastro, e a guarda de fidelidade do relatório passa a conferir códigos), o que muda o contrato da API; ou (ii) um adaptador converte os códigos nas frases em inglês do motor atual, que são cerca de 124 modelos e dependem de valores que o veredicto não tem. Nenhuma das duas cabe sem uma decisão.

### Desempenho (microssegundos por perfil, motor inteiro, livros carregados uma vez)

Perfil completo típico de cada grupo (o primeiro da amostra do módulo de educação; 3.000 repetições; o motor em sombra avalia os oito livros em cada chamada, como o atual avalia os oito grupos):

| Grupo do perfil | `RuleEngine` | `ShadowEngine` | |
|---|---|---|---|
| visual | 37 | 117 | 3,2x |
| intellectual | 35 | 74 | 2,1x |
| neuro | 40 | 166 | 4,2x |
| short_stature | 43 | 103 | 2,4x |
| limb_standing | 40 | 178 | 4,5x |
| wheelchair | 47 | 164 | 3,5x |
| limb_prosthesis | 40 | 134 | 3,3x |
| frame_runner | 38 | 164 | 4,3x |

Média: 40 µs contra 138 µs por perfil (3,4x). Na regressão exaustiva inteira (4,5 milhões de perfis, com o computador também ocupado por outras tarefas): 240 s o motor atual e 767 s o motor em sombra, 53 µs e 170 µs por perfil. Não há meta de tempo; é informação para a decisão da troca.

### O que falta para a troca do `RuleEngine`, depois desta etapa

1. ~~O motor montado~~ e ~~a carga dos livros~~: **feitos** (esta etapa).
2. **O `onset_age` no perfil (R12):** o motor em sombra usa a ponte 21 e 22; a variante `wpa-2023` só faz sentido com a idade verdadeira. Decisão que invalida checkpoints e muda a API.
3. **As razões** (a tabela acima): códigos com o valor do rastro, ou um adaptador para as frases do motor. Decisão que envolve a guarda de fidelidade do relatório e a API.
4. **`rules_version()`** precisa passar a incluir `rulebook/` (e o JSON de transparência e o guia, módulo de transparência e guia, são regerados com o novo id).
5. **Os rastros do módulo de educação e do guia** (`education/trace.py`) seguem próprios; só as tabelas de níveis têm teste de equivalência.
6. **Os números duplicados** do visual e da baixa estatura (livro e `classes.yaml`): escolher a fonte única.
7. **Decisões de conteúdo herdadas:** a fronteira dos 22 anos (não confirmada), os grupos provisórios (a matriz da especialista os substitui) e os comportamentos estranhos reproduzidos, listados nas etapas 5a, 5b e 5c.
8. **Trocar o padrão** em si: ligar o motor em sombra à API, ao relatório, ao módulo de educação e ao guia, fora desta etapa, com o aval da equipe.
