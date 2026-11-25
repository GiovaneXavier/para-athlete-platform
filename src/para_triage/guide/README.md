# guide (K18, guia de classes)

Conteúdo de estudo em português, por grupo e por classe, **gerado do catálogo e do motor** e commitado em `web/src/content/guide.json`. O web só renderiza esse arquivo. Só **lê** o núcleo (`rules/`, `data/`, `models/`). Desenho: `docs/guia.md`.

- `scope.py`: os mesmos quatro grupos do modo educação, os endereços em português e o aviso fixo.
- `texts_pt.py`: **toda a prosa e o glossário**, nossos, sem nenhum número (um teste falha se aparecer dígito). Todo número da página vem do catálogo ou do motor.
- `build.py`: monta páginas, figuras e **afirmações verificáveis** (`claims`): perfis fictícios e a resposta que a página implica, que os testes rodam no motor.
- `export.py`: `python -m para_triage.guide.export` regrava o JSON (`--date` fixa a data).
- `review_status.json`: nada é `reviewed` até a especialista rever.
- `review_sheet.py`: gera `docs/guia_folha_de_revisao.md`.

**Quando regerar:** quando o catálogo, o motor, os textos do guia ou o banco de casos do K2 mudarem. O teste `test_the_committed_content_is_what_the_build_produces_today` falha se o JSON estiver velho (ignora só `generated_on`).

Regras: texto nosso (sem copiar a cartilha nem a LEXI); tom neutro e respeitoso (sem pena, superação ou "falta"); aviso fixo e "Rascunho" em toda página; sem provas nem equipamentos.
