"""Every sentence of the class guide (K18), in Brazilian Portuguese, in one place for review.

All text is ours: nothing is copied from the CPB booklet or from LEXI. Rules of this module:

- **No digits.** Every number a page shows (limits, class numbers, pages) is generated from the catalog or
  the rule engine and enters through a `${name}` placeholder, so no sentence can keep an old number. A test
  fails when a digit shows up here (only the year in the notice is allowed, and it lives in scope.py).
- `{{term-id|text}}` marks a glossary term; the build turns it into a link to /guia/glossario.
- Tone: neutral and respectful. Amputation level is a characteristic, not a loss; drawings are schemes,
  not people. No pity, no "overcoming", no "lack of". The specialist is asked to check this tone.
"""
from __future__ import annotations

# --- hub ---------------------------------------------------------------------------------------------------

HUB_TITLE = "Guia de classes do atletismo paralímpico"
HUB_INTRO = (
    "Um guia para entender como as classes se organizam, grupo por grupo e classe por classe. "
    "É um texto de estudo: ele explica as regras que usamos, mas não calcula nada sobre você nem sobre ninguém."
)
HUB_SECTIONS = {
    "como-ler": (
        "Como ler uma classe",
        (
            "Uma {{classe-esportiva|classe esportiva}} reúne atletas com um nível parecido de impacto da deficiência no esporte. "
            "Cada classe tem um número, e a letra indica o tipo de prova: {{codigos-t-f|T para pista e saltos, F para lançamentos e arremessos}}.",
            "As regras aqui seguem o {{livreto|livreto do CPB}}, em {{leitura-nossa|leitura nossa}}. "
            "Para competir em uma classe, a pessoa precisa ter uma {{deficiencia-elegivel|deficiência elegível}} que atinja o "
            "{{criterio-minimo|critério mínimo de deficiência}} do esporte. A {{classificacao|classificação}} de verdade é feita "
            "por um {{classificador|classificador}}, em avaliação presencial.",
        ),
    ),
    "grupos": (
        "Os grupos deste guia",
        ("Cada {{grupo-de-deficiencia|grupo de deficiência}} reúne classes que dependem do mesmo tipo de característica.",),
    ),
    "fora": (
        "O que ficou de fora, por enquanto",
        (
            "Alguns grupos de classes não entram neste guia por estarem em validação. Eles voltam quando a leitura das regras "
            "for revista com a especialista. Provas e equipamentos também não aparecem, pelo mesmo motivo.",
        ),
    ),
    "usar": (
        "Para continuar",
        (
            "Quer testar o que leu? O modo educação traz casos fictícios, com a resposta e o passo a passo depois que você responde.",
        ),
    ),
}
HUB_GROUP_CARD = {
    "visual": "A classe depende da acuidade visual do melhor olho e do campo visual.",
    "short_stature": "A classe depende da estatura, do braço mais longo e da soma dos dois, por sexo.",
    "limb_standing": "A classe depende do nível de amputação em cada membro, para quem compete em pé e sem prótese.",
    "limb_prosthesis": "A classe depende do nível de amputação dos membros inferiores, para quem compete com prótese de corrida.",
}

# --- groups ------------------------------------------------------------------------------------------------

GROUP_TITLES = {
    "visual": "Deficiência visual",
    "short_stature": "Baixa estatura",
    "limb_standing": "Amputação de membros, em pé e sem prótese",
    "limb_prosthesis": "Amputação de membros inferiores, com prótese",
}

GROUP_DECIDES = {
    "visual": (
        "Neste grupo, a classe depende de dois resultados do exame: a {{acuidade|acuidade visual}} do {{melhor-olho|melhor olho}}, "
        "medida em {{logmar|logMAR}}, e o {{campo-visual|campo visual}}. Quando os dois resultados apontam classes diferentes, "
        "vale a classe mais comprometida entre as que o caso atende.",
    ),
    "short_stature": (
        "Neste grupo de {{baixa-estatura|baixa estatura}}, a classe depende de três medidas: a estatura, o {{comprimento-do-braco|comprimento do braço mais longo}} "
        "(do {{acromio|acrômio}} à ponta do dedo mais longo) e a {{soma|soma}} das duas. Os limites são diferentes para homens e para mulheres.",
    ),
    "limb_standing": (
        "Neste grupo, a classe depende do {{nivel-de-amputacao|nível de amputação}} em cada um dos quatro membros: "
        "as duas pernas e os dois braços. Uma {{amputacao|amputação}} é tratada aqui como uma característica do membro, "
        "descrita pelo nível. Só se considera quem compete {{em-pe-sem-protese|em pé e sem prótese}}.",
    ),
    "limb_prosthesis": (
        "Neste grupo, a classe depende do {{nivel-de-amputacao|nível de amputação}} nas pernas, para quem compete "
        "com {{protese-de-corrida|prótese de corrida}}. Amputação de braço junto com a prótese não é decidida só pelas regras.",
    ),
}

