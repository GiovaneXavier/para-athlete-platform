# Desenho: regras como código (K20)

**Rascunho v0, de 24/10/2026, escrito pela sessão de arquitetura. É só desenho: nada foi implementado e nenhuma escolha está tomada.** A adoção é da onda 2 e junta-se ao R1 do backlog. A escolha do formato (ADR-1) **é uma decisão do usuário**, que será consultado antes da adoção. Fontes: o código atual (lido pelo agente de código da matéria e por mim), as páginas e resumos do OpenFisca e do Catala (busca de 24/10/2026; **não li a documentação a fundo**).

## 1. Problema

Hoje as regras do atletismo estão em **dois lugares**: critérios numéricos em `rules/classes.yaml` (visual, baixa estatura) e **tabelas de decisão em Python** (`functional.py`, `limb.py`, `sensory.py`). As razões do motor são **textos em inglês**, sem critério, valor e resultado estruturados. Isso cria quatro dores:

1. **Não há versão nem vigência.** A WPA revisa suas regras (revisão aberta em set/2023); o texto de 2023 implementa o Código de 2015; o livreto do CPB (2024) diverge em pontos (classe 20: início aos 22 ou aos 18 anos). Hoje trocar uma leitura exige editar código.
2. **Não há fonte por critério** (documento, versão, página) nem **revisor e data**.
3. **Não há rastro por critério.** O modo educação (K2) e o guia (K18) tiveram de **reconstruir** o rastro em camada à parte, com teste de consistência.
4. **O guarda do relatório** procura as razões em inglês no texto (frágil).

## 2. O que as boas referências fazem (resumo, a confirmar)

| Ideia | Onde aparece | Valor para nós |
|---|---|---|
| **Variáveis** com fórmula, rótulo, **referência** à norma | OpenFisca | Cada critério com fonte |
| **Parâmetros com valores por data** | OpenFisca | Vigência: limite por período e por fonte |
| **Testes como dados** (YAML) | OpenFisca | Casos de teste ligados ao artigo da norma |
| **Reformas** (mudar regras sem editar o código-base) | OpenFisca | Variantes: `cpb-2024`, `wpa-2023`, `variante-do-estudo` |
| **Rastreador** (valores e subcálculos) | OpenFisca | O rastro por critério, nativo |
| **API web** de cálculo | OpenFisca | Triagem como serviço |
| **Exceções explícitas e prioridade** entre regras | Catala | Regras de "vale a mais comprometida" e "limítrofe" |
| **Verificação formal** do compilador | Catala | Confiança, mas custo alto para a equipe |

**O OpenFisca é AGPL.** Reaproveitar o framework pesa em uso comercial (D18) e pede cuidado.

## 3. Requisitos (o que o livro de regras tem de dar)

| # | Requisito | Origem |
|---|---|---|
| R-1 | Cada **critério** tem: fonte (documento, versão, página), **vigência** (início e fim), **status** (`implementado`, `provisório`, `contestado`, `revisado`), revisor e data | `03` módulo R |
| R-2 | **Variantes** de fonte selecionáveis (`cpb-2024`, `wpa-2023`, a próxima) e **parâmetros** (por exemplo, a idade de início da classe 20) | Divergência da classe 20 |
| R-3 | **Razões como códigos** com valores e tradução por idioma (pt, en, es) | Guarda do relatório, K2, K18 |
| R-4 | **Rastro por critério** (critério, valor, resultado) em toda avaliação | K2, K18, K11 |
| R-5 | **Casos de teste como dados**, cada um ligado ao critério e à fonte | Testes de propriedade |
| R-6 | **Diff entre variantes** sobre uma amostra de perfis (quantos mudam de classe e por quê) | E6, auditoria (P5) |
| R-7 | **Mesmo veredito do motor atual** nos perfis existentes (regressão) | Segurança da migração |
| R-8 | **Estados do veredito** preservados (`meets`, `borderline`, `needs_review`, `insufficient_data`, `not_met`, `not_applicable`, `not_implemented`) | O motor atual e o gerador de rótulos |
| R-9 | **Sem dependência de dado de pessoa** | Princípios |
| R-10 | Licença compatível com o uso do projeto, inclusive um possível uso comercial (D18, D21) | AGPL do OpenFisca |

## 4. Três opções

| Opção | O que é | Prós | Contras |
|---|---|---|---|
| **A. Adotar o OpenFisca** | Escrever as regras como variáveis e parâmetros do OpenFisca e usar o motor dele | Padrão maduro; vigência, testes, reformas, rastro e API **prontos**; há uso público em governos | **AGPL**; o domínio dele é **cálculo de benefícios por entidade e período**, não **classificação por perfil com status tri-valorados** (limítrofe, especialista, dados insuficientes): **encaixe incerto**; dependência grande; curva de aprendizado |
| **B. Livro de regras próprio em YAML**, com um interpretador pequeno, inspirado no OpenFisca | Critérios, parâmetros com vigência, variantes e testes em **dados**; um interpretador Python de ~algumas centenas de linhas que dá o **veredito e o rastro** | **Controle total** dos estados do veredito; **licença nossa**; migração **incremental** por grupo; o que já existe (`criteria` no YAML) é o começo | Trabalho nosso (R1 do backlog, estimado em 1 a 2 semanas pelo agente de código); **sem** verificação formal; é preciso testar bem |
| **C. Catala** | Escrever as regras na linguagem de leis do Inria | **Exceções e prioridades** explícitas; compilador com provas; **correspondência parágrafo a parágrafo** com a norma | Linguagem **nova** para a equipe; ecossistema pequeno; integração com Python e com os estados do veredito a estudar; **não** li a documentação a fundo |

