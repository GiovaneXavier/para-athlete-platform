"""Every user-facing text of the study mode (K2), in Brazilian Portuguese, in one place for review.

All sentences here are ours: nothing is copied from the CPB booklet or from LEXI. The catalog only
supplies class numbers, codes, our own `name_pt` and the booklet page as a reference. Review status
of these texts is tracked in review_status.json (everything is a draft until the specialist reviews).
"""
from __future__ import annotations

# --- formatting --------------------------------------------------------------------------------------


def fmt(value: float, digits: int = 1) -> str:
    """Decimal comma, fixed digits: 1.2 -> '1,2'."""
    return f"{value:.{digits}f}".replace(".", ",")


# --- groups -------------------------------------------------------------------------------------------

GROUP_LABELS = {
    "visual": "Deficiência visual",
    "short_stature": "Baixa estatura",
    "limb_standing": "Amputação de membros, em pé e sem prótese",
    "limb_prosthesis": "Amputação de membros inferiores, com prótese",
}

GROUP_SUMMARIES = {
    "visual": "Classes 11 a 13: decidem a acuidade visual do melhor olho e o campo visual.",
    "short_stature": "Classes 40 e 41: decidem a estatura, o braço mais longo e a soma dos dois, por sexo.",
    "limb_standing": "Classes 42 a 47: decide o nível de amputação em cada membro, de pé e sem prótese.",
    "limb_prosthesis": "Classes 61 a 64: decide o nível de amputação das pernas, com prótese de corrida.",
}

GROUP_WARNINGS = {
    "visual": None,
    "short_stature": None,
    "limb_standing": (
        "Só casos por nível de amputação. Força, amplitude de movimento e a diferença de 7 cm entre as pernas "
        "(classe 44) não entram, porque as regras ainda não as cobrem por inteiro."
    ),
    "limb_prosthesis": None,
}

DIFFICULTY_LABELS = {
    "easy": "Fácil",
    "medium": "Médio",
    "hard": "Difícil",
    "mixed": "Misto",
}

DIFFICULTY_HINTS = {
    "easy": "Valores longe dos limiares e todos os dados informados.",
    "medium": "Valores perto dos limiares, ou padrões que exigem ler os dois lados.",
    "hard": "Casos limítrofes, que exigem especialista, ou com dados faltando.",
    "mixed": "Uma mistura dos três níveis.",
}

# --- answer options -----------------------------------------------------------------------------------

OPTION_LABEL_NONE = "Nenhuma classe"
OPTION_LABEL_SPECIALIST = "Caso limítrofe ou que exige especialista"
OPTION_LABEL_INSUFFICIENT = "Faltam dados para decidir"


def option_label_class(class_id: int, codes: tuple[str, ...]) -> str:
    return f"Classe {class_id} ({'/'.join(codes)})" if codes else f"Classe {class_id}"


# --- case presentation -------------------------------------------------------------------------------

NOT_MEASURED = "não medido"

FACT_LABELS = {
    "logmar": "Acuidade do melhor olho, com a melhor correção",
    "field": "Campo visual",
    "sex": "Sexo",
    "height": "Estatura",
    "arm": "Braço mais longo (do acrômio à ponta do dedo mais longo)",
    "posture": "Posição de competição",
    "lower_left": "Perna esquerda",
    "lower_right": "Perna direita",
    "upper_left": "Braço esquerdo",
    "upper_right": "Braço direito",
}

SEX_LABELS = {"M": "masculino", "F": "feminino"}

POSTURE_LABELS = {
    "standing": "em pé, sem prótese",
    "prosthesis": "com prótese de corrida",
}

LOWER_LEVEL_LABELS = {
    0: "sem amputação",
    1: "parte do pé (nível de Lisfranc)",
    2: "abaixo do joelho",
    3: "através ou acima do joelho",
}

UPPER_LEVEL_LABELS = {
    0: "sem amputação",
    1: "nível do punho",
    2: "através ou acima do cotovelo",
}

SUMMARY_VISUAL = "Atleta fictício com deficiência visual."
SUMMARY_SHORT_STATURE = "Atleta fictício com baixa estatura."
SUMMARY_LIMB_STANDING = "Atleta fictício com amputação, que compete em pé e sem prótese."
SUMMARY_LIMB_PROSTHESIS = "Atleta fictício com amputação, que compete com prótese de corrida."

# --- trace --------------------------------------------------------------------------------------------

RESULT_LABELS = {
    "met": "atende",
    "not_met": "não atende",
    "not_assessed": "não avaliado",
}

SOURCE_REFERENCE = "Cartilha do CPB (2024), p. {page}"

