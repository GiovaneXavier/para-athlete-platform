"""Rule engine: Profile -> per-class verdicts."""
from __future__ import annotations

from dataclasses import dataclass

from .catalog import Catalog, load_catalog
from .evaluators import EVALUATORS
from .evaluators.base import uniform
from .schema import Profile, Status, Verdict


@dataclass(frozen=True)
class EligibilityResult:
    verdicts: dict[int, Verdict]

    def with_status(self, *statuses: Status) -> list[int]:
        return [cid for cid, v in self.verdicts.items() if v.status in statuses]

    @property
    def meets(self) -> list[int]:
        return self.with_status(Status.MEETS)

    @property
    def primary_class(self) -> int | None:
        """The single class that is met, or None when none or several are."""
        meets = self.meets
        return meets[0] if len(meets) == 1 else None

    @property
    def candidates(self) -> list[int]:
        """Classes that are met first, then borderline ones."""
        return self.with_status(Status.MEETS) + self.with_status(Status.BORDERLINE)


class RuleEngine:
    def __init__(self, catalog: Catalog | None = None):
        self.catalog = catalog or load_catalog()

    def evaluate(self, profile: Profile) -> EligibilityResult:
        verdicts: dict[int, Verdict] = {}
        for group in self.catalog.groups.values():
            specs = self.catalog.group_classes(group.name)
            if not profile.impairments & group.impairments:
                verdicts.update(
                    uniform(specs, Status.NOT_APPLICABLE, f"no impairment relevant to '{group.name}' declared")
                )
                continue
            verdicts.update(EVALUATORS[group.evaluator](profile, specs))
        return EligibilityResult(dict(sorted(verdicts.items())))

    def class_codes(self, class_id: int) -> tuple[str, ...]:
        return self.catalog.classes[class_id].codes
