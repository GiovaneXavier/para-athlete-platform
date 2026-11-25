"""Prompt versions. v1 is in `extractors.py` (kept as it was run). v2 was written after v1 answered `?` (or "all complete")
for almost everything: the models fell back to the easiest answer. v2 differences are disclosed in the report:

- image: a short free-text field `look` comes BEFORE the six fields, so the model says what it sees before it answers; and the
  prompt asks for `?` only when a limb is really hidden or cut.
- report: two worked examples (written by hand for this prompt, not taken from the evaluation set), and `?` only for what the
  report does not mention at all.

v2 was looked at on the `dev` subset only (disjoint from `eval`), at most 3 tries; the number of tries is in the report.
"""
from __future__ import annotations

from extractors import IMAGE_PROMPT, REPORT_SYSTEM, SCHEMA

IMAGE_SCHEMA_V2 = {
    "type": "object",
    "properties": {"look": {"type": "string", "maxLength": 200}, **SCHEMA["properties"]},
    "required": ["look"] + SCHEMA["required"],
    "additionalProperties": False,
}

IMAGE_PROMPT_V2 = (
    "This is a synthetic drawing of one person (a figure, not a photograph). "
    "First, in the field `look`, say in one short sentence what you see: the legs, the arms, and whether there is a wheelchair or an artificial limb. "
    "A missing limb is drawn as a shorter limb that ends early; a complete limb reaches the hand or the foot. "
    "Then fill the other fields. Lower limb level: 0 = complete leg, 1 = only part of the foot missing, 2 = leg ends below the knee, 3 = leg ends at or above the knee. "
    "Upper limb level: 0 = complete arm, 1 = arm ends at or below the elbow, 2 = arm ends at or above the elbow. "
    "lower_left, lower_right, upper_left and upper_right are the PERSON's own left and right, not the viewer's: "
    "the person's left is on the right-hand side of the picture when the person faces the viewer. "
    "Use ? for a limb only if it is really hidden, covered or cut by the edge of the picture; if you can see the limb, choose its level. "
    "wheelchair: yes if there is a wheelchair, no if not. prosthesis: yes if an artificial limb is visible, no if not."
)

REPORT_SYSTEM_V2 = (
    REPORT_SYSTEM.replace("Use ? for anything the report does not say. Never guess. ",
                          "Use ? only for a limb or side that the report does not mention at all; whenever the report states a limb, give its level. ")
    + " Examples. Report: 'Membro inferior esquerdo: amputação transtibial. Na perna direita, há membro íntegro. Braço dir.: membro completo.' "
      "Answer: {\"lower_left\":\"2\",\"lower_right\":\"0\",\"upper_left\":\"?\",\"upper_right\":\"0\",\"wheelchair\":\"?\",\"prosthesis\":\"?\"}. "
      "Report: 'Registra-se amputação parcial do pé no membro inferior direito. Braço esquerdo: amputação transumeral. Usa cadeira de rodas.' "
      "Answer: {\"lower_left\":\"?\",\"lower_right\":\"1\",\"upper_left\":\"2\",\"upper_right\":\"?\",\"wheelchair\":\"yes\",\"prosthesis\":\"?\"}."
)

# v3 (third and last try on the dev subset). v2 images: both vision models said "complete legs and arms" for every picture, even
# for a clearly shorter arm. v3 asks them to COMPARE the two arms and the two legs. v2 reports: the 1.5B model mixed up sides
# when it had to fill six fixed fields, so v3 asks for a list of statements ("which limb, which level"); limbs not stated stay `?`.
IMAGE_PROMPT_V3 = (
    "This is a synthetic drawing of one person (a figure, not a photograph). In the field `look`, compare the two arms and then the two legs: "
    "say whether one arm ends earlier (is shorter) than the other, or whether one leg ends earlier than the other, and on which side of the PICTURE. "
    "Then fill the other fields. Lower limb level: 0 = complete leg, 1 = only part of the foot missing, 2 = leg ends below the knee, 3 = leg ends at or above the knee. "
    "Upper limb level: 0 = complete arm, 1 = arm ends at or below the elbow, 2 = arm ends at or above the elbow. "
    "A limb that is shorter than its pair is NOT complete. "
    "lower_left, lower_right, upper_left and upper_right are the PERSON's own left and right, not the viewer's: "
    "the person's left is on the right-hand side of the picture when the person faces the viewer. "
    "Use ? for a limb only if it is really hidden, covered or cut by the edge of the picture. "
    "wheelchair: yes if there is a wheelchair, no if not. prosthesis: yes if an artificial limb is visible, no if not."
)

STATEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "statements": {"type": "array", "maxItems": 8, "items": {
            "type": "object",
            "properties": {"limb": {"enum": ["left_leg", "right_leg", "left_arm", "right_arm"]}, "level": {"enum": ["0", "1", "2", "3"]}},
            "required": ["limb", "level"], "additionalProperties": False}},
        "wheelchair": {"enum": ["yes", "no", "?"]},
        "prosthesis": {"enum": ["yes", "no", "?"]},
    },
    "required": ["statements", "wheelchair", "prosthesis"],
    "additionalProperties": False,
}

REPORT_SYSTEM_V3 = (
    "You read short medical-style reports written in Portuguese. List one statement for every limb the report talks about, "
    "with the limb (left_leg, right_leg, left_arm, right_arm) and its level. Do not list a limb the report does not mention. "
    "Legs (perna, membro inferior, MI): 0 = complete or intact (membro íntegro, completo, ausência de amputação), "
    "1 = partial foot amputation (amputação parcial do pé), 2 = below the knee (transtibial, abaixo do joelho), "
    "3 = through or above the knee (transfemoral, desarticulação do joelho, acima do joelho). "
    "Arms (braço, membro superior, MS): 0 = complete or intact, 1 = wrist or below the elbow (transradial, abaixo do cotovelo, punho), "
    "2 = elbow or above (transumeral, acima do cotovelo, desarticulação do cotovelo). "
    "esquerdo/esq. = left, direito/dir. = right. wheelchair and prosthesis: yes or no only if the report says so, otherwise ?. "
    "Example. Report: 'Membro inferior esquerdo: amputação transtibial. Na perna direita, há membro íntegro. Braço dir.: membro completo.' "
    "Answer: {\"statements\":[{\"limb\":\"left_leg\",\"level\":\"2\"},{\"limb\":\"right_leg\",\"level\":\"0\"},{\"limb\":\"right_arm\",\"level\":\"0\"}],\"wheelchair\":\"?\",\"prosthesis\":\"?\"}"
)

# v4 (report only), written AFTER the final round showed that v3 read "Não usa cadeira de rodas" as `?` in 547 of 548 reports.
# Only the wheelchair/prosthesis rule and the example change; the limb rules are as in v3. It is checked first on the level-2
# `dev` subset. Because the `eval` results were already seen, the v4 numbers on `eval` are NOT a clean held-out test of this fix.
REPORT_SYSTEM_V4 = (
    REPORT_SYSTEM_V3.split("esquerdo/esq. = left")[0]
    + "esquerdo/esq. = left, direito/dir. = right. "
      "wheelchair and prosthesis: yes if the report says the person uses one (usa, faz uso de), "
      "no if the report says the person does not use one (não usa, sem uso de, sem prótese), and ? only if the report says nothing about it. "
      "Example. Report: 'Membro inferior esquerdo: amputação transtibial. Na perna direita, há membro íntegro. Braço dir.: membro completo. "
      "Não usa cadeira de rodas. Faz uso de prótese.' "
      "Answer: {\"statements\":[{\"limb\":\"left_leg\",\"level\":\"2\"},{\"limb\":\"right_leg\",\"level\":\"0\"},{\"limb\":\"right_arm\",\"level\":\"0\"}],\"wheelchair\":\"no\",\"prosthesis\":\"yes\"}"
)

PROMPTS = {
    "v1": {"image_text": IMAGE_PROMPT, "image_schema": SCHEMA, "report_schema": SCHEMA, "report_system": REPORT_SYSTEM, "image_tokens": 120},
    "v2": {"image_text": IMAGE_PROMPT_V2, "image_schema": IMAGE_SCHEMA_V2, "report_schema": SCHEMA, "report_system": REPORT_SYSTEM_V2, "image_tokens": 220},
    "v3": {"image_text": IMAGE_PROMPT_V3, "image_schema": IMAGE_SCHEMA_V2, "report_schema": STATEMENT_SCHEMA, "report_system": REPORT_SYSTEM_V3, "image_tokens": 240},
    "v4": {"image_text": IMAGE_PROMPT_V3, "image_schema": IMAGE_SCHEMA_V2, "report_schema": STATEMENT_SCHEMA, "report_system": REPORT_SYSTEM_V4, "image_tokens": 240},  # report only
}
