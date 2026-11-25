# MLP × baseline de regras (5 execuções, 13800 linhas)

> **Documento histórico.** Estes números vêm do primeiro protocolo: um único conjunto de perfis para as 5 execuções, divisão 70/15/15 por linha e hiperparâmetros fixos. Eles **não valem mais** como resultado atual. Os experimentos em `src/para_triage/experiments/` usam um conjunto novo de perfis por semente, a divisão 60/10/15/15 (por linha e por perfil verdadeiro), mais baselines e hiperparâmetros ajustados na validação; veja "Reproduzir os experimentos" no README da raiz.

Média ± desvio padrão sobre divisões estratificadas 70/15/15 e inicializações diferentes. Quando as regras se abstêm, contam como erro.

| Sistema | Acurácia (%) | F1 macro (%) |
|---|---|---|
| Regras | 80.3 ± 0.4 | 86.7 ± 0.5 |
| MLP | 90.0 ± 0.4 | 90.3 ± 0.4 |
| Híbrido (regras, MLP se abstêm) | 89.9 ± 0.8 | 90.5 ± 0.7 |

- Cobertura das regras (decidem): 86.0 ± 0.3%
- Acurácia das regras quando decidem: 93.3 ± 0.5%
- Acurácia do MLP onde as regras decidem: 93.4 ± 0.4%
- Acurácia do MLP onde as regras se abstêm: 69.0 ± 3.7%
- Acurácia do MLP onde as regras decidem e erram: 43.9 ± 3.1%
- Top-2 do MLP: 96.7 ± 0.4%

## Calibração do MLP

| | NLL | ECE | Brier |
|---|---|---|---|
| Antes da temperatura | 0.289 ± 0.013 | 0.022 ± 0.006 | 0.145 ± 0.005 |
| Depois | 0.290 ± 0.011 | 0.026 ± 0.006 | 0.146 ± 0.005 |

Temperatura aprendida: 1.042 ± 0.052

## Acurácia por grupo (%)

| Grupo | Regras | MLP | Híbrido |
|---|---|---|---|
| frame_runner | 78.4 ± 1.6 | 91.8 ± 1.8 | 92.6 ± 1.4 |
| intellectual | 79.1 ± 4.0 | 95.3 ± 0.9 | 90.2 ± 2.0 |
| limb_prosthesis | 81.2 ± 1.3 | 92.9 ± 0.9 | 92.9 ± 0.9 |
| limb_standing | 82.4 ± 1.6 | 89.8 ± 2.4 | 90.7 ± 2.8 |
| neuro_seated | 79.1 ± 3.6 | 91.3 ± 1.5 | 89.4 ± 2.2 |
| neuro_standing | 81.1 ± 0.8 | 92.3 ± 0.5 | 92.1 ± 0.6 |
| short_stature | 87.4 ± 1.0 | 92.1 ± 1.8 | 95.4 ± 1.8 |
| visual | 76.4 ± 2.1 | 79.4 ± 2.8 | 79.3 ± 2.1 |
| wheelchair | 78.9 ± 1.1 | 89.8 ± 1.0 | 89.5 ± 1.4 |

Configuração: `{'hidden': (128, 64), 'dropout': 0.2, 'lr': 0.002, 'weight_decay': 0.0001, 'epochs': 80, 'batch_size': 128, 'feature_dropout': 0.1, 'patience': 12, 'seed': 0}`

## Como ler estes números

- **O MLP supera as regras (90,0% × 80,3%), mas o ganho vem de onde as regras se abstêm.** Onde as regras decidem, MLP e regras empatam (93,4% × 93,3%). Com ruído simétrico, a regra de limiar sobre o valor observado já é quase o melhor possível nessa região. Onde faltam dados, as regras não respondem, e o MLP acerta 69,0% usando as outras variáveis.
- **O híbrido (regras + MLP nos casos de abstenção) fica igual ao MLP** (89,9%). O modelo não entrega mais acurácia que um híbrido; entrega uma única saída com probabilidades por classe.
- **Calibração:** o MLP já sai calibrado (ECE 0,022) e a temperatura aprendida é ≈ 1. O top-2 é de 96,7%, o que sustenta mostrar as duas classes mais prováveis no relatório.
- **Casos em que as regras decidem e erram** (o ruído cruzou o limiar): o MLP acerta 44% deles. Esse é o limite do ruído.
- **Visual continua o grupo mais difícil** (79,4%): o ruído em logMAR e campo visual desloca muitos casos entre 11, 12 e 13.
- **O quadro se manteve ao passar de 5 para 9 grupos** (a versão com só os grupos numéricos e de membros dava 89,0% × 81,9%).

## Ressalvas

1. O conjunto é **balanceado por classe e concentra casos perto dos limiares**. O MLP aprende essa distribuição de amostragem, então os números não se transferem para prevalências reais.
2. O ruído e as taxas de campos faltantes são **suposições** (ver [synthetic_data.md](synthetic_data.md)).
3. O rótulo vem das mesmas regras. Nos grupos provisórios (encefálicos, Petra, cadeira), as regras são a nossa leitura da cartilha ([rules_coverage.md](rules_coverage.md)), então esses resultados medem a capacidade de reproduzir essa leitura sob ruído, não a classificação oficial.
4. A validade externa só virá do conjunto de vinhetas da especialista.

## Reproduzir

```bash
python -m para_triage.data.generate --n-per-label 300 --out data/processed/synthetic_v1.csv
python -m para_triage.models.train --data data/processed/synthetic_v1.csv --n-runs 5 --out runs/mlp_v1
```
