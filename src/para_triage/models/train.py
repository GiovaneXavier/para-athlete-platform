"""Train the MLP and compare it with the rules baseline.

    python -m para_triage.models.train --data data/processed/synthetic_v0.csv --n-runs 5
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split

from ..data import encode_profiles, generate_dataset, record_to_profile
from ..eval import metrics
from ..eval.compare import compare
from .mlp import Standardizer, TrainConfig, fit_model, fit_temperature, predict_logits, softmax


def prepare(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x, m = encode_profiles(record_to_profile(r) for r in df.to_dict("records"))
    classes = np.sort(df["label"].unique())
    return x, m, np.searchsorted(classes, df["label"].to_numpy()), classes


def split(df: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """70/15/15, stratified by group and label."""
    strata = df["group"].astype(str) + "|" + df["label"].astype(str)
    idx = np.arange(len(df))
    train, rest = train_test_split(idx, test_size=0.30, stratify=strata, random_state=seed)
    val, test = train_test_split(rest, test_size=0.50, stratify=strata.iloc[rest], random_state=seed)
    return train, val, test


def run_once(df: pd.DataFrame, cfg: TrainConfig, prepared=None):
    x, m, y_idx, classes = prepared or prepare(df)
    train, val, test = split(df, cfg.seed)

    scaler = Standardizer().fit(x[train], m[train])
    xs = scaler.transform(x, m)
    model, history = fit_model(
        (xs[train], m[train], y_idx[train]), (xs[val], m[val], y_idx[val]), len(classes), cfg
    )

    temperature = fit_temperature(predict_logits(model, xs[val], m[val]), y_idx[val])
    logits = predict_logits(model, xs[test], m[test])
    result = compare(df.iloc[test], softmax(logits, temperature), classes)

    raw = softmax(logits)
    result["temperature"] = temperature
    result["mlp_calibration_before_scaling"] = {
        "nll": metrics.nll(raw, y_idx[test]),
        "ece": metrics.ece(raw, y_idx[test]),
        "brier": metrics.brier(raw, y_idx[test]),
    }
    result["epochs_trained"] = len(history)
    artifacts = {
        "model": model,
        "classes": classes,
        "scaler": scaler,
        "temperature": temperature,
        "history": history,
    }
    return result, artifacts


def save_checkpoint(artifacts: dict, cfg: TrainConfig, path: Path) -> None:
    torch.save(
        {
            "state_dict": artifacts["model"].state_dict(),
            "classes": artifacts["classes"],
            "mean": artifacts["scaler"].mean,
            "std": artifacts["scaler"].std,
            "temperature": artifacts["temperature"],
            "config": asdict(cfg),
        },
        path,
    )


def aggregate(runs: list[dict]) -> dict:
    """Mean and standard deviation of every numeric leaf across runs."""
    first = runs[0]
    if isinstance(first, dict):
        return {k: aggregate([r[k] for r in runs]) for k in first}
    values = np.array(runs, dtype=float)
    return {"mean": float(values.mean()), "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0}


def _fmt(stat: dict, pct: bool = True) -> str:
    scale = 100 if pct else 1
    return f"{stat['mean'] * scale:.1f} ± {stat['std'] * scale:.1f}" if pct else f"{stat['mean']:.3f} ± {stat['std']:.3f}"


def render_report(agg: dict, n_runs: int, n_rows: int, cfg: TrainConfig) -> str:
    o = agg["overall"]
    lines = [
        f"# MLP × baseline de regras ({n_runs} execuções, {n_rows} linhas)",
        "",
        "Média ± desvio padrão sobre divisões estratificadas 70/15/15 e inicializações diferentes. "
        "Quando as regras se abstêm, contam como erro.",
        "",
        "| Sistema | Acurácia (%) | F1 macro (%) |",
        "|---|---|---|",
    ]
    names = {"rules": "Regras", "mlp": "MLP", "hybrid": "Híbrido (regras, MLP se abstêm)"}
    for key, name in names.items():
        lines.append(f"| {name} | {_fmt(o[key]['accuracy'])} | {_fmt(o[key]['macro_f1'])} |")

    lines += [
        "",
        f"- Cobertura das regras (decidem): {_fmt(agg['rules_coverage'])}%",
        f"- Acurácia das regras quando decidem: {_fmt(agg['rules_accuracy_when_decided'])}%",
        f"- Acurácia do MLP onde as regras decidem: {_fmt(agg['mlp_accuracy_when_rules_decided'])}%",
        f"- Acurácia do MLP onde as regras se abstêm: {_fmt(agg['mlp_accuracy_when_rules_abstain'])}%",
        f"- Acurácia do MLP onde as regras decidem e erram: {_fmt(agg['mlp_accuracy_when_rules_wrong'])}%",
        f"- Top-2 do MLP: {_fmt(agg['mlp_top2_accuracy'])}%",
        "",
        "## Calibração do MLP",
        "",
        "| | NLL | ECE | Brier |",
        "|---|---|---|---|",
    ]
    for label, key in (("Antes da temperatura", "mlp_calibration_before_scaling"), ("Depois", "mlp_calibration")):
        c = agg[key]
        lines.append(f"| {label} | {_fmt(c['nll'], False)} | {_fmt(c['ece'], False)} | {_fmt(c['brier'], False)} |")
    lines += [
        "",
        f"Temperatura aprendida: {_fmt(agg['temperature'], False)}",
        "",
        "## Acurácia por grupo (%)",
        "",
        "| Grupo | Regras | MLP | Híbrido |",
        "|---|---|---|---|",
    ]
    for group, row in agg["by_group"].items():
        lines.append(f"| {group} | {_fmt(row['rules'])} | {_fmt(row['mlp'])} | {_fmt(row['hybrid'])} |")
    lines += ["", f"Configuração: `{asdict(cfg)}`", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/processed/synthetic_v0.csv"))
    parser.add_argument("--out", type=Path, default=Path("runs/mlp_v0"))
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if args.data.exists():
        df = pd.read_csv(args.data)
    else:
        print(f"{args.data} not found; generating the default dataset")
        df = generate_dataset(n_per_label=300, seed=0)
    prepared = prepare(df)

    base = TrainConfig(epochs=args.epochs)
    runs, artifacts = [], None
    for i in range(args.n_runs):
        cfg = replace(base, seed=args.seed + i)
        result, artifacts = run_once(df, cfg, prepared)
        runs.append(result)
        o = result["overall"]
        print(
            f"run {i}: rules {o['rules']['accuracy']:.3f}  mlp {o['mlp']['accuracy']:.3f}  "
            f"hybrid {o['hybrid']['accuracy']:.3f}  ({result['epochs_trained']} epochs)"
        )

    agg = aggregate(runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps({"aggregate": agg, "runs": runs}, indent=2), encoding="utf-8")
    report = render_report(agg, args.n_runs, len(df), base)
    (args.out / "report.md").write_text(report, encoding="utf-8")
    save_checkpoint(artifacts, base, args.out / "model.pt")
    print()
    print(report)


if __name__ == "__main__":
    main()
