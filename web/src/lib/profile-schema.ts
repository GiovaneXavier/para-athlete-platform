import type { ProfileIn } from "./api-types";

// What the professional fills in, per kind of impairment. The values map onto the
// ProfileIn fields of the API; labels follow the CPB booklet wording.

export type Values = Record<string, string | boolean | string[] | undefined>;

export interface Option {
  value: string;
  label: string;
}

interface BaseField {
  name: string;
  label: string;
  help?: string;
  when?: (values: Values) => boolean;
  /** Pre-filled and always answered: no "clear" button. */
  required?: boolean;
}

export interface NumberField extends BaseField {
  kind: "number";
  min: number;
  max: number;
  step: number;
  unit?: string;
}

export interface SelectField extends BaseField {
  kind: "select";
  options: Option[];
  /** The API expects a number for this field. */
  numeric?: boolean;
}

export interface TriField extends BaseField {
  kind: "tri";
}

export interface MultiField extends BaseField {
  kind: "multi";
  options: Option[];
}

export type FieldDef = NumberField | SelectField | TriField | MultiField;

export interface Section {
  title?: string;
  description?: string;
  fields: FieldDef[];
}

export type GroupId = "visual" | "intellectual" | "short_stature" | "limb" | "seated" | "brain";

export interface GroupDef {
  id: GroupId;
  title: string;
  description: string;
  icon: "eye" | "puzzle" | "ruler" | "footprints" | "accessibility" | "brain";
  sections: Section[];
  defaults: Values;
  fixed: Partial<ProfileIn>;
  /** `profile` holds only the visible, filled-in fields, so hidden stale answers do not count. */
  impairments: (values: Values, profile: Record<string, unknown>) => string[];
}

const LOWER_LEVELS: Option[] = [
  { value: "0", label: "Sem amputação" },
  { value: "1", label: "Pé parcial (Lisfranc)" },
  { value: "2", label: "Abaixo do joelho" },
  { value: "3", label: "Através ou acima do joelho" },
];

const UPPER_LEVELS: Option[] = [
  { value: "0", label: "Sem amputação" },
  { value: "1", label: "Punho (através ou acima)" },
  { value: "2", label: "Cotovelo (através ou acima)" },
];

const hasAnkleCriteria = (v: Values) =>
  v.ankle_pf_mrc !== undefined || v.ankle_rom_deg !== undefined || v.leg_length_diff_cm !== undefined;

// Strength, range of motion and leg-length answers mean the corresponding impairment is present.
function ankleImpairments(profile: Record<string, unknown>): string[] {
  const out: string[] = [];
  if (profile.ankle_pf_mrc !== undefined) out.push("muscle_power");
  if (profile.ankle_rom_deg !== undefined) out.push("rom");
  if (profile.leg_length_diff_cm !== undefined) out.push("leg_length_difference");
  return out;
}

const ANKLE_FIELDS: FieldDef[] = [
  {
    kind: "number",
    name: "ankle_pf_mrc",
    label: "Força da flexão plantar",
    min: 0,
    max: 5,
    step: 1,
    unit: "grau 0 a 5",
    help: "Grau 2 ou menos já é um critério mínimo (o atleta não consegue ficar na ponta do pé).",
  },
  {
    kind: "number",
    name: "ankle_rom_deg",
    label: "Arco de movimento passivo do tornozelo",
    min: 0,
    max: 180,
    step: 1,
    unit: "graus",
    help: "Entre a flexão plantar e a dorsiflexão. 10° ou menos é um critério mínimo.",
  },
  {
    kind: "number",
    name: "leg_length_diff_cm",
    label: "Diferença de comprimento das pernas",
    min: 0,
    max: 60,
    step: 0.5,
    unit: "cm",
    help: "7 cm ou mais é um critério mínimo.",
  },
];

