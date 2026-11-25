"""Facts for one athlete: profile, rule verdicts and model probabilities.

The LLM only ever sees what is built here. It never decides the class; it
explains the classes this module hands it.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from ..rules import Profile, RuleEngine, Status
from ..rules.catalog import ClassSpec

EQUIPMENT_PT = {
    "guide_runner": "guia-corredor",
    "guide_runner_optional": "guia-corredor (opcional)",
    "racing_wheelchair": "cadeira de corrida",
    "throwing_frame": "banco ou cadeira de arremesso",
    "running_prosthesis": "prótese de corrida",
    "frame_runner": "Petra (frame running)",
}

FIELD_PT = {
    "sex": "sexo",
    "age": "idade",
    "posture": "posição de competição",
    "logmar_best_eye": "acuidade visual (logMAR, melhor olho)",
    "visual_field_deg": "campo visual (graus)",
    "iq": "QI",
    "adaptive_limitation": "limitação do comportamento adaptativo",
    "onset_before_22": "diagnóstico antes dos 22 anos",
    "height_cm": "estatura (cm)",
    "longest_arm_cm": "comprimento do braço mais longo (cm)",
    "brain_impairment_report": "laudo neurológico de lesão encefálica",
    "neuro_severity": "gravidade funcional",
    "cp_distribution": "distribuição da paralisia cerebral",
    "chair_propulsion": "propulsão da cadeira de corrida",
    "transfers_independently": "transfere-se sozinho para a Petra",
    "walks_short_distances": "caminha distâncias curtas",
    "trunk_straps_needed": "precisa de amarração de tronco",
    "arm_function": "função de braço e mão",
    "trunk_function": "função de tronco",
    "leg_function": "função das pernas",
    "lower_left": "membro inferior esquerdo",
    "lower_right": "membro inferior direito",
    "upper_left": "membro superior esquerdo",
    "upper_right": "membro superior direito",
    "ankle_pf_mrc": "força da flexão plantar (0 a 5)",
    "ankle_rom_deg": "arco de movimento passivo do tornozelo (graus)",
    "leg_length_diff_cm": "diferença de comprimento das pernas (cm)",
    "hip_knee_deficit": "déficit de quadril ou joelho",
    "lower_limb_sides_affected": "lados afetados nos membros inferiores",
}

IMPAIRMENT_PT = {
    "visual": "deficiência visual",
    "intellectual": "deficiência intelectual",
    "short_stature": "baixa estatura",
    "limb_deficiency": "deficiência de membro",
    "muscle_power": "déficit de força muscular",
    "rom": "déficit de amplitude de movimento",
    "leg_length_difference": "diferença de comprimento das pernas",
    "hypertonia": "hipertonia",
    "ataxia": "ataxia",
    "athetosis": "atetose",
}

# Keyed by "EnumClass.MEMBER" for integer enums (the same member name means different
# things in different scales) and by the plain value for string enums.
VALUE_PT = {
    "M": "masculino",
    "F": "feminino",
    "standing": "em pé, sem prótese",
    "seated": "sentado",
    "prosthesis": "em pé, com prótese",
    "frame_runner": "Petra",
    "quadriplegia": "quadriplegia",
    "triplegia": "triplegia",
    "hemiplegia": "hemiplegia",
    "diplegia": "diplegia",
    "LowerLimbLevel.NONE": "sem amputação",
    "LowerLimbLevel.PARTIAL_FOOT": "pé parcial",
    "LowerLimbLevel.BELOW_KNEE": "abaixo do joelho",
    "LowerLimbLevel.THROUGH_OR_ABOVE_KNEE": "através ou acima do joelho",
    "UpperLimbLevel.NONE": "sem amputação",
    "UpperLimbLevel.WRIST": "punho",
    "UpperLimbLevel.ELBOW_OR_ABOVE": "cotovelo ou acima",
    "Severity.NONE": "nenhuma",
    "Severity.MILD": "leve",
    "Severity.MODERATE": "moderada",
    "Severity.SEVERE": "severa",
    "Propulsion.FEET": "com os pés",
    "Propulsion.ARMS_IMPAIRED": "com os braços, com comprometimento",
    "Propulsion.ARMS_ASYMMETRIC": "com os braços, de forma assimétrica",
    "Propulsion.ARMS_SYMMETRIC": "com os braços, simétrica e potente",
    "ArmFunction.SHOULDER_ELBOW_DEFICIT": "déficit de ombro e cotovelo",
    "ArmFunction.FINGER_DEFICIT": "déficit de dedos",
    "ArmFunction.INTRINSIC_ONLY": "só a musculatura intrínseca da mão comprometida",
    "ArmFunction.PRESERVED": "preservada",
    "TrunkFunction.NONE": "sem função",
    "TrunkFunction.PARTIAL": "parcial",
    "TrunkFunction.FULL": "total",
    "LegFunction.NONE": "sem função",
    "LegFunction.HIP_FLEXORS_ONLY": "só flexores de quadril",
    "LegFunction.HIP_AND_KNEE": "quadril e joelho parciais",
    "LegFunction.ANKLE_LEVEL": "comprometimento só no nível do tornozelo",
    "LegFunction.NORMAL": "normal",
}

STATUS_PT = {
    Status.MEETS: "atende aos critérios",
    Status.BORDERLINE: "caso limítrofe",
    Status.NEEDS_REVIEW: "exige avaliação de especialista",
}

LOW_CONFIDENCE = 0.60

# Why the rules hand a case to a specialist, in Portuguese. Unknown reasons fall back to the original text.
REVIEW_PT = {
    "combined upper and lower limb deficiency": "deficiência combinada de membro superior e inferior",
    "bilateral involvement including above-knee while standing without prosthesis": (
        "comprometimento bilateral com amputação acima do joelho, em pé e sem prótese"
    ),
    "bilateral partial-foot deficiency": "deficiência bilateral de pé parcial",
    "partial-foot involvement combined with prosthesis use": "pé parcial combinado com uso de prótese",
    "upper limb deficiency combined with prosthesis use": "deficiência de membro superior combinada com uso de prótese",
    "mild impairment but competing seated": "comprometimento leve, mas o atleta compete sentado",
    "severe impairment while standing; seated classes may apply": (
        "comprometimento severo em pé: as classes sentadas podem se aplicar"
    ),
    "arm-function deficit combined with trunk function is not described": (
        "déficit de função de braço combinado com função de tronco, caso que a cartilha não descreve"
    ),
}
_STANDING_DISTRIBUTION = re.compile(r"^(\w+) while standing; seated classes may apply$")


def review_note_pt(reason: str) -> str:
    if reason in REVIEW_PT:
        return REVIEW_PT[reason]
    match = _STANDING_DISTRIBUTION.match(reason)
    if match:
        return f"{VALUE_PT.get(match.group(1), match.group(1))} em pé: as classes sentadas podem se aplicar"
    if reason.endswith("bilateral involvement"):
        return "critério mínimo atendido, mas com comprometimento bilateral"
    return reason


def _value_pt(value) -> str:
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, Enum):
        key = f"{type(value).__name__}.{value.name}" if isinstance(value, int) else value.value
        return VALUE_PT.get(key, str(key))
    return str(value)


@dataclass(frozen=True)
class ClassOption:
    class_id: int
    codes: tuple[str, ...]
    name_pt: str
    probability: float | None  # None when no model is available
    rule_status: Status | None
    rule_reasons: tuple[str, ...]
    events: tuple[str, ...]  # e.g. "T53: corridas e saltos"
    equipment: tuple[str, ...]


@dataclass(frozen=True)
class ReportContext:
    profile_facts: tuple[str, ...]
    missing: tuple[str, ...]
    options: tuple[ClassOption, ...]
    review_notes: tuple[str, ...]  # why the rules need a specialist, in Portuguese
    p_none: float | None
    p_ambiguous: float | None
    rules_primary: int | None
    rules_model_agree: bool | None
    flags: tuple[str, ...] = field(default=())

    @property
    def allowed_codes(self) -> set[str]:
        return {c for o in self.options for c in o.codes}

    @property
    def percentages(self) -> set[int]:
        values = [o.probability for o in self.options] + [self.p_none, self.p_ambiguous]
        return {round(v * 100) for v in values if v is not None}


def _events(spec: ClassSpec) -> tuple[str, ...]:
    out = []
    track = "track" in spec.events
    jump = "jump" in spec.events
    if track or jump:
        what = " e ".join(w for w, on in (("corridas", track), ("saltos", jump)) if on)
        out.append(f"T{spec.track_equivalent or spec.class_id}: {what}")
    if "field" in spec.events:
        out.append(f"F{spec.class_id}: arremessos e lançamentos")
    return tuple(out)


def profile_facts(profile: Profile) -> tuple[str, ...]:
    facts = []
    if profile.impairments:
        names = sorted(IMPAIRMENT_PT[i.value] for i in profile.impairments)
        facts.append("comprometimentos informados: " + ", ".join(names))
    for f in dataclasses.fields(profile):
        if f.name == "impairments":
            continue
        value = getattr(profile, f.name)
        if value is None or f.name not in FIELD_PT:
            continue
        facts.append(f"{FIELD_PT[f.name]}: {_value_pt(value)}")
    return tuple(facts)


def build_context(
    profile: Profile,
    engine: RuleEngine,
    probabilities: np.ndarray | None = None,
    classes: np.ndarray | None = None,
    top_k: int = 3,
) -> ReportContext:
    result = engine.evaluate(profile)
    catalog = engine.catalog

    p_by_class: dict[int, float] = {}
    if probabilities is not None:
        p_by_class = {int(c): float(p) for c, p in zip(classes, probabilities)}
    p_none, p_ambiguous = p_by_class.get(0), p_by_class.get(-1)

    if p_by_class:
        ranked = sorted((c for c in p_by_class if c > 0), key=lambda c: -p_by_class[c])
        chosen = [c for c in ranked if p_by_class[c] >= 0.02][:top_k]
    else:
        chosen = result.candidates[:top_k]

    options = []
    for cid in chosen:
        spec = catalog.classes[cid]
        verdict = result.verdicts[cid]
        shown = verdict.status in STATUS_PT
        options.append(
            ClassOption(
                class_id=cid,
                codes=spec.codes,
                name_pt=spec.name_pt,
                probability=p_by_class.get(cid),
                rule_status=verdict.status if shown else None,
                rule_reasons=verdict.reasons if shown else (),
                events=_events(spec),
                equipment=tuple(EQUIPMENT_PT[e] for e in spec.equipment if e in EQUIPMENT_PT),
            )
        )

    missing = []
    for verdict in result.verdicts.values():
        if verdict.status is Status.INSUFFICIENT_DATA or verdict.class_id in chosen:
            missing.extend(FIELD_PT.get(m, m) for m in verdict.missing)
    missing = tuple(dict.fromkeys(missing))

    agree = None
    if p_by_class and result.primary_class is not None:
        agree = bool(chosen and chosen[0] == result.primary_class)

    review_notes = tuple(
        dict.fromkeys(
            review_note_pt(reason)
            for verdict in result.verdicts.values()
            if verdict.status is Status.NEEDS_REVIEW
            for reason in verdict.reasons
        )
    )

    flags = []
    if not options and not review_notes:
        flags.append("nenhuma classe elegível foi identificada com os dados informados")
    if review_notes:
        flags.append("as regras pedem avaliação de especialista")
    if options and options[0].probability is not None and options[0].probability < LOW_CONFIDENCE:
        flags.append("a confiança do modelo na classe mais provável é baixa")
    if p_ambiguous is not None and p_ambiguous >= 0.25:
        flags.append("o perfil é limítrofe: o modelo vê chance relevante de caso ambíguo")
    if agree is False:
        flags.append("as regras e o modelo apontam classes diferentes")
    statuses = {v.status for v in result.verdicts.values()}
    if (
        p_by_class
        and result.primary_class is None
        and Status.INSUFFICIENT_DATA in statuses
        and not statuses & {Status.BORDERLINE, Status.NEEDS_REVIEW}
    ):
        flags.append("as regras da cartilha não conseguiram decidir com os dados informados; o resultado vem do modelo")

    return ReportContext(
        profile_facts=profile_facts(profile),
        missing=missing,
        options=tuple(options),
        review_notes=review_notes,
        p_none=p_none,
        p_ambiguous=p_ambiguous,
        rules_primary=result.primary_class,
        rules_model_agree=agree,
        flags=tuple(flags),
    )
