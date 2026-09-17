"""
What goes on a label, in which order, and how it is emphasised.

A label is a list of rows; a text row is a list of runs, because one row can
mix sizes — the shelf codes in a location print larger than the words around
them, which is what makes a label readable across a room.

The same rows feed both renderers: the TSPL job for the label printer and the
HTML label templates. Neither decides what a label says; they only know how
to draw a row.

The rows come from the ``LabelLine`` rows of a ``LabelFormat``, so an
installation whose locations look nothing like "Schrank 3 -> Fach 8" can
describe its own label instead of living with this one.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Callable
from typing import List
from typing import Optional
from typing import Sequence
import re


# What a line puts on the label.
CONTENT_NUMBER = 'number'
CONTENT_OWNER = 'owner'
CONTENT_NUMBER_OWNER = 'number_owner'
CONTENT_DESCRIPTION = 'description'
CONTENT_LOCATION = 'location'
CONTENT_BARCODE = 'barcode'

# How large a row prints, as a multiple of the layout's base size.
SIZE_SMALL = 'small'
SIZE_NORMAL = 'normal'
SIZE_LARGE = 'large'
SIZE_SCALE = {SIZE_SMALL: 0.75, SIZE_NORMAL: 1.0, SIZE_LARGE: 1.5}

ALIGN_LEFT = 'left'
ALIGN_CENTER = 'center'
ALIGN_RIGHT = 'right'

LOCATION_SEPARATOR = ' > '

# A location segment usually ends in the code that actually identifies the
# place — "Schrank 3", "Regal 4", "Fach B", "Fach B2". The words in front of
# it are context; the code is what someone reads from two metres away.
#
# A code standing as its own word may be digits with an optional letter
# ("3", "3a"), or one or two letters with optional digits ("B", "AB", "B12").
# Letters only count as a code when they stand apart: glued to a word they
# are just its last letters, and "Seminarraum" must not become "Seminarrau"
# plus a large "m". Digits glued to a word ("Raum12") still count, since no
# word ends in a digit.
_CODE_TOKEN = re.compile(r'^(?:[0-9]{1,3}[A-Za-z]?|[A-Za-z]{1,2}[0-9]{0,3})$')
_GLUED_DIGITS = re.compile(r'^(?P<words>.*\D)(?P<code>[0-9]{1,3}[A-Za-z]?)$')
_SPLIT = re.compile(r'\s*(?:->|→|>)\s*')


def split_code(segment: str):
    """Return the words of a location level and the code ending it.

    Returns:
        ``(words, code)``; ``code`` is empty when the level carries none.
    """
    segment = segment.strip()
    words, _space, last = segment.rpartition(' ')
    if _CODE_TOKEN.match(last):
        return words.strip(), last
    glued = _GLUED_DIGITS.match(segment)
    if glued:
        return glued.group('words').strip(), glued.group('code')
    return segment, ''


@dataclass
class Run:
    """A stretch of text on one row that prints at a single size."""

    text: str
    scale: float = 1.0
    role: str = ''


@dataclass
class Row:
    """One row of a label: either the bars or a line of text."""

    kind: str
    content: str = ''
    align: str = ALIGN_CENTER
    size: str = SIZE_NORMAL
    runs: List[Run] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Return the row's plain text, sizes ignored."""
        return ''.join(run.text for run in self.runs)


@dataclass(frozen=True)
class LineSpec:
    """A label line as configured, independent of the database."""

    content: str
    size: str = SIZE_NORMAL
    align: str = ALIGN_CENTER
    shorten_words: bool = True
    highlight_codes: bool = True
    drop_leading_segments: int = 0


# The layout this module was asked for: what the item is called and who owns
# it read above the bars, the location last and largest where it counts.
DEFAULT_LINES: Sequence[LineSpec] = (
    LineSpec(content=CONTENT_NUMBER_OWNER, size=SIZE_NORMAL),
    LineSpec(content=CONTENT_BARCODE),
    LineSpec(content=CONTENT_DESCRIPTION, size=SIZE_NORMAL),
    LineSpec(content=CONTENT_LOCATION, size=SIZE_SMALL),
)


def shorten_word(word: str) -> str:
    """Return a word short enough for a label, without losing what it means.

    Only words long enough to be worth shortening are touched, and the result
    keeps the beginning, which is what a reader recognises: "Schrank" becomes
    "Schr.", "Stativschrank" becomes "Stat.".
    """
    word = word.strip()
    if len(word) <= 5:
        return word
    return word[:4] + '.'