export const GROUPS: GroupDef[] = [
  {
    id: "visual",
    title: "Deficiência visual",
    description: "Acuidade e campo visual (classes 11 a 13)",
    icon: "eye",
    defaults: {},
    fixed: { posture: "standing" },
    impairments: () => ["visual"],
    sections: [
      {
        description: "Sempre no melhor olho e com a melhor correção (óculos ou lentes).",
        fields: [
          {
            kind: "number",
            name: "logmar_best_eye",
            label: "Acuidade visual",
            min: -0.5,
            max: 3.5,
            step: 0.05,
            unit: "logMAR",
            help: "Quanto maior, pior a visão. Ex.: 1,0 a 1,4 corresponde à classe 13.",
          },
          {
            kind: "number",
            name: "visual_field_deg",
            label: "Campo visual",
            min: 0,
            max: 180,
            step: 1,
            unit: "graus de diâmetro",
            help: "Menos de 10° é classe 12 e menos de 40° é classe 13.",
          },
        ],
      },
    ],
  },
  {
    id: "intellectual",
    title: "Deficiência intelectual",
    description: "QI e comportamento adaptativo (classe 20)",
    icon: "puzzle",
    defaults: {},
    fixed: { posture: "standing" },
    impairments: () => ["intellectual"],
    sections: [
      {
        description: "O QI deve vir de teste aplicado por psicólogo (WISC-IV até 16 anos, WAIS-IV a partir dos 17).",
        fields: [
          { kind: "number", name: "iq", label: "QI total", min: 20, max: 160, step: 1 },
          { kind: "tri", name: "adaptive_limitation", label: "Limitação significativa no comportamento adaptativo?" },
          { kind: "tri", name: "onset_before_22", label: "Diagnosticada antes dos 22 anos?" },
        ],
      },
    ],
  },
  {
    id: "short_stature",
    title: "Baixa estatura",
    description: "Estatura e comprimento do braço (classes 40 e 41)",
    icon: "ruler",
    defaults: {},
    fixed: { posture: "standing" },
    impairments: () => ["short_stature"],
    sections: [
      {
        fields: [
          {
            kind: "select",
            name: "sex",
            label: "Sexo",
            options: [
              { value: "M", label: "Masculino" },
              { value: "F", label: "Feminino" },
            ],
            help: "Os limites da classificação são diferentes por sexo.",
          },
          {
            kind: "number",
            name: "height_cm",
            label: "Estatura",
            min: 40,
            max: 250,
            step: 0.1,
            unit: "cm",
            help: "Medida com estadiômetro.",
          },
          {
            kind: "number",
            name: "longest_arm_cm",
            label: "Comprimento do braço mais longo",
            min: 10,
            max: 120,
            step: 0.1,
            unit: "cm",
            help: "Do acrômio ao dedo mais longo, com o atleta deitado e o braço a 90° de abdução. Compare os dois lados.",
          },
        ],
      },
    ],
  },
  {
    id: "limb",
    title: "Amputação ou déficit de membros",
    description: "Em pé, com ou sem prótese (classes 42 a 47 e 61 a 64)",
    icon: "footprints",
    defaults: { posture: "standing", lower_left: "0", lower_right: "0", upper_left: "0", upper_right: "0" },
    fixed: {},
    impairments: (_v, p) => ["limb_deficiency", ...ankleImpairments(p)],
    sections: [
      {
        fields: [
          {
            kind: "select",
            name: "posture",
            label: "Como o atleta compete",
            required: true,
            options: [
              { value: "standing", label: "Em pé, sem prótese" },
              { value: "prosthesis", label: "Em pé, com prótese" },
            ],
          },
        ],
      },
      {
        title: "Membros inferiores",
        fields: [
          { kind: "select", name: "lower_left", label: "Esquerdo", required: true, options: LOWER_LEVELS, numeric: true },
          { kind: "select", name: "lower_right", label: "Direito", required: true, options: LOWER_LEVELS, numeric: true },
        ],
      },
      {
        title: "Membros superiores",
        fields: [
          { kind: "select", name: "upper_left", label: "Esquerdo", required: true, options: UPPER_LEVELS, numeric: true },
          { kind: "select", name: "upper_right", label: "Direito", required: true, options: UPPER_LEVELS, numeric: true },
        ],
      },
      {
        title: "Tornozelo e pernas (opcional)",
        description: "Para déficits sem amputação. Preencha só o que foi medido.",
        fields: [
          ...ANKLE_FIELDS,
          {
            kind: "select",
            name: "lower_limb_sides_affected",
            label: "Lados afetados",
            numeric: true,
            options: [
              { value: "1", label: "Um lado" },
              { value: "2", label: "Os dois lados" },
            ],
            when: hasAnkleCriteria,
          },
        ],
      },
    ],
  },
  {
    id: "seated",
    title: "Lesão medular e cadeira de rodas",
    description: "Compete sentado (classes F51 a F57 e T51 a T54)",
    icon: "accessibility",
    defaults: {},
    fixed: { posture: "seated" },
    impairments: (_v, p) => [...new Set(["muscle_power", ...ankleImpairments(p)])],
    sections: [
      {
        description: "Descreva a função que o atleta preserva, não o diagnóstico.",
        fields: [
          {
            kind: "select",
            name: "arm_function",
            label: "Função de braço e mão",
            numeric: true,
            options: [
              { value: "0", label: "Déficit de ombro, extensores do cotovelo e dedos" },
              { value: "1", label: "Déficit só na flexão e extensão dos dedos" },
              { value: "2", label: "Só a musculatura intrínseca da mão comprometida" },
              { value: "3", label: "Preservada" },
            ],
          },
          {
            kind: "select",
            name: "trunk_function",
            label: "Função de tronco",
            numeric: true,
            options: [
              { value: "0", label: "Nenhuma" },
              { value: "1", label: "Parcial" },
              { value: "2", label: "Total" },
            ],
          },
          {
            kind: "select",
            name: "leg_function",
            label: "Função das pernas",
            numeric: true,
            options: [
              { value: "0", label: "Nenhuma" },
              { value: "1", label: "Só flexores de quadril" },
              { value: "2", label: "Quadril e joelho parciais" },
              { value: "3", label: "Comprometimento só no nível do tornozelo" },
              { value: "4", label: "Normal" },
            ],
          },
        ],
      },
      {
        title: "Critérios do tornozelo",
        description: "Para comprometimento no nível do tornozelo (classe F57).",
        fields: ANKLE_FIELDS.map((f) => ({ ...f, when: (v: Values) => v.leg_function === "3" })),
      },
    ],
  },
  {
    id: "brain",
    title: "Paralisia cerebral e lesão encefálica",
    description: "Sentado, em pé ou na Petra (classes 31 a 38 e 71 e 72)",
    icon: "brain",
    defaults: { brain_impairment_report: true },
    fixed: {},
    impairments: (v) => (Array.isArray(v.impairments) ? v.impairments : []),
    sections: [
      {
        fields: [
          {
            kind: "multi",
            name: "impairments",
            label: "Tipo de comprometimento",
            help: "Marque todos que se aplicam (quadros mistos são comuns).",
            options: [
              { value: "hypertonia", label: "Hipertonia (espasticidade)" },
              { value: "athetosis", label: "Atetose" },
              { value: "ataxia", label: "Ataxia" },
            ],
          },
          {
            kind: "select",
            name: "posture",
            label: "Como o atleta compete",
            options: [
              { value: "seated", label: "Sentado (cadeira de corrida ou arremesso)" },
              { value: "standing", label: "Em pé" },
              { value: "frame_runner", label: "Petra (frame running)" },
            ],
          },
          {
            kind: "tri",
            name: "brain_impairment_report",
            label: "Há laudo ou exame comprovando a lesão encefálica?",
            help: "É obrigatório na classificação oficial.",
          },
          {
            kind: "select",
            name: "neuro_severity",
            label: "Impacto funcional na prática do esporte",
            numeric: true,
            options: [
              { value: "0", label: "Nenhum" },
              { value: "1", label: "Leve" },
              { value: "2", label: "Moderado" },
              { value: "3", label: "Severo" },
            ],
          },
          {
            kind: "select",
            name: "cp_distribution",
            label: "Distribuição do comprometimento",
            options: [
              { value: "hemiplegia", label: "Hemiplegia (um lado do corpo)" },
              { value: "diplegia", label: "Diplegia (sobretudo as pernas)" },
              { value: "triplegia", label: "Triplegia" },
              { value: "quadriplegia", label: "Quadriplegia" },
            ],
          },
        ],
      },
      {
        title: "Cadeira de corrida",
        fields: [
          {
            kind: "select",
            name: "chair_propulsion",
            label: "Como propulsiona a cadeira de corrida",
            numeric: true,
            options: [
              { value: "1", label: "Com os pés" },
              { value: "2", label: "Com os braços, apesar do comprometimento" },
              { value: "3", label: "Com os braços, de forma assimétrica ou com pouca potência" },
              { value: "4", label: "Com os braços, de forma simétrica e potente" },
            ],
            when: (v) => v.posture === "seated",
          },
        ],
      },
      {
        title: "Petra",
        fields: [
          {
            kind: "tri",
            name: "transfers_independently",
            label: "Transfere-se sozinho para a Petra?",
            when: (v) => v.posture === "frame_runner",
          },
          {
            kind: "tri",
            name: "walks_short_distances",
            label: "Caminha distâncias curtas?",
            when: (v) => v.posture === "frame_runner",
          },
          {
            kind: "tri",
            name: "trunk_straps_needed",
            label: "Precisa de amarração para fixar o tronco?",
            when: (v) => v.posture === "frame_runner",
          },
        ],
      },
    ],
  },
];

