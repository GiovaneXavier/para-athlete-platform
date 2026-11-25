# Painel de transparência (K11)

A página `/transparencia` do web mostra a versão do livro de regras, os grupos de classes e seu estado, as divergências conhecidas, o histórico das regras, a ficha do modelo e os resultados dos experimentos E1, E7 e V1. **Todo número é do nível de evidência N1**: concordância com rótulos sintéticos produzidos pelas mesmas regras, sob ruído simulado, não validade clínica. Por isso o painel nunca usa a palavra "acurácia" para essas métricas.

## De onde vêm os dados

```
runs/ (fora do git, na máquina de quem rodou os experimentos)
   │   lido só por:  python -m para_triage.transparency.export
   ▼
web/public/transparency.json   (commitado; só agregados)
   │
   ├── página /transparencia      (importa o JSON no build)
   └── GET /api/transparency       (valida o JSON e confere o que está em uso)
```

- A web e a API **nunca leem `runs/`** em tempo de execução.
- O JSON traz o commit de origem de cada experimento, o id do livro de regras em uso e o id que as regras tinham nesse commit (lido do git), o nível N1 de cada bloco, e **só agregados** (média, desvio, mínimo e máximo entre sementes). Não há vinhetas, gabarito, perfis, caminhos locais nem dados pessoais.
- As colunas `accuracy` dos CSV são renomeadas para `agreement` (concordância) na exportação.

## Como regerar o JSON

A pasta `runs/` é ignorada pelo git. Ela existe na máquina de quem rodou os experimentos (E1, E7, V1, e a variante `*_profile` de E1 e E7). A partir da raiz do repositório:

```bash
python -m para_triage.transparency.export --runs <caminho para a pasta runs/>
```

ou, com a variável de ambiente:

```bash
PARA_RUNS_DIR=<caminho para a pasta runs/> python -m para_triage.transparency.export
```

Por padrão grava `web/public/transparency.json` (use `--out` para outro destino). Se a pasta ou um arquivo esperado faltar, o script termina com uma mensagem clara e sem gravar nada. A saída é determinística: as mesmas pastas geram o mesmo arquivo, byte a byte (LF).

Depois de regerar, rode `pytest tests/test_transparency_guard.py tests/test_api_transparency.py`, revise o diff do JSON e commite.

## Quando regerar

- **Quando as regras mudarem.** O id do livro de regras (hash de `classes.yaml`, `engine.py`, `catalog.py`, `schema.py` e `evaluators/*.py`) está no JSON, e o teste `test_the_committed_report_matches_the_current_rule_book` falha se ele ficar velho. Acrescente também uma entrada em `src/para_triage/transparency/rules_changelog.json` (o teste do histórico falha sem ela).
- **Quando os experimentos forem refeitos.** Rode o script de novo sobre a nova `runs/`.
- **Quando o checkpoint servido mudar.** Registre o hash em `KNOWN_CHECKPOINTS` (`src/para_triage/provenance_info/checkpoint.py`); um hash que não está lá aparece como "desconhecido", sem protocolo nem métricas emprestados de outro.

## O que a página e a API conferem ao vivo

`GET /api/transparency` devolve o relatório e um bloco `live`: o id das regras que o servidor está usando (e se é igual ao do relatório) e o hash do checkpoint carregado (e se é o da ficha). A página mostra isso na "Verificação ao vivo" e continua funcionando, só com o arquivo versionado, se a API estiver fora do ar. A API usa `PARA_TRANSPARENCY_JSON` para ler outro arquivo; sem o arquivo responde 503 e a triagem segue normal.

## Guardas nos testes

- `tests/test_transparency_guard.py`: o JSON bate com as regras atuais; tem N1 em tudo; não tem a palavra "acurácia" nem "accuracy"; não tem caminho local nem e-mail; só tem agregados; valida contra o modelo da API. Qualquer arquivo do painel (página, componentes, esta documentação) que diga "acurácia" ou "accuracy" precisa ter **N1** a até 200 caracteres.
- `tests/test_transparency_export.py`: o exportador sobre uma `runs/` sintética.
- `tests/test_api_transparency.py`: a rota.

## Limites conhecidos

- Os desvios são **entre as 5 sementes**. Nas coberturas do conforme, as 20 repartições de calibração e teste de cada semente reaproveitam as mesmas linhas, então elas não são independentes; o painel mostra o desvio entre sementes e o pior caso entre as repartições.
- O `mlp_v1` servido é preliminar e anterior ao protocolo atual; a ficha diz isso.
- "Implementado" no estado dos grupos não quer dizer revisado por classificadores oficiais.
