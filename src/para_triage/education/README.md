# education (K2, modo educação)

Casos clínicos **fictícios** e determinísticos por semente, com o rastro dos critérios depois da resposta. Só **lê** o núcleo (`rules/`, `data/`, `models/`). Desenho e decisões: `docs/educacao.md`.

- `scope.py`: os quatro grupos do escopo (D28), o aviso fixo e as constantes. Neuro, Petra, cadeira e classe 20 são recusados.
- `cases.py`: banco por (grupo, semente), níveis, `case_id` e gabarito, que vem sempre do motor.
- `trace.py`: rastro por critério (visual e baixa estatura pelos `criteria` do catálogo; amputação por uma tabela própria, conferida contra o motor nas 144 combinações de níveis).
- `presentation.py`, `options.py`: o texto do caso e as opções de resposta.
- `texts_pt.py`: **todos os textos**, nossos, num só lugar para revisão.
- `review_status.json`: nada é `reviewed` até a especialista rever.
- `review_sheet.py`: gera a folha de revisão (`docs/educacao_folha_de_revisao.md`).

Regras: gabarito só sai em `POST /api/education/answer`; nada é guardado; aviso fixo e marca "Rascunho" em toda tela; sem texto da cartilha do CPB nem da LEXI.
