"""Tables and macros of V1 (duplicates and the split by true profile); called by paper_outputs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .paper_outputs import HEADER, macro, mean_sd, pct, pm, write

SYSTEMS = ("rules", "rules_imp", "gb", "mlp", "hybrid")
SYSTEM_TAG = {"rules": "Rules", "rules_imp": "RulesImp", "gb": "GB", "mlp": "MLP", "hybrid": "Hybrid"}
# "profile": new true profiles, labels may be unseen; "profile_by_label": new profiles of labels that are seen
VARIANT_TAG = {"profile": "DiagProfileSplit", "profile_by_label": "DiagNewProfile"}  # "Diag": E1 configurations, not retuned
MAIN_VARIANT = "profile_by_label"


def load(runs: Path) -> dict[str, pd.DataFrame]:
    names = ("duplicates", "accuracy", "grouped_systems", "grouped_by_group", "grouped_meta")
    out = {n: pd.read_csv(runs / "v1" / f"{n}.csv") for n in names}
    e1 = pd.read_csv(runs / "e1" / "by_group.csv")
    out["e1_by_group"] = e1[(e1.train_noise == 1) & (e1.train_missing == 1) & (e1.test_noise == 1) & (e1.test_missing == 1)]
    e1r = pd.read_csv(runs / "e1" / "results.csv")
    out["e1_results"] = e1r[(e1r.train_noise == 1) & (e1r.train_missing == 1) & (e1r.test_noise == 1) & (e1r.test_missing == 1)]
    return out


def seed_series(df: pd.DataFrame, **where) -> pd.Series:
    d = df
    for k, v in where.items():
        d = d[d[k] == v]
    return d.set_index("seed")["accuracy"].sort_index()


def no_duplicate_composition(e: dict) -> tuple[dict, dict]:
    """Which groups the test rows without a true-profile twin in training come from, and how the systems do on them."""
    d = e["duplicates"]
    d = d[d.group != "all"].assign(n_free=lambda x: x.n_test * (1 - x.share_true_duplicate))
    by_group = d.groupby("group").n_free.sum()
    total = by_group.sum()
    comp = {"share_of_rows": float(total / d.n_test.sum()), **{g: float(by_group.get(g, 0.0) / total) for g in ("visual", "short_stature")}}
    comp["other"] = 1.0 - comp["visual"] - comp["short_stature"]
    sub = e["accuracy"][e["accuracy"].subset == "no_true_duplicate"]
    acc = {s: float(sub[sub.system == s].accuracy.mean()) for s in SYSTEMS}
    return comp, acc


def table(e: dict) -> str:
    dup, e1_grp = e["duplicates"], e["e1_by_group"]
    g_grp = e["grouped_by_group"][e["grouped_by_group"].variant == MAIN_VARIANT]
    head = (
        "Group & Test rows with an identical true profile in training (\\%) & Identical observed profile (\\%) & "
        "MLP, split by row & MLP, new profiles & Boosting, split by row & Boosting, new profiles \\\\"
    )
    lines = []
    for group in sorted(dup[dup.group != "all"].group.unique()):
        d = dup[dup.group == group].set_index("seed")
        cells = [pct(d.share_true_duplicate.mean()), pct(d.share_observed_duplicate.mean())]
        for system in ("mlp", "gb"):
            cells += [pm(seed_series(e1_grp, group=group, system=system)), pm(seed_series(g_grp, group=group, system=system))]
        lines.append(group.replace("_", " ") + " & " + " & ".join(cells) + " \\\\")
    d = dup[dup.group == "all"].set_index("seed")
    allc = [pct(d.share_true_duplicate.mean()), pct(d.share_observed_duplicate.mean())]
    main_sys = e["grouped_systems"][e["grouped_systems"].variant == MAIN_VARIANT]
    for system in ("mlp", "gb"):
        allc += [pm(seed_series(e["e1_results"], system=system)), pm(seed_series(main_sys, system=system))]
    lines += ["\\midrule", "All groups & " + " & ".join(allc) + " \\\\"]
    comp, acc = no_duplicate_composition(e)
    lines.append(
        "\\multicolumn{7}{l}{Test rows with no identical true profile in training: "
        f"{pct(comp['share_of_rows'])}\\% of the rows, of which {pct(comp['visual'])}\\% are visual and {pct(comp['short_stature'])}\\% short stature "
        f"(MLP {pct(acc['mlp'])}\\%, rules + imputation {pct(acc['rules_imp'])}\\%, hybrid {pct(acc['hybrid'])}\\% on them; not comparable with the new-profile columns)}} \\\\"
    )
    return "\\begin{tabular}{lcccccc}\n\\toprule\n" + head + "\n\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n"


def numbers(e: dict) -> str:
    out = [HEADER.format(src="runs/v1")]
    dup = e["duplicates"]
    by_group = dup[dup.group != "all"].groupby("group").share_true_duplicate.mean()
    allr = dup[dup.group == "all"]
    out += [
        macro("shareTrueDuplicate", pct(allr.share_true_duplicate.mean()), "held-out rows whose true profile also appears among the training rows (split by row, E1)"),
        macro("shareObservedDuplicate", pct(allr.share_observed_duplicate.mean()), "the same for the observed profile at the default noise and missing level"),
        macro("shareTrueDuplicateMin", pct(by_group.min()), f"lowest group: {by_group.idxmin()}"),
        macro("shareTrueDuplicateMax", pct(by_group.max()), f"highest group: {by_group.idxmax()}"),
        macro("nUniqueTrueProfiles", f"{int(e['grouped_meta'].unique_true_profiles.mean())}", "distinct true profiles in the 13,800 rows of one seed"),
    ]
    comp, acc_free = no_duplicate_composition(e)
    dup_acc = e["accuracy"][e["accuracy"].subset == "true_duplicate"]
    out += [
        macro("shareNoTrueDuplicateRows", pct(comp["share_of_rows"]), "test rows with no identical true profile in training"),
        macro("shareNoDupVisual", pct(comp["visual"]), "of those rows, the share that are visual"),
        macro("shareNoDupShortStature", pct(comp["short_stature"]), "of those rows, the share that are short stature"),
        macro("shareNoDupOther", pct(comp["other"]), "of those rows, the share from every other group"),
    ]
    for system, tag in SYSTEM_TAG.items():
        out.append(macro(f"acc{tag}NoTrueDup", pct(acc_free[system]), "accuracy on the test rows without a true-profile twin in training; mostly visual and short stature"))
        out.append(macro(f"acc{tag}TrueDup", pct(float(dup_acc[dup_acc.system == system].accuracy.mean())), "accuracy on the test rows with a true-profile twin in training"))
    row = e["e1_results"]
    for variant, vtag in VARIANT_TAG.items():
        sys_rows = e["grouped_systems"][e["grouped_systems"].variant == variant]
        for system, tag in SYSTEM_TAG.items():
            prof = seed_series(sys_rows, system=system)
            base = seed_series(row, system=system)
            m, sd = mean_sd(prof)
            out.append(macro(f"acc{tag}{vtag}", pct(m), f"{system}, split {variant}, default cell; runs/v1/grouped_systems.csv"))
            out.append(macro(f"sd{tag}{vtag}", pct(sd), "sd over seeds"))
            out.append(macro(f"drop{tag}{vtag}", f"{100 * (prof - base).mean():+.1f}", "this split minus the split by row, points (different test rows; not paired)"))
        meta = e["grouped_meta"][e["grouped_meta"].variant == variant]
        out.append(macro(f"shareLabelUnseen{vtag}", pct(meta.share_test_label_unseen_in_train.mean()), "test rows whose label never appears in the training rows of this split"))
        by_group = e["grouped_by_group"][(e["grouped_by_group"].variant == variant) & (e["grouped_by_group"].system == "mlp")]
        worst = by_group.groupby("group").accuracy.mean()
        out.append(macro(f"accMLPWorstGroup{vtag}", pct(worst.min()), f"MLP, lowest group under this split: {worst.idxmin()}"))
    return "".join(out)


EPOCH_COLUMNS = (10, 20, 40, 80)
EPOCH_TAG = {10: "Ten", 20: "Twenty", 40: "Forty", 80: "Eighty"}
CONTINUOUS = ("visual", "short_stature")
DIAG = {"NewProfile": "diag_epochs_profile", "Row": "diag_epochs_row"}


def table_epochs(runs: Path) -> str:
    """Accuracy by group at fixed epochs of an MLP trained without early stopping, on both splits."""
    data = {tag: pd.read_csv(runs / name / "epochs.csv") for tag, name in DIAG.items()}
    head1 = "Group & \\multicolumn{4}{c}{Split by new profile, epoch} & \\multicolumn{4}{c}{Split by row, epoch} \\\\"
    head2 = " & " + " & ".join(str(c) for c in EPOCH_COLUMNS) * 1 + " & " + " & ".join(str(c) for c in EPOCH_COLUMNS) + " \\\\"
    groups = ["all", *CONTINUOUS, *sorted(set(data["Row"].group) - {"all", *CONTINUOUS})]
    lines = []
    for g in groups:
        cells = []
        for tag in ("NewProfile", "Row"):
            d = data[tag][data[tag].group == g]
            cells += [pct(d[d.epoch == c].accuracy.mean()) for c in EPOCH_COLUMNS]
        lines.append(g.replace("_", " ") + " & " + " & ".join(cells) + " \\\\")
    best = {tag: pd.read_csv(runs / name / "best_epoch.csv").best_validation_epoch.mean() for tag, name in DIAG.items()}
    lines += ["\\midrule", f"\\multicolumn{{9}}{{l}}{{Epoch with the best validation loss (the one E1 keeps): {best['NewProfile']:.0f} on new profiles, {best['Row']:.0f} by row}} \\\\"]
    return ("\\begin{tabular}{lcccccccc}\n\\toprule\n" + head1 + "\n\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}\n" + head2 + "\n\\midrule\n"
            + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def numbers_epochs(runs: Path) -> str:
    out = [HEADER.format(src="runs/diag_epochs_*")]
    for tag, name in DIAG.items():
        d = pd.read_csv(runs / name / "epochs.csv")
        best = pd.read_csv(runs / name / "best_epoch.csv").best_validation_epoch
        out.append(macro(f"epochBestVal{tag}", f"{best.mean():.0f}", f"epoch of the best validation loss, mean over seeds; {name}"))
        discrete = d[~d.group.isin(["all", *CONTINUOUS])]
        for epoch, et in EPOCH_TAG.items():
            at = d[d.epoch == epoch]
            out.append(macro(f"accEpochAll{et}{tag}", pct(at[at.group == "all"].accuracy.mean()), "MLP without early stopping, all groups"))
            out.append(macro(f"accEpochVisual{et}{tag}", pct(at[at.group == "visual"].accuracy.mean()), "MLP without early stopping, visual"))
            out.append(macro(f"accEpochShortStature{et}{tag}", pct(at[at.group == "short_stature"].accuracy.mean()), "MLP without early stopping, short stature"))
            out.append(macro(f"accEpochDiscrete{et}{tag}", pct(discrete[discrete.epoch == epoch].accuracy.mean()), "MLP without early stopping, mean of the six groups with discrete profiles"))
    return "".join(out)


def write_outputs(runs: Path, paper: Path, figures: bool) -> str:
    e = load(runs)
    write(paper / "p1" / "tables" / "t_leakage.tex", HEADER.format(src="runs/v1/*.csv") + table(e))
    text = numbers(e)
    if all((runs / name / "epochs.csv").exists() for name in DIAG.values()):
        write(paper / "p1" / "tables" / "t_epochs.tex", HEADER.format(src="runs/diag_epochs_*/epochs.csv") + table_epochs(runs))
        text += "\n" + numbers_epochs(runs)
    return text
