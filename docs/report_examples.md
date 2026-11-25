# Exemplos de relatórios gerados

Gerados com `qwen2.5:7b` (Ollama, temperatura 0,2) sobre os perfis de `examples/`, com as probabilidades do MLP treinado em `synthetic_v1`.

| Exemplo | Fonte | Tentativas | Tempo (s) |
|---|---|---|---|
| combined_deficiency | llm | 1 | 352 |
| hemiplegia_standing | llm | 1 | 285 |
| prosthesis_below_knee | template | 2 | 459 |
| short_stature_incomplete | llm | 1 | 207 |
| visual_borderline | llm | 2 | 540 |
| wheelchair_t10 | llm | 1 | 290 |

## combined_deficiency

*Fonte: llm; tentativas: 1.*

## Resumo
O caso apresenta deficiência em membros superiores e inferiores, mas não há classes candidatas de acordo com as regras fornecidas. O perfil é considerado limítrofe, com 100% de chance de ser um caso ambíguo. A avaliação presencial de um especialista é necessária para determinar a classe apropriada.

## Classes prováveis
Nenhuma classe candidata.

## Provas sugeridas
Nenhuma prova a sugerir.

## Equipamentos
Nenhum equipamento a indicar.

## Dados que faltam ou são incertos
Nenhum dado relevante em falta.

## Próximos passos
Procurar um Centro de Referência do CPB ou um classificador para a avaliação presencial oficial. Levar os laudos e exames disponíveis (por exemplo, oftalmológico, neurológico ou testes de QI, conforme o caso) e confirmar as medidas com instrumentos padronizados.

## Aviso
Este relatório é uma triagem automática de apoio. Ele não substitui a classificação esportiva oficial, feita presencialmente por classificadores do CPB e da World Para Athletics.

## hemiplegia_standing

*Fonte: llm; tentativas: 1.*

## Resumo
O atleta apresenta hipertonia e hemiplegia devido a uma lesão encefálica, com gravidade funcional moderada. A competição será realizada em pé, sem a utilização de próteses. As classes mais prováveis são a T37/F37, com uma probabilidade de 97%, e a T35/F35, com 2%. A triagem automática indica que a classe T37/F37 é a mais adequada, de acordo com os critérios estabelecidos.

## Classes prováveis
1. **Classe T37/F37** - Hemiplegia (em pé) - **97% de probabilidade**
   - **Provas**: Corridas e saltos (T37) / Arremessos e lançamentos (F37)
   - **Equipamentos**: Nenhum específico

2. **Classe T35/F35** - Diplegia leve (em pé) - **2% de probabilidade**
   - **Provas**: Corridas (T35) / Arremessos e lançamentos (F35)
   - **Equipamentos**: Nenhum específico

## Provas sugeridas
- **Corridas e saltos** (T37)
- **Arremessos e lançamentos** (F37)
- **Corridas** (T35)
- **Arremessos e lançamentos** (F35)

## Equipamentos
- **Nenhum específico** para as classes T37/F37 e T35/F35.

## Dados que faltam ou são incertos
- Não há dados relevantes em falta.

## Próximos passos
Procurar um Centro de Referência do CPB ou um classificador para a avaliação presencial oficial. Levar os laudos e exames disponíveis (por exemplo, oftalmológico, neurológico ou testes de QI, conforme o caso) e confirmar as medidas com instrumentos padronizados.

## Aviso
Este relatório é uma triagem automática de apoio. Ele não substitui a classificação esportiva oficial, feita presencialmente por classificadores do CPB e da World Para Athletics.

## prosthesis_below_knee

*Fonte: template; tentativas: 2.*

Problemas detectados no rascunho do LLM:

- `duplicate_section`: a seção '## Aviso' aparece 2 vezes; use uma só

## Resumo
Com base nos dados informados, a classe mais provável é a 64 (T64 / F64), com probabilidade estimada de 97%: Amputação unilateral abaixo do joelho (prótese).
As regras da cartilha e o modelo apontam a mesma classe.

## Classes prováveis
- **T64 / F64** — Amputação unilateral abaixo do joelho (prótese). Probabilidade estimada: 97%. Pelas regras: atende aos critérios.
- Outras possibilidades do modelo: nenhuma classe elegível (0%); caso ambíguo (2%).

## Provas sugeridas
- T64: corridas e saltos (classe 64)
- F64: arremessos e lançamentos (classe 64)

## Equipamentos
- prótese de corrida

## Dados que faltam ou são incertos
- Nenhum ponto em aberto.

## Próximos passos
Procurar um Centro de Referência do CPB ou um classificador para a avaliação presencial oficial. Levar os laudos e exames disponíveis (por exemplo, oftalmológico, neurológico ou testes de QI, conforme o caso) e confirmar as medidas com instrumentos padronizados.

## Aviso
Este relatório é uma triagem automática de apoio. Ele não substitui a classificação esportiva oficial, feita presencialmente por classificadores do CPB e da World Para Athletics.

## short_stature_incomplete

*Fonte: llm; tentativas: 1.*