# visual
VIS_ACUITY_CRITERION = "Acuidade do melhor olho: critério da classe {cid}"
VIS_ACUITY_REF_11 = "pior que {limit} logMAR"
VIS_ACUITY_REF_RANGE = "de {low} a {high} logMAR"
VIS_ACUITY_VALUE = "{value} logMAR"
VIS_FIELD_CRITERION = "Campo visual: critério da classe {cid}"
VIS_FIELD_REF = "abaixo de {limit} graus de diâmetro"
VIS_FIELD_VALUE = "{value} graus de diâmetro"
VIS_MET = "O valor está dentro do critério da classe {cid}."
VIS_NOT_MET = "O valor está fora do critério da classe {cid}."
VIS_GAP = (
    "O valor cai entre {high} e {low} logMAR, faixa que o livreto deixa sem classe: por isso o caso é limítrofe."
)
VIS_MISSING_ACUITY = "A acuidade não foi medida."
VIS_MISSING_FIELD = "O campo visual não foi medido."
VIS_CONCLUSION_CLASS = "Vale a classe mais comprometida entre as que o caso atende: classe {cid}."
VIS_CONCLUSION_NONE = "Nem a acuidade nem o campo atendem a algum critério: nenhuma classe."
VIS_CONCLUSION_SPECIALIST = (
    "A acuidade cai na faixa sem classe entre {high} e {low} logMAR, então o caso é limítrofe e pede avaliação de especialista."
)
VIS_CONCLUSION_INSUFFICIENT = (
    "A medida informada sozinha não atende a nenhum critério e falta a outra ({missing}): sem ela não dá para decidir."
)
VIS_MISSING_NAMES = {"acuity": "acuidade", "field": "campo visual"}

# short stature
SS_CRITERION = "Classe {cid}: {what}"
SS_WHAT_HEIGHT = "estatura"
SS_WHAT_ARM = "braço mais longo"
SS_WHAT_SUM = "soma de estatura e braço"
SS_REF = "até {limit} cm"
SS_VALUE_SUM = "{height} + {arm} = {total} cm"
SS_VALUE = "{value} cm"
SS_MET = "Dentro do limite."
SS_NOT_MET = "Acima do limite."
SS_ALL_CRITERION = "Classe {cid}: as três condições ao mesmo tempo"
SS_ALL_REF = "as três valem"
SS_ALL_VALUE = "{count} de 3"
SS_ALL_MET = "As três condições valem: o caso atende a classe {cid}."
SS_ALL_NOT_MET = "Pelo menos uma condição falha: o caso não atende a classe {cid}."
SS_MISSING = "Não foi medido: {what}."
SS_MISSING_NAMES = {"sex": "sexo", "height": "estatura", "arm": "braço mais longo"}
SS_CONCLUSION_CLASS = "As classes são aninhadas e vale a mais comprometida que o caso atende: classe {cid}."
SS_CONCLUSION_NONE = "Nem os limites da classe 40 nem os da classe 41 são atendidos: nenhuma classe."
SS_CONCLUSION_INSUFFICIENT = "Falta {missing}: sem isso não dá para comparar com os limites."

# limb groups
LIMB_LEVEL_CRITERION = "Nível de amputação: {where}"
LIMB_LEVEL_WHERE = {
    "lower_left": "perna esquerda",
    "lower_right": "perna direita",
    "upper_left": "braço esquerdo",
    "upper_right": "braço direito",
}
LIMB_LEVEL_REF = "informado"
LIMB_LEVEL_MET = "O nível foi informado."
LIMB_LEVEL_MISSING = "O nível não foi medido."
LIMB_BOTH_CRITERION = "Há amputação nos membros superiores e nos inferiores ao mesmo tempo?"
LIMB_GATE_REF = "se sim, as regras não decidem sozinhas"
LIMB_BOTH_VALUE_YES = "sim"
LIMB_BOTH_VALUE_NO = "não"
LIMB_BOTH_EXPLANATION_YES = "Em pé, a combinação de membro superior e inferior não é decidida pelas regras: vai para o especialista."
LIMB_BOTH_EXPLANATION_NO = "Só um dos conjuntos de membros tem amputação, então segue-se a tabela daquele conjunto."
LIMB_UPPER_PROSTHESIS_CRITERION = "Há amputação nos membros superiores?"
LIMB_UPPER_PROSTHESIS_YES = "Amputação de membro superior junto com prótese não é decidida pelas regras: vai para o especialista."
LIMB_UPPER_PROSTHESIS_NO = "Não há: segue-se a tabela dos membros inferiores."
LIMB_PAIR_CRITERION = "Padrão dos {which}"
LIMB_PAIR_WHICH = {"lower": "membros inferiores", "upper": "membros superiores"}
LIMB_PAIR_REF = "tabela de níveis de amputação"
LIMB_PAIR_VALUE = "mais afetado: {high}; menos afetado: {low}"
LIMB_NONE_CRITERION = "Há amputação em algum membro?"
LIMB_NONE_VALUE = "não"
LIMB_NONE_EXPLANATION = "Nenhum nível de amputação foi registrado, então nenhuma classe de amputação se aplica."
LIMB_NO_LOWER_CRITERION = "Há amputação em membro inferior?"
LIMB_NO_LOWER_EXPLANATION = "As classes com prótese exigem amputação de membro inferior: nenhuma classe."

