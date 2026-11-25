"""Prompt, deterministic reference report and fidelity checks."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .context import STATUS_PT, ReportContext

SECTIONS = (
    "Resumo",
    "Classes prováveis",
    "Provas sugeridas",
    "Equipamentos",
    "Dados que faltam ou são incertos",
    "Próximos passos",
    "Aviso",
)

NEXT_STEPS = (
    "Procurar um Centro de Referência do CPB ou um classificador para a avaliação presencial oficial. "
    "Levar os laudos e exames disponíveis (por exemplo, oftalmológico, neurológico ou testes de QI, "
    "conforme o caso) e confirmar as medidas com instrumentos padronizados."
)
DISCLAIMER = (
    "Este relatório é uma triagem automática de apoio. Ele não substitui a classificação esportiva "
    "oficial, feita presencialmente por classificadores do CPB e da World Para Athletics."
)

SYSTEM_PROMPT = f"""Você escreve relatórios de triagem para profissionais do paradesporto no Brasil.

Regras obrigatórias:
- Use SOMENTE os fatos fornecidos. Não invente classes, critérios de elegibilidade, probabilidades, provas, equipamentos ou diagnósticos.
- Não decida a classe: explique as classes candidatas e as probabilidades fornecidas, sem alterá-las.
- Cite as classes pelos códigos fornecidos (por exemplo, T44/F44) e as probabilidades em porcentagem, exatamente como fornecidas.
- Se o modelo e as regras discordarem, ou se houver alertas, diga isso com clareza e cautela.
- Não dê conselho médico nem de treino. Use português do Brasil, em tom profissional, claro e cauteloso.
- Responda em Markdown, com exatamente estes títulos de seção, nesta ordem: {", ".join("## " + s for s in SECTIONS)}.
- Em "Próximos passos" e "Aviso", reproduza o texto fornecido, com suas palavras apenas se mantiver o sentido.
- Cada seção aparece uma única vez e só traz o conteúdo do seu título. Não repita o Aviso nem copie o texto de "Próximos passos" para outra seção.
- As razões das regras vêm em inglês: traduza-as para o português, sem mudar o sentido.
- Use só as classes, provas e equipamentos que aparecem nos fatos. Nunca diga que não há classes candidatas, provas ou equipamentos quando os fatos listam algum.
- No máximo 350 palavras."""


def _pct(p: float | None) -> str:
    return "sem estimativa do modelo" if p is None else f"{round(p * 100)}%"


def _borderline_led(ctx: ReportContext) -> bool:
    top = ctx.options[0].probability if ctx.options else None
    return ctx.p_ambiguous is not None and top is not None and ctx.p_ambiguous > top


def render_facts(ctx: ReportContext) -> str:
    lines = ["DADOS INFORMADOS"]
    lines += [f"- {f}" for f in ctx.profile_facts] or ["- (nenhum dado informado)"]

    lines += ["", "CLASSES CANDIDATAS (da mais para a menos provável)"]
    if not ctx.options:
        lines.append("- nenhuma")
    for i, o in enumerate(ctx.options, 1):
        lines.append(f"{i}. Classe {o.class_id} — códigos {' / '.join(o.codes)} — {o.name_pt}")
        lines.append(f"   - probabilidade estimada pelo modelo: {_pct(o.probability)}")
        if o.rule_status is not None:
            reasons = "; ".join(o.rule_reasons)
            lines.append(f"   - regras da cartilha: {STATUS_PT[o.rule_status]} ({reasons})")
        lines.append(f"   - provas: {'; '.join(o.events) or 'nenhuma'}")
        lines.append(f"   - equipamentos: {', '.join(o.equipment) or 'nenhum específico'}")

    if ctx.review_notes:
        lines += ["", "AS REGRAS NÃO DECIDEM ESTE CASO: EXIGE AVALIAÇÃO DE ESPECIALISTA"]
        lines += [f"- {note}" for note in ctx.review_notes]

    others = []
    if ctx.p_none is not None:
        others.append(f"nenhuma classe elegível: {_pct(ctx.p_none)}")
    if ctx.p_ambiguous is not None:
        others.append(f"caso ambíguo: {_pct(ctx.p_ambiguous)}")
    if others:
        lines += ["", "OUTRAS PROBABILIDADES DO MODELO", "- " + "; ".join(others)]

    lines += ["", "DADOS QUE FALTAM"]
    lines += [f"- {m}" for m in ctx.missing] or ["- nenhum dado relevante em falta"]
    lines += ["", "ALERTAS"]
    lines += [f"- {f}" for f in ctx.flags] or ["- nenhum"]
    lines += ["", "TEXTO PARA PRÓXIMOS PASSOS", NEXT_STEPS, "", "TEXTO PARA AVISO", DISCLAIMER]
    return "\n".join(lines)


NO_CANDIDATES_INSTRUCTION = (
    'Não há classes candidatas. Escreva "Nenhuma classe candidata." em "Classes prováveis", '
    '"Nenhuma prova a sugerir." em "Provas sugeridas" e "Nenhum equipamento a indicar." em "Equipamentos", '
    'e explique o motivo no "Resumo".'
)


def user_prompt(ctx: ReportContext, issues: list["Issue"] | None = None) -> str:
    text = "Escreva o relatório de triagem com base nestes fatos.\n\n" + render_facts(ctx)
    if not ctx.options:
        text += "\n\n" + NO_CANDIDATES_INSTRUCTION
    if issues:
        text += "\n\nO rascunho anterior foi rejeitado pelos seguintes problemas. Corrija-os:\n"
        text += "\n".join(f"- {i.detail}" for i in issues)
    return text


# --- deterministic reference report --------------------------------------------------------------------


def render_template(ctx: ReportContext) -> str:
    out = ["## Resumo"]
    if not ctx.options and ctx.review_notes:
        out.append(
            "Os dados informados exigem avaliação de especialista, porque as regras da cartilha não decidem este caso: "
            + "; ".join(ctx.review_notes)
            + "."
        )
    elif ctx.options and _borderline_led(ctx):
        names = ", ".join(" / ".join(o.codes) for o in ctx.options)
        out.append(
            f"Os dados colocam o atleta numa zona limítrofe: o modelo estima {_pct(ctx.p_ambiguous)} de "
            f"chance de caso ambíguo. As classes candidatas são {names}, e a decisão final cabe ao classificador."
        )
    elif ctx.options:
        top = ctx.options[0]
        prob = f", com probabilidade estimada de {_pct(top.probability)}" if top.probability is not None else ""
        out.append(
            f"Com base nos dados informados, a classe mais provável é a {top.class_id} "
            f"({' / '.join(top.codes)}){prob}: {top.name_pt}."
        )
        if ctx.rules_model_agree:
            out.append("As regras da cartilha e o modelo apontam a mesma classe.")
        elif ctx.rules_model_agree is False:
            out.append("As regras da cartilha e o modelo apontam classes diferentes; isso merece atenção.")
    else:
        out.append("Com os dados informados, não foi possível identificar uma classe elegível.")

    out += ["", "## Classes prováveis"]
    for o in ctx.options:
        line = f"- **{' / '.join(o.codes)}** — {o.name_pt}. Probabilidade estimada: {_pct(o.probability)}."
        if o.rule_status is not None:
            line += f" Pelas regras: {STATUS_PT[o.rule_status]}."
        out.append(line)
    if not ctx.options:
        out.append("- Nenhuma classe candidata.")
    extra = []
    if ctx.p_none is not None:
        extra.append(f"nenhuma classe elegível ({_pct(ctx.p_none)})")
    if ctx.p_ambiguous is not None:
        extra.append(f"caso ambíguo ({_pct(ctx.p_ambiguous)})")
    if extra:
        out.append("- Outras possibilidades do modelo: " + "; ".join(extra) + ".")

    out += ["", "## Provas sugeridas"]
    events = [f"{e} (classe {o.class_id})" for o in ctx.options[:2] for e in o.events]
    out += [f"- {e}" for e in events] or ["- Sem provas a sugerir."]

    out += ["", "## Equipamentos"]
    gear = list(dict.fromkeys(g for o in ctx.options[:2] for g in o.equipment))
    out += [f"- {g}" for g in gear] or ["- Nenhum equipamento específico indicado."]

    out += ["", "## Dados que faltam ou são incertos"]
    out += [f"- Avaliação de especialista: {note}." for note in ctx.review_notes]
    out += [f"- Falta informar: {m}." for m in ctx.missing]
    out += [f"- Atenção: {f}." for f in ctx.flags]
    if not ctx.missing and not ctx.flags:
        out.append("- Nenhum ponto em aberto.")

    out += ["", "## Próximos passos", NEXT_STEPS, "", "## Aviso", DISCLAIMER]
    return "\n".join(out)


# --- fidelity checks -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    kind: str
    detail: str


_CODE = re.compile(r"\b([TF])(\d{2})\b")
_CLASS_NUMBER = re.compile(r"\b[Cc]lasses?\s+(\d{2})\b")
_PERCENT = re.compile(r"(\d{1,3})\s?%")
_HEADING = re.compile(r"^#{1,3}\s*(.+?)\s*$", re.MULTILINE)

# Phrases that belong to exactly one section; finding them elsewhere means the model pasted text in the wrong place.
_NEXT_STEPS_MARK = "centro de referência"
_DISCLAIMER_MARK = "não substitui"


def split_sections(text: str) -> list[tuple[str, str]]:
    """(title, body) for every Markdown heading, in order of appearance."""
    matches = list(_HEADING.finditer(text))
    return [
        (m.group(1), text[m.end() : matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip())
        for i, m in enumerate(matches)
    ]


def _structure_issues(text: str) -> list[Issue]:
    issues = []
    sections = split_sections(text)
    titles = [title for title, _ in sections]
    for title in SECTIONS:
        count = titles.count(title)
        if count == 0:
            issues.append(Issue("missing_section", f"falta a seção '## {title}'"))
        elif count > 1:
            issues.append(Issue("duplicate_section", f"a seção '## {title}' aparece {count} vezes; use uma só"))

    known = [t for t in dict.fromkeys(titles) if t in SECTIONS]
    if known != sorted(known, key=SECTIONS.index):
        issues.append(Issue("section_order", "as seções estão fora de ordem; siga: " + ", ".join(SECTIONS)))

    for title, body in sections:
        if title not in SECTIONS:
            continue
        lowered = body.lower()
        if not body:
            issues.append(Issue("empty_section", f"a seção '## {title}' está vazia"))
        if title != "Próximos passos" and _NEXT_STEPS_MARK in lowered:
            issues.append(Issue("misplaced_text", f"o texto de 'Próximos passos' foi colado em '## {title}'"))
        if title not in ("Aviso", "Resumo") and _DISCLAIMER_MARK in lowered:
            issues.append(Issue("misplaced_text", f"o texto do 'Aviso' foi colado em '## {title}'"))

    aviso = next((body for title, body in sections if title == "Aviso"), "")
    if "aviso" in " ".join(titles).lower() and (_DISCLAIMER_MARK not in aviso.lower() or "classificação" not in aviso.lower()):
        issues.append(Issue("missing_disclaimer", "o aviso deve dizer que não substitui a classificação oficial"))
    elif "Aviso" not in titles and (_DISCLAIMER_MARK not in text.lower() or "classificação" not in text.lower()):
        issues.append(Issue("missing_disclaimer", "o aviso deve dizer que não substitui a classificação oficial"))
    return issues


def check_report(text: str, ctx: ReportContext) -> list[Issue]:
    """Problems that make a report unfaithful to the facts or badly structured. Empty means acceptable."""
    issues = _structure_issues(text)

    allowed_codes = ctx.allowed_codes
    allowed_numbers = {int(c[1:]) for c in allowed_codes} | {o.class_id for o in ctx.options}
    for letter, number in dict.fromkeys(_CODE.findall(text)):
        if f"{letter}{number}" not in allowed_codes:
            issues.append(Issue("unknown_class", f"o código {letter}{number} não foi fornecido; use só {', '.join(sorted(allowed_codes)) or 'nenhum código'}"))
    for number in dict.fromkeys(_CLASS_NUMBER.findall(text)):
        if int(number) not in allowed_numbers:
            issues.append(Issue("unknown_class", f"a classe {number} não foi fornecida"))

    lowered = text.lower()
    if ctx.options:
        for phrase in ("nenhuma classe candidata", "nenhuma prova a sugerir"):
            if phrase in lowered:
                issues.append(Issue("contradiction", f'o texto diz "{phrase}", mas os fatos listam classes candidatas'))
        if any(o.equipment for o in ctx.options) and "nenhum equipamento a indicar" in lowered:
            issues.append(Issue("contradiction", 'o texto diz "nenhum equipamento a indicar", mas os fatos listam equipamentos'))
    for option in ctx.options:
        for reason in option.rule_reasons:
            if reason.lower() in lowered:
                issues.append(Issue("untranslated_text", f'traduza para o português a razão "{reason}"'))

    allowed_pct = ctx.percentages
    for pct in dict.fromkeys(int(p) for p in _PERCENT.findall(text)):
        if not any(abs(pct - a) <= 1 for a in allowed_pct):
            issues.append(Issue("unknown_percentage", f"a porcentagem {pct}% não corresponde a nenhuma probabilidade fornecida"))
    return issues
