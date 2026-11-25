"""Trains the small network on CPU, watching the DEVELOPMENT set only. The test set is never opened here.

    PYTHONPATH=src;spikes  python -m imagem_formulario.train [--epochs 30] [--threads 10] [--budget-min 100] [--name run1]

Writes the weights, a JSON log and the development predictions to `paths.RUNS` (outside the repository).
What is tuned here, and on which set, is recorded in the report: the number of epochs (early stop on the development mean accuracy of the
four limbs), nothing else was tuned on the test set.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import torch

from . import data, paths
from .labels import HEADS, IGNORE, LIMBS
from .net import SmallNet, loss_fn, mirror_batch, parameter_count, peak_memory_mb, predict, to_tensor


def limb_accuracy(probs: list[np.ndarray], y: np.ndarray) -> float:
    """Mean over the four limb heads of the share of images where the argmax equals the image label."""
    return float(np.mean([(probs[i].argmax(1) == y[:, i]).mean() for i in range(4)]))


def stack(splits: list[data.Split]):
    return np.concatenate([s.x for s in splits]), np.concatenate([s.y for s in splits])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--threads", type=int, default=10)
    ap.add_argument("--budget-min", type=float, default=100.0)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-mirror", action="store_true", help="train without the mirror augmentation (a control)")
    ap.add_argument("--name", default="run1")
    args = ap.parse_args()

    paths.ensure()
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    rng = np.random.RandomState(args.seed)
    train = [data.load(1, "train"), data.load(2, "train")]
    dev = [data.load(1, "dev"), data.load(2, "dev")]
    x_train, y_train = stack(train)
    x_dev, y_dev = stack(dev)
    model = SmallNet()
    print(f"parameters: {parameter_count(model)}; train {len(x_train)}, dev {len(x_dev)}; threads {args.threads}", flush=True)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    steps_per_epoch = int(np.ceil(len(x_train) / args.batch))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * steps_per_epoch)

    log, best, bad, t0 = [], -1.0, 0, time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = rng.permutation(len(x_train))
        running, seen = 0.0, 0
        t_epoch = time.time()
        for start in range(0, len(order), args.batch):
            idx = order[start:start + args.batch]
            xb = to_tensor(x_train[idx])
            yb = torch.from_numpy(y_train[idx])
            if not args.no_mirror:
                flip = torch.from_numpy(rng.rand(len(idx)) < 0.5)
                if flip.any():
                    xm, ym = mirror_batch(xb[flip], yb[flip])
                    xb, yb = xb.clone(), yb.clone()
                    xb[flip], yb[flip] = xm, ym
            xb = xb * (1.0 + 0.2 * (torch.rand(len(idx), 1, 1, 1) - 0.5))  # brightness jitter of up to +-10%
            loss = loss_fn(model(xb), yb)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            running += float(loss.detach()) * len(idx)
            seen += len(idx)
        probs = predict(model, x_dev)
        acc = limb_accuracy(probs, y_dev)
        entry = {"epoch": epoch, "train_loss": round(running / seen, 4), "dev_limb_accuracy": round(acc, 4), "epoch_seconds": round(time.time() - t_epoch, 1),
                 "elapsed_minutes": round((time.time() - t0) / 60, 1), "peak_memory_mb": round(peak_memory_mb())}
        log.append(entry)
        print(json.dumps(entry), flush=True)
        if acc > best:
            best, bad = acc, 0
            torch.save(model.state_dict(), paths.RUNS / f"{args.name}.pt")
        else:
            bad += 1
        if bad >= args.patience:
            print("early stop on the development set", flush=True)
            break
        if (time.time() - t0) / 60 > args.budget_min:
            print("time budget reached", flush=True)
            break
    summary = {"name": args.name, "parameters": parameter_count(model), "best_dev_limb_accuracy": round(best, 4), "train_minutes": round((time.time() - t0) / 60, 1),
               "peak_memory_mb": round(peak_memory_mb()), "args": vars(args), "log": log}
    (paths.RUNS / f"{args.name}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"done: best dev limb accuracy {best:.4f} in {summary['train_minutes']} min, peak memory {summary['peak_memory_mb']} MB", flush=True)


if __name__ == "__main__":
    main()
