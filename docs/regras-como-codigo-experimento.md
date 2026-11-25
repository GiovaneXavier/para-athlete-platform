# K20: experimento de um dia, regras como código (grupo visual)

**Resultado em uma frase:** as duas opções **reproduzem o motor atual sem nenhuma divergência** em 4.357 perfis, aguentam a variante por parâmetro e dão rastro; a diferença está no **tipo de artefato** (dado contra código), na **licença** (AGPL) e no **crescimento** de cada uma quando entrarem os outros sete grupos. **Recomendação: a opção B**, como o desenho propunha, com uma regra de parada (seção 10). Os dados **não contrariam** a recomendação da arquitetura, mas **tiram o argumento "o OpenFisca não encaixa"**: ele encaixa, só que com outro custo.

Ramo `feature/k20-experiment`; protótipos descartáveis, que **não estão neste repositório**. Nada fora de `spikes/` e deste documento foi alterado: núcleo, API, web, `pyproject.toml`, `web/package.json` e CI intocados, e **nenhum código do OpenFisca foi copiado**.

## 1. O que foi feito

| Passo | Resultado |
|---|---|
| Opção **B**: `visual.yaml` + `rulebook.py` | Pronta; os 9 testes do próprio YAML passam |
| Opção **A**: modelo no OpenFisca-Core 46.0.1 (Python 3.12), em um venv temporário fora do repositório | Pronta; os 4 testes no formato do OpenFisca passam (`openfisca test`) |
| Comparação com `RuleEngine.evaluate` | **0 divergências em 4.357 perfis**, nas duas opções (seção 2) |
| Variante por parâmetro | Igual nas duas opções (seção 3) |

## 2. Comparação com o motor atual

Os perfis (`make_cases.py` do protótipo) e o critério de igualdade (status **e** campos faltantes por classe, nas três classes):

| Fonte | Perfis | Divergências B | Divergências A |
|---|---|---|---|
| Amostra do K2 (200 por semente, sementes 0 a 4) | 1.000 | **0** | **0** |
| A mesma amostra sem a acuidade | 1.000 | **0** | **0** |
| A mesma amostra sem o campo visual | 1.000 | **0** | **0** |
| A mesma amostra sem nenhuma medida | 1.000 | **0** | **0** |
| Varredura (limiares 1,00, 1,40, 1,50 e 2,60 de acuidade, e 10 e 40 graus de campo, cada um com −0,01, 0, +0,01 e +0,05; toda a faixa de 1,40 a 1,50 de 0,01 em 0,01; medidas faltando; valores extremos) | 351 | **0** | **0** |
| Outras deficiências (`not_applicable`) | 6 | **0** | **0** |
| **Total** | **4.357** | **0** | **0** |

A meta ("veredito idêntico nas duas opções") foi atingida **na primeira rodada completa** das duas. O que apareceu no caminho foram erros de encaixe (seção 8), não divergência de regra.

**Ressalva honesta sobre o A:** a lista de campos faltantes (`missing`) do veredito é montada pelo **script de execução** a partir das marcas `*_known`, não por uma variável do OpenFisca. Pôr isso dentro do modelo custa duas variáveis a mais (cerca de 10 linhas).

## 3. Variantes (R-6)

Duas variantes, uma por parâmetro, sobre os mesmos 4.357 perfis. O motor atual **não** faz variante sem editar código; B e A fazem, e dão **o mesmo diff**:

| Variante | Como se escreve em B | Como se escreve em A | Perfis que mudam | O que muda |
|---|---|---|---|---|
| Limite da classe 11 de 2,60 para 2,70 | `variant={"logmar_gt_11": 2.70}` | `variant(logmar_gt_11=2.70)` (uma `Reform` de cerca de 10 linhas) | **234** | classe 11 `meets`→`not_met` 128 e →`insufficient_data` 106; classes 12 e 13 ganham 12 e 37 casos `meets`, e 106 passam a `insufficient_data` |
| Leitura "o valor 2,60 pertence à classe 11" | `variant={"boundary_in_class_11": True}` | `variant(boundary_in_class_11=True)` | **29** | classe 11 `not_met`→`meets` e classe 12 `meets`→`not_met`, 29 casos cada |

