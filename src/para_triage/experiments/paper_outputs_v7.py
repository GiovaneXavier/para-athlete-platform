"""Tables, figure and macros of V7 (conformal sets by observed missing fields); called by paper_outputs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .paper_outputs import HEADER, macro, pct, write
from .paper_outputs_e7 import MODEL_LABEL, pooled

ALPHA = 0.1
BANDS = ("0", "1", "2+")
BAND_TAG = {"0": "Zero", "1": "One", "2+": "TwoPlus"}
METHOD_LABEL = {"LAC": "Marginal LAC", "LAC_band": "LAC per band (0, 1, 2+)", "LAC_band2": "LAC per band (0, 1+)", "LAC_Tband": "LAC after a temperature per band"}
METHOD_TAG = {"LAC": "Obs", "LAC_band": "Band", "LAC_band2": "BandTwo", "LAC_Tband": "Tband"}
VIEW = ("mcar", 1.0)
VIEW_DOUBLE = ("mcar", 2.0)
MNAR_TAG = {("label_0.9", 1.0): "LabelNinety", ("value_up_0.9", 1.0): "ValueUpNinety"}


def load(runs: Path) -> dict[str, pd.DataFrame]:
    return {n: pd.read_csv(runs / "v7" / f"{n}.csv") for n in ("marginal", "by_band", "agreement")}


def cond(e: dict, kind: str, model: str, method: str, test: tuple, cal: tuple | None = None, alpha: float = ALPHA) -> pd.DataFrame:
    b = e["by_band"]
    cal = cal or test
    d = b[(b.by == kind) & (b.model == model) & (b.method == method) & np.isclose(b.alpha, alpha)
          & (b.test_regime == test[0]) & (b.test_multiplier == test[1]) & (b.cal_regime == cal[0]) & (b.cal_multiplier == cal[1])]
    return d.assign(value=d.value.astype(str))


def per_pair_sd(d: pd.DataFrame, band: str) -> float:
    x = d[d.value == band]
    return float(x.coverage.std(ddof=1)) if len(x) > 1 else float("nan")


def table_methods(e: dict) -> str:
    head = ("Model & Method & \\multicolumn{3}{c}{Coverage (\\%) with 0, 1, 2+ observed missing} & \\multicolumn{3}{c}{Mean set size} \\\\\n"
            "\\cmidrule(lr){3-5}\\cmidrule(lr){6-8}")
    lines = []
    for model in ("mlp", "gb"):
        for method in METHOD_LABEL:
            d = cond(e, "observed", model, method, VIEW)
            cov, size = pooled(d, "coverage"), pooled(d, "size")
            cells = [f"{pct(cov[b])} $\\pm$ {pct(per_pair_sd(d, b))}" for b in BANDS] + [f"{size[b]:.2f}" for b in BANDS]
            lines.append(f"{MODEL_LABEL[model]} & {METHOD_LABEL[method]} & " + " & ".join(cells) + " \\\\")
        lines.append("\\midrule")
    lines.pop()
    return f"\\begin{{tabular}}{{llcccccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def table_obs_true(e: dict) -> str:
    head = "Cell & Missing fields & Share, observed (\\%) & Coverage, observed (\\%) & Share, true profile (\\%) & Coverage, true profile (\\%) \\\\"
    lines = []
    for view, name in ((VIEW, "$1\\times$ noise, $1\\times$ missing"), (VIEW_DOUBLE, "$1\\times$ noise, $2\\times$ missing")):
        o, t = cond(e, "observed", "mlp", "LAC", view), cond(e, "true_profile", "mlp", "LAC", view)
        for b in BANDS:
            share = lambda d: d[d.value == b].n.sum() / d.n.sum()  # noqa: E731
            lines.append(f"{name if b == '0' else ''} & {b} & {pct(share(o))} & {pct(pooled(o)[b])} & {pct(share(t))} & {pct(pooled(t)[b])} \\\\")
        lines.append("\\midrule")
    ag = e["agreement"]
    a = ag[(ag.regime == VIEW[0]) & (ag.multiplier == VIEW[1])].agreement_observed_true_count.mean()
    lines.append(f"\\multicolumn{{6}}{{l}}{{Rows where the observed count equals the true-profile count (default cell): {pct(a)}\\%}} \\\\")
    return f"\\begin{{tabular}}{{llcccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def table_reliability(e: dict) -> str:
    """Coverage in the 2+ band against the number of calibration rows in that band, per calibration draw."""
    m = e["marginal"]
    d = m[(m.model == "mlp") & (m.method == "LAC_band") & np.isclose(m.alpha, ALPHA) & (m.cal_regime == VIEW[0]) & (m.cal_multiplier == VIEW[1])
          & (m.test_regime == VIEW[0]) & (m.test_multiplier == VIEW[1])]
    b = cond(e, "observed", "mlp", "LAC_band", VIEW)
    b = b[b.value == "2+"][["seed", "split", "coverage", "n"]]
    d = d.merge(b, on=["seed", "split"])
    bins = [(0, 30), (30, 45), (45, 60), (60, 1000)]
    lines = []
    for lo, hi in bins:
        s = d[(d["n_cal_2+"] >= lo) & (d["n_cal_2+"] < hi)]
        if len(s):
            lines.append(f"{lo}--{hi - 1 if hi < 1000 else '+'} & {len(s)} & {pct(s.coverage_y.mean())} & {pct(s.coverage_y.std(ddof=1) if len(s) > 1 else float('nan'))} \\\\")
    head = "Calibration rows in the 2+ band & Draws & Mean coverage (\\%) & Spread (points) \\\\"
    return f"\\begin{{tabular}}{{lccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n", d


def table_mnar(e: dict) -> str:
    head = ("Test view & Calibrated on & Method & \\multicolumn{3}{c}{Coverage (\\%) with 0, 1, 2+ observed missing} \\\\\n\\cmidrule(lr){4-6}")
    names = {("mcar", 1.0): "MCAR, $1\\times$", ("mcar", 2.0): "MCAR, $2\\times$", ("label_0.9", 1.0): "By label, $s=0.9$", ("value_up_0.9", 1.0): "By value, $s=0.9$"}
    lines = []
    for test, name in names.items():
        for cal, cal_name in ((VIEW, "MCAR, $1\\times$"), (test, "the tested view")):
            if cal == test and test == VIEW:
                continue
            for method in ("LAC", "LAC_band"):
                d = cond(e, "observed", "mlp", method, test, cal)
                cov = pooled(d, "coverage")
                lines.append(f"{name} & {cal_name} & {METHOD_LABEL[method].split(' (')[0]} & " + " & ".join(pct(cov[b]) for b in BANDS) + " \\\\")
        lines.append("\\midrule")
    lines.pop()
    return f"\\begin{{tabular}}{{lllccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def numbers(e: dict, reliability: pd.DataFrame) -> str:
    out = [HEADER.format(src="runs/v7")]
    src = "runs/v7/by_band.csv, LAC family, alpha 0.1, pooled over seeds x repartitions (test halves)"
    for suffix, view in (("", VIEW), ("Double", VIEW_DOUBLE)):
        for method, tag in METHOD_TAG.items():
            for model, mtag in (("mlp", ""), ("gb", "GB")):
                d = cond(e, "observed", model, method, view)
                cov, size = pooled(d, "coverage"), pooled(d, "size")
                for b, bt in BAND_TAG.items():
                    out.append(macro(f"cov{tag}{bt}{suffix}{mtag}", pct(cov[b]), f"{src}; {model}, view {view}, observed band {b}"))
                    out.append(macro(f"size{tag}{bt}{suffix}{mtag}", f"{size[b]:.2f}", "mean set size in the band"))
        d = cond(e, "observed", "mlp", "LAC_band", view)
        for b, bt in BAND_TAG.items():
            out.append(macro(f"sdCovBand{bt}{suffix}", pct(per_pair_sd(d, b)), "sd over the 100 seed x repartition pairs"))
    # observed against true-profile counts
    o, t = cond(e, "observed", "mlp", "LAC", VIEW), cond(e, "true_profile", "mlp", "LAC", VIEW)
    for b, bt in BAND_TAG.items():
        out.append(macro(f"shareObs{bt}", pct(o[o.value == b].n.sum() / o.n.sum()), "share of held-out rows with this observed count"))
        out.append(macro(f"covTrueCount{bt}", pct(pooled(t)[b]), "marginal LAC coverage by the true-profile count (E7 definition)"))
    ag = e["agreement"]
    out.append(macro("agreeObsTrueCount", pct(ag[(ag.regime == VIEW[0]) & (ag.multiplier == VIEW[1])].agreement_observed_true_count.mean()), "rows where the observed and true-profile counts are equal"))
    # reliability of the 2+ band
    m = e["marginal"]
    sel = m[(m.model == "mlp") & (m.method == "LAC_band") & np.isclose(m.alpha, ALPHA) & (m.cal_regime == VIEW[0]) & (m.cal_multiplier == VIEW[1]) & (m.test_regime == VIEW[0]) & (m.test_multiplier == VIEW[1])]
    out += [
        macro("nCalTwoPlusMean", f"{sel['n_cal_2+'].mean():.0f}", "calibration rows in the 2+ band per draw"),
        macro("nCalTwoPlusMin", f"{sel['n_cal_2+'].min():.0f}", "smallest over the draws"),
        macro("nTestTwoPlusMean", f"{o[(o.value == '2+')].n.mean():.0f}", "test rows in the 2+ band per draw"),
    ]
    # not-at-random views: marginal LAC calibrated at MCAR, and band LAC calibrated on the tested view
    for test, tag in MNAR_TAG.items():
        shift, own = cond(e, "observed", "mlp", "LAC", test, VIEW), cond(e, "observed", "mlp", "LAC_band", test, test)
        for b, bt in BAND_TAG.items():
            out.append(macro(f"covObsShift{tag}{bt}", pct(pooled(shift)[b]), f"marginal LAC calibrated under MCAR, tested on {test}"))
            out.append(macro(f"covBandOwn{tag}{bt}", pct(pooled(own)[b]), f"LAC per band calibrated on {test}"))
    return "".join(out)


def figure(e: dict, fig_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    style = {"LAC": ("#000000", "o", "-"), "LAC_band": ("#0072B2", "s", "-"), "LAC_band2": ("#56B4E9", "^", "--"), "LAC_Tband": ("#D55E00", "D", ":")}
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=True)
    for ax, view, title in ((axes[0], VIEW, "Default missing rate"), (axes[1], VIEW_DOUBLE, "Twice the missing rate")):
        for method, (color, marker, ls) in style.items():
            d = cond(e, "observed", "mlp", method, view)
            cov = pooled(d, "coverage").reindex(BANDS)
            sd = [per_pair_sd(d, b) for b in BANDS]
            ax.errorbar(range(3), 100 * cov.values, yerr=100 * np.array(sd), color=color, marker=marker, ls=ls, ms=4, capsize=2, label=METHOD_LABEL[method])
        ax.axhline(100 * (1 - ALPHA), color="gray", ls="--", lw=1)
        ax.set_xticks(range(3), BANDS)
        ax.set_xlabel("Observed missing fields")
        ax.set_title(title, fontsize=9)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Empirical coverage (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=7)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_dir / "f_condobs.pdf")
    plt.close(fig)


def write_outputs(runs: Path, paper: Path, figures: bool) -> str:
    e = load(runs)
    t = paper / "p1" / "tables"
    src = HEADER.format(src="runs/v7/*.csv")
    reliability_table, joined = table_reliability(e)
    write(t / "t_condobs.tex", src + table_methods(e))
    write(t / "t_obs_true.tex", src + table_obs_true(e))
    write(t / "t_band_reliability.tex", src + reliability_table)
    write(t / "t_condobs_mnar.tex", src + table_mnar(e))
    if figures:
        figure(e, paper / "p1" / "figures")
    return numbers(e, joined)
