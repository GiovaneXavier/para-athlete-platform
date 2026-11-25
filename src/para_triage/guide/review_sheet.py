"""Review sheet of the class guide for the specialist: every page as text, the figures and the glossary.

    python -m para_triage.guide.review_sheet [--out docs/guia_folha_de_revisao.md]

Reads web/src/content/guide.json (what the site shows). Nothing is marked as reviewed here: moving a page to
`reviewed` is done by hand in guide/review_status.json after the specialist has read it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .export import DEFAULT_OUT

QUESTIONS = (
    "Os níveis de amputação, os limites numéricos e a descrição de cada classe estão de acordo com o livreto? (leitura nossa, a validar)",
    "O texto é correto para quem trabalha na área e claro para quem está começando?",
    "**Tom:** o texto e as figuras são neutros e respeitosos? Não deve haver tom de pena, de superação nem de \"falta\"; "
    "o nível de amputação é uma característica, e os bonecos são esquemas, não pessoas. Aponte qualquer trecho que soe diferente.",
    "Os desenhos afirmam algo que não deveriam (por exemplo, um nível no lugar errado do membro)?",
    "Faltou algum termo no glossário? Algum está mal definido?",
    "Idealmente, a revisão do tom e das figuras também é feita por uma atleta ou um atleta com deficiência (ainda não identificado).",
)


def flat(segments: list[dict]) -> str:
    return "".join(segment["t"] for segment in segments)


def cell(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return flat(value)
    return value["t"]


def block_lines(block: dict, figures: dict) -> list[str]:
    kind = block["kind"]
    if kind == "p":
        return [flat(block["text"]), ""]
    if kind == "ul":
        return [*(f"- {flat(item)}" for item in block["items"]), ""]
    if kind == "table":
        header = "| " + " | ".join(block["headers"]) + " |"
        rule = "|" + "---|" * len(block["headers"])
        rows = ["| " + " | ".join(cell(c) for c in row) + " |" for row in block["rows"]]
        return [f"*{block['caption']}*", "", header, rule, *rows, ""]
    if kind == "figure":
        figure = figures[block["id"]]
        return [f"**Figura: {figure['title']}.** {flat(figure['caption'])}", "", f"> Descrição: {figure['long']}", ""]
    if kind == "example":
        facts = [f"- {fact['label']}: {fact['value']}" for fact in block["facts"]]
        return [f"**Exemplo (modo educação, `{block['case_id']}`):** {block['summary']}", "", *facts, "", f"Conclusão: {block['conclusion']}", ""]
    if kind == "link":
        return [f"Link: {block['label']} -> `{block['href']}`", ""]
    if kind == "cards":
        return [*(f"- **{item['title']}** (`{item['href']}`): {flat(item['text'])}" for item in block["items"]), ""]
    if kind == "details":
        lines = [f"*{block['summary']}*", ""]
        for inner in block["blocks"]:
            lines += block_lines(inner, figures)
        return lines
    return []


def build(content: dict) -> str:
    lines = [
        "# Folha de revisão do guia de classes",
        "",
        "Gerada por `python -m para_triage.guide.review_sheet`. Tudo é rascunho até a especialista rever. "
        f"Versão das regras: `{content['rules_id']}`.",
        "",
        f"> {content['notice']}",
        "",
        "## O que conferir",
        "",
        *(f"{number}. {question}" for number, question in enumerate(QUESTIONS, start=1)),
        "",
        "Os textos estão em `src/para_triage/guide/texts_pt.py`; os números de cada página são gerados do catálogo e do motor.",
        "",
    ]
    for page in content["pages"]:
        if page["kind"] == "glossary":
            continue
        lines += [f"## {page['title']} (`{page['path']}`)", ""]
        if page["intro"]:
            lines += [flat(page["intro"]), ""]
        for section in page["sections"]:
            lines += [f"### {section['heading']}", ""]
            for block in section["blocks"]:
                lines += block_lines(block, content["figures"])
    lines += ["## Glossário", ""]
    lines += [f"- **{item['term']}** (`{item['id']}`): {flat(item['definition'])}" for item in content["glossary"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    text = build(json.loads(DEFAULT_OUT.read_text(encoding="utf-8")))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"gravado {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
