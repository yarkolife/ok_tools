"""
Direct label printing on a network label printer speaking TSPL.

Printing labels through the browser means every workstation needs the media
size, the margins and the orientation set up in its own print dialog, and a
wrong setting there spreads one label over two. A TSPL printer instead takes
the label geometry inside the job: ``SIZE`` and ``GAP`` describe the roll,
so the same job prints identically from any machine.

What the label says is decided in :mod:`rental.label_layout` and shared with
the HTML templates; this module only knows how to draw a row with the
printer's own fonts.
"""

from __future__ import annotations

from ..label_layout import ALIGN_LEFT
from ..label_layout import ALIGN_RIGHT
from ..label_layout import DEFAULT_LINES
from ..label_layout import LineSpec
from ..label_layout import Run
from ..label_layout import SIZE_LARGE
from ..label_layout import SIZE_SCALE
from ..label_layout import SIZE_SMALL
from ..label_layout import build_rows
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from typing import List
from typing import Optional
from typing import Sequence
import socket


DOTS_PER_INCH_DEFAULT = 203
MM_PER_INCH = Decimal('25.4')
SOCKET_TIMEOUT_SECONDS = 5

# The printer's internal bitmap fonts, in dots at 203 dpi: the nominal cell
# the characters are drawn in, and how far a character actually advances,
# measured on a TE210. The advance is the wider of the two and is what the
# layout has to reserve.
_FONT_SMALL = '1'
_FONT_NORMAL = '2'
_FONT_CELL = {_FONT_SMALL: (8, 12), _FONT_NORMAL: (12, 20)}
_FONT_ADVANCE = {_FONT_SMALL: 11, _FONT_NORMAL: 16}

# TSPL takes its strings in double quotes, with a backslash escape inside.
_ESCAPES = (('\\', '\\\\'), ('"', '\\"'))


class LabelPrinterError(Exception):
    """Raised when a label job cannot be delivered to the printer."""


@dataclass(frozen=True)
class PrinterSettings:
    """Everything a job needs to know about the printer and its media."""

    host: str
    port: int = 9100
    dpi: int = DOTS_PER_INCH_DEFAULT
    gap_mm: Decimal = Decimal('2.0')
    density: int = 8
    speed: int = 4
    offset_x_mm: Decimal = Decimal('0.0')
    offset_y_mm: Decimal = Decimal('0.0')

    @classmethod
    def from_config(cls, config) -> 'PrinterSettings':
        """Build the settings from a ``RentalConfig`` instance."""
        return cls(
            host=config.label_printer_host.strip(),
            port=config.label_printer_port,
            dpi=config.label_printer_dpi,
            gap_mm=config.label_gap_mm,
            density=config.label_printer_density,
            speed=config.label_printer_speed,
            offset_x_mm=config.label_offset_x_mm,
            offset_y_mm=config.label_offset_y_mm,
        )


def _escape(text: str) -> str:
    """Return ``text`` safe to place inside a quoted TSPL string."""
    for raw, escaped in _ESCAPES:
        text = text.replace(raw, escaped)
    return text


def row_number(item: dict) -> str:
    """Return the inventory number the bars encode."""
    return str(item.get('inventory_number') or '').strip()


def _advance(font: str, scale: float) -> int:
    """Return how far one character of ``font`` moves the cursor, in dots.

    The nominal cell of the printer's internal fonts is narrower than what
    they actually advance: measured on a TE210, a line of font 2 runs about a
    third wider than 12 dots per character would suggest. Estimating a
    character as too narrow is what makes two columns collide, so the
    measured advance is used and rounded up.
    """
    return int(round(_FONT_ADVANCE[font] * scale))


def _base_font(size: str) -> str:
    """Return the printer font a row of this size prints in."""
    return _FONT_SMALL if size == SIZE_SMALL else _FONT_NORMAL


def _run_font(row, run):
    """Return the font and whole-number multiplier a run prints at.

    The printer scales its bitmap fonts in whole steps, so a run that asks to
    stand out — a shelf code among the words of a location — moves up to the
    next font, or to double size when it is already on the larger one. That
    is what makes the codes readable from across the room while the words
    beside them stay out of the way.
    """
    font = _base_font(row.size)
    scale = 2 if row.size == SIZE_LARGE else 1
    if run.scale > 1.0:
        if font == _FONT_SMALL:
            font = _FONT_NORMAL
        else:
            scale *= 2
    return font, scale


