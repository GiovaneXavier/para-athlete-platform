# Cobertura das regras (v1)

Fontes: Cartilha CPB de Atletismo (jan/2024) e lista de classes e provas do Lexi (`lexi.global/sports/athletics`). As páginas individuais de cada classe no Lexi **ainda não foram conferidas**.

## Classes (33)

| Grupo | Classes | Estado | Origem dos critérios |
|---|---|---|---|
| Visual | 11, 12, 13 | implementado | numéricos (LogMAR, campo visual) |
| Intelectual | 20 | implementado | numérico (QI ≤ 75) + 2 critérios booleanos |
| Baixa estatura | 40, 41 | implementado | numéricos (estatura, braço, soma; por sexo) |
| Membros, em pé, sem prótese | 42-47 | parcial | níveis de amputação; força/ADMP/diferença de perna só para o tornozelo (T44) |
| Membros, com prótese | 61-64 | implementado | níveis de amputação |
| Encefálicos | 31-38 | **provisório** | perfil funcional qualitativo, em tabela de decisão |
| Petra | 71-72 | **provisório** | perfil funcional qualitativo |
| Cadeira e arremesso sentado | 51-57 | **provisório** | perfil funcional (função de braço, tronco e perna) |

"Provisório" quer dizer: a cartilha descreve essas classes só em texto, e as tabelas de decisão em [functional.py](../src/para_triage/rules/evaluators/functional.py) são a minha leitura. Devem ser substituídas ou refinadas com a matriz da especialista.

## Número de classe: T e F coincidem, exceto nas classes de cadeira

Nos grupos 11-47 e 61-72, as classes T e F têm o mesmo perfil funcional, e o modelo prevê o número da classe. **Nas classes de cadeira os números diferem.** Pela descrição da cartilha:

| Classe F (usada no modelo) | Classe T equivalente |
|---|---|
| F51 (C5-C6) | T51 |
| F52 (C7) | T52 |
| F53 (C8) | T52 |
| F54 (T1-T7, sem tronco) | T53 |
| F55, F56, F57 | T54 |

Por isso as classes 51-57 do catálogo são as **classes F**, e `track_equivalent` indica a classe T. Exemplo: `class_codes(54)` devolve `("T53", "F54")`. Essa equivalência é inferência minha a partir das descrições, não uma tabela da cartilha, e deve ser confirmada.

## Decisões de interpretação que precisam de validação

Grupos já descritos na versão anterior:

1. **T11:** a cartilha escreve "menor que LogMAR 2.60". Interpretei como acuidade *pior* que 2.60 (logMAR > 2.60). O valor 2.60 exato cai na T12 ("até 2.60").
2. **Lacuna logMAR entre 1.40 e 1.50:** T13 vai até 1.40 e T12 começa em 1.50. Valores intermediários saem como `borderline` entre 12 e 13.
3. **Visual, medida única:** com só acuidade ou só campo, a classe é atribuída com aviso de que a medida faltante pode indicar classe mais comprometida.
4. **Baixa estatura:** os três limites são conjuntivos. A soma costuma ser o limite que decide (ex.: 130 cm + 59 cm = 189 > 180). Quem atende T40 recebe T40, mesmo atendendo também T41.
5. **Membros superiores (45-47):** `ELBOW_OR_ABOVE` nos dois lados → T45; um lado → T46; punho nos dois lados → T46; cotovelo + punho → `borderline` 45/46; punho em um lado → T47.
6. **Membros inferiores em pé (42-44):** acima do joelho unilateral → T42; abaixo do joelho bilateral → T43; abaixo do joelho unilateral → T44. Combinações com pé parcial ou acima do joelho bilateral em pé viram `borderline` ou `needs_review`.
7. **Pé parcial (Lisfranc):** a cartilha cita como critério mínimo na F57. Tratei como `borderline` para T44, sem confirmação.
8. **Prótese (61-64):** acima + abaixo do joelho (um de cada lado) fica `borderline` entre 61 e 62. A cartilha não define esse caso.
9. **Deficiências combinadas** (membro superior e inferior): `needs_review`.
10. **Critérios de tornozelo (T44 e F57):** força grau ≤ 2 na flexão plantar, arco passivo ≤ 10° ou diferença de 7 cm entre os membros inferiores. O limiar de 7 cm vem da F57; confirmar para a T44.
11. **Déficit de quadril/joelho (T42):** exige avaliação técnica; o motor só sinaliza `borderline`.
12. **Força e ADMP de membros superiores (T45-T47):** não implementados.

