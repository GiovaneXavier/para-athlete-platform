"""Tables, figure and macros of E-MNAR; called by paper_outputs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .paper_outputs import HEADER, macro, mean_sd, pct, pm, write

REGIME_LABEL = {
    "mcar": "MCAR (as E1)",
    "label_0.5": "By label, $s=0.5$",
    "label_0.9": "By label, $s=0.9$",
    "value_up_0.5": "By value (high), $s=0.5$",
    "value_up_0.9": "By value (high), $s=0.9$",
    "value_down_0.9": "By value (low), $s=0.9$",
}
REGIME_TAG = {"mcar": "Mcar", "label_0.5": "LabelHalf", "label_0.9": "LabelNinety", "value_up_0.5": "ValueUpHalf",
              "value_up_0.9": "ValueUpNinety", "value_down_0.9": "ValueDownNinety"}
MULT_TAG = {1.0: "One", 2.0: "Two"}
SYSTEMS = ("rules", "rules_imp", "gb", "mlp")
SYSTEM_LABEL = {"rules": "Rules", "rules_imp": "Rules + imputation", "gb": "Gradient boosting", "mlp": "MLP"}
SYSTEM_TAG = {"rules": "Rules", "rules_imp": "RulesImp", "gb": "GB", "mlp": "MLP", "hybrid": "Hybrid"}


def load(runs: Path) -> dict[str, pd.DataFrame]:
    return {n: pd.read_csv(runs / "emnar" / f"{n}.csv") for n in ("results", "mask_only", "missing_rates")}


def acc(res: pd.DataFrame, regime: str, mult: float, system: str, training: str) -> pd.Series:
    d = res[(res.regime == regime) & (res.multiplier == mult) & (res.system == system) & (res.training == training)]
    return d.set_index("seed")["accuracy"].sort_index()


def table_accuracy(e: dict, training: str) -> str:
    res = e["results"]
    head = "Missing fields & Rate & " + " & ".join(SYSTEM_LABEL[s] for s in SYSTEMS) + " & MLP $-$ best baseline \\\\"
    lines = []
    for mult in (1.0, 2.0):
        for regime in REGIME_LABEL:
            cols = {s: acc(res, regime, mult, s, training) for s in SYSTEMS}
            best = max(("rules", "rules_imp", "gb"), key=lambda s: cols[s].mean())
            gap = cols["mlp"] - cols[best]
            m, sd = mean_sd(gap)
            lines.append(f"{REGIME_LABEL[regime]} & {mult:g}$\\times$ & " + " & ".join(pm(cols[s]) for s in SYSTEMS) + f" & {100 * m:+.1f} $\\pm$ {100 * sd:.1f} \\\\")
        if mult == 1.0:
            lines.append("\\midrule")
    return f"\\begin{{tabular}}{{llccccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def table_mask(e: dict) -> str:
    m = e["mask_only"]
    head = "Missing fields & Rate & Impairments only & Impairments + mask & Gain from the mask \\\\"
    lines = []
    for mult in (1.0, 2.0):
        for regime in REGIME_LABEL:
            d = m[(m.regime == regime) & (m.multiplier == mult)]
            g = d[d.predictor == "group_only"].set_index("seed").accuracy
            gm = d[d.predictor == "group_and_mask"].set_index("seed").accuracy
            lines.append(f"{REGIME_LABEL[regime]} & {mult:g}$\\times$ & {pm(g)} & {pm(gm)} & {100 * (gm - g).mean():+.1f} \\\\")
        if mult == 1.0:
            lines.append("\\midrule")
    return f"\\begin{{tabular}}{{llccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def rate_summary(e: dict) -> pd.DataFrame:
    r = e["missing_rates"]
    # pool the seeds of each field first, so the gap is not dominated by the sampling noise of a single seed
    pooled = (
        r.assign(realized_n=r.realized * r.rows, target_n=r.target * r.rows)
        .groupby(["regime", "multiplier", "field"])
        .agg(rows=("rows", "sum"), realized_n=("realized_n", "sum"), target_n=("target_n", "sum"), clipped_share=("clipped_share", "max"))
        .reset_index()
    )
    pooled["realized"], pooled["target"] = pooled.realized_n / pooled.rows, pooled.target_n / pooled.rows
    pooled["gap"] = (pooled.realized - pooled.target).abs()
    g = pooled.groupby(["regime", "multiplier"])
    return g.apply(
        lambda d: pd.Series(
            {
                "target_mean": float(np.average(d.target, weights=d.rows)),
                "realized_mean": float(np.average(d.realized, weights=d.rows)),
                "max_field_gap": float(d.gap.max()),
                "max_clipped_share": float(d.clipped_share.max()),
            }
        ),
        include_groups=False,
    ).reset_index()


def table_rates(e: dict) -> str:
    s = rate_summary(e)
    head = "Missing fields & Rate & Target (\\%) & Realized (\\%) & Largest field gap (points) & Largest capped share (\\%) \\\\"
    lines = []
    for mult in (1.0, 2.0):
        for regime in REGIME_LABEL:
            d = s[(s.regime == regime) & (s.multiplier == mult)].iloc[0]
            lines.append(f"{REGIME_LABEL[regime]} & {mult:g}$\\times$ & {pct(d.target_mean)} & {pct(d.realized_mean)} & {pct(d.max_field_gap)} & {pct(d.max_clipped_share)} \\\\")
        if mult == 1.0:
            lines.append("\\midrule")
    return f"\\begin{{tabular}}{{llcccc}}\n\\toprule\n{head}\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def numbers(e: dict) -> str:
    res, mask = e["results"], e["mask_only"]
    out = [HEADER.format(src="runs/emnar")]
    src = "runs/emnar/results.csv"
    for regime, tag in REGIME_TAG.items():
        for mult, mt in MULT_TAG.items():
            for system in (*SYSTEMS, "hybrid"):
                a = acc(res, regime, mult, system, "matched")
                out.append(macro(f"accMnar{SYSTEM_TAG[system]}{tag}{mt}", pct(a.mean()), f"{regime} x{mult:g}, trained and tested on the cell, {src}"))
            for training, suffix in (("matched", ""), ("mcar_1x", "FromMcar")):
                for against, atag in (("rules_imp", "Imp"), ("gb", "GB"), ("rules", "Rules")):
                    gap = acc(res, regime, mult, "mlp", training) - acc(res, regime, mult, against, training)
                    m, sd = mean_sd(gap)
                    out.append(macro(f"gapMnarMLP{atag}{suffix}{tag}{mt}", f"{100 * m:+.1f}", f"MLP minus {against}, points, paired over seeds, sd {100 * sd:.1f}; training {training}"))
            d = mask[(mask.regime == regime) & (mask.multiplier == mult)]
            g = d[d.predictor == "group_only"].set_index("seed").accuracy
            gm = d[d.predictor == "group_and_mask"].set_index("seed").accuracy
            out.append(macro(f"accMaskGroup{tag}{mt}", pct(g.mean()), "boosting on the declared impairments only"))
            out.append(macro(f"accMaskPattern{tag}{mt}", pct(gm.mean()), "boosting on the impairments plus the missing-field mask only (no values)"))
            out.append(macro(f"gainMaskPattern{tag}{mt}", f"{100 * (gm - g).mean():+.1f}", "what the mask adds over the impairments, points"))
    s = rate_summary(e)
    out.append(macro("maxFieldRateGap", pct(s.max_field_gap.max()), "largest |realized - target| missing rate over fields, regimes and multipliers"))
    out.append(macro("maxCappedShare", pct(s.max_clipped_share.max()), "largest share of a field's rows whose probability hit the cap of 1"))
    return "".join(out)


def figure(e: dict, fig_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    res = e["results"]
    style = {"rules": ("#000000", "o"), "rules_imp": ("#E69F00", "s"), "gb": ("#009E73", "^"), "mlp": ("#0072B2", "D")}
    keys = [(r, m) for m in (1.0, 2.0) for r in REGIME_LABEL]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4), sharey=True)
    for ax, training, title in ((axes[0], "matched", "Trained on the cell"), (axes[1], "mcar_1x", "Trained under MCAR at $1\\times$")):
        for system, (color, marker) in style.items():
            means = [100 * acc(res, r, m, system, training).mean() for r, m in keys]
            sds = [100 * acc(res, r, m, system, training).std(ddof=1) for r, m in keys]
            ax.errorbar(range(len(keys)), means, yerr=sds, color=color, marker=marker, ms=4, ls="none", capsize=1.5, label=SYSTEM_LABEL[system])
        short = {"mcar": "MCAR", "label_0.5": "label .5", "label_0.9": "label .9", "value_up_0.5": "value+ .5", "value_up_0.9": "value+ .9", "value_down_0.9": "value- .9"}
        ax.set_xticks(range(len(keys)), [f"{short[r]}, {m:g}x" for r, m in keys], rotation=75, fontsize=6, ha="right")
        ax.axvline(len(REGIME_LABEL) - 0.5, color="gray", lw=0.6, ls=":")
        ax.set_title(title, fontsize=9)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Agreement with rules' label (%)")
    axes[0].legend(fontsize=7, frameon=False, loc="lower left")
    fig.tight_layout()
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_dir / "f_mnar.pdf")
    plt.close(fig)


def write_outputs(runs: Path, paper: Path, figures: bool) -> str:
    e = load(runs)
    t = paper / "p1" / "tables"
    src = HEADER.format(src="runs/emnar/*.csv")
    write(t / "t_mnar.tex", src + table_accuracy(e, "matched"))
    write(t / "t_mnar_mismatch.tex", src + table_accuracy(e, "mcar_1x"))
    write(t / "t_mnar_mask.tex", src + table_mask(e))
    write(t / "t_mnar_rates.tex", src + table_rates(e))
    if figures:
        figure(e, paper / "p1" / "figures")
    return numbers(e)
