"""Tables, figure and macros of E2 (ablations); called by paper_outputs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .paper_outputs import HEADER, macro, mean_sd, pct, pm, write

LABEL = {
    "full": "Full model",
    "no_dropout": "No feature dropout",
    "no_mask": "No missing-field mask",
    "no_dropout_no_mask": "Neither",
}
TAG = {"no_dropout": "Dropout", "no_mask": "Mask", "no_dropout_no_mask": "Both"}
DEFAULT, CLEAN = (1.0, 1.0), (0.0, 0.0)
# (training cell, test cell, column header)
COLUMNS = [
    (DEFAULT, DEFAULT, "$1\\times,1\\times$"),
    (DEFAULT, (1.0, 2.0), "$1\\times,2\\times$"),
    (DEFAULT, (2.0, 1.0), "$2\\times,1\\times$"),
    (CLEAN, DEFAULT, "$1\\times,1\\times$"),
    (CLEAN, (1.0, 2.0), "$1\\times,2\\times$"),
    (CLEAN, (2.0, 1.0), "$2\\times,1\\times$"),
]


def load(runs: Path) -> pd.DataFrame:
    return pd.read_csv(runs / "e2" / "results.csv")


def series(df: pd.DataFrame, variant: str, train: tuple, test: tuple, column: str = "accuracy") -> pd.Series:
    d = df[(df.variant == variant) & (df.train_noise == train[0]) & (df.train_missing == train[1])
           & (df.test_noise == test[0]) & (df.test_missing == test[1])]
    return d.set_index("seed")[column].sort_index()


def table(df: pd.DataFrame) -> str:
    head1 = "Variant & \\multicolumn{3}{c}{Trained at $1\\times,1\\times$, tested at} & \\multicolumn{3}{c}{Trained at $0\\times,0\\times$, tested at} \\\\"
    head2 = " & " + " & ".join(h for _, _, h in COLUMNS) + " \\\\"
    lines = []
    for variant, label in LABEL.items():
        lines.append(label + " & " + " & ".join(pm(series(df, variant, tr, te)) for tr, te, _ in COLUMNS) + " \\\\")
    lines.append("\\midrule")
    full_tau = " & ".join(pm(series(df, "full", tr, te, "accuracy_hybrid_tau")) for tr, te, _ in COLUMNS)
    full_h = " & ".join(pm(series(df, "full", tr, te, "accuracy_hybrid")) for tr, te, _ in COLUMNS)
    rules = " & ".join(pm(series(df, "full", tr, te, "accuracy_rules")) for tr, te, _ in COLUMNS)
    lines += [f"Hybrid, rules when they decide & {full_h} \\\\", f"Hybrid, MLP if confidence $\\ge\\tau$ & {full_tau} \\\\", f"Rules & {rules} \\\\"]
    return ("\\begin{tabular}{lcccccc}\n\\toprule\n" + head1 + "\n\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\n" + head2 + "\n\\midrule\n"
            + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def numbers(df: pd.DataFrame) -> str:
    src = "runs/e2/results.csv"
    out = [HEADER.format(src="runs/e2")]
    for variant, tag in TAG.items():
        a = series(df, variant, DEFAULT, DEFAULT)
        out.append(macro(f"acc{'No' + tag}", pct(a.mean()), f"{variant}, trained and tested at (1, 1), {src}"))
        cells = {
            "Matched": (DEFAULT, DEFAULT),
            "CleanTrain": (CLEAN, DEFAULT),
            "DoubleMissing": (DEFAULT, (1.0, 2.0)),
            "CleanTrainDoubleMissing": (CLEAN, (1.0, 2.0)),  # no missing field in training, twice the default at test
        }
        for name, (tr, te) in cells.items():
            gain = series(df, "full", tr, te) - series(df, variant, tr, te)
            m, s = mean_sd(gain)
            out.append(macro(f"gain{tag}{name}", f"{100 * m:+.1f}", f"full minus {variant}, points, train {tr}, test {te}; paired over seeds; sd {100 * s:.1f}"))
            out.append(macro(f"sdGain{tag}{name}", pct(s), "sd of the paired difference over seeds"))
    hyb = series(df, "full", DEFAULT, DEFAULT, "accuracy_hybrid_tau")
    gain = hyb - series(df, "full", DEFAULT, DEFAULT, "accuracy_hybrid")
    m, s = mean_sd(hyb)
    taus = df[(df.variant == "full") & (df.train_noise == 1) & (df.train_missing == 1)].drop_duplicates("seed").tau
    out += [
        macro("accHybridTau", pct(m), src),
        macro("sdHybridTau", pct(s), src),
        macro("gainHybridTau", f"{100 * gain.mean():+.1f}", "thresholded hybrid minus the hybrid that always trusts the rules when they decide"),
        macro("sdGainHybridTau", pct(gain.std(ddof=1)), "sd over seeds of that paired difference"),
        macro("tauMedian", f"{taus.median():g}", "chosen on validation rows; per seed in runs/e2/results.csv"),
    ]
    return "".join(out)


def figure(df: pd.DataFrame, fig_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    colors = {"full": "#0072B2", "no_dropout": "#D55E00", "no_mask": "#009E73"}
    levels = sorted(df.test_missing.unique())
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), sharey=True)
    for ax, train in zip(axes, (DEFAULT, CLEAN)):
        for variant, color in colors.items():
            means, sds = [], []
            for lv in levels:
                m, s = mean_sd(series(df, variant, train, (1.0, lv)))
                means.append(100 * m)
                sds.append(100 * s)
            means, sds = np.array(means), np.array(sds)
            ax.plot(levels, means, color=color, marker="o", ms=4, label=LABEL[variant])
            ax.fill_between(levels, means - sds, means + sds, color=color, alpha=0.15, lw=0)
        ax.set_xticks(levels, [f"{v:g}$\\times$" for v in levels])
        ax.set_xlabel("Missing-field multiplier at test (noise $1\\times$)")
        ax.set_title(f"Trained at {train[0]:g}$\\times$ noise, {train[1]:g}$\\times$ missing", fontsize=9)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Agreement with rules' label (%)")
    axes[0].legend(fontsize=7, frameon=False, loc="lower left")
    fig.tight_layout()
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_dir / "f_ablation.pdf")
    plt.close(fig)


def write_outputs(runs: Path, paper: Path, figures: bool) -> str:
    df = load(runs)
    p1 = paper / "p1"
    write(p1 / "tables" / "t_ablation.tex", HEADER.format(src="runs/e2/results.csv") + table(df))
    if figures:
        figure(df, p1 / "figures")
    return numbers(df)
