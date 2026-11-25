"""The pipeline of design note section 3.1: image extractor and report extractor read SEPARATELY,
then the comparator (pure code) decides. Nobody asks a model "does it match?".

An image extractor is any callable `png bytes -> Attrs`; a report extractor is any callable
`text -> Attrs`. Real models come in a later PR; here they are classical readers, rules, and
fakes. The result of each pair says WHERE an error is: in the image reading, in the report
reading, in both, or in the comparison (the last must never happen with the real comparator).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

from .compare import Comparison, compare
from .errors import Pair
from .schema import Attrs

ImageExtractor = Callable[[bytes], Attrs]
ReportExtractor = Callable[[str], Attrs]
Comparator = Callable[[Attrs, Attrs], Comparison]


@dataclass(frozen=True)
class Outcome:
    image_id: str
    level: int
    kind: str
    status: str  # of the pair: ok, indistinguishable
    note: str
    expected: str
    got: str
    image_true: Attrs
    image_read: Attrs
    report_true: Attrs
    report_read: Attrs

    @property
    def correct(self) -> bool:
        return self.got == self.expected

    @property
    def image_wrong(self) -> bool:
        return self.image_read != self.image_true

    @property
    def report_wrong(self) -> bool:
        return self.report_read != self.report_true

    @property
    def locus(self) -> str:
        """Where a wrong verdict comes from. Empty when the verdict is the expected one (even if the extractors erred and the errors cancelled)."""
        if self.correct:
            return ""
        if self.image_wrong and self.report_wrong:
            return "imagem e laudo"
        if self.image_wrong:
            return "imagem"
        if self.report_wrong:
            return "laudo"
        return "comparação"


def evaluate(pairs: Iterable[Pair], images: Mapping[str, object], image_extractor: ImageExtractor,
             report_extractor: ReportExtractor, comparator: Comparator = compare) -> list[Outcome]:
    """Runs every buildable pair. `images` maps an image id to an object with `.png`, `.attrs` and `.level`
    (an `ImageRecord`). Each image is read once, however many pairs it has."""
    read_cache: dict[str, Attrs] = {}
    outcomes: list[Outcome] = []
    for pair in pairs:
        if pair.content is None:  # not_applicable: nothing to run
            continue
        record = images[pair.image_id]
        if pair.image_id not in read_cache:
            read_cache[pair.image_id] = image_extractor(record.png)
        image_read = read_cache[pair.image_id]
        report_read = report_extractor(pair.text)
        result = comparator(image_read, report_read)
        outcomes.append(Outcome(
            image_id=pair.image_id, level=record.level, kind=pair.kind, status=pair.status, note=pair.note, expected=pair.expected,
            got=result.verdict, image_true=record.attrs, image_read=image_read, report_true=pair.content.attrs, report_read=report_read,
        ))
    return outcomes


def index_images(records: Sequence) -> dict[str, object]:
    return {r.image_id: r for r in records}
