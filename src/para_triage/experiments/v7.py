"""V7: conformal sets conditional on the number of OBSERVED missing fields.

    python -m para_triage.experiments.v7 --seeds 0 1 2 3 4 --jobs 5 --out runs/v7

E7 found that the marginal coverage hides much lower coverage when fields are missing, but it counted the
missing fields from the true profile, which nobody has in the field. Here the count comes from what is known
at prediction time: the fields that the form of the profile's impairment set asks for, minus those observed.
The form of an impairment set is the set of fields present in every true profile of that set in the training
rows (the generator's schema), not a property of the individual row.

Two different things are reported and must not be confused:
  diagnostic  coverage of the marginal LAC sets, broken down by band of missing fields (observed count, and
              the true-profile count of E7 for comparison). Nothing is promised there.
  method      sets calibrated separately in each observed band ("LAC_band"; bands 0, 1, 2+) or in two bands
              ("LAC_band2"; 0 and 1+), and LAC after a temperature fitted per band on the validation rows
              ("LAC_Tband"). The guarantee is coverage within each observed band, on average over the
              calibration draw, under exchangeability inside the band; not coverage for an individual case,
              and not per pattern of missing fields.

Bands with few rows give unreliable coverage: the number of rows per band and the spread over repartitions
are reported. Also run on two of the E-MNAR regimes (calibrated at MCAR or on the tested regime).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from ..models.mlp import fit_temperature, softmax
from . import conformal as C
from . import protocol as P
from .baselines import _FIELDS
from .e7 import ALPHA_MAIN, ALPHAS, BAND_CUTS, N_SPLITS, band, missing_counts
from .emnar import REGIMES
from .provenance import provenance, write_json
from .seed_context import SeedContext, default_models, load_seed, log, seed_main

MODELS = ("mlp", "gb")
METHODS = ("LAC", "LAC_band", "LAC_band2", "LAC_Tband")
# regime name, multiplier -> where the view comes from
VIEWS = (("mcar", 1.0), ("mcar", 2.0), ("label_0.9", 1.0), ("value_up_0.9", 1.0))
REFERENCE = ("mcar", 1.0)


def _key(profile) -> tuple:
    return tuple(sorted(i.value for i in profile.impairments))


def expected_fields(true_profiles, rows) -> dict[tuple, frozenset]:
    """Fields the form asks for, per impairment set: present in every true training profile of the set."""
    out: dict[tuple, set] = {}
    for i in rows:
        p = true_profiles[i]
        present = {f for f in _FIELDS if getattr(p, f) is not None}
        out[_key(p)] = present if _key(p) not in out else out[_key(p)] & present
    return {k: frozenset(v) for k, v in out.items()}


def observed_missing(profiles, expected: dict[tuple, frozenset]) -> np.ndarray:
    """Number of the form's fields that the observed profile lacks (what is known in the field)."""
    return np.array([sum(getattr(p, f) is None for f in expected.get(_key(p), ())) for p in profiles])


def merged_band(bands: np.ndarray) -> np.ndarray:
    return np.where(bands == "0", "0", "1+")


def band_temperatures(p_val: np.ndarray, y_val: np.ndarray, bands_val: np.ndarray) -> dict[str, float]:
    """One temperature for the rows with no observed missing field and one for the rest."""
    merged = merged_band(bands_val)
    return {b: fit_temperature(np.log(np.clip(p_val[merged == b], 1e-12, 1)), y_val[merged == b]) for b in ("0", "1+")}


def apply_temperatures(p: np.ndarray, bands: np.ndarray, temps: dict[str, float]) -> np.ndarray:
    out = p.copy()
    merged = merged_band(bands)
    for b, t in temps.items():
        sel = merged == b
        out[sel] = softmax(np.log(np.clip(p[sel], 1e-12, 1)), t)
    return out


