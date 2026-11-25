"""Numbers for the report (numpy and the standard library; no torch). Evidence level N1: synthetic pictures, labels by construction.

Words used below, all fixed before any run:

- IMAGE LABEL: what the picture shows (`?` for a limb whose end is hidden or cut). The network is scored against it.
- TRUE attributes: what the generator built (the real level of every limb, hidden or not). The form and the class are scored against these.
- CLASS: the set of candidate classes (met plus borderline) that the rules give from four limb levels and a posture. Compared as a set.
  The class of a combination that gives no class is the EMPTY set and is a valid answer; it is not the same as UNDECIDED.
- UNDECIDED: an attribute the class needs is `?` (a hidden limb; a chair or prosthesis flag that is unknown), so the rules cannot be run.
  An undecided answer is never counted as correct.
- AUTOMATIC CLASS CORRECT: decided, not sent to review, and the set equals the true set.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from para_triage.consistency.metrics import bootstrap_by_image, wilson
from para_triage.consistency.schema import UNKNOWN

from . import classes, forms
from .labels import FLAGS, HEADS, IGNORE, LIMBS, decode

REVIEW = "revisar"


def values(row, level: int) -> dict:
    """Head indices -> attribute values. At level 1 the flags are 'no' (the mannequin has no chair or prosthesis)."""
    out = {name: decode(name, int(i)) if int(i) != IGNORE else "no" for name, i in zip(HEADS, row)}
    return out


def klass(vals: dict) -> frozenset | None:
    return classes.candidates(tuple(vals[n] for n in LIMBS), vals["wheelchair"], vals["prosthesis"])


def interval(k: int, n: int) -> str:
    if n == 0:
        return "n/a (n=0)"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({k}/{n}; {100 * lo:.1f} a {100 * hi:.1f})"


def boot(flags: list[bool]) -> tuple[float, float]:
    return bootstrap_by_image({str(i): (int(f), 1) for i, f in enumerate(flags)}, draws=1000)


# ---------------------------------------------------------------------------------------------
# readings of the network


def readings(probs: list[np.ndarray]):
    """(indices (N, 6), confidences (N, 6)): the argmax of every head and its probability."""
    idx = np.stack([p.argmax(1) for p in probs], axis=1)
    conf = np.stack([p.max(1) for p in probs], axis=1)
    return idx, conf


def attribute_hits(idx: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict[str, tuple[int, int]]:
    """(hits, n) per head against the IMAGE label, over the images in `mask` (a head with IGNORE is skipped)."""
    out = {}
    for j, name in enumerate(HEADS):
        use = mask & (y[:, j] != IGNORE)
        out[name] = (int((idx[use, j] == y[use, j]).sum()), int(use.sum()))
    return out


def visible_hits(idx: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict[str, tuple[int, int]]:
    """The same, only where the picture shows the attribute (the image label is not `?`)."""
    out = {}
    for j, name in enumerate(HEADS):
        unknown = [i for i in range(len(y)) if y[i, j] != IGNORE and decode(name, int(y[i, j])) == UNKNOWN]
        drop = np.zeros(len(y), bool)
        drop[unknown] = True
        use = mask & (y[:, j] != IGNORE) & ~drop
        out[name] = (int((idx[use, j] == y[use, j]).sum()), int(use.sum()))
    return out


def classical_hits(reads: list[dict], y: np.ndarray, mask: np.ndarray) -> dict[str, tuple[int, int]]:
    """The classical reader against the image label (limbs only; it does not read chair or prosthesis)."""
    out = {}
    for j, name in enumerate(LIMBS):
        use = [i for i in np.nonzero(mask)[0]]
        out[name] = (sum(reads[i][name] == decode(name, int(y[i, j])) for i in use), len(use))
    return out


def mirror_consistency(idx: np.ndarray, idx_flipped: np.ndarray, mask: np.ndarray) -> dict:
    """`idx_flipped` is the reading of the reflected picture with the sides put back in the person's order, so for a network that
    respects the mirror it equals `idx`. Per limb head, and for the four heads at once."""
    same = idx[:, :4] == idx_flipped[:, :4]
    out = {name: (int(same[mask, j].sum()), int(mask.sum())) for j, name in enumerate(LIMBS)}
    out["all four limbs"] = (int(same[mask].all(axis=1).sum()), int(mask.sum()))
    return out


def calibration(idx: np.ndarray, conf: np.ndarray, y: np.ndarray, mask: np.ndarray, bins: int = 10) -> dict:
    """Expected calibration error of the four limb heads pooled (equal-width bins of confidence), plus mean confidence and accuracy."""
    c = conf[mask][:, :4].ravel()
    hit = (idx[mask][:, :4] == y[mask][:, :4]).ravel().astype(float)
    ece, edges = 0.0, np.linspace(0.0, 1.0, bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (c > lo) & (c <= hi) if lo > 0 else (c >= lo) & (c <= hi)
        if sel.any():
            ece += sel.mean() * abs(hit[sel].mean() - c[sel].mean())
    return {"ece": float(ece), "mean_confidence": float(c.mean()), "accuracy": float(hit.mean()), "n": int(len(c))}


def majority_hits(train_y: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict[str, tuple[int, int]]:
    """The best constant guess (the most common image label of each head in `train_y`), scored on `y` over `mask`: the chance floor."""
    out = {}
    for j, name in enumerate(HEADS):
        col = train_y[train_y[:, j] != IGNORE, j]
        if len(col) == 0:
            continue
        guess = Counter(col.tolist()).most_common(1)[0][0]
        use = mask & (y[:, j] != IGNORE)
        out[name] = (int((y[use, j] == guess).sum()), int(use.sum()))
    return out


# ---------------------------------------------------------------------------------------------
# the class and the three arms


def class_arms(split, idx: np.ndarray, level: int, mask: np.ndarray, oracle_posture: bool = False) -> dict:
    """The IMAGE arm: the class from the network's argmax values. Returns counts over `mask`."""
    ok = und = empty_true = ok_nonempty = n_nonempty = 0
    flags = []
    n = int(mask.sum())
    for i in np.nonzero(mask)[0]:
        truth = values(split.t[i], level)
        want = klass(truth)
        vals = values(idx[i], level)
        if oracle_posture:
            vals["wheelchair"], vals["prosthesis"] = truth["wheelchair"], truth["prosthesis"]
        got = klass(vals)
        right = got is not None and got == want
        ok += right
        und += got is None
        flags.append(right)
        if want:
            n_nonempty += 1
            ok_nonempty += right
    return {"n": n, "ok": ok, "undecided": und, "n_nonempty": n_nonempty, "ok_nonempty": ok_nonempty, "flags": flags}