## 5. Recomendação (a confirmar com o usuário antes da adoção)

**Opção B**, **modelada nas ideias do OpenFisca** (variáveis, parâmetros com vigência, testes como dados, variantes como "reformas", rastreador), por estas razões: (1) o domínio é **classificação com status tri-valorados**, e o controle dos estados é essencial; (2) **sem AGPL**, a licença fica livre; (3) a **migração é incremental**: começa pelo que já é YAML; (4) o rastro e os testes que o K2 e o K18 construíram viram a **fundação dos testes de regressão**. Antes de fechar, **um experimento curto** (um dia): modelar **visual (11 a 13)** no OpenFisca e na opção B, e comparar o esforço e o encaixe dos estados `borderline` e `insufficient_data`. **Isso pode mudar a recomendação.**

## 6. Esboço da opção B

### 6.1 Estrutura de arquivos (proposta)

```
rulebook/
  sources.yaml                 documentos: id, título, versão, data, página/URL (citável)
  variants/cpb-2024.yaml       qual versão de cada critério vale nesta variante
  groups/visual.yaml           critérios, parâmetros e testes do grupo
  groups/short_stature.yaml
  groups/limb_standing.yaml    tabela de níveis como dados
  groups/limb_prosthesis.yaml
  messages/pt.yaml             textos por código de razão
  messages/en.yaml
```

### 6.2 Um critério (exemplo ilustrativo; os números vêm do catálogo, não são decisão)

```yaml
criterion: visual.acuity.class_12
source: {doc: cpb-booklet-2024, page: 14}
status: implemented            # implemented | provisional | contested | reviewed
valid: {from: 2024-01-01, to: null}
parameters:
  logmar_min: 1.50
  logmar_max: 2.60
test:
  - {input: {logmar_best_eye: 2.00}, expect: meets, tag: inside}
  - {input: {logmar_best_eye: 2.61}, expect: not_met, tag: just_outside}
reason: VISUAL_ACUITY_IN_RANGE
```

### 6.3 Veredito e rastro

O interpretador avalia critérios na ordem declarada, produz o **veredito por classe** (com os mesmos sete estados do motor atual) e uma **lista de passos** `{criterion, value, result, reason_code, source}`, **de onde o texto sai por código e idioma**. O **rastro dos grupos numéricos** que o K2 e o K18 montam em camada à parte passa a **sair do interpretador**, e o teste de consistência passa a testar o interpretador contra o motor antigo (R-7).

### 6.4 Variantes e diff

Uma variante é um **conjunto de escolhas** (qual versão de cada critério vale, qual valor de cada parâmetro). O **diff** executa **duas variantes** sobre uma **amostra** de perfis (o gerador) e relata **quantos mudam de classe, por grupo e por critério**. Isso responde, em segundos, a "o que muda se a WPA mudar a idade de início da classe 20 de 22 para 18?", **desde que o perfil guarde a idade** (R12 do backlog).

### 6.5 Migração incremental

| Etapa | O que migra | Verificação |
|---|---|---|
| 0 | Esqueleto: `sources.yaml`, formato dos critérios, interpretador mínimo | Testes do interpretador |
| 1 | **Visual** (já tem `criteria` no YAML) | Veredito idêntico ao motor em amostras e em varredura de limiares |
| 2 | **Baixa estatura** | Idem |
| 3 | **Amputação** (tabela de níveis como dados) | **Exaustivo**: as 144 combinações, como no K2 |
| 4 | **Classe 20** com idade como parâmetro (depende de R12) | Variantes 18 e 22 |
| 5 | **Grupos provisórios** (neuro, Petra, cadeira) | Marcados `provisório`; revisão da especialista |

**Regra:** a cada etapa, o motor **antigo** e o **novo** rodam lado a lado até a regressão (`meets` e `status` idênticos nas amostras) ficar limpa; só então o antigo sai.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| **Duas implementações divergirem** durante a migração | Regressão automática lado a lado; sem remover o antigo antes da limpeza |
| **Alterar a linha matéria sem querer** | A migração acontece **na plataforma**; qualquer mudança no núcleo da matéria passa pelo agente de código dela |
| **Formato não comportar um caso** (as tabelas funcionais, exceções) | Etapas por grupo; o experimento de 1 dia antes de fechar |
| **Confundir "implementado" com "validado"** | O campo `status` e os avisos; só `reviewed` com revisor e data |
| **Esforço maior que o estimado** | A estimativa de 1 a 2 semanas é do agente de código para o R1; **revisar** depois do experimento |
| **AGPL** (se escolher A) | Tratar antes de qualquer uso comercial (D21, Inova) |
| **Dependência de R12** (campo de idade) para a classe 20 | Planejar R12 junto, em lockstep com o esquema do perfil |

## 8. Decisões pendentes (para o usuário, antes da adoção)

1. **Formato:** B (recomendado), A ou C? (ADR-1)
2. **Experimento de um dia** (OpenFisca contra B) antes de fechar? **Recomendo sim.**
3. **Quando:** na onda 2, junto do R1 e do R12, como planejado.
4. **Quem executa:** a sessão de código da plataforma, sob revisão da arquitetura.

## 9. Fontes e limites

OpenFisca (descrição pública da API Python: variáveis, parâmetros por instante, testes em YAML, reformas, API web, rastreador, licença AGPL); Catala (artigo do ICFP 2021: exceções explícitas, correspondência com a lei, provas do compilador); o código atual do projeto. **Não** li a documentação do OpenFisca a fundo, **não** testei nenhum dos dois, e **não** estimei esforço além do que o agente de código disse para o R1.