def _run_width(row, run) -> int:
    """Return the width of a run in dots."""
    font, scale = _run_font(row, run)
    return len(run.text) * _advance(font, scale)


def _run_height(row, run) -> int:
    """Return the height of a run in dots."""
    font, scale = _run_font(row, run)
    return _FONT_CELL[font][1] * scale


def _row_width(row) -> int:
    """Return the width of a whole text row in dots."""
    return sum(_run_width(row, run) for run in row.runs)


def _row_height(row) -> int:
    """Return the height of a text row in dots, its tallest run deciding."""
    default = _FONT_CELL[_base_font(row.size)][1]
    return max((_run_height(row, run) for run in row.runs), default=default)


def _row_commands(row, margin: int, inner: int, y: int, height: int) -> list:
    """Return the TSPL for one text row, clipped to the label.

    Runs of different size share a baseline, so a small word does not float
    above the larger code standing next to it.
    """
    runs, width = _clip(row, inner)
    if row.align == ALIGN_RIGHT:
        x = margin + max(inner - width, 0)
    elif row.align == ALIGN_LEFT:
        x = margin
    else:
        x = margin + max((inner - width) // 2, 0)

    commands = []
    for run in runs:
        run_width = _run_width(row, run)
        if run.text.strip():
            font, scale = _run_font(row, run)
            baseline = y + height - _run_height(row, run)
            commands.append(
                f'TEXT {x},{baseline},"{font}",0,{scale},{scale},'
                f'"{_escape(run.text)}"')
        x += run_width
    return commands


def _clip(row, inner: int):
    """Return the runs of ``row`` cut to ``inner`` dots, and their width.

    TSPL neither wraps nor shortens by itself, so a row that is still too
    long after the layout did what it could is cut here; otherwise it would
    print over the label edge and, on the last row, over the next label.
    """
    kept, width = [], 0
    for run in row.runs:
        run_width = _run_width(row, run)
        if width + run_width <= inner:
            kept.append(run)
            width += run_width
            continue
        per_char = max(_run_width(row, Run('x', scale=run.scale)), 1)
        room = max((inner - width) // per_char, 0)
        text = run.text[:room].rstrip()
        if text:
            cut = Run(text, scale=run.scale, role=run.role)
            kept.append(cut)
            width += _run_width(row, cut)
        break
    return kept, width


class LabelPrinterService:
    """Render inventory labels as TSPL and send them to the printer."""

    @staticmethod
    def build_label(
        item: dict,
        width_mm: int,
        height_mm: int,
        settings: PrinterSettings,
        lines: Optional[Sequence[LineSpec]] = None,
    ) -> str:
        """Return the TSPL job for one label.

        Args:
            item: Mapping with ``inventory_number`` and the optional keys
                ``description``, ``owner`` and ``location``.
            width_mm: Label width in millimetres.
            height_mm: Label height in millimetres.
            settings: Printer and media settings.
            lines: The label's configured lines; the default layout is used
                when none are given.

        Returns:
            The TSPL commands for a single label, newline separated.
        """
        dots_per_mm = Decimal(settings.dpi) / MM_PER_INCH
        width_dots = int(Decimal(width_mm) * dots_per_mm)
        height_dots = int(Decimal(height_mm) * dots_per_mm)
        # The offsets trim the usable area rather than displacing the finished
        # layout, so moving the content away from one edge can never push it
        # over the opposite one.
        offset_x = int(settings.offset_x_mm * dots_per_mm)
        offset_y = int(settings.offset_y_mm * dots_per_mm)
        edge = int(Decimal('2') * dots_per_mm)
        margin = edge + max(offset_x, 0)
        inner = width_dots - margin - edge

        commands = [
            f'SIZE {width_mm} mm,{height_mm} mm',
            f'GAP {settings.gap_mm} mm,0 mm',
            f'DENSITY {settings.density}',
            f'SPEED {settings.speed}',
            'DIRECTION 1',
            'CLS',
        ]

        rows = build_rows(
            item,
            lines or DEFAULT_LINES,
            fits=lambda row: _row_width(row) <= inner,
        )
        if not rows:
            commands.append('PRINT 1,1')
            return '\n'.join(commands) + '\n'

        # The bars take 40% of the label; what is left of the height is
        # shared out evenly, so a label missing a line is not top heavy.
        bar_height = int(Decimal(height_mm) * dots_per_mm * Decimal('0.4'))
        heights = [
            bar_height if row.kind == 'barcode' else _row_height(row)
            for row in rows
        ]
        usable = height_dots - offset_y
        spacing = max((usable - sum(heights)) // (len(heights) + 1), 2)

        y = offset_y + spacing
        for row, height in zip(rows, heights):
            if row.kind == 'barcode':
                number = row_number(item)
                narrow = LabelPrinterService._narrow_bar(number, inner)
                bar_width = LabelPrinterService._code128_width(number, narrow)
                bar_x = margin + max((inner - bar_width) // 2, 0)
                commands.append(
                    f'BARCODE {bar_x},{y},"128",{height},0,0,{narrow},'
                    f'{narrow * 2},"{_escape(number)}"')
            else:
                commands.extend(
                    _row_commands(row, margin, inner, y, height))
            y += height + spacing

        commands.append('PRINT 1,1')
        return '\n'.join(commands) + '\n'

    @staticmethod
    def build_job(
        items: Iterable[dict],
        width_mm: int,
        height_mm: int,
        settings: PrinterSettings,
        lines: Optional[Sequence[LineSpec]] = None,
    ) -> bytes:
        """Return the TSPL job for all ``items``, ready to be sent.

        The printer's own character set is selected explicitly, so German
        umlauts in a description arrive as the printer expects them; a
        character outside it is replaced instead of failing the job.
        """
        labels: List[str] = [
            LabelPrinterService.build_label(
                item, width_mm, height_mm, settings, lines)
            for item in items
        ]
        job = 'CODEPAGE 1252\n' + ''.join(labels)
        return job.encode('cp1252', errors='replace')

    @staticmethod
    def send(payload: bytes, settings: PrinterSettings) -> None:
        """Send a prepared job to the printer over a raw socket.

        Raises:
            LabelPrinterError: If the printer cannot be reached or the job
                cannot be written.
        """
        if not settings.host:
            raise LabelPrinterError('No label printer configured.')
        try:
            with socket.create_connection(
                (settings.host, settings.port),
                timeout=SOCKET_TIMEOUT_SECONDS,
            ) as connection:
                connection.sendall(payload)
        except OSError as error:
            raise LabelPrinterError(
                f'{settings.host}:{settings.port} — {error}') from error

    @staticmethod
    def print_items(
        items: Iterable[dict],
        width_mm: int,
        height_mm: int,
        settings: PrinterSettings,
        lines: Optional[Sequence[LineSpec]] = None,
    ) -> int:
        """Build and send the labels, returning how many were sent."""
        items = list(items)
        if not items:
            return 0
        payload = LabelPrinterService.build_job(
            items, width_mm, height_mm, settings, lines)
        LabelPrinterService.send(payload, settings)
        return len(items)

    @staticmethod
    def _narrow_bar(value: str, available_dots: int) -> int:
        """Return the widest narrow bar of ``value`` that fits the label.

        Kept between 1 and 4 dots: below 1 there is nothing to print, and
        past 4 the bars only eat the space the text needs.
        """
        modules = LabelPrinterService._code128_width(value, 1)
        if modules <= 0:
            return 1
        return max(min(available_dots // modules, 4), 1)

    @staticmethod
    def _code128_width(value: str, narrow: int) -> int:
        """Return the printed width of a Code 128 barcode in dots.

        Every symbol is 11 modules wide, plus the 13 module stop pattern, and
        the printer adds start and check symbols to the payload. Subset B is
        assumed, which is what the printer picks for mixed content.
        """
        symbols = len(value) + 2
        return (symbols * 11 + 13) * narrow
