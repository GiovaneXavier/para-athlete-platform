import type { E1Split, E7Split, Metrics, Source, TransparencyReport } from "@/lib/api-types";
import { SPLIT_LABELS, SYSTEM_LABELS, num, pct, shortHash, statNum, statPct, dateBr } from "@/lib/transparency-format";
import { DataTable, EvidenceBadge, Note, Section, Td, Th } from "./parts";

const SELECTIVE_LABELS: Record<string, string> = {
  mlp_maxprob: "MLP (probabilidade máxima)",
  gb_maxprob: "Gradient boosting (probabilidade máxima)",
};

const BAND_LABELS: Record<string, string> = {
  "0": "Nenhum campo faltando",
  "1": "1 campo faltando",
  "2+": "2 ou mais campos faltando",
};

function SourceLine({ source }: { source: Source }) {
  return (
    <p className="text-sm text-foreground/85">
      Origem: commit <code className="font-mono text-xs">{source.commit ? shortHash(source.commit, 8) : "desconhecido"}</code>
      {source.code_tree_dirty ? " (com alterações no código)" : ""}, gerado em {dateBr(source.written_at)}, {source.n_seeds}{" "}
      sementes{source.n_per_label ? `, ${source.n_per_label} perfis verdadeiros por rótulo` : ""}. Comando:{" "}
      <code className="font-mono text-xs">{source.command}</code>
    </p>
  );
}

// --- E1 -----------------------------------------------------------------------------------------