Novos, nos grupos provisórios:

13. **Encefálicos sentados (31-34):** a classe vem de como o atleta propulsiona a cadeira de corrida: pés → 31; braços com comprometimento → 32; braços assimétricos ou com pouca potência → 33; braços simétricos e potentes → 34. A classe 34 só vale para hipertonia com diplegia; outros casos viram `borderline` entre 33 e 34. Comprometimento leve sentado vira `needs_review`.
14. **Encefálicos em pé (35-38):** gravidade leve → 38 (leve com diplegia → `borderline` 35/38); moderada: atetose ou ataxia → 36, hemiplegia → 37, diplegia → 35; tipos mistos → `borderline` com a 36; quadriplegia ou triplegia em pé e gravidade severa → `needs_review`.
15. **Descritores novos:** gravidade funcional (nenhuma, leve, moderada, severa), distribuição da paralisia cerebral e padrão de propulsão. Não aparecem como escalas na cartilha; são rótulos que reduzem o texto a algo que o profissional preenche. A especialista deve dizer se existem escalas melhores.
16. **Petra (71-72):** exige gravidade moderada ou severa; transferir-se sozinho para a Petra → 72, não → 71. Respostas contraditórias (não transfere mas caminha distâncias curtas; transfere mas precisa de amarração de tronco) → `borderline` 71/72.
17. **Cadeira (51-57):** função de braço (déficit de ombro e cotovelo → 51; déficit de dedos → 52; só musculatura intrínseca da mão → 53; preservada) e de tronco (nenhuma, parcial, total). Com braços preservados: sem tronco → 54; com tronco, pernas limitadas a flexores de quadril → 55; quadril e joelho parciais → 56; nível do tornozelo → 57. Déficit de braço com função de tronco é uma combinação que a cartilha não descreve (`needs_review`).
18. **F55-F57 e amputação:** a cartilha cita amputação bilateral de quadril (F55), amputação unilateral de quadril ou bilateral alta com cotos curtos (F56) e transfemoral/transtibial (F57). Esses casos **não** têm campos próprios; hoje entram só pelo descritor de função da perna.
19. **Nível medular:** os níveis (C5-C6, C7, C8, T1-T7, T8-L1, L2-L4) aparecem na cartilha como "normalmente", e não como critério. O modelo usa a função, não o nível.

## Eventos e equipamentos

A tabela de provas por classe vem da cartilha e da lista do Lexi, e **não foi validada**. Pontos incertos:

- Salto: incluí 11-13, 20, 36-38, 42, 44-47, 61-64. A cartilha afirma que T45 e T46 podem competir em todas as corridas e saltos, e que T47 só em velocidade (100-400 m) e saltos.
- T40 e T41 não têm provas de pista (a cartilha cita apenas arremessos e lançamentos).
- Guia: T11 `guide_runner`, T12 opcional, T13 nenhum. Confirmar nas regras da World Para Athletics.
- F31 só lança club, e F32 não lança dardo (só peso, disco e club), segundo a cartilha. Restrições por prova ainda não estão no catálogo.
- Junções de classe em competições (ex.: F51/F52/F53 feminino em Paris 2024) não estão modeladas.

## Próximos passos

1. Receber a matriz classe × critério × variável da especialista e substituir as tabelas de decisão provisórias (itens 13-19).
2. Validar a equivalência T/F das classes de cadeira e a lista de provas nas páginas do Lexi.
3. Campos próprios para amputação de quadril e força muscular por articulação (classes 55-57 e 45-47).
4. Restrições por prova no catálogo.