GROUP_TABLE_CAPTION = "As classes do grupo lado a lado"
GROUP_TABLE_HEADERS = ("Classe", "Códigos", "O que a regra pede")
CLASS_LABEL = "Classe ${class_id}"

# numeric groups: the rule of each class in one line (placeholders filled from the catalog criteria)
VISUAL_RULE_11 = "{{acuidade|acuidade}} pior que ${logmar_gt_11} {{logmar|logMAR}}"
VISUAL_RULE_RANGE = (
    "acuidade de ${logmar_min} a ${logmar_max} logMAR, ou {{campo-visual|campo visual}} abaixo de ${field_lt} graus de diâmetro"
)
SHORT_RULE = "estatura, braço e soma dentro dos limites da tabela abaixo, que são diferentes por sexo"

VISUAL_DIFFS = (
    "A classe ${c11} é a faixa de acuidade mais baixa do grupo: o melhor olho fica com acuidade pior que ${logmar_gt_11} logMAR. "
    "Quanto maior o valor em logMAR, menor a acuidade.",
    "A classe ${c12} cobre acuidade de ${logmar_min_12} a ${logmar_max_12} logMAR, ou campo visual abaixo de ${field_lt_12} graus de diâmetro.",
    "A classe ${c13} cobre acuidade de ${logmar_min_13} a ${logmar_max_13} logMAR, ou campo visual abaixo de ${field_lt_13} graus de diâmetro.",
    "Entre ${logmar_max_13} e ${logmar_min_12} logMAR o livreto não indica classe. Este guia chama esse caso de "
    "{{caso-limitrofe|limítrofe}}: ele pede avaliação de especialista.",
    "O campo visual pode apontar uma classe diferente da acuidade; vale a classe mais comprometida entre as que o caso atende.",
)

SHORT_DIFFS_INTRO = (
    "As classes ${c40} e ${c41} são {{classes-aninhadas|aninhadas}}. Para entrar em uma delas, o caso precisa respeitar os três "
    "limites ao mesmo tempo (estatura, braço e soma). Se atende as duas, vale a classe ${c40}, a mais comprometida."
)
SHORT_TABLE_CAPTION = "Limites de cada classe, por sexo"
SHORT_TABLE_HEADERS = ("Sexo", "Classe", "Estatura até", "Braço até", "Soma até")
SEX_LABELS = {"male": "Homens", "female": "Mulheres"}

LIMB_DIFFS = {
    "limb_standing": (
        "O que muda de uma classe para outra é quantos membros têm amputação e em que nível. A tabela mostra um padrão "
        "de cada classe; a regra completa de cada uma está na página da classe.",
        "Quando os braços e as pernas têm amputação ao mesmo tempo, as regras não escolhem uma classe: o caso fica para "
        "a avaliação de especialista.",
    ),
    "limb_prosthesis": (
        "O que muda de uma classe para outra é quantos membros inferiores têm amputação e em que nível. A tabela mostra "
        "um padrão de cada classe; a regra completa de cada uma está na página da classe.",
        "Quando um lado é através ou acima do joelho e o outro é abaixo do joelho, ou quando há parte do pé envolvida, "
        "as regras não escolhem uma classe: o caso fica para a avaliação de especialista.",
    ),
}
LIMB_TABLE_CAPTION = "Um padrão de cada classe"
LIMB_TABLE_HEADERS = ("Classe", "Um padrão que leva a ela")
LIMB_SPECIALIST_HEADING = "Padrões que ficam para a avaliação de especialista"
LIMB_SPECIALIST_INTRO = "As regras deste guia não escolhem uma classe para os padrões abaixo. Eles são {{caso-limitrofe|limítrofes}} ou pedem especialista."

# --- limb pattern sentences ---------------------------------------------------------------------------------

