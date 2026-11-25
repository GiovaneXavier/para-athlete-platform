"""Diagnostic: accuracy by group over the training epochs, with no early stopping.

    python -m para_triage.experiments.diag_epochs --e1 runs/e1_profile --out runs/diag_epochs_profile
    python -m para_triage.experiments.diag_epochs --e1 runs/e1 --out runs/diag_epochs_row

On the split by new profile the best validation loss comes after ~10 epochs, and the E1 rule (keep the weights
of the epoch with the best validation NLL) stops there. The question is whether that under-trains the groups
with continuous values (visual, short stature), whose validation loss would still improve while the discrete
groups, where a held-out profile is new, start to overfit. The model is trained for 80 epochs with the E1
configuration of each seed and its test accuracy by group is recorded at fixed epochs, next to the epoch that
the E1 rule would have picked. Nothing here changes E1 or E7.
"""
from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from ..models.mlp import _DROPPABLE, MaskedMLP, Standardizer, predict_logits
from . import protocol as P
from .provenance import provenance, write_json
from .seed_context import load_seed, log, seed_main

CHECK = (10, 20, 30, 40, 60, 80)
EPOCHS = 80


def run_seed(seed: int, out: Path, e1_dir: Path, n_per_label: int, force: bool) -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "epochs.csv").exists() and not force:
        log(f"seed {seed}: already done, skipping")
        return
    ctx = load_seed(seed, e1_dir, cells=[P.DEFAULT_CELL], n_per_label=n_per_label)
    cfg = dataclasses.replace(ctx.mlp_config, epochs=EPOCHS, patience=10**6)
    view, split, y = ctx.views[P.DEFAULT_CELL], ctx.split, ctx.y
    train, val, test = split["train"], split["val"], split["test"]
    scaler = Standardizer().fit(view.x[train], view.m[train])
    xs = scaler.transform(view.x, view.m)
    xt, mt, yt = (torch.as_tensor(a) for a in (xs[train], view.m[train], y[train]))
    xv, mv, yv = (torch.as_tensor(a) for a in (xs[val], view.m[val], y[val]))
    torch.manual_seed(cfg.seed)
    gen = torch.Generator().manual_seed(cfg.seed)
    model = MaskedMLP(xt.shape[1], len(ctx.classes), cfg.hidden, cfg.dropout, cfg.use_mask)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    groups = np.asarray(ctx.true.groups)[test]
    best, best_epoch, rows = float("inf"), -1, []
    for epoch in range(1, EPOCHS + 1):
        model.train()
        order = torch.randperm(len(xt), generator=gen)
        for start in range(0, len(order), cfg.batch_size):
            idx = order[start : start + cfg.batch_size]
            if len(idx) < 2:
                continue
            xb, mb, yb = xt[idx], mt[idx], yt[idx]
            drop = (torch.rand(mb.shape, generator=gen) < cfg.feature_dropout) & (mb > 0) & _DROPPABLE
            mb = mb * (~drop)
            xb = xb * mb
            loss = F.cross_entropy(model(xb, mb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val_loss = F.cross_entropy(model(xv, mv), yv).item()
        if val_loss < best:
            best, best_epoch = val_loss, epoch
        if epoch in CHECK:
            correct = predict_logits(model, xs[test], view.m[test]).argmax(1) == y[test]
            for g in sorted(set(groups)):
                rows.append({"seed": seed, "epoch": epoch, "group": g, "accuracy": float(correct[groups == g].mean()), "val_loss": val_loss})
            rows.append({"seed": seed, "epoch": epoch, "group": "all", "accuracy": float(correct.mean()), "val_loss": val_loss})
    sdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"seed": seed, "best_validation_epoch": best_epoch, "best_validation_loss": best}]).to_csv(sdir / "best_epoch.csv", index=False)
    pd.DataFrame(rows).to_csv(sdir / "epochs.csv", index=False)  # last: marks the seed as done
    log(f"seed {seed}: best validation epoch {best_epoch}")


def aggregate(out: Path, seeds: list[int]) -> None:
    for name in ("epochs", "best_epoch"):
        frames = [pd.read_csv(out / f"seed_{s}" / f"{name}.csv") for s in seeds if (out / f"seed_{s}" / f"{name}.csv").exists()]
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{name}.csv", index=False)


def write_config(out: Path, seeds: list[int], e1_dir: Path) -> None:
    write_json(
        out / "config.json",
        {
            "experiment": "diag_epochs",
            "seeds": seeds,
            "uses": f"{e1_dir}: split.npz and tuning.json of each seed (the chosen MLP configuration)",
            "training": f"{EPOCHS} epochs, no early stopping, the E1 configuration of the seed",
            "recorded_epochs": list(CHECK),
            "note": "diagnostic only; E1 and E7 keep the weights of the epoch with the best validation loss",
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1", type=Path, default=Path("runs/e1_profile"))
    parser.add_argument("--out", type=Path, default=Path("runs/diag_epochs_profile"))
    parser.add_argument("--n-per-label", type=int, default=P.N_PER_LABEL)
    seed_main(
        "para_triage.experiments.diag_epochs",
        parser,
        argv,
        run_one=lambda seed, a: run_seed(seed, a.out, a.e1, a.n_per_label, a.force),
        write_config=lambda a: write_config(a.out, a.seeds, a.e1),
        aggregate=lambda a: aggregate(a.out, a.seeds),
        extra_args=lambda a: ["--e1", str(a.e1), "--n-per-label", str(a.n_per_label)],
    )


if __name__ == "__main__":
    main()
