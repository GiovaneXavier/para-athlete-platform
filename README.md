# para-athlete-platform

Triagem de elegibilidade e recomendação de provas no **atletismo paralímpico**, a partir de dados clínicos inseridos por um profissional. O pacote Python se chama `para_triage`.

Projeto final de Deep Learning (Mestrado, UNICAMP).

**Por onde começar (para quem vai avaliar):**

1. Esta página, da "Ideia" até "Imagens sintéticas e modelo de imagem".
2. [docs/decisoes/19_robustez_e_aprendizado_profundo.md](docs/decisoes/19_robustez_e_aprendizado_profundo.md): a crítica de que o projeto "é uma árvore de decisão" e o que decidimos medir.
3. [docs/imagens-sinteticas-e-modelos.md](docs/imagens-sinteticas-e-modelos.md): como as imagens foram geradas, o modelo treinado (ficha técnica e pesos) e os modelos usados para avaliá-las.
4. Os relatórios de resultados: [MLP e experimentos de robustez](docs/results_mlp.md), [K34, imagem e laudo (resultado negativo)](docs/consistencia-imagem-laudo-relatorio.md) e [K35, rede treinada contra o formulário](docs/imagem-contra-formulario-relatorio.md).

Todo número com imagem ou modelo é **N1** (dados sintéticos, rótulos por construção) e **não vale para pessoas nem fotos reais**. Nenhum dado de atleta foi usado.

> **Aviso:** esta é uma ferramenta de apoio à triagem. Ela **não substitui** a classificação esportiva oficial, feita por classificadores do CPB/World Para Athletics.

## Ideia