LOWER_LEVELS = {
    1: "em parte do pé ({{pe-parcial|nível de Lisfranc}})",
    2: "{{abaixo-do-joelho|abaixo do joelho}}",
    3: "{{atraves-do-joelho|através}} ou {{acima-do-joelho|acima do joelho}}",
}
UPPER_LEVELS = {
    1: "no nível do {{punho|punho}}",
    2: "através ou acima do {{cotovelo|cotovelo}}",
}
LIMB_NONE = {"lower": "nenhuma perna com amputação", "upper": "nenhum braço com amputação"}
LIMB_ONE = {
    "lower": "uma perna com amputação {hi} e a outra sem amputação",
    "upper": "um braço com amputação {hi} e o outro sem amputação",
}
LIMB_BOTH_EQUAL = {
    "lower": "as duas pernas com amputação {hi}",
    "upper": "os dois braços com amputação {hi}",
}
LIMB_BOTH_DIFFERENT = {
    "lower": "uma perna com amputação {hi} e a outra com amputação {lo}",
    "upper": "um braço com amputação {hi} e o outro com amputação {lo}",
}
PATTERN_SENTENCE = "{lower}; {upper}."
PATTERN_SENTENCE_LOWER_ONLY = "{lower}."

# --- class pages --------------------------------------------------------------------------------------------

CLASS_ONE_SENTENCE = {
    11: "A faixa de acuidade visual mais baixa do grupo, medida no melhor olho.",
    12: "Uma faixa intermediária de acuidade visual, ou um campo visual bastante reduzido.",
    13: "A faixa de acuidade visual mais alta do grupo, ou um campo visual reduzido em menor grau.",
    40: "A classe de baixa estatura com os limites mais baixos de estatura e de braço. As medidas são comparadas por sexo.",
    41: "A classe de baixa estatura com limites mais altos, para quem fica fora da classe anterior mas dentro destes limites.",
    42: "Amputação de um só membro inferior, através ou acima do joelho, para quem compete em pé e sem prótese.",
    43: "Amputação dos dois membros inferiores, abaixo do joelho, para quem compete em pé e sem prótese.",
    44: "Amputação de um só membro inferior, abaixo do joelho, para quem compete em pé e sem prótese. Neste guia, só pelo nível de amputação.",
    45: "Amputação dos dois membros superiores, através ou acima do cotovelo.",
    46: "Amputação de um só membro superior através ou acima do cotovelo, ou dos dois membros superiores no nível do punho.",
    47: "Amputação de um só membro superior, no nível do punho.",
    61: "Amputação dos dois membros inferiores, através ou acima do joelho, para quem compete com prótese de corrida.",
    62: "Amputação dos dois membros inferiores, abaixo do joelho, para quem compete com prótese de corrida.",
    63: "Amputação de um só membro inferior, através ou acima do joelho, para quem compete com prótese de corrida.",
    64: "Amputação de um só membro inferior, abaixo do joelho, para quem compete com prótese de corrida.",
}
CLASS_RULE_HEADING = "O que a regra pede"
CLASS_NUMERIC_VISUAL = (
    "Para a classe ${class_id}, o critério é: {rule}.",
)
CLASS_NUMERIC_SHORT = (
    "Para a classe ${class_id}, o critério é respeitar os três limites da tabela (estatura, braço e soma) ao mesmo tempo.",
)
CLASS_PATTERNS_INTRO = "A classe ${class_id} corresponde a estes padrões de amputação (o lado, direito ou esquerdo, não muda a classe):"
CLASS_DIFF_HEADING = "Como se diferencia das vizinhas"
CLASS_DIFF_LIMB_TABLE = "Lado a lado com as outras classes do grupo"
CLASS_DIFF_THIS = "esta classe"
CLASS_FIGURE_HEADING = "Ilustração"
CLASS_EXAMPLE_HEADING = "Um exemplo fictício"
CLASS_EXAMPLE_INTRO = "Caso fictício do modo educação (nada aqui é de uma pessoa real). Com estes dados, as regras chegam à classe ${class_id}."
CLASS_EXAMPLE_LINK = "Praticar casos deste grupo no modo educação"
CLASS_REFERENCE_HEADING = "Referência"
CLASS_REFERENCE = "Cartilha do CPB (2024), p. ${page}. Só como referência de onde ler no livreto; o texto desta página é nosso."
CLASS_CODES_NOTE = (
    "Os códigos T e F vêm do catálogo do projeto, e a lista de provas de cada classe ainda está por validar. "
    "Confira os códigos no livreto antes de usá-los para qualquer decisão."
)

# --- limits shown on pages ("what this guide does not cover") -----------------------------------------------

