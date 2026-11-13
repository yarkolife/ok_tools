"""The chapters of the manual.

Every chapter is a template in ``handbuch/templates/handbuch/kapitel/`` and is
listed here with the OK-Tools version and the date it was last checked
against. When a described page changes, the chapter is updated and its
``version`` and ``stand`` are raised in the same commit, so readers always see
how current the text is.

A chapter is only offered when the modules it describes are installed (a
module switched off in the environment is not in ``INSTALLED_APPS``).
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from django.apps import apps
from typing import Optional
from typing import Tuple


@dataclass(frozen=True)
class Kapitel:
    """One chapter of the manual."""

    slug: str
    title: str
    summary: str
    version: str
    stand: date
    icon: str = 'menu_book'
    requires: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def template(self) -> str:
        return f'handbuch/kapitel/{self.slug}.html'

    def available(self) -> bool:
        return all(apps.is_installed(app) for app in self.requires)


KAPITEL: Tuple[Kapitel, ...] = (
    Kapitel(
        slug='inventar-und-ausleihe',
        title='Inventar und Ausleihe',
        summary=(
            'Vom neuen Gerät bis zur Rückgabe: inventarisieren, Standort und '
            'Eigentümer festlegen, Etikett drucken und aufkleben, ausleihen '
            '(geführt oder mit dem Scanner) und zurücknehmen.'
        ),
        version='4.71.0',
        stand=date(2026, 11, 13),
        icon='inventory_2',
        requires=('inventory', 'rental'),
    ),
)


def available_chapters():
    """Chapters whose modules are installed here."""
    return [kapitel for kapitel in KAPITEL if kapitel.available()]


def get_chapter(slug: str) -> Optional[Kapitel]:
    """The chapter with this slug, if it exists and is available."""
    return next((k for k in available_chapters() if k.slug == slug), None)
