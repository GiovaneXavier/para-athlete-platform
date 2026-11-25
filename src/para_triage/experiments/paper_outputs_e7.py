"""Tables, figures and macros of E7 (selective and conformal prediction); called by paper_outputs.

Labels come from the same rules as the baseline. The conformal guarantee is marginal; the
conditional views (group, class, missing fields) measure what it does not promise.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .e7 import ALPHA_MAIN, ALPHAS, N_SPLITS, PRIMARY_METHOD
from .paper_outputs import HEADER, figname, macro, mean_sd, pct, pm

MODEL_LABEL = {"mlp": "MLP", "gb": "Gradient boosting"}
METHOD_LABEL = {"LAC": "LAC", "APS": "APS", "LAC_Mondrian": "LAC (per class)"}
DEFAULT = (1.0, 1.0)


CURRENT = {"name": "e7"}  # which run is being written, for the source comments of the macros


def load_e7(runs: Path, e7_name: str = "e7") -> dict[str, pd.DataFrame]:
    CURRENT["name"] = e7_name
    return {n: pd.read_csv(runs / e7_name / f"{n}.csv") for n in ("marginal", "conditional", "selective_curve", "selective_summary", "selective_points")}


def main_marginal(e7: dict, model: str, method: str, alpha: float, cal=DEFAULT, test=DEFAULT) -> pd.DataFrame:
    m = e7["marginal"]
    return m[(m.model == model) & (m.method == method) & np.isclose(m.alpha, alpha)
             & (m.cal_noise == cal[0]) & (m.cal_missing == cal[1]) & (m.test_noise == test[0]) & (m.test_missing == test[1])]


# ---------------------------------------------------------------- tables

def table_selective(e7: dict) -> str:
    s, pts = e7["selective_summary"], e7["selective_points"]
    names = {"mlp_maxprob": "MLP, maximum probability", "mlp_margin": "MLP, margin",
             "gb_maxprob": "Gradient boosting, maximum probability", "gb_margin": "Gradient boosting, margin"}
    cols = ["aurc", "selective_accuracy_at_rules_coverage", "selective_accuracy_at_50", "selective_accuracy_at_70", "selective_accuracy_at_90", "accuracy_full"]
    head = "System & AURC (\\%) & At the rules' coverage & At 50\\% & At 70\\% & At 90\\% & At 100\\% \\\\"
    lines = []
    for key, label in names.items():
        sub = s[s.method == key].set_index("seed")
        lines.append(label + " & " + " & ".join(pm(sub[c]) for c in cols) + " \\\\")
    lines.append("\\midrule")
    for system, label in (("rules", "Rules (decide on their own coverage)"), ("rules_imp", "Rules + imputation"), ("hybrid", "Hybrid")):
        sub = pts[pts.system == system].set_index("seed")
        cov = sub["coverage"].mean()
        acc = pm(sub["selective_accuracy"])
        if system == "rules":
            lines.append(f"{label}, {pct(cov)}\\% & -- & {acc} & -- & -- & -- & -- \\\\")
        else:
            lines.append(f"{label} & -- & -- & -- & -- & -- & {acc} \\\\")
    return f"\\begin{{tabular}}{{lcccccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def table_conformal(e7: dict) -> str:
    head = ("Model & Score & Target & Coverage & Min.\\ coverage & Set size & Singletons (\\%) & Decided (\\%) & Empty (\\%) & With ambiguous (\\%) \\\\")
    lines = []
    for model in ("mlp", "gb"):
        for method in ("LAC", "APS"):
            for alpha in ALPHAS:
                d = main_marginal(e7, model, method, alpha)
                lines.append(
                    f"{MODEL_LABEL[model]} & {method} & {pct(1 - alpha)} & {pct(d.coverage.mean())} $\\pm$ {pct(d.coverage.std(ddof=1))} & {pct(d.coverage.min())} & "
                    f"{d['size'].mean():.2f} & {pct(d.frac_singleton.mean())} & {pct(d.frac_decided.mean())} & {pct(d.frac_empty.mean())} & {pct(d.frac_has_ambiguous.mean())} \\\\"
                )
        lines.append("\\midrule")
    lines.pop()
    return f"\\begin{{tabular}}{{llcccccccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def pooled(d: pd.DataFrame, column: str = "coverage") -> pd.Series:
    """Mean of `column` for each value, weighted by the test rows behind every (seed, repartition) entry.

    Equals the coverage of all the held-out rows of that value pooled together.
    """
    w = d.assign(_x=d[column] * d["n"]).groupby("value")
    return w["_x"].sum() / w["n"].sum()


def cond_slice(e7: dict, by: str, model: str, method: str, alpha: float = ALPHA_MAIN, cell=DEFAULT) -> pd.DataFrame:
    c = e7["conditional"]
    return c[(c.by == by) & (c.model == model) & (c.method == method) & np.isclose(c.alpha, alpha) & (c.cell_noise == cell[0]) & (c.cell_missing == cell[1])]


def class_coverage(e7: dict, model: str, method: str, alpha: float = ALPHA_MAIN) -> pd.Series:
    return pooled(cond_slice(e7, "class", model, method, alpha))


def table_class(e7: dict) -> str:
    cols = {("mlp", "LAC"): "MLP, LAC", ("gb", "LAC"): "GB, LAC", ("mlp", "LAC_Mondrian"): "MLP, per class"}
    data = pd.DataFrame({label: class_coverage(e7, m, meth) for (m, meth), label in cols.items()})
    data.index = data.index.astype(int)
    data = data.sort_index()
    lines = []
    for cls, row in data.iterrows():
        name = {0: "none", -1: "ambiguous"}.get(cls, str(cls))
        lines.append(f"{name} & " + " & ".join(pct(v) for v in row) + " \\\\")
    head = "Class & " + " & ".join(cols.values()) + " \\\\"
    return f"\\begin{{tabular}}{{lccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


# ---------------------------------------------------------------- macros

def numbers_conditional(e7: dict) -> list[str]:
    """Conditional coverage of the MLP with LAC at the main alpha (the figure f_cond and t_class use the same pooling)."""
    out = []
    src = f"runs/{CURRENT['name']}/conditional.csv, MLP, LAC, pooled over seeds x repartitions (test halves)"
    for suffix, cell in (("", DEFAULT), ("Double", (1.0, 2.0))):
        bands = cond_slice(e7, "missing_fields", "mlp", PRIMARY_METHOD, cell=cell)
        bands = bands.assign(value=bands.value.astype(str))
        cov, share = pooled(bands), bands.groupby("value").n.sum() / bands.groupby("value").n.sum().sum()
        for tag, key in (("Zero", "0"), ("One", "1"), ("TwoPlus", "2+")):
            out.append(macro(f"covMiss{tag}{suffix}", pct(cov[key]), f"{src}; cell {cell}"))
            if not suffix:
                out.append(macro(f"shareMiss{tag}", pct(share[key]), f"share of the held-out rows in this band (default cell); runs/{CURRENT['name']}/seed_*/missing_bands.json has the pool of seed 0 only"))
    groups = pooled(cond_slice(e7, "group", "mlp", PRIMARY_METHOD))
    classes = pooled(cond_slice(e7, "class", "mlp", PRIMARY_METHOD))
    mondrian = pooled(cond_slice(e7, "class", "mlp", f"{PRIMARY_METHOD}_Mondrian"))
    out += [
        macro("covGroupMin", pct(groups.min()), f"{src}; group {groups.idxmin()}"),
        macro("covGroupMax", pct(groups.max()), f"{src}; group {groups.idxmax()}"),
        macro("covClassMin", pct(classes.min()), f"{src}; class {classes.idxmin()}"),
        macro("covMondrianMin", pct(mondrian.min()), "per-class conformal (Mondrian), lowest class"),
        macro("covMondrianMax", pct(mondrian.max()), "per-class conformal (Mondrian), highest class"),
    ]
    m = e7["marginal"]
    sub = m[(m.model == "mlp") & (m.method == PRIMARY_METHOD) & np.isclose(m.alpha, ALPHA_MAIN)]

    def cell_cov(cal, test) -> float:
        d = sub[(sub.cal_noise == cal[0]) & (sub.cal_missing == cal[1]) & (sub.test_noise == test[0]) & (sub.test_missing == test[1])]
        return float(d.coverage.mean())

    own = [cell_cov((n, mm), (n, mm)) for n in sorted(sub.test_noise.unique()) for mm in sorted(sub.test_missing.unique())]
    out += [
        macro("covShiftMax", pct(cell_cov(DEFAULT, (0.0, 0.0))), "calibrated at (1, 1), tested at (0, 0)"),
        macro("covShiftMin", pct(cell_cov(DEFAULT, (2.0, 2.0))), "calibrated at (1, 1), tested at (2, 2)"),
        macro("covOwnCalMin", pct(min(own)), "calibrated on the tested cell: lowest of the 16 cells"),
        macro("covOwnCalMax", pct(max(own)), "calibrated on the tested cell: highest of the 16 cells"),
    ]
    return out


def numbers_e7(e7: dict, runs: Path) -> str:
    out = [HEADER.format(src=f"runs/{CURRENT['name']}")]
    src = f"runs/{CURRENT['name']}/marginal.csv"
    out += [macro("alphaMain", f"{ALPHA_MAIN:g}", f"declared in runs/{CURRENT['name']}/config.json"), macro("nSplitsConf", str(N_SPLITS), "repartitions per seed")]
    for tag, model in (("Main", "mlp"), ("GB", "gb")):
        d = main_marginal(e7, model, PRIMARY_METHOD, ALPHA_MAIN)
        per_seed = d.groupby("seed").coverage.mean()
        out += [
            macro(f"covConf{tag}", pct(d.coverage.mean()), f"{PRIMARY_METHOD}, {model}, mean over seeds x repartitions, {src}"),
            macro(f"sdCovConf{tag}", pct(d.coverage.std(ddof=1)), "sd over the 100 pairs (repartitions reuse the same rows)"),
            macro(f"sdSeedsCovConf{tag}", pct(per_seed.std(ddof=1)), "sd of the per-seed means"),
            macro(f"minCovConf{tag}", pct(d.coverage.min()), "minimum over the 100 pairs"),
            macro(f"sizeConf{tag}", f"{d['size'].mean():.2f}", src),
            macro(f"singletonConf{tag}", pct(d.frac_singleton.mean()), "sets with exactly one class"),
            macro(f"decidedConf{tag}", pct(d.frac_decided.mean()), "one class that is not the ambiguous label"),
            macro(f"decidedAccConf{tag}", pct(d.decided_accuracy.mean()), "agreement of the decided sets; not guaranteed"),
        ]
    out += numbers_conditional(e7)
    s = e7["selective_summary"]
    for tag, key in (("MLP", "mlp_maxprob"), ("Margin", "mlp_margin"), ("GB", "gb_maxprob"), ("GBMargin", "gb_margin")):
        sub = s[s.method == key]
        out.append(macro(f"aurc{tag}", pct(sub.aurc.mean(), 2), "mean selective error over coverage, %; lower is better"))
    for tag, key in (("", "mlp_maxprob"), ("GB", "gb_maxprob")):
        sub = s[s.method == key]
        out.append(macro(f"selAccAtRulesCov{tag}", pct(sub.selective_accuracy_at_rules_coverage.mean()), "confidence-based selective accuracy at the rules' coverage"))
    return "".join(out)


# ---------------------------------------------------------------- figures

def figures_e7(e7: dict, fig_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    fig_dir.mkdir(parents=True, exist_ok=True)

    # F-risk
    curve, pts = e7["selective_curve"], e7["selective_points"]
    style = {"mlp_maxprob": ("#0072B2", "-", "MLP, maximum probability"), "mlp_margin": ("#0072B2", "--", "MLP, margin"),
             "gb_maxprob": ("#009E73", "-", "Gradient boosting, maximum probability"), "gb_margin": ("#009E73", "--", "Gradient boosting, margin")}
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    for key, (color, ls, label) in style.items():
        sub = curve[curve.method == key].groupby("coverage").selective_accuracy.agg(["mean", "std"])
        ax.plot(100 * sub.index, 100 * sub["mean"], color=color, ls=ls, lw=1.5, label=label)
        ax.fill_between(100 * sub.index, 100 * (sub["mean"] - sub["std"]), 100 * (sub["mean"] + sub["std"]), color=color, alpha=0.12, lw=0)
    markers = {"rules": ("#000000", "o", "Rules"), "rules_imp": ("#E69F00", "s", "Rules + imputation"), "hybrid": ("#CC79A7", "v", "Hybrid")}
    for system, (color, marker, label) in markers.items():
        sub = pts[pts.system == system]
        ax.errorbar(100 * sub.coverage.mean(), 100 * sub.selective_accuracy.mean(), yerr=100 * sub.selective_accuracy.std(ddof=1), color=color,
                    marker=marker, ms=6, ls="none", capsize=2, label=label)
    rules_cov = 100 * pts[pts.system == "rules"].coverage.mean()
    ax.axvline(rules_cov, color="gray", ls=":", lw=1)
    ax.set_xlabel("Coverage (% of profiles answered)")
    ax.set_ylabel("Agreement with rules' label (%)")
    ax.set_xlim(5, 101)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7, loc="lower left", frameon=False)
    fig.tight_layout()
    fig.savefig(fig_dir / figname("f_risk.pdf"))
    plt.close(fig)

    # F-cond
    cond = e7["conditional"]
    sel = cond[(cond.method == PRIMARY_METHOD) & np.isclose(cond.alpha, ALPHA_MAIN)]
    colors = {"mlp": "#0072B2", "gb": "#009E73"}
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.5), gridspec_kw={"width_ratios": [1.6, 1, 1]})
    ax = axes[0]
    groups = sorted(sel[sel.by == "group"].value.unique())
    width = 0.38
    for i, model in enumerate(("mlp", "gb")):
        d = pooled(sel[(sel.by == "group") & (sel.model == model) & (sel.cell_noise == 1) & (sel.cell_missing == 1)]).reindex(groups)
        ax.bar(np.arange(len(groups)) + (i - 0.5) * width, 100 * d.values, width, color=colors[model], label=MODEL_LABEL[model])
    ax.axhline(100 * (1 - ALPHA_MAIN), color="black", ls="--", lw=1)
    ax.set_xticks(np.arange(len(groups)), [g.replace("_", " ") for g in groups], rotation=60, ha="right", fontsize=7)
    ax.set_ylim(70, 110)
    ax.set_yticks([70, 80, 90, 100])
    ax.set_ylabel("Empirical coverage (%)")
    ax.set_title("By rule group", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="upper left", ncol=2)
    bands = sorted(sel[sel.by == "missing_fields"].value.astype(str).unique())
    for ax, column, ylabel, title in ((axes[1], "coverage", "Empirical coverage (%)", "By missing fields"), (axes[2], "size", "Mean set size", "Set size")):
        for model in ("mlp", "gb"):
            for cell, ls, marker in (((1.0, 1.0), "-", "o"), ((1.0, 2.0), "--", "s")):
                d = sel[(sel.by == "missing_fields") & (sel.model == model) & (sel.cell_noise == cell[0]) & (sel.cell_missing == cell[1])]
                d = pooled(d.assign(value=d.value.astype(str)), column).reindex(bands)
                scale = 100 if column == "coverage" else 1
                ax.plot(range(len(bands)), scale * d.values, color=colors[model], ls=ls, marker=marker, ms=4,
                        label=f"{MODEL_LABEL[model]}, {'default' if cell == (1.0, 1.0) else '2x missing'}")
        ax.set_xticks(range(len(bands)), bands)
        ax.set_xlabel("Applicable fields missing")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=9)
        if column == "coverage":
            ax.axhline(100 * (1 - ALPHA_MAIN), color="black", ls="--", lw=1)
    handles, labels = axes[2].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=7)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(fig_dir / figname("f_cond.pdf"))
    plt.close(fig)

    # F-shift: calibrate on the default view, or on the tested view (the remedy)
    m = e7["marginal"]
    sub = m[(m.method == PRIMARY_METHOD) & np.isclose(m.alpha, ALPHA_MAIN)]
    levels_n, levels_m = sorted(sub.test_noise.unique()), sorted(sub.test_missing.unique())
    fig, axes = plt.subplots(2, 2, figsize=(6.2, 5.4), sharex=True, sharey=True, constrained_layout=True)
    for r, model in enumerate(("mlp", "gb")):
        for c, remedy in enumerate((False, True)):
            grid = np.zeros((len(levels_n), len(levels_m)))
            for i, n in enumerate(levels_n):
                for j, mm in enumerate(levels_m):
                    cal = (n, mm) if remedy else DEFAULT
                    d = sub[(sub.model == model) & (sub.test_noise == n) & (sub.test_missing == mm) & (sub.cal_noise == cal[0]) & (sub.cal_missing == cal[1])]
                    grid[i, j] = 100 * d.coverage.mean()
            ax = axes[r, c]
            im = ax.imshow(grid, cmap="viridis", vmin=60, vmax=100, origin="lower")
            for i in range(len(levels_n)):
                for j in range(len(levels_m)):
                    ax.text(j, i, f"{grid[i, j]:.1f}", ha="center", va="center", fontsize=7.5, color="white" if grid[i, j] < 85 else "black")
            ax.set_xticks(range(len(levels_m)), [f"{v:g}$\\times$" for v in levels_m])
            ax.set_yticks(range(len(levels_n)), [f"{v:g}$\\times$" for v in levels_n])
            short = {"mlp": "MLP", "gb": "Boosting"}[model]
            ax.set_title(f"{short}: " + ("calibrated on tested view" if remedy else "calibrated at 1x, 1x"), fontsize=8)
            if r == 1:
                ax.set_xlabel("Missing-field multiplier")
            if c == 0:
                ax.set_ylabel("Noise multiplier")
    fig.colorbar(im, ax=axes, label=f"Empirical coverage (%), target {100 * (1 - ALPHA_MAIN):.0f}%", shrink=0.85)
    fig.savefig(fig_dir / figname("f_shift.pdf"))
    plt.close(fig)