LIMITS_HEADING = "O que este guia não cobre"
LIMITS = {
    "visual": (
        "O exame real tem mais do que dois resultados; este guia reduz a acuidade e o campo visual a valores prontos.",
        "O livreto escreve o limite da classe ${c11} como \"menor que ${logmar_gt_11}\". Lemos como pior que ${logmar_gt_11}, "
        "de modo que o valor exato ${logmar_gt_11} cai na classe ${c12}.",
        "A faixa entre ${logmar_max_13} e ${logmar_min_12} logMAR o livreto deixa sem classe; este guia a trata como caso limítrofe.",
        "Os limites do {{campo-visual|campo visual}} são em graus de diâmetro, como no livreto. Outras fontes, inclusive artigos científicos, usam o raio, que é a metade; ao comparar, confira qual medida cada fonte usa.",
    ),
    "short_stature": (
        "Os valores aqui são números prontos; a medição de verdade segue um protocolo próprio, que este guia não ensina.",
    ),
    "limb_standing": (
        "Estas páginas tratam só do nível de amputação. Força, amplitude de movimento e a diferença de comprimento entre as "
        "pernas (classe ${c44}) ficam de fora, e as regras do projeto cobrem essas medidas só em parte.",
        "Parte do pé ({{pe-parcial|nível de Lisfranc}}) sozinha é lida como caso limítrofe, ainda sem confirmação.",
        "Força e amplitude de movimento dos membros superiores não estão implementadas.",
    ),
    "limb_prosthesis": (
        "Parte do pé junto com a prótese, e a combinação de acima e abaixo do joelho, ficam para a avaliação de especialista; o guia não escolhe uma classe.",
        "O tipo de prótese e o ajuste dela não entram.",
    ),
}
LIMITS_COMMON = (
    "Provas e equipamentos não aparecem aqui e ainda estão por validar. "
    "A leitura das regras é nossa e está por validar com a especialista."
)

# --- practice (K2) and transparency (K11) -------------------------------------------------------------------

PRACTICE_HEADING = "Praticar"
PRACTICE_TEXT = (
    "Quer ver como isso aparece em um caso? No modo educação você responde a casos fictícios deste grupo "
    "e depois vê o {{rastro|rastro dos critérios}}, passo a passo."
)
PRACTICE_LINK = "Praticar casos deste grupo"
TRANSPARENCY_LINK = "Ver a versão das regras e o estado de cada grupo"

# --- figures ------------------------------------------------------------------------------------------------