def classical_class(split, reads: list[dict], level: int, mask: np.ndarray, oracle_posture: bool = True) -> dict:
    """The classical reader reads only the limbs, so its class uses the TRUE posture (generous to it, and said so in the report)."""
    ok = und = n_nonempty = ok_nonempty = 0
    flags = []
    for i in np.nonzero(mask)[0]:
        truth = values(split.t[i], level)
        want = klass(truth)
        vals = {**{n: reads[i][n] for n in LIMBS}, "wheelchair": truth["wheelchair"], "prosthesis": truth["prosthesis"]}
        got = klass(vals)
        right = got is not None and got == want
        ok += right
        und += got is None
        flags.append(right)
        if want:
            n_nonempty += 1
            ok_nonempty += right
    return {"n": int(mask.sum()), "ok": ok, "undecided": und, "n_nonempty": n_nonempty, "ok_nonempty": ok_nonempty, "flags": flags}


def fuse(form: dict, net_idx_row, net_conf_row, level: int, tau: float) -> tuple[dict, bool]:
    """The simple fusion, no learning. Field by field: where the form has a value it stands; where it is blank the network's value stands if the
    network is at least `tau` sure and not `?`, otherwise the field stays `?`. If both have a value and they differ, the verdict is REVIEW."""
    merged, review = {}, False
    use = HEADS if level == 2 else LIMBS
    for j, name in enumerate(HEADS):
        f = form[name]
        if name not in use:
            merged[name] = f
            continue
        v = decode(name, int(net_idx_row[j]))
        net = v if (net_conf_row[j] >= tau and v != UNKNOWN) else None
        if f != UNKNOWN:
            merged[name] = f
            review = review or (net is not None and net != f)
        else:
            merged[name] = net if net is not None else UNKNOWN
    return merged, review


def form_values(truth: dict, cell, key: str, level: int) -> dict:
    form = forms.make_form(truth, cell[0], cell[1], key, level)
    if level == 1:
        form["wheelchair"], form["prosthesis"] = "no", "no"  # the mannequin has neither; the form does not leave them blank
    return form