def location_runs(
    location: str,
    *,
    shorten_words: bool = True,
    highlight_codes: bool = True,
    fits: Optional[Callable[[Sequence[Run]], bool]] = None,
    drop_leading: int = 0,
) -> List[Run]:
    """Return the runs a location path prints as.

    The path is shortened only as far as it has to be: first the full text,
    then with the words abbreviated, then dropping segments from the front,
    which are the ones a reader already knows — the building before the room.

    Args:
        location: The path, its levels separated by ``->``, ``→`` or ``>``.
        shorten_words: Whether abbreviating the words is allowed at all.
        highlight_codes: Whether the shelf codes print larger than the words.
        fits: Tells whether a candidate still fits on the row. Without it the
            full text is returned and the renderer clips it.
        drop_leading: Segments to drop from the front before anything else.

    Returns:
        The runs, in reading order.
    """
    segments = [part for part in _SPLIT.split(location.strip()) if part]
    segments = segments[drop_leading:] or segments[-1:]

    def build(parts: Sequence[str], short: bool) -> List[Run]:
        runs: List[Run] = []
        for index, segment in enumerate(parts):
            if index:
                runs.append(Run(LOCATION_SEPARATOR))
            words, code = split_code(segment)
            if not code or not highlight_codes:
                words = segment
                if short:
                    words = ' '.join(
                        shorten_word(word) for word in segment.split())
                runs.append(Run(words))
                continue
            if short:
                words = ' '.join(shorten_word(word) for word in words.split())
            if words:
                runs.append(Run(words + ' '))
            runs.append(Run(code, scale=1.5, role='code'))
        return runs

    candidates = [build(segments, False)]
    if shorten_words:
        candidates.append(build(segments, True))
    for drop in range(1, len(segments)):
        rest = segments[drop:]
        candidates.append(build(rest, shorten_words))
    if fits is None:
        return candidates[0]
    for candidate in candidates:
        if fits(candidate):
            return candidate
    return candidates[-1]


def build_rows(
    item: dict,
    lines: Sequence[LineSpec],
    *,
    fits: Optional[Callable[[Row], bool]] = None,
) -> List[Row]:
    """Return the rows a label prints, dropping the ones with nothing to say.

    Args:
        item: Mapping with ``inventory_number`` and the optional keys
            ``description``, ``owner`` and ``location``.
        lines: The configured lines, in order.
        fits: Tells whether a row still fits, used to decide how far a
            location has to be shortened. Without it nothing is shortened.

    Returns:
        The rows, in printing order.
    """
    number = str(item.get('inventory_number') or '').strip()
    owner = str(item.get('owner') or '').strip()
    description = str(item.get('description') or '').strip()
    location = str(item.get('location') or '').strip()
    if description == number:
        description = ''

    rows: List[Row] = []
    for line in lines:
        if line.content == CONTENT_BARCODE:
            if number:
                rows.append(Row(kind='barcode', content=CONTENT_BARCODE))
            continue

        runs: List[Run] = []
        if line.content == CONTENT_NUMBER and number:
            runs = [Run(number, role='number')]
        elif line.content == CONTENT_OWNER and owner:
            runs = [Run(owner, role='owner')]
        elif line.content == CONTENT_NUMBER_OWNER and (number or owner):
            runs = [Run(number, role='number')]
            if owner:
                runs += [Run('  '), Run(owner, role='owner')]
        elif line.content == CONTENT_DESCRIPTION and description:
            runs = [Run(description, role='description')]
        elif line.content == CONTENT_LOCATION and location:
            row = Row(kind='text', content=line.content, align=line.align,
                      size=line.size)

            def row_fits(candidate: Sequence[Run], row=row) -> bool:
                row.runs = list(candidate)
                return fits(row) if fits else True

            runs = location_runs(
                location,
                shorten_words=line.shorten_words,
                highlight_codes=line.highlight_codes,
                fits=row_fits if fits else None,
                drop_leading=line.drop_leading_segments,
            )

        if not runs:
            continue
        for run in runs:
            if not run.role:
                run.role = line.content
        rows.append(Row(kind='text', content=line.content, align=line.align,
                        size=line.size, runs=runs))
    return rows


def lines_for(label_format: Optional[dict]) -> Sequence[LineSpec]:
    """Return the configured lines of a format, or the default layout."""
    if label_format:
        lines = label_format.get('lines')
        if lines:
            return lines
    return DEFAULT_LINES