FIG_LOGMAR_TITLE = "Escala de acuidade visual em logMAR"
FIG_LOGMAR_CAPTION = "Faixas de acuidade de cada classe no {{logmar|logMAR}}. Esquema, sem escala de exame."
FIG_LOGMAR_LONG = (
    "Barra horizontal com marcas de ${axis_min} a ${axis_max}. Da esquerda para a direita: de ${low13} a ${high13}, classe ${c13} "
    "(pontilhado); de ${high13} a ${low12}, faixa sem classe no livreto (cruzado); de ${low12} a ${high12}, classe ${c12} (listrado "
    "na diagonal); acima de ${gt11} até ${axis_max}, classe ${c11} (preenchido em linhas verticais). "
    "Valores maiores indicam acuidade mais baixa."
)
FIG_FIELD_TITLE = "Limites do campo visual"
FIG_FIELD_CAPTION = "Dois círculos em proporção entre si, que mostram os limites do {{campo-visual|campo visual}}. Esquema."
FIG_FIELD_LONG = (
    "Dois círculos com o mesmo centro. O círculo menor representa um campo visual abaixo de ${field12} graus de diâmetro e leva o rótulo "
    "classe ${c12} (listrado na diagonal). O anel entre o círculo menor e o maior vai de ${field12} a ${field13} graus de diâmetro e leva o rótulo "
    "classe ${c13} (pontilhado). Os dois círculos estão em proporção de tamanho entre si."
)
FIG_STATURE_TITLE = "Medidas usadas na baixa estatura"
FIG_STATURE_CAPTION = "Onde se medem a estatura e o {{comprimento-do-braco|comprimento do braço mais longo}}. Esquema, não é uma pessoa."
FIG_STATURE_LONG = (
    "Boneco de traços, de frente. Uma linha vertical ao lado do corpo, da cabeça aos pés, marca a estatura. Uma linha tracejada "
    "no braço, do ombro ({{acromio|acrômio}}) até a ponta do dedo mais longo, marca o comprimento do braço mais longo. "
    "As duas medidas, somadas, formam a soma usada pela regra."
)
FIG_LEVELS_LOWER_TITLE = "Níveis de amputação no membro inferior"
FIG_LEVELS_LOWER_CAPTION = "Três níveis que as regras distinguem no membro inferior. Esquema, não é uma pessoa."
FIG_LEVELS_LOWER_LONG = (
    "Uma perna desenhada em traços, do quadril ao pé, com três marcas horizontais. A marca mais baixa é parte do pé (nível de "
    "Lisfranc), em linha pontilhada curta. A marca do meio é abaixo do joelho, em linha tracejada. A marca mais alta é através ou "
    "acima do joelho, em linha contínua. Cada marca tem o nome escrito ao lado."
)
FIG_LEVELS_UPPER_TITLE = "Níveis de amputação no membro superior"
FIG_LEVELS_UPPER_CAPTION = "Dois níveis que as regras distinguem no membro superior. Esquema, não é uma pessoa."
FIG_LEVELS_UPPER_LONG = (
    "Um braço desenhado em traços, do ombro à mão, com duas marcas. A marca mais baixa é o nível do punho, em linha tracejada. "
    "A marca mais alta é através ou acima do cotovelo, em linha contínua. Cada marca tem o nome escrito ao lado."
)
FIG_PATTERN_TITLE = "Esquema do padrão de amputação da classe ${class_id}"
FIG_PATTERN_CAPTION = "Um padrão da classe ${class_id}. Esquema com traços, não é uma pessoa; o lado desenhado não muda a classe."
FIG_PATTERN_LONG_START = (
    "Boneco de traços, de frente, com os quatro membros. Esquerda e direita são as do próprio desenho: "
    "esquerda na metade esquerda da imagem."
)
FIG_PATTERN_LIMB = "{limb}: {state}."
FIG_PATTERN_LIMB_NAMES = {
    "lower_left": "Perna esquerda",
    "lower_right": "Perna direita",
    "upper_left": "Braço esquerdo",
    "upper_right": "Braço direito",
}
FIG_PATTERN_STATE_NONE = "sem amputação, desenhada inteira"
FIG_PATTERN_STATE_CUT = "amputação {level}, desenhada até esse ponto"
FIG_PATTERN_PROSTHESIS = " Uma linha tracejada continua a perna até o pé e representa a prótese de corrida."
FIG_LEVEL_SHORT = {
    ("lower", 1): "pé parcial",
    ("lower", 2): "abaixo do joelho",
    ("lower", 3): "acima do joelho",
    ("upper", 1): "punho",
    ("upper", 2): "cotovelo ou acima",
}

# --- freshness ----------------------------------------------------------------------------------------------

FOOTER_VERSION = "Versão das regras: ${rules_id}. Conteúdo gerado em ${generated_on}."
FRESHNESS_WARNING = (
    "Este guia foi gerado com a versão ${page_rules_id} das regras, e o servidor usa a versão ${live_rules_id}. "
    "O texto pode estar desatualizado."
)

# --- glossary -----------------------------------------------------------------------------------------------
# id -> (term, definition). Definitions are short, ours, and have no digits.

