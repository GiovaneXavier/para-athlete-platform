# rulebook (K20, adoção do livro de regras)

Livro de regras em YAML e o interpretador, **ao lado** do `RuleEngine` atual, que continua sendo o padrão: nada fora deste pacote o importa (um teste garante). Desenho e números: `docs/rulebook.md`; decisão: ADR 0020.

- `interpreter.py`: carrega um grupo, avalia um perfil (veredito por classe com os sete estados e rastro por critério), vigência e variantes. **Não conhece nenhum grupo pelo nome.** Regra de parada: este arquivo e `messages.py` têm no máximo 500 linhas de código (teste).
- `messages.py`: texto por código de razão e idioma (pt e en).
- `compare.py`: regressão lado a lado e diff entre variantes. `__main__.py`: os comandos.
- `data/`: `sources.yaml`, `variants/`, `groups/` (visual e baixa estatura), `messages/`.

```bash
python -m para_triage.rulebook test                       # testes como dados dos grupos
python -m para_triage.rulebook regress                    # contra o motor atual: tem de dar 0 divergências
python -m para_triage.rulebook diff --group visual --set boundary_in_class_11=true   # diff entre variantes
```

Para acrescentar um grupo: um YAML em `data/groups/`, com fonte e status em todo critério e parâmetro, testes como dados e uma regressão contra o motor. Se o grupo pedir uma construção que não está no vocabulário (`tests/test_rulebook_interpreter.py`), pare e fale com a arquitetura.
