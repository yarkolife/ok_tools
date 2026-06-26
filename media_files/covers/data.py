"""Plain data carrier for cover content (decoupled from Django models)."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CoverData:
    """Everything a template needs to render a cover, already resolved."""

    title: str = ''
    subtitle: str = ''
    author: str = ''
    category: str = ''
    number: Optional[int] = None
    duration_seconds: Optional[float] = None

    # Series / episode info parsed from the title (see covers.series).
    series: str = ''
    episode_marker: str = ''
    episode_part: Optional[int] = None
    episode_total: Optional[int] = None

    @property
    def is_series(self) -> bool:
        """True when an episode number was detected in the title."""
        return self.episode_part is not None