export const GROUPS_BY_ID = Object.fromEntries(GROUPS.map((g) => [g.id, g])) as Record<GroupId, GroupDef>;

export function allFields(group: GroupDef): FieldDef[] {
  return group.sections.flatMap((s) => s.fields);
}

/** Visible fields of a section for the current values. */
export const visibleFields = (section: Section, values: Values) =>
  section.fields.filter((f) => !f.when || f.when(values));

/** ProfileIn for the API: only the fields that are visible and filled in. */
export function buildProfile(group: GroupDef, values: Values): ProfileIn {
  const profile: Record<string, unknown> = { ...group.fixed };
  for (const field of allFields(group)) {
    if (field.kind === "multi") continue;
    if (field.when && !field.when(values)) continue;
    const raw = values[field.name];
    if (raw === undefined || raw === "") continue;
    if (field.kind === "number") profile[field.name] = Number(raw);
    else if (field.kind === "select") profile[field.name] = field.numeric ? Number(raw) : raw;
    else profile[field.name] = raw === true;
  }
  profile.impairments = group.impairments(values, profile);
  return profile as ProfileIn;
}

/** Why the form cannot be submitted yet, or null. */
export function validate(group: GroupDef, values: Values): string | null {
  if (group.id === "brain" && group.impairments(values, {}).length === 0) {
    return "Marque pelo menos um tipo de comprometimento.";
  }
  // Answers that equal the pre-filled defaults do not count as information.
  const touched = allFields(group).some(
    (f) => f.kind !== "multi" && values[f.name] !== undefined && values[f.name] !== group.defaults[f.name],
  );
  return touched ? null : "Preencha pelo menos um campo.";
}
