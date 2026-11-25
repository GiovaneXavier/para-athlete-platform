# Dados sintéticos (v0)

## Como funciona

```
amostrador (perfil verdadeiro) ──> motor de regras ──> label
        │
        └──> ruído de medida + campos faltantes ──> perfil observado ──> features do modelo
                                                          │
                                                          └──> motor de regras ──> rule_label (baseline)
```

O **label** vem do motor de regras aplicado ao perfil verdadeiro. As **features** são o perfil observado, com erro de medida e campos que o profissional não preencheu. Assim o modelo não recebe a resposta de graça: perto dos limiares, a mesma observação pode vir de classes diferentes, e o modelo precisa devolver probabilidades.

A coluna `rule_label` é a predição do motor de regras sobre o perfil observado, isto é, o **baseline de regras sob o mesmo ruído**. Ela permite comparar regras × MLP sem recalcular.

## Códigos de label

| Valor | Significado |
|---|---|
| 11 … 72 | número da classe (T e F compartilham o número, exceto nas classes de cadeira, onde vale o número F; ver [rules_coverage.md](rules_coverage.md)) |
| 0 | nenhuma classe elegível |
| -1 | ambíguo (`borderline` ou `needs_review`); a coluna `candidates` lista as classes possíveis |
| -2 | só em `rule_label`: as regras se abstêm (dados insuficientes) |

## Geração

```bash
python -m para_triage.data.generate --n-per-label 300 --out data/processed/synthetic_v1.csv
python -m para_triage.data.generate --no-noise   # medidas exatas, sem faltantes
```

O conjunto é balanceado: `n-per-label` linhas para cada label de cada grupo. As proporções reais não são essas; para estudar prevalência, reamostre depois.

Grupos cobertos (nome da coluna `group`): `visual`, `intellectual`, `short_stature`, `limb_standing`, `limb_prosthesis`, `neuro_seated`, `neuro_standing`, `frame_runner` (Petra) e `wheelchair` (classes 51-57). Os amostradores concentram cerca de 40% dos valores em faixas estreitas ao redor dos limiares, para ter muitos casos limítrofes.

## Suposições de ruído (a validar com a especialista)

| Medida | Erro padrão |
|---|---|
| logMAR | 0,05 |
| Campo visual | 2° |
| QI | 3 pontos |
| Estatura | 0,3 cm |
| Comprimento do braço | 0,5 cm |
| Arco de movimento do tornozelo | 3° |
| Diferença de comprimento das pernas | 0,5 cm |
| Força (MRC) | 8% das vezes registrada com 1 grau de diferença |
| Nível de amputação | 3% das vezes registrado com 1 nível de diferença |
| Descritores funcionais ordinais (gravidade, propulsão, função de braço, tronco e perna) | 5% das vezes registrados com 1 passo de diferença |
| Respostas sim/não funcionais (transferência, caminhada, amarração) | 3% das vezes registradas ao contrário |
| Distribuição da paralisia cerebral | 3% das vezes registrada errada |

Campos faltantes: entre 1% (sexo) e 20% (arco de movimento) por campo, definidos em `NoiseConfig.missing_p`. O formulário visual nunca perde as duas medidas de uma vez.

## Limitações conhecidas

- Cada perfil pertence a **um grupo**. Deficiências combinadas (por exemplo, visual + membro) não são geradas.
- Os valores dentro de cada classe seguem distribuições simples (uniformes e faixas ao redor dos limiares), não dados de atletas reais.
- `age` não é gerada, porque nenhuma regra a usa.
- Nos grupos provisórios (encefálicos, Petra, cadeira), o rótulo vem de regras que são a nossa leitura da cartilha; os descritores funcionais são amostrados de padrões típicos por faixa (por exemplo, nível medular), com 8% de combinações atípicas na cadeira.
- Como o rótulo vem de regras sobre as mesmas variáveis, a acurácia máxima possível é limitada só pelo ruído. O ganho esperado do modelo é **calibração e tratamento de dados faltantes**, não superar as regras com dados exatos.

## Resultado de referência (seed 0, 300 por label, 13.800 linhas)

O baseline de regras, aplicado ao perfil observado, concorda com o label verdadeiro em 79,9% das linhas e se abstém em cerca de 14%. A comparação completa com o MLP, por grupo, está em [results_mlp.md](results_mlp.md).