1. Um profissional informa o perfil do atleta (tipo de deficiência, níveis de amputação, medidas, posição de competição...).
2. Um **motor de regras** codifica os critérios do CPB (Cartilha "Perfil de Classes do Atletismo", 2024) e da plataforma [Lexi](https://lexi.global/sports/athletics). Ele serve de baseline e de fonte dos rótulos sintéticos.
3. Um **modelo** (MLP em PyTorch com máscara de campos faltantes) aprende a lidar com ruído, dados faltantes e casos limítrofes, devolvendo probabilidades por classe.
4. Uma **LLM** (Ollama) transforma o resultado num relatório com classes prováveis, provas elegíveis, equipamentos e próximos passos. A LLM só explica; um verificador rejeita relatórios que citem classes ou porcentagens que não foram fornecidas.

A parte de **imagem** (K34 e K35) é um experimento à parte, só com **imagens sintéticas**: ver [Imagens sintéticas e modelo de imagem](#imagens-sintéticas-e-modelo-de-imagem-k34-e-k35).

## Estado atual (v0)

| Componente | Estado |
|---|---|
| Catálogo de 33 classes (`rules/classes.yaml`) | pronto, eventos e equipamentos a validar |
| Regras: visual (11-13), intelectual (20), baixa estatura (40-41) | implementadas |
| Regras: membros em pé (42-47) e com prótese (61-64) | implementadas para amputação; força/ADMP só no tornozelo |
| Regras: encefálicos (31-38), Petra (71-72), cadeira e arremesso sentado (51-57) | **provisórias**, a validar com a especialista |
| Gerador de dados sintéticos (ruído + faltantes) para os 9 grupos | pronto, ver [docs/synthetic_data.md](docs/synthetic_data.md) |
| MLP com máscara de faltantes e avaliação contra o baseline de regras | pronto, ver [docs/results_mlp.md](docs/results_mlp.md) |
| Relatório via LLM (Ollama) com verificação de fidelidade e relatório de referência | pronto, ver [docs/report.md](docs/report.md) |
| API HTTP (FastAPI) com relatório assíncrono | pronta |
| Interface web (Next.js 16) | pronta, ver [web/README.md](web/README.md) |
| Experimentos de robustez (ruído, campos faltantes, predição seletiva e conforme, vazamento entre treino e teste) | prontos, ver [Reproduzir os experimentos](#reproduzir-os-experimentos) |

Detalhes e decisões em aberto: [docs/rules_coverage.md](docs/rules_coverage.md).

## Imagens sintéticas e modelo de imagem (K34 e K35)

Resposta à crítica de que o projeto "se reduz a uma árvore de decisão": medimos onde uma árvore não chega, a **imagem**. **Nenhuma foto de pessoa e nenhum dado de atleta foram usados.** As imagens são bonecos **desenhados por código nosso** (rótulo certo por construção), então todo número é **N1** e não vale para fotos reais.

| O quê | Onde |
|---|---|
| **Guia: como as imagens foram geradas, o modelo treinado e os modelos usados para avaliá-las** | [docs/imagens-sinteticas-e-modelos.md](docs/imagens-sinteticas-e-modelos.md) |
| Geradores de imagem (nível 1 e nível 2) | `src/para_triage/consistency/` (`mannequin.py`, `level2.py`) |
| Imagens de exemplo (14 PNG) | `docs/exemplos-imagens/` |
| Rede treinada por nós (K35), código | `spikes/k35/` |
| Pesos da rede (3,9 MB cada, duas sementes) | `docs/modelo-k35/` |
| Modelos abertos testados (K34): SmolVLM2, Qwen2.5-VL, CLIP; não estão no repositório (gigabytes), com fonte e SHA-256 no relatório | `spikes/k34/` e [docs/consistencia-imagem-laudo-relatorio.md](docs/consistencia-imagem-laudo-relatorio.md) |
| Resultados do K35 (rede contra formulário, quatro hipóteses, limites) | [docs/imagem-contra-formulario-relatorio.md](docs/imagem-contra-formulario-relatorio.md) |

## Estrutura

```
src/para_triage/
  rules/      catálogo de classes, schema do perfil, motor de regras e avaliadores
  data/       amostradores, ruído de medida, registros, features e CLI de geração
  models/     MLP com máscara de faltantes, calibração por temperatura e CLI de treino
  eval/       métricas e comparação regras × MLP × híbrido
  experiments/ experimentos de robustez (E1, E2, E3, E7, E-MNAR, V1, V7), baselines e geração de tabelas
  report/     contexto, prompt, cliente Ollama, verificação de fidelidade e CLI do relatório
  api/        API HTTP (FastAPI) usada pelo frontend
web/          interface web (Next.js, React, Tailwind, shadcn/ui)
tests/
docs/
```

## Uso

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -e ".[api,dev,plots]"
pytest
```

Os extras: `api` (FastAPI e Uvicorn, para a API e a interface web), `dev` (pytest e httpx) e `plots` (matplotlib, só para as figuras dos experimentos). Sem `api`, os testes da API são ignorados.

```python
from para_triage.rules import Impairment, LowerLimbLevel, Posture, Profile, RuleEngine, UpperLimbLevel

profile = Profile(
    impairments=frozenset({Impairment.LIMB_DEFICIENCY}),
    posture=Posture.PROSTHESIS,
    lower_left=LowerLimbLevel.BELOW_KNEE,
    lower_right=LowerLimbLevel.NONE,
    upper_left=UpperLimbLevel.NONE,
    upper_right=UpperLimbLevel.NONE,
)
result = RuleEngine().evaluate(profile)
result.primary_class   # 64
result.verdicts[64]    # status, reasons e campos faltantes
```

Cada classe recebe um veredito: `meets`, `borderline`, `needs_review`, `insufficient_data`, `not_met`, `not_applicable` ou `not_implemented`.

### Relatório

```bash
python -m para_triage.data.generate --n-per-label 300 --out data/processed/synthetic_v1.csv
python -m para_triage.models.train --data data/processed/synthetic_v1.csv --n-runs 5 --out runs/mlp_v1
ollama pull qwen2.5:7b
python -m para_triage.report.cli examples/prosthesis_below_knee.json
python -m para_triage.report.cli examples/prosthesis_below_knee.json --no-llm   # sem LLM
```

Sem o checkpoint do MLP, o relatório usa só as regras (sem probabilidades). Sem o Ollama, cai no relatório de referência.

Os checkpoints (`runs/`, `*.pt`) e os dados gerados (`data/processed/`) **não ficam no repositório**: a API e a interface só mostram probabilidades depois de você treinar o modelo com os dois primeiros comandos acima. A API procura `runs/mlp_v1/model.pt`; para usar outro arquivo, defina `PARA_CHECKPOINT`.

### Interface web

```bash
pip install -e ".[api]"
python -m uvicorn para_triage.api.app:app --port 8000     # terminal 1
cd web && npm install && npm run dev                      # terminal 2 -> http://localhost:3000
```

Detalhes, arquitetura e como adicionar campos em [web/README.md](web/README.md).

## Reproduzir os experimentos

Os experimentos ficam em `src/para_triage/experiments/`. Eles comparam as regras, as regras com imputação, o gradient boosting, o MLP e o híbrido sob ruído e campos faltantes, e medem predição seletiva e conjuntos conformes. **Todos os rótulos vêm do mesmo motor de regras**: os números medem a fidelidade às regras diante de entradas corrompidas, e não a acurácia contra classificadores oficiais.

Cada etapa abaixo grava seus resultados em `runs/` (ignorado pelo git). Quando roda com várias sementes, grava também um `config.json` com as sementes, a divisão dos dados, o hash do commit, `code_tree_dirty` (se `src/`, `tests/` ou `pyproject.toml` tinham mudanças não commitadas), as versões de Python, NumPy, scikit-learn e PyTorch e o comando exato (uma semente avulsa não grava esse arquivo). Os tempos são de uma máquina de 18 threads sem GPU, com 5 sementes em 5 processos de 3 threads (`--jobs 5 --threads 3`); ajuste `--jobs` e `--threads` ao seu número de núcleos (jobs × threads não deve passar dele). Para uma só semente, use `--seeds 0` sem `--jobs`.

Rode na ordem: a partir da etapa 2, os experimentos usam o que as etapas 1 e 3 gravaram em `runs/e1` e `runs/e1_profile` (divisão por semente, checkpoint do MLP e hiperparâmetros escolhidos).

```bash
python -m para_triage.experiments.e1 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/e1
python -m para_triage.experiments.e7 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/e7
python -m para_triage.experiments.e1 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/e1_profile --split-mode profile_by_label
python -m para_triage.experiments.e7 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --e1 runs/e1_profile --out runs/e7_profile
python -m para_triage.experiments.e2 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/e2
python -m para_triage.experiments.e3 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/e3
python -m para_triage.experiments.emnar --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/emnar
python -m para_triage.experiments.v1 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/v1
python -m para_triage.experiments.v7 --seeds 0 1 2 3 4 --jobs 5 --threads 3 --out runs/v7
python -m para_triage.experiments.diag_epochs --e1 runs/e1_profile --out runs/diag_epochs_profile --seeds 0 1 2 3 4 --jobs 5 --threads 3
python -m para_triage.experiments.diag_epochs --e1 runs/e1 --out runs/diag_epochs_row --seeds 0 1 2 3 4 --jobs 5 --threads 3
python -m para_triage.experiments.paper_outputs --runs runs --paper outputs
```

| Etapa | Tempo | O que mede |
|---|---|---|
| 1. `e1` | ~25 min | Varredura de ruído e de campos faltantes (grade 4×4), treino e teste no mesmo nível e em níveis diferentes |
| 2. `e7` | ~4 min | Predição seletiva (risco × cobertura) e conjuntos conformes, a partir dos modelos do E1 |
| 3. `e1 --split-mode profile_by_label` | ~25 min | O mesmo E1, com a divisão feita por perfil verdadeiro: nenhum perfil aparece no treino e no teste |
| 4. `e7 --e1 runs/e1_profile` | ~4 min | O E7 sobre essa divisão (as metades de calibração e de teste também não repartem perfis) |
| 5. `e2` | ~8 min | Ablações: sem *feature dropout*, sem máscara de campos faltantes, e híbrido com limiar de confiança |
| 6. `e3` | ~2 min | Cenários de prevalência (ilustrativos) e um amostrador "natural", sem concentração perto dos limiares |
| 7. `emnar` | ~22 min | Campos faltantes que dependem do rótulo ou do valor do campo (o mecanismo é gravado em `config.json` antes de rodar) |
| 8. `v1` | ~3 min | Quantos perfis do teste se repetem no treino e o resultado numa divisão sem repetição |
| 9. `v7` | ~9 min | Conjuntos conformes por número de campos faltantes **observados** |
| 10. `diag_epochs` | ~1,5 min cada | Acurácia por grupo ao longo das épocas, sem parada antecipada |
| 11. `paper_outputs` | ~1 min | Tabelas (`.tex`), figuras (PDF) e macros (`numbers_exp.tex`) em `outputs/p1/` e `outputs/p4/`; as pastas são criadas se faltarem, e `--paper` escolhe outra raiz |

Os modelos e a divisão por semente vêm do E1. Rodar de novo a partir do mesmo commit, com as mesmas sementes e o mesmo número de threads, dá os mesmos resultados: isso foi verificado para todas as etapas acima (diferença numérica zero, tabelas e macros idênticos). Com outra versão do PyTorch, de NumPy ou de scikit-learn, ou com outro número de threads, os números podem variar na última casa.

Para conferir a instalação sem esperar, rode uma versão pequena de uma semente: `python -m para_triage.experiments.e1 --seeds 0 --out runs/e1 --n-per-label 40 --noise-levels 0 1 --missing-levels 0 1` (cerca de 2 min) e depois o `paper_outputs`.

## Fontes

- Comitê Paralímpico Brasileiro. *Classificação Esportiva Paralímpica: Perfil de Classes do Atletismo*. Janeiro de 2024. (O PDF não é redistribuído; coloque em `references/`.)
- Lexi: https://lexi.global/sports/athletics

## Licença

Licença a definir; até lá, todos os direitos reservados.