def sets_for(method: str, p_cal, y_cal, bands_cal, p_test, bands_test, alpha, temps=None) -> np.ndarray:
    if method == "LAC":
        return C.conformal_sets(p_cal, y_cal, p_test, alpha, "LAC")
    if method == "LAC_band":
        return C.conformal_sets_by_group(p_cal, y_cal, bands_cal, p_test, bands_test, alpha, "LAC")
    if method == "LAC_band2":
        return C.conformal_sets_by_group(p_cal, y_cal, merged_band(bands_cal), p_test, merged_band(bands_test), alpha, "LAC")
    if method == "LAC_Tband":
        return C.conformal_sets(apply_temperatures(p_cal, bands_cal, temps), y_cal, apply_temperatures(p_test, bands_test, temps), alpha, "LAC")
    raise ValueError(method)


def run_seed(seed: int, out: Path, e1_dir: Path, n_per_label: int, n_splits: int, force: bool) -> None:
    sdir = out / f"seed_{seed}"
    if (sdir / "marginal.csv").exists() and not force:
        log(f"seed {seed}: already done, skipping")
        return
    ctx: SeedContext = load_seed(seed, e1_dir, cells=[P.DEFAULT_CELL, (1.0, 2.0)], n_per_label=n_per_label)
    models = default_models(ctx)
    from ..data.noise import NoiseConfig

    stream_of = {name: i for i, (name, _) in enumerate(REGIMES)}
    mech_of = dict(REGIMES)
    views = {}
    for name, mult in VIEWS:
        views[(name, mult)] = ctx.views[(1.0, mult)] if mech_of[name] is None else P.make_mnar_view(ctx.true, seed, mech_of[name], stream_of[name], mult, NoiseConfig())[0]

    split = ctx.split
    pool = np.sort(np.concatenate([split["cal"], split["test"]]))
    val = split["val"]
    expected = expected_fields(ctx.true.profiles, split["train"])
    probs = {m: {} for m in MODELS}
    obs_band, true_band, agree = {}, {}, []
    for key, view in views.items():
        for m in MODELS:
            fn = models.mlp_proba if m == "mlp" else models.gb_proba
            probs[m][key] = fn(view.x[pool], view.m[pool])
        counts = observed_missing(view.profiles, expected)
        true_counts = missing_counts(ctx.true, view)
        obs_band[key], true_band[key] = band(counts[pool]), band(true_counts[pool])
        agree.append({"seed": seed, "regime": key[0], "multiplier": key[1], "agreement_observed_true_count": float((counts == true_counts).mean()),
                      **{f"share_observed_{b}": float((obs_band[key] == b).mean()) for b in ("0", "1", f"{BAND_CUTS[-1]}+")},
                      **{f"share_true_{b}": float((true_band[key] == b).mean()) for b in ("0", "1", f"{BAND_CUTS[-1]}+")}})
    # temperatures per band, from the validation rows of the reference view (what is known when deploying)
    ref = views[REFERENCE]
    val_band = band(observed_missing([ref.profiles[i] for i in val], expected))
    temps = {m: band_temperatures((models.mlp_proba if m == "mlp" else models.gb_proba)(ref.x[val], ref.m[val]), ctx.y[val], val_band) for m in MODELS}
    log(f"seed {seed}: probabilities for {len(views)} views")

    y_pool = ctx.y[pool]
    strata = pd.Series(np.asarray(ctx.true.groups)[pool]).str.cat(pd.Series(ctx.true.labels[pool].astype(str)), sep="|")
    marginal, by_band = [], []
    for r in range(n_splits):
        a, b = train_test_split(np.arange(len(pool)), test_size=0.5, stratify=strata, random_state=seed * 1000 + r)
        for model in MODELS:
            for method in METHODS:
                for alpha in ALPHAS:
                    for test_key in views:
                        for cal_key in dict.fromkeys([REFERENCE, test_key]):
                            sets = sets_for(method, probs[model][cal_key][a], y_pool[a], obs_band[cal_key][a], probs[model][test_key][b], obs_band[test_key][b], alpha, temps[model])
                            base = {"seed": seed, "split": r, "model": model, "method": method, "alpha": alpha,
                                    "cal_regime": cal_key[0], "cal_multiplier": cal_key[1], "test_regime": test_key[0], "test_multiplier": test_key[1],
                                    **{f"n_cal_{bd}": int((obs_band[cal_key][a] == bd).sum()) for bd in ("0", "1", f"{BAND_CUTS[-1]}+")}}
                            marginal.append({**base, **C.set_metrics(sets, y_pool[b], ctx.ambiguous_index)})
                            if cal_key == test_key or cal_key == REFERENCE:
                                cond = C.coverage_by(sets, y_pool[b], {"observed": obs_band[test_key][b], "true_profile": true_band[test_key][b]})
                                for k, v in base.items():
                                    cond[k] = v
                                by_band.append(cond)
        if r % 5 == 4:
            log(f"seed {seed}: split {r + 1}/{n_splits}")

    # rows per band in each calibration half (reliability), over the repartitions
    sdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(agree).to_csv(sdir / "agreement.csv", index=False)
    write_json(sdir / "temperatures.json", temps)
    pd.concat(by_band, ignore_index=True).to_csv(sdir / "by_band.csv", index=False)
    pd.DataFrame(marginal).to_csv(sdir / "marginal.csv", index=False)  # last: marks the seed as done
    log(f"seed {seed}: done")


