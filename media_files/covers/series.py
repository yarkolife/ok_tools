"""Parse series / episode information out of a license title.

German community-TV titles frequently encode an episode marker, e.g.
``"Rudi Ra Teil 14"``, ``"CSD Halle 13.09.2025 Teil: 2/4"`` or
``"Haltestelle - das Straßenbahnmagazin Folge 248"``. The text before the
marker is usually the recurring series name (a brand for the whole series).
"""

import re
from dataclasses import dataclass
from typing import Optional

# Markers that introduce an episode/part number, in German usage.
_MARKER = r'(?:Folge|Teil|Episode|Ep|Staffel|Vol)'
_SERIES_RE = re.compile(
    rf'\b(?P<marker>{_MARKER})\.?\s*:?\s*'
    r'(?P<part>\d+)(?:\s*/\s*(?P<total>\d+))?',
    re.IGNORECASE,
)

# Characters/separators to strip from a trailing series name.
_TRAILING = ' \t-–—:|"\'„“”«»()'


@dataclass
class SeriesInfo:
    """Parsed series metadata; ``part`` is ``None`` when nothing matched."""

    series: str = ''
    marker: str = ''
    part: Optional[int] = None
    total: Optional[int] = None

    @property
    def matched(self) -> bool:
        """True if an episode marker was found."""
        return self.part is not None


def parse_series(title: str) -> SeriesInfo:
    """Extract series name and episode number from a title.

    Returns an empty :class:`SeriesInfo` (``matched is False``) when no
    episode marker is present.
    """
    if not title:
        return SeriesInfo()

    match = _SERIES_RE.search(title)
    if not match:
        return SeriesInfo()

    part = int(match.group('part'))
    total = match.group('total')
    series = title[:match.start()].strip(_TRAILING).strip()

    return SeriesInfo(
        series=series,
        marker=match.group('marker').capitalize(),
        part=part,
        total=int(total) if total else None,
    )
