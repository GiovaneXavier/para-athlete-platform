# Relatório via LLM

## Princípio

**A LLM não decide a classe.** Ela só redige o texto a partir de fatos que o sistema já calculou: o perfil informado, o veredito das regras e as probabilidades do MLP. Isso evita que um modelo de linguagem invente critérios de elegibilidade, e permite verificar o texto automaticamente.

```
perfil ──> regras ──┐
                    ├──> contexto (fatos) ──> LLM ──> verificação ──> relatório
perfil ──> MLP ─────┘                           │          │ falhou 2 vezes
                                                │          └──> relatório de referência (template)
                                                └── rascunho devolvido com os problemas listados (1 retentativa)
```

## Módulos

| Arquivo | Papel |
|---|---|
| [context.py](../src/para_triage/report/context.py) | Monta os fatos: dados informados, classes candidatas com probabilidade, veredito e motivo das regras, provas, equipamentos, dados que faltam e alertas |
| [prompt.py](../src/para_triage/report/prompt.py) | Prompt de sistema, texto dos fatos, **relatório de referência** (template) e verificação de fidelidade |
| [client.py](../src/para_triage/report/client.py) | Cliente do Ollama (só biblioteca padrão) |
| [generate.py](../src/para_triage/report/generate.py) | Gera com a LLM, verifica, retenta uma vez e cai no template se necessário |
| [cli.py](../src/para_triage/report/cli.py) | `python -m para_triage.report.cli perfil.json` |
| [predict.py](../src/para_triage/models/predict.py) | Carrega o checkpoint do MLP e devolve probabilidades |

## O que o relatório contém

Sete seções fixas: Resumo, Classes prováveis, Provas sugeridas, Equipamentos, Dados que faltam ou são incertos, Próximos passos e Aviso. O aviso diz que o relatório é uma triagem e não substitui a classificação oficial.

Alertas que entram no relatório quando se aplicam:

- regras e modelo apontam classes diferentes;
- as regras não conseguiram decidir com os dados informados (o resultado vem só do modelo);
- confiança baixa na classe mais provável, ou chance relevante (≥ 25%) de caso ambíguo;
- parte dos casos exige avaliação de especialista.

Quando o modelo vê mais chance de "caso ambíguo" do que de qualquer classe, o resumo começa dizendo que o perfil é limítrofe, em vez de destacar uma classe de baixa probabilidade.

## Verificação de fidelidade

Um rascunho é rejeitado se:

1. faltar alguma das sete seções, repetir ou esvaziar uma seção, ou pô-las fora de ordem;
2. citar um código de classe (T44, F54…) ou "classe NN" que não foi fornecido;
3. citar uma porcentagem que não corresponde (com 1 ponto de tolerância) a nenhuma probabilidade fornecida;
4. o aviso não disser que o texto não substitui a classificação oficial.

Na primeira rejeição, o rascunho volta ao modelo com os problemas listados. Na segunda, o sistema usa o relatório de referência, que passa na verificação por construção (há um teste para isso). O resultado informa a fonte (`llm` ou `template`), o número de tentativas e os problemas.

## O que se observou com o `qwen2.5:7b`

Nos 6 perfis de [report_examples.md](report_examples.md), com todas as verificações: **4 passaram na primeira tentativa**, **1 só na segunda** (o primeiro rascunho se contradizia: listava classes e depois dizia "nenhuma classe candidata") e **1 caiu no relatório de referência** (duas vezes seguidas com o Aviso duplicado). Um modelo de 7B em CPU erra a estrutura com frequência, e é por isso que a verificação e o relatório de referência existem. Vale reportar essa taxa no artigo e comparar com modelos maiores.

## O que a verificação **não** pega

Ela garante que o texto não cita classes nem probabilidades inventadas. Não garante que cada frase esteja certa. Um erro de **fato** nas entradas passa direto: durante o desenvolvimento, o valor `NONE` da função das pernas foi traduzido como "sem comprometimento", quando significa "sem função", e o relatório de uma lesão medular dizia que as pernas não tinham comprometimento. Foi corrigido, e há um teste para que toda escala tenha tradução própria. Por isso a avaliação qualitativa por especialista continua necessária.

## Avaliação qualitativa sugerida (plano de trabalho, seção 7)

Para uma especialista ou um especialista da área, por relatório, em escala de 1 a 5: clareza, coerência com o perfil, precisão técnica, adequação ao leitor e cautela (não promete classificação). Os exemplos de [report_examples.md](report_examples.md) servem de primeiro material. Vale comparar o texto da LLM com o relatório de referência (`--no-llm`).

## Limitações

- Um relatório leva de 1 a 6 minutos com `qwen2.5:7b` em CPU, conforme a carga da máquina (medimos de 67 s a 578 s). Em GPU seria bem mais rápido.
- O texto de "Próximos passos" é fixo e genérico.
- As traduções das razões das regras (em inglês no motor) ficam a cargo da LLM.
- As provas e equipamentos vêm do catálogo, que ainda não foi validado (ver [rules_coverage.md](rules_coverage.md)).
- Os perfis de exemplo em `examples/` são fictícios.