LIMB_CONCLUSION_CLASS = "O padrão corresponde à classe {cid}."
LIMB_CONCLUSION_NONE = "Nenhuma classe de amputação se aplica a este caso."
LIMB_CONCLUSION_SPECIALIST = "As regras não decidem sozinhas este padrão: o caso é limítrofe ou pede avaliação de especialista."
LIMB_CONCLUSION_INSUFFICIENT = "Falta o nível de amputação de pelo menos um membro: sem ele não dá para decidir."

# Reading of each decision-table row (ours). Key: (kind, row id).
LIMB_ROWS = {
    ("lower_standing", "unilateral_above"): "Um só membro inferior amputado através ou acima do joelho.",
    ("lower_standing", "unilateral_above_plus_foot"): "Acima do joelho de um lado e parte do pé do outro: as regras pedem confirmação.",
    ("lower_standing", "bilateral_with_above"): "Os dois membros inferiores afetados, ao menos um acima do joelho, sem prótese: especialista.",
    ("lower_standing", "bilateral_below"): "Os dois membros inferiores amputados abaixo do joelho.",
    ("lower_standing", "unilateral_below"): "Um só membro inferior amputado abaixo do joelho.",
    ("lower_standing", "below_plus_foot"): "Abaixo do joelho de um lado e parte do pé do outro: fica entre duas classes.",
    ("lower_standing", "unilateral_foot"): "Só parte do pé amputada: as regras pedem confirmação.",
    ("lower_standing", "bilateral_foot"): "Parte do pé nos dois lados: especialista.",
    ("upper_standing", "bilateral_elbow"): "Os dois membros superiores amputados através ou acima do cotovelo.",
    ("upper_standing", "unilateral_elbow"): "Um só membro superior amputado através ou acima do cotovelo.",
    ("upper_standing", "bilateral_wrist"): "Os dois membros superiores amputados no nível do punho.",
    ("upper_standing", "elbow_plus_wrist"): "Cotovelo de um lado e punho do outro: fica entre duas classes.",
    ("upper_standing", "unilateral_wrist"): "Um só membro superior amputado no nível do punho.",
    ("lower_prosthesis", "bilateral_above"): "Os dois membros inferiores amputados através ou acima do joelho.",
    ("lower_prosthesis", "bilateral_below"): "Os dois membros inferiores amputados abaixo do joelho.",
    ("lower_prosthesis", "unilateral_above"): "Um só membro inferior amputado através ou acima do joelho.",
    ("lower_prosthesis", "unilateral_below"): "Um só membro inferior amputado abaixo do joelho.",
    ("lower_prosthesis", "above_plus_below"): "Acima do joelho de um lado e abaixo do outro: fica entre duas classes.",
    ("lower_prosthesis", "foot_involved"): "Parte do pé envolvida junto com a prótese: especialista.",
}

# --- limits: what the trace does not cover (shown with every answer) ---------------------------------

LIMITS_COMMON = "Provas e equipamentos não aparecem aqui e não estão validados. A leitura das regras é nossa e está por validar com a especialista."

LIMITS = {
    "visual": (
        "O exame real tem mais do que dois números; este caso reduz a acuidade e o campo a valores prontos.",
        "O livreto escreve o limite da classe 11 como \"menor que 2,60\" e lemos como pior que 2,60 (o valor 2,60 cai na classe 12).",
        "A faixa entre 1,40 e 1,50 logMAR o livreto deixa sem classe; tratamos como caso limítrofe.",
        "O campo visual é medido em graus de diâmetro, como no livreto. Outras fontes, inclusive artigos científicos, usam o raio, que é a metade.",
    ),
    "short_stature": (
        "O caso traz os números prontos; a medição real segue protocolo próprio, que este rastro não ensina.",
    ),
    "limb_standing": (
        "Força, amplitude de movimento e a diferença de 7 cm entre as pernas (classe 44) não entram: estes casos são só por nível de amputação, e as regras cobrem essas medidas só em parte.",
        "Parte do pé (nível de Lisfranc) sozinha é lida como caso limítrofe, sem confirmação.",
        "Força e amplitude dos membros superiores não estão implementadas.",
    ),
    "limb_prosthesis": (
        "Parte do pé junto com prótese e a combinação de acima e abaixo do joelho vão para especialista: o rastro diz isso e não escolhe uma classe.",
        "O tipo de prótese e o ajuste dela não entram no caso.",
    ),
}

# --- API messages -------------------------------------------------------------------------------------

CORRECT_TITLE = "Você acertou"
WRONG_TITLE = "Não foi dessa vez"
REVEALED_TITLE = "Resposta"
