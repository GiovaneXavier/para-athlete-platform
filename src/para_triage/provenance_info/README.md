# provenance_info

Funções **somente de leitura** sobre o que a plataforma serve. Nada aqui escreve em `rules/` ou `models/` nem muda o comportamento deles.

- `rules_version()`: id de versão do livro de regras, `rules-<12 hex>`. É o hash de `rules/classes.yaml`, `rules/engine.py`, `rules/catalog.py`, `rules/schema.py` e `rules/evaluators/*.py` (fins de linha normalizados, então o id é o mesmo no Windows e no Linux). Muda quando qualquer um deles muda; `rules/__init__.py` fica de fora (só reexporta nomes).
- `checkpoint_info(path)`: hash SHA-256, tamanho e nome do arquivo (nunca o caminho) de um checkpoint. Quando o hash está em `KNOWN_CHECKPOINTS`, traz também o nome, o estado (`preliminary`), o protocolo, os limites e as métricas lidas do `metrics.json` ao lado do arquivo, sempre com o nível de evidência **N1**. Checkpoint desconhecido recebe só o hash: não herda protocolo nem métricas de outro. O checkpoint **não é carregado** (é um pickle), só lido como bytes.
- `EVIDENCE_LEVEL` e `EVIDENCE_NOTICE`: o nível N1 e o aviso "concordância com as regras sob ruído simulado, não validade clínica", para quem mostra métrica de fidelidade às regras.

Para registrar um checkpoint novo, acrescente o hash em `KNOWN_CHECKPOINTS` (só texto; nenhum número vai à mão).