A segunda variante é um **parâmetro booleano de leitura** que dois critérios usam (a classe 11 inclui o limite, a classe 12 deixa de incluí-lo). É o tipo de escolha que hoje está escondida no código do motor e na `docs/rules_coverage.md`.

Tempo de cálculo (4.357 perfis, só para dar a ordem de grandeza): **A** cerca de 0,02 a 0,05 s por variante (cálculo vetorizado); **B** cerca de 0,2 s por variante (laço em Python). Nenhuma das duas é gargalo para o diff de variantes sobre a amostra.

## 4. Linhas de código

Contagem sem linhas em branco nem comentários:

| | **B** | **A** |
|---|---|---|
| **Modelo do grupo** | `visual.yaml`: **104** (parâmetros com fonte e vigência cerca de 35, critérios e flag cerca de 30, decisão cerca de 25, testes 10) | `visual_fisca/__init__.py`: **147** (Python) + 9 arquivos de parâmetros: **49** (YAML) = **196** |
| **Maquinário reutilizável** | `rulebook.py`: **139** (o interpretador, serve para todos os grupos que cabem na linguagem) | **0** próprio, mas **22 pacotes** no ambiente (OpenFisca-Core e 10 dependências diretas: numpy, numexpr, pendulum, psutil, dpath, sortedcontainers, StrEnum, pytest…) |
| **Cola para rodar** | `run_b.py`: 34 | `run_a.py`: 57 |
| **Testes como dados** | 9 casos em 10 linhas, dentro do YAML | 4 casos em 43 linhas, em `tests/visual.yaml` |

Leitura: o **modelo do grupo** custa o mesmo em ordem de grandeza (cerca de 100 a 200 linhas). A diferença é o que essas linhas **são**: em B, dados que um revisor lê; em A, **fórmulas em Python** (numpy), que um revisor precisa ler como código.

## 5. Encaixe dos sete estados do veredito

| Estado | B | A |
|---|---|---|
| `meets`, `not_met` | Resultado de uma regra de decisão (`meets: {pick: lowest_class}`) | `Enum` de 7 valores e `np.select` na fórmula |
| `borderline` | Regra com condição (`borderline: [{class: 12, if: {flag: acuity_gap, primary_above: 12}}]`); a faixa 1,40 a 1,50 é um **flag** | Mesma lógica na fórmula, com `np.select`; o flag vira uma variável booleana |
| `insufficient_data` | Nativo: o interpretador **conhece** "medida faltando" (`all_missing`, `any_missing`) e lista os campos em `missing` | **Não há "faltando" no OpenFisca**: todo valor tem um padrão. Cada medida precisa de uma **marca `*_known`** como entrada, e a fórmula a consulta |
| `not_applicable` | Teste de `applies_to` antes de tudo | Entrada booleana `impairment_visual` |
| `needs_review`, `not_implemented` | Suportados pelo vocabulário (`STATUSES`); **o grupo visual não os usa**, então não foram exercitados | Estão no `Enum`; também não usados |

**Conclusão do encaixe:** os estados cabem nas duas, **sem forçar**. No A o custo é **estrutural** (a marca `*_known` para cada medida; o `Enum`; um `Variable` por classe, que gerei por função) e o domínio (benefício por pessoa e período) obriga a escolher uma **entidade** (`Person`) e um **período** (`YEAR`, só para o parâmetro ter data), que não significam nada no nosso problema. Em B o custo é a **linguagem de decisão**: a regra "é limítrofe em 12 só se houver faixa sem classe **e** a classe principal for maior que 12" precisou de uma condição própria (`primary_above`). Isso é o sinal de **crescimento da linguagem** (seção 10).