function E1Table({ mode, split }: { mode: string; split: E1Split }) {
  const label = SPLIT_LABELS[mode] ?? mode;
  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold">{label}</h3>
      <SourceLine source={split.source} />
      <DataTable
        label={`E1, ${label}`}
        caption={
          <span className="flex flex-wrap items-center gap-2">
            E1, {label.toLowerCase()}: ruído e faltantes no nível padrão, treino e teste no mesmo nível <EvidenceBadge />
          </span>
        }
      >
        <thead className="border-b bg-muted/40">
          <tr>
            <Th>Sistema</Th>
            <Th numeric>Concordância com o rótulo</Th>
            <Th numeric>F1 macro</Th>
            <Th numeric>Decide em</Th>
            <Th numeric>Concordância quando decide</Th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {Object.entries(split.systems).map(([system, metrics]) => (
            <tr key={system}>
              <Td>{SYSTEM_LABELS[system] ?? system}</Td>
              <Td numeric>{statPct(metrics.agreement)}</Td>
              <Td numeric>{statPct(metrics.macro_f1)}</Td>
              <Td numeric>{statPct(metrics.coverage)}</Td>
              <Td numeric>{statPct(metrics.agreement_when_decided)}</Td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </div>
  );
}

export function E1Section({ report }: { report: TransparencyReport }) {
  const { E1 } = report.experiments;
  return (
    <Section id="e1" title="E1: ruído e campos faltantes">
      <p className="max-w-3xl">
        Compara as regras, as regras com imputação, o gradient boosting, o MLP e o híbrido (regras e, onde elas se abstêm, o MLP) sobre
        perfis sintéticos com ruído de medida e campos faltantes simulados. “Decide em” é a fração de casos em que o sistema dá uma
        resposta; as regras se abstêm no resto, e esses casos contam como erro na primeira coluna. Valores: média ± desvio entre
        sementes.
      </p>
      {Object.entries(E1.splits).map(([mode, split]) => (
        <E1Table key={mode} mode={mode} split={split} />
      ))}
    </Section>
  );
}

// --- E7 -----------------------------------------------------------------------------------------

function ConformalTable({ mode, split }: { mode: string; split: E7Split }) {
  const label = SPLIT_LABELS[mode] ?? mode;
  const rows = Object.entries(split.conformal).flatMap(([method, byAlpha]) =>
    Object.entries(byAlpha).map(([alpha, entry]) => ({ method, alpha: Number(alpha), entry })),
  );
  return (
    <DataTable
      label={`E7, conjuntos conformes, ${label}`}
      caption={
        <span className="flex flex-wrap items-center gap-2">
          E7, conjuntos conformes do MLP, {label.toLowerCase()} <EvidenceBadge />
        </span>
      }
    >
      <thead className="border-b bg-muted/40">
        <tr>
          <Th>Escore</Th>
          <Th numeric>α</Th>
          <Th numeric>Cobertura alvo (1 − α)</Th>
          <Th numeric>Cobertura empírica</Th>
          <Th numeric>Pior divisão</Th>
          <Th numeric>Tamanho médio do conjunto</Th>
          <Th numeric>Conjuntos unitários</Th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {rows.map(({ method, alpha, entry }) => (
          <tr key={`${method}-${alpha}`}>
            <Td>{method}</Td>
            <Td numeric>{num(alpha, 2)}</Td>
            <Td numeric>{pct(1 - alpha, 0)}</Td>
            <Td numeric>{statPct(entry.metrics.coverage)}</Td>
            <Td numeric>{pct(entry.coverage_min_over_splits)}</Td>
            <Td numeric>{statNum(entry.metrics.size)}</Td>
            <Td numeric>{statPct(entry.metrics.frac_singleton)}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function BandTable({ mode, split }: { mode: string; split: E7Split }) {
  const label = SPLIT_LABELS[mode] ?? mode;
  const target = 1 - split.main_alpha;
  return (
    <DataTable
      label={`E7, cobertura por campos faltando, ${label}`}
      caption={
        <span className="flex flex-wrap items-center gap-2">
          E7, cobertura por número de campos faltando (escore LAC, α = {num(split.main_alpha, 2)}, alvo {pct(target, 0)}),{" "}
          {label.toLowerCase()} <EvidenceBadge />
        </span>
      }
    >
      <thead className="border-b bg-muted/40">
        <tr>
          <Th>Campos faltando</Th>
          <Th numeric>Cobertura empírica</Th>
          <Th numeric>Tamanho médio do conjunto</Th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {Object.entries(split.coverage_by_missing_fields).map(([band, entry]) => (
          <tr key={band}>
            <Td>{BAND_LABELS[band] ?? band}</Td>
            <Td numeric>{statPct(entry.coverage)}</Td>
            <Td numeric>{statNum(entry.size)}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function SelectiveTable({ mode, split }: { mode: string; split: E7Split }) {
  const label = SPLIT_LABELS[mode] ?? mode;
  return (
    <DataTable
      label={`E7, predição seletiva, ${label}`}
      caption={
        <span className="flex flex-wrap items-center gap-2">
          E7, predição seletiva (responde só quando está confiante), {label.toLowerCase()} <EvidenceBadge />
        </span>
      }
    >
      <thead className="border-b bg-muted/40">
        <tr>
          <Th>Pontuação de confiança</Th>
          <Th numeric>Concordância na cobertura das regras</Th>
          <Th numeric>Respondendo a 50%</Th>
          <Th numeric>Respondendo a 70%</Th>
          <Th numeric>Respondendo a 90%</Th>
          <Th numeric>Risco médio (AURC)</Th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {Object.entries(split.selective).map(([method, metrics]: [string, Metrics]) => (
          <tr key={method}>
            <Td>{SELECTIVE_LABELS[method] ?? method}</Td>
            <Td numeric>{statPct(metrics.selective_agreement_at_rules_coverage)}</Td>
            <Td numeric>{statPct(metrics.selective_agreement_at_50)}</Td>
            <Td numeric>{statPct(metrics.selective_agreement_at_70)}</Td>
            <Td numeric>{statPct(metrics.selective_agreement_at_90)}</Td>
            <Td numeric>{statNum(metrics.aurc, 3)}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

export function E7Section({ report }: { report: TransparencyReport }) {
  const { E7 } = report.experiments;
  return (
    <Section id="e7" title="E7: incerteza do modelo (predição seletiva e conforme)">
      <p className="max-w-3xl">
        Em vez de uma única classe, o método conforme devolve um <em>conjunto</em> de classes que, em média, contém a classe do rótulo
        sintético em pelo menos 1 − α dos casos. A garantia é <strong>marginal</strong>: vale na média de todos os casos, não para
        cada grupo nem para cada número de campos faltando. A segunda tabela mostra isso: a cobertura muda conforme faltam campos. O
        escore principal (LAC) e os valores de α foram declarados antes de rodar.
      </p>
      <p className="max-w-3xl text-sm text-foreground/85">
        Os desvios (±) são entre as sementes. Em cada semente, as 20 repartições de calibração e teste reaproveitam as mesmas linhas,
        então não são independentes; por isso a coluna “Pior divisão” mostra o pior caso entre elas, e o desvio sozinho tende a
        subestimar a variação real.
      </p>
      {Object.entries(E7.splits).map(([mode, split]) => (
        <div key={mode} className="space-y-3">
          <h3 className="text-lg font-semibold">{SPLIT_LABELS[mode] ?? mode}</h3>
          <SourceLine source={split.source} />
          <ConformalTable mode={mode} split={split} />
          <BandTable mode={mode} split={split} />
          <SelectiveTable mode={mode} split={split} />
        </div>
      ))}
    </Section>
  );
}

// --- V1 -----------------------------------------------------------------------------------------

const SUBSET_LABELS: Record<string, string> = {
  all: "Todos os casos de teste",
  true_duplicate: "Perfil verdadeiro já visto no treino",
  no_true_duplicate: "Perfil verdadeiro novo",
  observed_duplicate: "Perfil observado já visto no treino",
  no_observed_duplicate: "Perfil observado novo",
};

export function V1Section({ report }: { report: TransparencyReport }) {
  const { V1 } = report.experiments;
  const systems = ["rules", "rules_imp", "gb", "mlp", "hybrid"];
  return (
    <Section id="v1" title="V1: perfis repetidos entre treino e teste">
      <p className="max-w-3xl">
        Um perfil sintético pode aparecer no treino e no teste. Esta verificação mede quanto, e o que acontece com a concordância
        quando o teste só tem perfis que o modelo nunca viu.
      </p>
      <SourceLine source={V1.source} />
      <p className="max-w-3xl">
        Casos de teste cujo perfil verdadeiro (antes do ruído) já está no treino: <strong>{statPct(V1.duplicates_in_test.share_true_duplicate)}</strong>.
        Cujo perfil observado (depois do ruído e dos campos faltantes) já está no treino:{" "}
        <strong>{statPct(V1.duplicates_in_test.share_observed_duplicate)}</strong>.
      </p>
      <DataTable
        label="V1, concordância por tipo de caso de teste"
        caption={
          <span className="flex flex-wrap items-center gap-2">
            V1, concordância com o rótulo conforme o perfil já tenha sido visto no treino <EvidenceBadge />
          </span>
        }
      >
        <thead className="border-b bg-muted/40">
          <tr>
            <Th>Casos de teste</Th>
            {systems.map((s) => (
              <Th key={s} numeric>
                {SYSTEM_LABELS[s]}
              </Th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {Object.entries(V1.agreement_by_duplicate_subset).map(([subset, entry]) => (
            <tr key={subset}>
              <Td>{SUBSET_LABELS[subset] ?? subset}</Td>
              {systems.map((s) => (
                <Td key={s} numeric>
                  {statPct(entry.systems[s]?.agreement)}
                </Td>
              ))}
            </tr>
          ))}
        </tbody>
      </DataTable>
      <DataTable
        label="V1, divisão por perfil verdadeiro"
        caption={
          <span className="flex flex-wrap items-center gap-2">
            V1, teste só com perfis verdadeiros novos <EvidenceBadge />
          </span>
        }
      >
        <thead className="border-b bg-muted/40">
          <tr>
            <Th>Divisão</Th>
            <Th numeric>Rótulos do teste que o treino nunca viu</Th>
            {systems.map((s) => (
              <Th key={s} numeric>
                {SYSTEM_LABELS[s]}
              </Th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {Object.entries(V1.new_profile_splits).map(([variant, entry]) => (
            <tr key={variant}>
              <Td>{SPLIT_LABELS[variant] ?? variant}</Td>
              <Td numeric>{statPct(entry.split.share_test_label_unseen_in_train)}</Td>
              {systems.map((s) => (
                <Td key={s} numeric>
                  {statPct(entry.systems[s]?.agreement)}
                </Td>
              ))}
            </tr>
          ))}
        </tbody>
      </DataTable>
      <Note title="Como ler">
        <p>
          Na divisão que não garante os rótulos no treino, parte da queda vem de classes que o modelo nunca viu; a divisão por
          perfil com os rótulos garantidos no treino separa esse efeito. As regras não aprendem com o treino, então quase não mudam.
        </p>
      </Note>
    </Section>
  );
}