FILES = ("marginal", "by_band", "agreement")


def aggregate(out: Path, seeds: list[int]) -> None:
    for name in FILES:
        frames = [pd.read_csv(out / f"seed_{s}" / f"{name}.csv") for s in seeds if (out / f"seed_{s}" / f"{name}.csv").exists()]
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{name}.csv", index=False)


def write_config(out: Path, seeds: list[int], n_per_label: int, n_splits: int) -> None:
    write_json(
        out / "config.json",
        {
            "experiment": "V7",
            "seeds": seeds,
            "n_per_label": n_per_label,
            "uses": "runs/e1 (split, MLP checkpoint, tuning); the E-MNAR views of the same seeds",
            "observed_missing_count": "fields in the form of the impairment set (present in every true training profile of the set) that the observed profile lacks",
            "bands": f"0, 1, {BAND_CUTS[-1]} or more observed missing fields; 'band2' merges 1 and more",
            "methods": {
                "LAC": "marginal LAC (as E7); a diagnostic when broken down by band",
                "LAC_band": "LAC with one threshold per observed band",
                "LAC_band2": "LAC with one threshold for 0 missing and one for 1 or more",
                "LAC_Tband": "LAC after a temperature per band (0 versus 1+) fitted on the validation rows of the reference view",
            },
            "guarantee": "coverage within each observed band, on average over the calibration draw, under exchangeability inside the band; not per case, not per mask pattern",
            "alphas": list(ALPHAS),
            "main_alpha": ALPHA_MAIN,
            "n_splits_per_seed": n_splits,
            "views": [{"regime": r, "multiplier": m} for r, m in VIEWS],
            "reference_view": list(REFERENCE),
            "models": "MLP (E1 checkpoint) and gradient boosting, trained at (1, 1) MCAR; never retrained",
            "nothing_tuned_on_test": True,
            **provenance(),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1", type=Path, default=Path("runs/e1"))
    parser.add_argument("--out", type=Path, default=Path("runs/v7"))
    parser.add_argument("--n-per-label", type=int, default=P.N_PER_LABEL)
    parser.add_argument("--n-splits", type=int, default=N_SPLITS)
    seed_main(
        "para_triage.experiments.v7",
        parser,
        argv,
        run_one=lambda seed, a: run_seed(seed, a.out, a.e1, a.n_per_label, a.n_splits, a.force),
        write_config=lambda a: write_config(a.out, a.seeds, a.n_per_label, a.n_splits),
        aggregate=lambda a: aggregate(a.out, a.seeds),
        extra_args=lambda a: ["--e1", str(a.e1), "--n-per-label", str(a.n_per_label), "--n-splits", str(a.n_splits)],
    )


if __name__ == "__main__":
    main()
