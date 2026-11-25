# transparency (K11, painel de transparência)

Exportação e serviço dos resultados agregados e versionados do painel `/transparencia`.

- `export.py`: único leitor de `runs/`. `python -m para_triage.transparency.export --runs <caminho>` grava `web/public/transparency.json` (só agregados, com o commit de origem e o nível N1).
- `rules_changelog.json`: histórico das versões do livro de regras, mantido à mão; uma entrada por id de versão.
- A rota está em `api/routers/transparency.py` e a página em `web/src/app/transparencia/`.

Princípios: a web e a API **nunca leem `runs/`** em tempo de execução. Toda métrica de fidelidade às regras leva o nível de evidência **N1** e o aviso "concordância com as regras sob ruído simulado, não validade clínica", e nunca é chamada de acurácia. Versão das regras e hash do checkpoint vêm de `para_triage.provenance_info`. Como regerar o JSON e o que os testes guardam: `docs/transparencia.md`.