## 6. Rastro

**B** devolve, por critério avaliado, `{critério, classe, medida, valor, teste (com o limite já resolvido), resultado, código da razão, fonte}`. Exemplo (acuidade 1,45 e campo 35 graus):

```
acuity_12   classe 12  1,45  [1,5, 2,6]   não atende   ACUITY_IN_CLASS_RANGE   p. 14
field_13    classe 13  35    < 40         atende       FIELD_IN_CLASS_RANGE    p. 14
acuity_gap  (flag)     1,45  (1,4, 1,5)   atende       ACUITY_IN_BOOKLET_GAP   p. 14
decisão: some_class_hit
```

É praticamente o rastro do K2 (critério, valor, referência, resultado), **com código de razão e fonte**, sem camada à parte.

**A** devolve o **grafo de cálculo** (`simulation.trace = True`): para cada variável, o valor, as dependências **e os parâmetros lidos com seus valores** (por exemplo, `acuity_gap = True`, usando `visual.logmar_max_13 = 1.4` e `visual.logmar_min_12 = 1.5`). É **mais completo** em dependências (mostra até a cadeia de `primary_class`), mas é **o grafo, não o texto**: falta traduzir nome de variável em critério legível, e **não há código de razão** (R-3) nem fonte por critério na saída. Dá para chegar lá, escrevendo a conversão.

## 7. Vigência, variantes, testes como dados, status e fonte

| Requisito | B | A |
|---|---|---|
| **Vigência** (R-1, R-2) | Lista `values: [{from, to, value}]` por parâmetro; 3 linhas de código para escolher por data | **Nativa**: parâmetros por data, e o período da simulação escolhe o valor |
| **Variantes** (R-2, R-6) | Dicionário de sobreposições; diff sobre uma amostra em poucas linhas | `Reform`: nativa e idiomática |
| **Testes como dados** (R-5) | No próprio YAML, com `source` | Formato próprio do OpenFisca (`openfisca test`), um arquivo à parte; roda **pelo pytest do repositório** se chamado de dentro dele (usa o `pyproject.toml` como configuração, então convém rodar de dentro de `spikes/`) |
| **Fonte, status e revisor por critério** (R-1) | **Campos do formato**: `source`, `status` (`implemented`, `provisional`…), e dá para exigir revisor e data com um teste | Parâmetros aceitam `metadata` livre (usei `reference`); **variáveis** têm `reference`, mas **`status` implementado/provisório/revisado e revisor não existem**: seria convenção nossa |
| **Razões como código, por idioma** (R-3) | Campo `reason` por critério e por decisão; mensagens por idioma ainda a escrever | Não nativo |
| **Regra legível como dado** | Sim: o revisor (a especialista) lê o YAML | Não: as regras são **fórmulas em Python**; só os parâmetros são dado |

## 8. O que foi fácil e o que atrapalhou

**A (OpenFisca):**
- Fácil: parâmetros por data, `Reform`, o `Enum` de estados, o cálculo vetorizado, os testes em YAML e o rastro com parâmetros. A infraestrutura de variantes e de testes é **a melhor das duas**.
- Atrapalhou: (1) **não existe valor faltante** (precisei das marcas `*_known`); (2) **entidade e período** obrigatórios, sem sentido no nosso domínio; (3) o modelo é **Python vetorizado** (`np.where`, `np.select`), o que é mais difícil de ler e de revisar do que uma tabela; (4) tropeços de ambiente: a instalação teve **quedas de conexão** no `pip` (as tentativas automáticas resolveram); uma **descrição com dois-pontos** quebrou o YAML de parâmetros; criar as variáveis por função (`type(...)`) falhou até eu **tirar o `staticmethod`**; o `openfisca test` exige o nome `CountryTaxBenefitSystem` no pacote; (5) o rastro sai como grafo, sem razão em código.

