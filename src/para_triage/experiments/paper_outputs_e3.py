"""Tables and macros of E3 (prevalence scenarios and natural sampler); called by paper_outputs.

The prevalence scenarios are illustrative stress tests, not estimates from data.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .e3 import SCENARIOS
from .paper_outputs import HEADER, macro, mean_sd, pct, pm, write

SYSTEMS = ("rules", "rules_imp", "gb", "mlp", "hybrid")
SYSTEM_LABEL = {"rules": "Rules", "rules_imp": "Rules + imputation", "gb": "Gradient boosting", "mlp": "MLP", "hybrid": "Hybrid"}
SYSTEM_TAG = {"rules": "Rules", "rules_imp": "RulesImp", "gb": "GB", "mlp": "MLP", "hybrid": "Hybrid"}
SCENARIO_LABEL = {"balanced": "Balanced (training distribution)", "screening": "Screening (no class $\\times 5$)", "rare_borderline": "Rare borderline cases",
                  "skewed_classes": "Skewed classes", "skewed_groups": "Skewed groups", "combined": "Skewed groups and screening"}
SCENARIO_TAG = {"balanced": "Balanced", "screening": "Screening", "rare_borderline": "RareBorderline", "skewed_classes": "SkewedClasses",
                "skewed_groups": "SkewedGroups", "combined": "Combined"}


def load(runs: Path) -> dict[str, pd.DataFrame]:
    names = ("scenarios", "scenario_conformal", "natural", "natural_conformal", "natural_labels", "natural_meta")
    return {n: pd.read_csv(runs / "e3" / f"{n}.csv") for n in names}


def acc(df: pd.DataFrame, system: str, column: str = "accuracy", **where) -> pd.Series:
    d = df[df.system == system]
    for k, v in where.items():
        d = d[d[k] == v]
    return d.set_index("seed")[column].sort_index()


def best_baseline(df: pd.DataFrame, **where) -> str:
    return max(("rules", "rules_imp", "gb"), key=lambda s: acc(df, s, **where).mean())


def table_scenarios(e: dict) -> str:
    s = e["scenarios"]
    head = "Scenario & " + " & ".join(SYSTEM_LABEL[x] for x in SYSTEMS) + " & MLP $-$ best baseline \\\\"
    lines = []
    for scenario, label in SCENARIO_LABEL.items():
        cols = {x: acc(s, x, scenario=scenario) for x in SYSTEMS}
        best = best_baseline(s, scenario=scenario)
        m, sd = mean_sd(cols["mlp"] - cols[best])
        lines.append(f"{label} & " + " & ".join(pm(cols[x]) for x in SYSTEMS) + f" & {100 * m:+.1f} $\\pm$ {100 * sd:.1f} \\\\")
    return f"\\begin{{tabular}}{{lcccccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def table_scenario_conformal(e: dict) -> str:
    c = e["scenario_conformal"]
    head = "Scenario & \\multicolumn{2}{c}{Coverage (\\%)} & \\multicolumn{2}{c}{Mean set size} \\\\\n\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n & LAC & LAC per class & LAC & LAC per class \\\\"
    lines = []
    for scenario, label in SCENARIO_LABEL.items():
        d = c[c.scenario == scenario]
        row = {m: d[d.method == m].set_index("seed") for m in ("LAC", "LAC_Mondrian")}
        lines.append(f"{label} & {pm(row['LAC'].coverage)} & {pm(row['LAC_Mondrian'].coverage)} & {row['LAC']['size'].mean():.2f} & {row['LAC_Mondrian']['size'].mean():.2f} \\\\")
    return f"\\begin{{tabular}}{{lcccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def table_natural(e: dict) -> str:
    n, s = e["natural"], e["scenarios"]
    head = "System & Balanced test rows & Natural sample & Difference \\\\"
    lines = []
    for x in SYSTEMS:
        bal, nat = acc(s, x, scenario="balanced"), acc(n, x, scope="all")
        diff = nat - bal
        lines.append(f"{SYSTEM_LABEL[x]} & {pm(bal)} & {pm(nat)} & {100 * diff.mean():+.1f} \\\\")
    nc = e["natural_conformal"]
    nc = nc[nc.scope == "all"]
    lines.append("\\midrule")
    for method, label in (("LAC", "LAC coverage (target 90)"), ("LAC_Mondrian", "LAC per class coverage (target 90)")):
        d = nc[nc.method == method].set_index("seed")
        lines.append(f"{label} & -- & {pm(d.coverage)} & -- \\\\")
    return f"\\begin{{tabular}}{{lccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def table_natural_groups(e: dict) -> str:
    n = e["natural"]
    n = n[n.scope != "all"]
    head = "Group & " + " & ".join(SYSTEM_LABEL[x] for x in SYSTEMS) + " \\\\"
    lines = []
    for group in sorted(n.scope.unique()):
        lines.append(group.replace("_", " ") + " & " + " & ".join(pm(acc(n, x, scope=group)) for x in SYSTEMS) + " \\\\")
    return f"\\begin{{tabular}}{{lccccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def numbers(e: dict) -> str:
    s, c, n, nc = e["scenarios"], e["scenario_conformal"], e["natural"], e["natural_conformal"]
    out = [HEADER.format(src="runs/e3")]
    for scenario, tag in SCENARIO_TAG.items():
        for x in SYSTEMS:
            out.append(macro(f"acc{SYSTEM_TAG[x]}Scen{tag}", pct(acc(s, x, scenario=scenario).mean()), f"scenario {scenario}, reweighted E1 test rows; illustrative, not a real prevalence"))
        best = best_baseline(s, scenario=scenario)
        m, sd = mean_sd(acc(s, "mlp", scenario=scenario) - acc(s, best, scenario=scenario))
        out.append(macro(f"gapMLPBestScen{tag}", f"{100 * m:+.1f}", f"MLP minus {best}, points, paired over seeds; sd {100 * sd:.1f}"))
        out.append(macro(f"covRulesScen{tag}", pct(acc(s, "rules", "coverage", scenario=scenario).mean()), "share of profiles the rules decide"))
        for method, mtag in (("LAC", "Conf"), ("LAC_Mondrian", "Mondrian")):
            d = c[(c.scenario == scenario) & (c.method == method)]
            out.append(macro(f"cov{mtag}Scen{tag}", pct(d.coverage.mean()), f"{method}, alpha 0.1, calibrated on the balanced rows, not recalibrated"))
    for x in SYSTEMS:
        out.append(macro(f"acc{SYSTEM_TAG[x]}Natural", pct(acc(n, x, scope="all").mean()), "natural sampler, default noise and missing fields"))
        out.append(macro(f"sd{SYSTEM_TAG[x]}Natural", pct(acc(n, x, scope="all").std(ddof=1)), "sd over seeds"))
    best = best_baseline(n, scope="all")
    m, sd = mean_sd(acc(n, "mlp", scope="all") - acc(n, best, scope="all"))
    out.append(macro("gapMLPBestNatural", f"{100 * m:+.1f}", f"MLP minus {best}, points, paired over seeds; sd {100 * sd:.1f}"))
    out.append(macro("covRulesNatural", pct(acc(n, "rules", "coverage", scope="all").mean()), "share of natural profiles the rules decide"))
    for method, mtag in (("LAC", "Conf"), ("LAC_Mondrian", "Mondrian")):
        d = nc[(nc.scope == "all") & (nc.method == method)]
        out.append(macro(f"cov{mtag}Natural", pct(d.coverage.mean()), f"{method}, alpha 0.1, calibrated on the balanced rows"))
        out.append(macro(f"size{mtag}Natural", f"{d['size'].mean():.2f}", "mean set size"))
    lab = e["natural_labels"].groupby("label").share.mean()
    meta = e["natural_meta"]
    out += [
        macro("naturalShareNone", pct(lab.get(0, 0.0)), "share of natural profiles labelled 'no eligible class'"),
        macro("naturalShareAmbiguous", pct(lab.get(-1, 0.0)), "share labelled ambiguous (-1)"),
        macro("nNatural", f"{int(meta.rows.mean())}", "natural profiles per seed"),
        macro("naturalDropped", f"{int(meta.dropped_unlabelled_draws.mean())}", "draws per seed the rules could not label, dropped"),
    ]
    return "".join(out)


def write_outputs(runs: Path, paper: Path, figures: bool) -> str:
    e = load(runs)
    t = paper / "p1" / "tables"
    src = HEADER.format(src="runs/e3/*.csv")
    write(t / "t_prevalence.tex", src + table_scenarios(e))
    write(t / "t_prevalence_conformal.tex", src + table_scenario_conformal(e))
    write(t / "t_natural.tex", src + table_natural(e))
    write(t / "t_natural_groups.tex", src + table_natural_groups(e))
    return numbers(e)
