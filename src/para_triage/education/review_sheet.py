"""Review sheet for the specialist: fixed cases with answer, trace and limits, plus every text of the study mode.

    python -m para_triage.education.review_sheet [--seed 0] [--per-group 10] [--out docs/educacao_folha_de_revisao.md]

Nothing is marked as reviewed here: moving a case to `reviewed` is done in review_status.json by hand,
after the specialist has read it.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import cases, scope
from . import texts_pt as T
from .options import options_for

LEVEL_CYCLE = ("easy", "easy", "medium", "medium", "hard", "hard", "easy", "medium", "hard", "hard")


def case_block(number: int, case: cases.Case) -> list[str]:
    trace = cases.trace_of(case)
    labels = {o.id: o.label for o in options_for(case.group)}
    lines = [
        f"#### Caso {number} (`{case.case_id}`, nível {T.DIFFICULTY_LABELS[case.difficulty].lower()})",
        "",
        case.presentation.summary,
        "",
        *(f"- {fact.label}: {fact.value}" for fact in case.presentation.facts),
        "",
        f"**Resposta:** {labels[case.answer]}. **Conclusão do rastro:** {trace.conclusion}",
        "",
        "| Critério | Referência | Valor | Resultado | Explicação |",
        "|---|---|---|---|---|",
        *(
            f"| {s.criterion} | {s.reference} | {s.value} | {T.RESULT_LABELS[s.result]} | {s.explanation} |"
            for s in trace.steps
        ),
        "",
    ]
    return lines


def texts_block() -> list[str]:
    lines = ["## Textos do modo educação", "", "Todos os textos estão em `src/para_triage/education/texts_pt.py`.", ""]
    lines += ["### Avisos", "", f"- Aviso fixo: {scope.NOTICE}", ""]
    for group in scope.ALLOWED_GROUPS:
        lines += [f"### {T.GROUP_LABELS[group]}", "", T.GROUP_SUMMARIES[group], ""]
        if T.GROUP_WARNINGS[group]:
            lines += [f"- Aviso do grupo: {T.GROUP_WARNINGS[group]}"]
        lines += [f"- Limites mostrados com a resposta:", *(f"  - {limit}" for limit in (*T.LIMITS[group], T.LIMITS_COMMON)), ""]
    lines += ["### Opções de resposta", "", f"- {T.OPTION_LABEL_NONE}", f"- {T.OPTION_LABEL_SPECIALIST}", f"- {T.OPTION_LABEL_INSUFFICIENT}", ""]
    lines += ["### Leitura de cada padrão de amputação", ""]
    lines += [f"- ({kind}, {row}) {text}" for (kind, row), text in T.LIMB_ROWS.items()]
    return lines + [""]


def build(seed: int, per_group: int) -> str:
    lines = [
        "# Folha de revisão do modo educação",
        "",
        f"Gerada por `python -m para_triage.education.review_sheet --seed {seed} --per-group {per_group}`. "
        "Tudo é rascunho até a especialista rever. Casos fictícios, sem dado de atleta.",
        "",
        f"> {scope.NOTICE}",
        "",
    ]
    for group in scope.ALLOWED_GROUPS:
        lines += [f"## {T.GROUP_LABELS[group]}", ""]
        for number in range(per_group):
            level = LEVEL_CYCLE[number % len(LEVEL_CYCLE)]
            lines += case_block(number + 1, cases.get_case(group, level, seed, _slot(number)))
    return "\n".join(lines + texts_block()) + "\n"


def _slot(number: int) -> int:
    """Index inside the pool of the level: each repetition of a level in the cycle takes the next case."""
    level = LEVEL_CYCLE[number % len(LEVEL_CYCLE)]
    return sum(1 for earlier in range(number) if LEVEL_CYCLE[earlier % len(LEVEL_CYCLE)] == level)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-group", type=int, default=10)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    text = build(args.seed, args.per_group)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"gravado {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