**B (YAML próprio):**
- Fácil: o critério numérico do catálogo virou YAML quase literal; os sete estados **não precisaram de adaptação**; "faltando" é um conceito da linguagem; vigência, variante e testes são poucas linhas.
- Atrapalhou: **desenhar a linguagem de decisão** (a ordem das regras, "vale a classe mais comprometida", o limítrofe condicionado). Um erro meu: a primeira versão do interpretador deixou o nome do flag `acuity_gap` **fixo no código**, o que só apareceu na revisão; corrigi para vir do YAML (`reason` por item). É um exemplo do risco: **cada grupo novo tende a pedir mais um operador**.

**Tempo.** O relógio do ambiente marcou cerca de **4 minutos de execução de ferramentas** do começo ao fim, o que **não** mede o trabalho de escrever e depurar. Minha estimativa de **trabalho de uma pessoa** para este grupo: **B, 2 a 3 horas** (YAML, interpretador, testes); **A, 3 a 4 horas** (instalar, aprender o encaixe de entidade, período e `Enum`, e os tropeços acima). **É uma estimativa, não uma medição.**

## 9. Dependências e licença

| | B | A |
|---|---|---|
| Dependência nova | Nenhuma (PyYAML já está no projeto) | **OpenFisca-Core** e 10 dependências diretas obrigatórias (entre elas **pytest**, numexpr, pendulum, psutil, dpath, sortedcontainers e StrEnum); 22 pacotes no venv, contando o pip |
| **Licença** | A nossa (D22 em aberto) | **AGPL-3.0-or-later** (conferido no metadado do pacote instalado) |

**O ponto da AGPL, sem ser parecer jurídico:** a AGPL, diferentemente da GPL, tem a cláusula de **uso por rede** (seção 13): quem oferece a usuários, por uma rede, uma versão **modificada** do programa precisa oferecer o código-fonte correspondente. Se a plataforma **importar** o OpenFisca em um serviço de rede (a API), é provável que o **serviço combinado** precise de uma licença compatível com a AGPL, o que **colide com R-10 e com D18/D21** (possível uso comercial, consulta à Inova). **Não há como saber sem consultar**; é razão suficiente para **não colocar o OpenFisca no caminho do serviço** antes dessa consulta. Neste experimento isso foi respeitado: o protótipo A fica fora do pacote, do `pyproject.toml` e do CI, e nada do OpenFisca foi copiado.

## 10. Esforço para migrar todos os grupos, e a incerteza

O experimento cobre **só o visual**, o grupo mais fácil (já tem `criteria` numéricos no catálogo). Os outros **sete** grupos (baixa estatura, amputação em pé, amputação com prótese, classe 20, neuro, Petra, cadeira) **não foram modelados**; as estimativas abaixo são **extrapolações**, com incerteza alta.

| | **B** | **A** |
|---|---|---|
| Infraestrutura (uma vez) | Estender o interpretador: limites por sexo, medida derivada (a soma de estatura e braço), "a primeira classe que cabe", tabela de padrões com o par ordenado de níveis, tabelas categóricas dos funcionais: **+150 a 300 linhas** | Adaptador do `Profile` para a simulação, as marcas `*_known`, a conversão do grafo de rastro para o formato do K2 e dos códigos de razão, a decisão de licença |
| Por grupo | **1 a 2 dias** (YAML + testes, mais regressão exaustiva nos de amputação) | **1 a 2 dias** (fórmulas em Python + parâmetros + testes) |
| Ligar K2, K18 e o guarda do relatório ao novo rastro | Igual nas duas | Igual nas duas |
| **Total (uma pessoa)** | **10 a 15 dias úteis** (faixa de 7 a 25) | **12 a 18 dias úteis** (faixa de 8 a 30), **mais** a questão da AGPL, que **pode inviabilizar** a opção |

