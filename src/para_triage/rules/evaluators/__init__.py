"""Group evaluators, keyed by the `evaluator` field of each group in classes.yaml."""
from __future__ import annotations

from collections.abc import Callable, Sequence

from ..catalog import ClassSpec
from ..schema import Profile, Verdict
from .functional import evaluate_frame_runner, evaluate_neuro, evaluate_seated
from .limb import evaluate_limb_prosthesis, evaluate_limb_standing
from .sensory import evaluate_intellectual, evaluate_short_stature, evaluate_visual

Evaluator = Callable[[Profile, Sequence[ClassSpec]], dict[int, Verdict]]

EVALUATORS: dict[str, Evaluator] = {
    "visual": evaluate_visual,
    "intellectual": evaluate_intellectual,
    "short_stature": evaluate_short_stature,
    "limb_standing": evaluate_limb_standing,
    "limb_prosthesis": evaluate_limb_prosthesis,
    "neuro": evaluate_neuro,
    "frame_runner": evaluate_frame_runner,
    "seated": evaluate_seated,
}