## Resumo
A atleta, uma mulher com baixa estatura, compete em pé sem a utilização de próteses. O modelo de classificação indica fortemente a possibilidade de ela se encaixar na classe F41, com uma probabilidade de 90%. A classe F40, mais severa, tem uma probabilidade de apenas 6%. No entanto, a falta de medidas adicionais, como o comprimento do braço mais longo, pode afetar a precisão da classificação.

## Classes prováveis
1. **F41** - Baixa estatura (90% de probabilidade)
2. **F40** - Baixa estatura (mais severa) (6% de probabilidade)

## Provas sugeridas
- **F41: arremessos e lançamentos**

## Equipamentos
- **Nenhum específico**

## Dados que faltam ou são incertos
- **Comprimento do braço mais longo (cm)**

## Próximos passos
Procurar um Centro de Referência do CPB ou um classificador para a avaliação presencial oficial. Levar os laudos e exames disponíveis (por exemplo, oftalmológico, neurológico ou testes de QI, conforme o caso) e confirmar as medidas com instrumentos padronizados.

## Aviso
Este relatório é uma triagem automática de apoio. Ele não substitui a classificação esportiva oficial, feita presencialmente por classificadores do CPB e da World Para Athletics.

## visual_borderline

*Fonte: llm; tentativas: 2.*

## Resumo
O atleta apresenta deficiência visual com acuidade visual de 1.45 logMAR e campo visual de 80.0 graus. O modelo estimou uma probabilidade de 24% para a classe T12/F12 e 7% para a classe T13/F13, ambas classificadas como casos limítrofe. A confiança do modelo na classe mais provável é baixa, e o perfil é considerado limítrofe, com 68% de chance de caso ambíguo.

## Classes prováveis
1. **Classe 12 (T12/F12) - Deficiência visual - perda visual intermediária**
   - **Probabilidade estimada pelo modelo:** 24%
   - **Regras da cartilha:** Caso limítrofe, pois a acuidade visual de 1.45 logMAR está entre os limites das classes 12 e 13.
   - **Provas:** Corridas e saltos (T12); Arremessos e lançamentos (F12).
   - **Equipamentos:** Guia-corredor (opcional).

2. **Classe 13 (T13/F13) - Deficiência visual - perda visual leve**
   - **Probabilidade estimada pelo modelo:** 7%
   - **Regras da cartilha:** Caso limítrofe, pois a acuidade visual de 1.45 logMAR está entre os limites das classes 12 e 13.
   - **Provas:** Corridas e saltos (T13); Arremessos e lançamentos (F13).
   - **Equipamentos:** Nenhum específico.

## Provas sugeridas
- Corridas e saltos (T12)
- Arremessos e lançamentos (F12)
- Corridas e saltos (T13)
- Arremessos e lançamentos (F13)

## Equipamentos
- Guia-corredor (opcional para T12)

## Dados que faltam ou são incertos
- Não há dados relevantes em falta.

## Próximos passos
Procurar um Centro de Referência do CPB ou um classificador para a avaliação presencial oficial. Levar os laudos e exames disponíveis (por exemplo, oftalmológico, neurológico ou testes de QI, conforme o caso) e confirmar as medidas com instrumentos padronizados.

## Aviso
Este relatório é uma triagem automática de apoio. Ele não substitui a classificação esportiva oficial, feita presencialmente por classificadores do CPB e da World Para Athletics.

## wheelchair_t10

*Fonte: llm; tentativas: 1.*

## Resumo
O atleta apresenta um déficit de força muscular, com função preservada nos braços e mão, mas com função parcial no tronco e sem função nas pernas. As classes mais prováveis, conforme o modelo, são a T54/F55 (85% de probabilidade) e a T53/F54 (14% de probabilidade).

## Classes prováveis
1. **Classe T54/F55 (85% de probabilidade)**
   - **Descrição**: Lesão toracolombar T8-L1, com tronco parcial ou total e quadril limitado.
   - **Provas**: Corridas (T54) e arremessos e lançamentos (F55).
   - **Equipamentos**: Cadeira de corrida, banco ou cadeira de arremesso.

2. **Classe T53/F54 (14% de probabilidade)**
   - **Descrição**: Lesão medular T1-T7, com braços preservados e sem função no tronco.
   - **Provas**: Corridas (T53) e arremessos e lançamentos (F54).
   - **Equipamentos**: Cadeira de corrida, banco ou cadeira de arremesso.

## Provas sugeridas
- **Corridas (T54)**: Para avaliar a função do tronco e a capacidade de movimentação dos membros inferiores.
- **Arremessos e lançamentos (F55)**: Para avaliar a força e a precisão dos braços e mãos.

## Equipamentos
- Cadeira de corrida
- Banco ou cadeira de arremesso

## Dados que faltam ou são incertos
- Não há dados relevantes em falta.

## Próximos passos
Procurar um Centro de Referência do CPB ou um classificador para a avaliação presencial oficial. Levar os laudos e exames disponíveis (por exemplo, oftalmológico, neurológico ou testes de QI, conforme o caso) e confirmar as medidas com instrumentos padronizados.

## Aviso
Este relatório é uma triagem automática de apoio. Ele não substitui a classificação esportiva oficial, feita presencialmente por classificadores do CPB e da World Para Athletics.