A estimativa do agente de código para o R1 (1 a 2 semanas) é **compatível com a de B** se a integração com K2 e K18 ficar para uma segunda etapa. As faixas largas refletem o que não sei: se as **tabelas funcionais** (neuro, Petra, cadeira) cabem numa linguagem de tabela sem virar uma linguagem geral.

## 11. Riscos

| Risco | B | A |
|---|---|---|
| **Crescimento da linguagem**: cada grupo pede um operador, e o interpretador vira uma linguagem mal definida | **Alto, o maior risco de B** | Não se aplica (a linguagem é o Python) |
| **Regra em código, fora do alcance de revisão** | Baixo (as regras são dado) | **Alto**: o revisor lê fórmulas numpy |
| **Licença** (AGPL no serviço de rede) | Nenhum | **Alto** até a consulta (D21) |
| **Duas implementações divergirem** na migração | Mesmo risco; mitigado pela regressão lado a lado (já feita aqui: 0 em 4.357) | Idem |
| **Dependência de um projeto externo** (versões, mudança de API, Python 3.12) | Nenhuma | Média (o pacote evolui; houve mudanças de tipos entre versões) |
| **Erro do tipo "o experimento só mostra o caso fácil"** | O visual é o mais fácil: **os grupos de amputação e os funcionais ainda podem surpreender** | Idem |

**Regra de parada proposta para B:** se o interpretador passar de **cerca de 500 linhas** ou precisar de uma **linguagem de expressões geral** (variáveis, condicionais aninhadas arbitrárias) para os grupos de amputação e funcionais, **parar e reavaliar** (A com a consulta jurídica feita, ou C).

## 12. Recomendação

**Opção B**, nas ideias do OpenFisca (parâmetros por data, variantes como reformas, testes como dados, rastro por critério), pelos dados:

1. **Equivalência provada nas duas**: a escolha **não** depende de uma opção não conseguir reproduzir o motor.
2. **Regras como dado revisável** (R-1, R-3, R-4): em B são campos do formato; em A são convenções nossas sobre fórmulas em Python.
3. **Licença** (R-10): B não tem pendência; A depende de uma consulta que ainda não foi feita e que **pode** barrar o uso em serviço.
4. **O custo do modelo do grupo é igual em ordem de grandeza**; A ganha em infraestrutura pronta (vigência, `Reform`, testes, tracer), e isso é real: se a AGPL deixar de ser um problema, **A volta à mesa**.

**O que eu faria antes de adotar B:** (a) a etapa 2 do desenho (**baixa estatura**), porque ela testa a linguagem (limite por sexo, soma, ordem) **antes** de comprometer os grupos grandes; (b) a **regra de parada** da seção 11; (c) uma **consulta curta sobre a AGPL** em paralelo, só para saber se A é uma opção real.

## 13. O que não foi verificado

- **Só um grupo** (o visual, o mais fácil). Baixa estatura, amputação, classe 20 e os funcionais **não** foram modelados; as estimativas da seção 10 são extrapolação.
- **`needs_review` e `not_implemented`** não são usados pelo grupo visual; o interpretador B os aceita como vocabulário, mas **não foram exercitados**.
- O **tempo** da seção 8 é estimado, não medido; o relógio do ambiente não mede o trabalho de escrita.
- **A AGPL** foi lida pelo metadado do pacote e por conhecimento geral, **não** por parecer jurídico.
- O A foi rodado **só no Windows com Python 3.12** e com a versão 46.0.1 do OpenFisca-Core; não testei outras versões nem Linux.
- Não verifiquei se o OpenFisca tem recurso próprio para **valor faltante** além das marcas que usei (não encontrei na leitura do pacote instalado e na API que usei); pode haver um padrão da comunidade que eu não conheço.
- O **rastro em A** foi inspecionado no formato bruto; a conversão para o formato do K2 **não foi escrita**.
- A **migração lado a lado** (rodar o interpretador B dentro da API, no lugar do motor) **não foi tentada**: fora do escopo do experimento.