GLOSSARY = {
    "classe-esportiva": (
        "Classe esportiva",
        "Grupo de atletas com um nível parecido de impacto da deficiência no desempenho no esporte. Cada classe tem um número.",
    ),
    "classificacao": (
        "Classificação",
        "O processo oficial que coloca cada atleta em uma classe. É feito por classificadores, em avaliação presencial. Este guia não faz classificação.",
    ),
    "classificador": (
        "Classificador",
        "Pessoa formada e credenciada para avaliar atletas e atribuir a classe esportiva.",
    ),
    "grupo-de-deficiencia": (
        "Grupo de deficiência",
        "Conjunto de classes que dependem do mesmo tipo de característica, como a visão, a estatura ou a amputação de membros.",
    ),
    "deficiencia-elegivel": (
        "Deficiência elegível",
        "Tipo de deficiência que o esporte reconhece como válido para competir em uma classe.",
    ),
    "criterio-minimo": (
        "Critério mínimo de deficiência",
        "O mínimo que a deficiência precisa atingir para que a pessoa possa competir em uma classe do esporte.",
    ),
    "livreto": (
        "Livreto do CPB",
        "Documento do Comitê Paralímpico Brasileiro (2024) que descreve as classes do atletismo. É a fonte que lemos, e não o reproduzimos aqui.",
    ),
    "codigos-t-f": (
        "Códigos T e F",
        "A letra T indica provas de pista e saltos, e a letra F indica lançamentos e arremessos. Os códigos vêm do catálogo do projeto, e a lista de provas está por validar.",
    ),
    "logmar": (
        "logMAR",
        "Escala usada para registrar a acuidade visual. Quanto maior o valor, menor a acuidade.",
    ),
    "acuidade": (
        "Acuidade visual",
        "Quanto a pessoa enxerga de detalhes, em geral medida com uma tabela de letras ou símbolos.",
    ),
    "melhor-olho": (
        "Melhor olho, com a melhor correção",
        "A acuidade é medida no olho que enxerga melhor, usando óculos ou lentes quando a pessoa os utiliza.",
    ),
    "campo-visual": (
        "Campo visual",
        "A área que a pessoa enxerga ao olhar para a frente, sem mexer os olhos. O livreto mede o campo em graus de diâmetro. Outras fontes, inclusive artigos científicos, usam o raio, que é a metade: o mesmo limite aparece lá com a metade do valor.",
    ),
    "baixa-estatura": (
        "Baixa estatura",
        "Estatura e comprimento dos membros menores do que os limites definidos nas regras para a classe.",
    ),
    "acromio": (
        "Acrômio",
        "A ponta do osso do ombro, de onde se começa a medir o comprimento do braço.",
    ),
    "comprimento-do-braco": (
        "Comprimento do braço mais longo",
        "A medida do acrômio até a ponta do dedo mais longo, no braço mais longo.",
    ),
    "soma": (
        "Soma de estatura e braço",
        "A estatura mais o comprimento do braço mais longo. É um dos três limites da baixa estatura.",
    ),
    "classes-aninhadas": (
        "Classes aninhadas",
        "Classes em que os limites de uma contêm os da outra. Quando o caso atende as duas, vale a mais comprometida.",
    ),
    "amputacao": (
        "Amputação",
        "A ausência de parte de um membro, de nascença ou por cirurgia ou acidente. Aqui é tratada como uma característica que define a classe.",
    ),
    "nivel-de-amputacao": (
        "Nível de amputação",
        "O ponto do membro em que a amputação acontece, por exemplo abaixo do joelho ou no nível do punho.",
    ),
    "atraves-do-joelho": (
        "Através do joelho",
        "Amputação no nível da própria articulação do joelho.",
    ),
    "acima-do-joelho": (
        "Acima do joelho",
        "Amputação na coxa, acima da articulação do joelho.",
    ),
    "abaixo-do-joelho": (
        "Abaixo do joelho",
        "Amputação na perna, entre o joelho e o pé.",
    ),
    "pe-parcial": (
        "Parte do pé (nível de Lisfranc)",
        "Amputação que preserva parte do pé. O nome vem da articulação de Lisfranc, no meio do pé.",
    ),
    "punho": (
        "Punho",
        "A articulação entre o antebraço e a mão.",
    ),
    "cotovelo": (
        "Cotovelo",
        "A articulação entre o braço e o antebraço.",
    ),
    "protese-de-corrida": (
        "Prótese de corrida",
        "Prótese feita para correr, em geral de lâmina. Neste guia, indica o grupo de classes de quem compete com prótese.",
    ),
    "em-pe-sem-protese": (
        "Em pé e sem prótese",
        "A posição de competição de quem corre ou salta de pé, sem usar prótese.",
    ),
    "caso-limitrofe": (
        "Caso limítrofe",
        "Caso em que as regras do projeto não escolhem uma classe sozinhas, por cair entre duas ou por pedir avaliação de especialista.",
    ),
    "rastro": (
        "Rastro dos critérios",
        "A lista de critérios verificados em um caso, com o valor do caso e o resultado de cada um. Aparece no modo educação.",
    ),
    "leitura-nossa": (
        "Leitura nossa",
        "A interpretação que o projeto fez do livreto. Ainda está por validar com a especialista e pode mudar.",
    ),
}

GLOSSARY_TITLE = "Glossário"
GLOSSARY_INTRO = "Definições curtas, nossas, dos termos usados no guia. Cada termo do texto leva até aqui."
PAGE_TERMS_HEADING = "Termos desta página"

# --- forbidden tone (a test scans the prose for these) -------------------------------------------------------

TONE_AVOID = (
    "perda",
    "perdeu",
    "sofre",
    "sofrimento",
    "superação",
    "superar",
    "vítima",
    "portador",
    "falta de",
    "deficiente",
    "coitado",
)