def form_grid(split, idx, conf, level: int, mask: np.ndarray, tau: float, cells=forms.CELLS) -> dict:
    """For each (missing, errors) cell: the FORM arm and the FUSION arm over `mask`."""
    out = {}
    rows = np.nonzero(mask)[0]
    for cell in cells:
        f_ok = f_und = fu_ok = fu_und = fu_review = 0
        err_n = err_flagged = clean_n = clean_flagged = clean_correct_auto = 0
        flags_form, flags_fusion = [], []
        for i in rows:
            truth = values(split.t[i], level)
            want = klass(truth)
            form = form_values(truth, cell, f"{level}:{split.name}:{i}", level)
            got_form = klass(form)
            right_form = got_form is not None and got_form == want
            f_ok += right_form
            f_und += got_form is None
            merged, review = fuse(form, idx[i], conf[i], level, tau)
            got = klass(merged)
            right = (not review) and got is not None and got == want
            fu_ok += right
            fu_und += got is None
            fu_review += review
            flags_form.append(right_form)
            flags_fusion.append(right)
            if forms.has_error(form, truth):
                err_n += 1
                err_flagged += review
            else:
                clean_n += 1
                clean_flagged += review
                clean_correct_auto += right
        out[cell] = {"n": len(rows), "form_ok": f_ok, "form_undecided": f_und, "fusion_ok": fu_ok, "fusion_undecided": fu_und, "fusion_review": fu_review,
                     "form_with_error": err_n, "error_flagged": err_flagged, "form_clean": clean_n, "clean_flagged": clean_flagged, "clean_correct_auto": clean_correct_auto,
                     "form_flags": flags_form, "fusion_flags": flags_fusion}
    return out


def choose_tau(per_level: dict, candidates=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)) -> tuple[float, dict]:
    """The fusion threshold, chosen on the DEVELOPMENT set only, at 30% blank and 5% mistaken fields: the one with the most GOOD OUTCOMES, where
    a good outcome is: the form has a limb mistake and the verdict is REVIEW, or the form has none and the automatic class is correct.
    `per_level` maps a level to (Split, idx, conf)."""
    scores = {}
    cell = (0.30, 0.05)
    for tau in candidates:
        good = n = 0
        for level, (sp, ix, cf) in per_level.items():
            g = form_grid(sp, ix, cf, level, np.ones(len(sp), bool), tau, cells=[cell])[cell]
            good += g["error_flagged"] + g["clean_correct_auto"]
            n += g["n"]
        scores[tau] = good / n
    best = max(candidates, key=lambda t: (scores[t], -t))
    return best, scores


# ---------------------------------------------------------------------------------------------
# replication (second training seed) and the post-test look at the visible slice


def _visible_mask(y: np.ndarray, j: int, name: str, mask: np.ndarray) -> np.ndarray:
    unk = np.array([y[i, j] != IGNORE and decode(name, int(y[i, j])) == UNKNOWN for i in range(len(y))], bool)
    return mask & (y[:, j] != IGNORE) & ~unk


def classical_visible_hits(reads: list[dict], y: np.ndarray, mask: np.ndarray) -> dict[str, tuple[int, int]]:
    """POST-TEST ANALYSIS. The classical reader against the image label only where the picture shows the limb (label not `?`)."""
    out = {}
    for j, name in enumerate(LIMBS):
        use = np.nonzero(_visible_mask(y, j, name, mask))[0]
        out[name] = (sum(reads[i][name] == decode(name, int(y[i, j])) for i in use), len(use))
    return out


def majority_visible_hits(train_y: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict[str, tuple[int, int]]:
    """POST-TEST ANALYSIS. The best constant guess among the VISIBLE labels of the training set, scored on the visible slice of `y`."""
    out = {}
    for j, name in enumerate(LIMBS):
        col = train_y[_visible_mask(train_y, j, name, np.ones(len(train_y), bool)), j]
        guess = Counter(col.tolist()).most_common(1)[0][0]
        use = _visible_mask(y, j, name, mask)
        out[name] = (int((y[use, j] == guess).sum()), int(use.sum()))
    return out


def seed_gap(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Difference in percentage points between two (hits, n) pairs of the same cell (second minus first)."""
    return 100.0 * (b[0] / b[1] - a[0] / a[1])
