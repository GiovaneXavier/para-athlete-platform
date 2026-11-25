import { Badge } from "@/components/ui/badge";
import type { ModelCard, TransparencyReport } from "@/lib/api-types";
import { CATEGORY_LABELS, dateBr, pct } from "@/lib/transparency-format";
import { DataTable, EvidenceBadge, Hash, Note, Section, Td, Th } from "./parts";

const EXPERIMENT_NAMES = ["E1", "E7", "V1"] as const;

function unchangedText(report: TransparencyReport): string {
  const values = EXPERIMENT_NAMES.map((name) => report.rules.unchanged_since_runs[name]);
  if (values.every((v) => v === true)) {
    return "Os experimentos E1, E7 e V1 rodaram com este mesmo livro de regras (o id calculado no commit de origem é igual ao atual).";
  }
  if (values.some((v) => v === false)) {
    const changed = EXPERIMENT_NAMES.filter((name) => report.rules.unchanged_since_runs[name] === false).join(", ");
    return `Atenção: o livro de regras mudou depois dos experimentos ${changed}. Os números abaixo descrevem as regras anteriores.`;
  }
  return "Não foi possível conferir se o livro de regras mudou desde os experimentos (o histórico do git não estava disponível na exportação).";
}

export function RulesSection({ report }: { report: TransparencyReport }) {
  const { rules } = report;
  return (
    <Section id="regras" title="Livro de regras">
      <p className="max-w-3xl">
        Versão do livro de regras em uso: <code className="font-mono text-sm">{rules.id}</code>. O id é um hash do catálogo
        (<code className="font-mono text-sm">classes.yaml</code>), do motor, do carregador e do esquema de perfil e dos
        avaliadores; ele muda sempre que um desses arquivos muda. O catálogo tem {rules.n_classes} classes em {rules.n_groups} grupos. {unchangedText(report)}
      </p>
      <details className="rounded-lg border bg-card p-3 text-sm">
        <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
          Arquivos que entram no hash
        </summary>
        <ul className="mt-2 space-y-1">
          {rules.files.map((file) => (
            <li key={file.path} className="flex flex-wrap items-center gap-2">
              <code className="font-mono text-xs">{file.path}</code>
              <Hash value={file.sha256} />
            </li>
          ))}
        </ul>
      </details>

      <h3 className="pt-2 text-lg font-semibold">Grupos de classes e o estado de cada um</h3>
      <p className="max-w-3xl text-sm text-foreground/85">
        <strong>Implementado</strong> quer dizer que o critério numérico do livreto do CPB (2024) está codificado.{" "}
        <strong>Parcial</strong> quer dizer que só parte dos critérios está. <strong>Provisório</strong> quer dizer que o livreto
        descreve a classe só em texto e a tabela de decisão é a nossa leitura, ainda a validar com a especialista. Nenhum grupo foi
        revisado por classificadores oficiais.
      </p>
      <DataTable label="Grupos de classes e estado" caption="Grupos de classes, estado e origem dos critérios">
        <thead className="border-b bg-muted/40">
          <tr>
            <Th>Grupo</Th>
            <Th>Classes</Th>
            <Th>Estado</Th>
            <Th>Origem dos critérios</Th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {report.rule_groups.map((group) => (
            <tr key={group.group}>
              <Td>{group.group}</Td>
              <Td>{group.classes}</Td>
              <Td>
                <Badge variant={group.category === "provisional" ? "outline" : "secondary"}>
                  {CATEGORY_LABELS[group.category] ?? group.state}
                </Badge>
              </Td>
              <Td>{group.origin}</Td>
            </tr>
          ))}
        </tbody>
      </DataTable>

      <h3 className="pt-2 text-lg font-semibold">Divergências e limites conhecidos</h3>
      <ul className="max-w-3xl list-disc space-y-1 pl-5">
        {report.known_divergences.map((item) => (
          <li key={item.id}>{item.text}</li>
        ))}
      </ul>

      <h3 className="pt-2 text-lg font-semibold">Histórico das regras</h3>
      <ol className="max-w-3xl space-y-3">
        {[...report.changelog].reverse().map((entry) => (
          <li key={entry.rules_id} className="rounded-lg border p-3 text-sm">
            <p className="font-medium">
              <code className="font-mono">{entry.rules_id}</code> · {dateBr(entry.date)}
            </p>
            <p className="mt-1 text-foreground/85">{entry.summary}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}

const STATUS_LABELS: Record<string, string> = {
  preliminary: "Preliminar",
  unknown: "Desconhecido",
};

function CardMetrics({ card }: { card: ModelCard }) {
  if (!card.metrics) return null;
  const { metrics } = card;
  return (
    <div className="space-y-2">
      <h3 className="flex flex-wrap items-center gap-2 text-lg font-semibold">
        Resultado do treino original <EvidenceBadge />
      </h3>
      <p className="max-w-3xl text-sm text-foreground/85">
        Média e desvio entre {metrics.n_runs} execuções, lidos do arquivo de métricas que acompanha o checkpoint. É concordância com
        os rótulos sintéticos das regras sob ruído simulado, não validade clínica. Esse protocolo foi substituído; os números do
        protocolo atual estão nas seções de experimentos.
      </p>
      <DataTable label="Resultado do treino original do modelo" caption="MLP do treino original (nível N1)">
        <thead className="border-b bg-muted/40">
          <tr>
            <Th>Medida</Th>
            <Th numeric>Média ± desvio</Th>
          </tr>
        </thead>
        <tbody className="divide-y">
          <tr>
            <Td>Concordância com o rótulo sintético</Td>
            <Td numeric>
              {pct(metrics.mlp_agreement_with_rule_labels.mean)} ± {pct(metrics.mlp_agreement_with_rule_labels.std).replace("%", "")} p.p.
            </Td>
          </tr>
          <tr>
            <Td>F1 macro</Td>
            <Td numeric>
              {pct(metrics.mlp_macro_f1.mean)} ± {pct(metrics.mlp_macro_f1.std).replace("%", "")} p.p.
            </Td>
          </tr>
        </tbody>
      </DataTable>
    </div>
  );
}

export function ModelSection({ report }: { report: TransparencyReport }) {
  const card = report.model_card;
  return (
    <Section id="modelo" title="Ficha do modelo">
      {card ? (
        <>
          <p className="max-w-3xl">
            O modelo descrito aqui é o <strong>{card.name ?? "checkpoint sem nome registrado"}</strong>. Estado:{" "}
            <Badge variant="outline">{STATUS_LABELS[card.status] ?? card.status}</Badge>
          </p>
          {card.protocol ? (
            <div className="max-w-3xl space-y-1">
              <h3 className="text-lg font-semibold">Protocolo de treino</h3>
              <p>{card.protocol}</p>
            </div>
          ) : null}
          {card.limits.length > 0 ? (
            <div className="max-w-3xl space-y-1">
              <h3 className="text-lg font-semibold">Limites</h3>
              <ul className="list-disc space-y-1 pl-5">
                {card.limits.map((limit) => (
                  <li key={limit}>{limit}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="text-sm">
            Arquivo <code className="font-mono">{card.file_name}</code> ({(card.size_bytes / 1024).toFixed(0)} KB), SHA-256{" "}
            <Hash value={card.sha256} />
          </p>
          <CardMetrics card={card} />
        </>
      ) : (
        <Note title="Sem ficha de modelo">
          <p>A exportação não encontrou o checkpoint do modelo. Sem ele, a triagem usa só as regras.</p>
        </Note>
      )}
    </Section>
  );
}
