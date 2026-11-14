"""The chapters of the manual.

Every chapter is a Markdown file in ``handbuch/inhalt/<slug>.md`` (see
``handbuch/render.py`` for the extras it may use) and is listed here with the
OK-Tools version and the date it was last checked against. When a described
page changes, the chapter is updated and its ``version`` and ``stand`` are
raised in the same commit, so readers always see how current the text is.
A chapter written for an older minor version than the installed one says so.

``pfade`` lists the files and folders of the pages a chapter describes.
``python handbuch/aktualitaet.py`` lists commits that touched them after the
chapter's ``stand``; with ``--staged`` (pre-commit hook) it warns when they are
changed without the chapter. Keep this file free of Django calls at import
time in the ``KAPITEL`` literal: the script reads it without Django.

A chapter is only offered when the modules it describes are installed (a
module switched off in the environment is not in ``INSTALLED_APPS``).
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from django.apps import apps
from ok_tools.version import VERSION
from ok_tools.version import version_tuple
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
    pfade: Tuple[str, ...] = field(default_factory=tuple)

    def available(self) -> bool:
        return all(apps.is_installed(app) for app in self.requires)

    @property
    def older_than_installed(self) -> bool:
        """Written for an older minor version than the one running."""
        return version_tuple(self.version)[:2] < version_tuple(VERSION)[:2]


KAPITEL: Tuple[Kapitel, ...] = (
    Kapitel(
        slug='inventar-und-ausleihe',
        title='Inventar und Ausleihe',
        summary=(
            'Vom neuen Gerät bis zur Rückgabe: inventarisieren, Standort und '
            'Eigentümer festlegen, Etikett drucken und aufkleben, ausleihen '
            '(geführt oder mit dem Scanner) und zurücknehmen.'
        ),
        version='4.73.0',
        stand=date(2026, 11, 14),
        icon='inventory_2',
        requires=('inventory', 'rental'),
        pfade=(
            'inventory/admin.py',
            'inventory/forms.py',
            'inventory/templates/',
            'rental/admin.py',
            'rental/forms.py',
            'rental/views.py',
            'rental/label_layout.py',
            'rental/templates/rental/',
            'rental/static/rental/js/',
            'rental/static/rental/css/',
            'rental/locale/',
        ),
    ),
    Kapitel(
        slug='einstellungen',
        title='Einstellungen für Administratoren',
        summary=(
            'Alle Einstellungen im Browser: Konfigurationsseite, jedes Formular '
            'Feld für Feld, Benachrichtigungen, Stammdaten, periodische Aufgaben '
            'und was nur in der .env eingestellt wird.'
        ),
        version='4.73.0',
        stand=date(2026, 11, 14),
        icon='settings',
        pfade=(
            'ok_tools/admin.py',
            'ok_tools/admin_secrets.py',
            'ok_tools/templates/admin/configuration_index.html',
            'registration/admin.py',
            'rental/admin.py',
            'inventory/admin.py',
            'licenses/admin.py',
            'media_files/admin.py',
            'planung/admin.py',
            'austausch/admin.py',
            'tools/admin.py',
            'notifications/admin.py',
            'notifications/templates/admin/notifications/settings.html',
        ),
    ),
)


def available_chapters():
    """Chapters whose modules are installed here."""
    return [kapitel for kapitel in KAPITEL if kapitel.available()]


def get_chapter(slug: str) -> Optional[Kapitel]:
    """The chapter with this slug, if it exists and is available."""
    return next((k for k in available_chapters() if k.slug == slug), None)
