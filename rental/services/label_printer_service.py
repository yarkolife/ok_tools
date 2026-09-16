"""
Direct label printing on a network label printer speaking TSPL.

Printing labels through the browser means every workstation needs the media
size, the margins and the orientation set up in its own print dialog, and a
wrong setting there spreads one label over two. A TSPL printer instead takes
the label geometry inside the job: ``SIZE`` and ``GAP`` describe the roll,
so the same job prints identically from any machine.

The layout mirrors ``rental/barcode_print_roll.html``: description and owner
on the top line, the Code 128 barcode below, the inventory number under the
bars and the location at the bottom.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from typing import List
import socket


DOTS_PER_INCH_DEFAULT = 203
MM_PER_INCH = Decimal('25.4')
SOCKET_TIMEOUT_SECONDS = 5

# Cell sizes of the printer's internal bitmap fonts, in dots at 203 dpi.
# Only the two the layout uses are listed.
_FONT_SMALL = '1'
_FONT_NORMAL = '2'
_FONT_CELL = {_FONT_SMALL: (8, 12), _FONT_NORMAL: (12, 20)}

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
        )


def _escape(text: str) -> str:
    """Return ``text`` safe to place inside a quoted TSPL string."""
    for raw, escaped in _ESCAPES:
        text = text.replace(raw, escaped)
    return text


def _fit(text: str, font: str, width_dots: int, scale: int = 1) -> str:
    """Return ``text`` cut to what fits into ``width_dots``.

    The internal fonts are fixed width, so the number of characters that fit
    is simply the available width divided by the cell width. TSPL neither
    wraps nor shortens by itself; an overlong description would print over
    the label edge and, on the last line, over the next label.
    """
    cell_width = _FONT_CELL[font][0] * scale
    limit = max(width_dots // cell_width, 0)
    return text[:limit]


def _text_width(text: str, font: str, scale: int = 1) -> int:
    """Return the width ``text`` occupies in dots."""
    return len(text) * _FONT_CELL[font][0] * scale


class LabelPrinterService:
    """Render inventory labels as TSPL and send them to the printer."""

    @staticmethod
    def build_label(
        item: dict,
        width_mm: int,
        height_mm: int,
        settings: PrinterSettings,
    ) -> str:
        """Return the TSPL job for one label.

        Args:
            item: Mapping with ``inventory_number`` and the optional keys
                ``description``, ``owner`` and ``location``.
            width_mm: Label width in millimetres.
            height_mm: Label height in millimetres.
            settings: Printer and media settings.

        Returns:
            The TSPL commands for a single label, newline separated.
        """
        dots_per_mm = Decimal(settings.dpi) / MM_PER_INCH
        width_dots = int(Decimal(width_mm) * dots_per_mm)
        height_dots = int(Decimal(height_mm) * dots_per_mm)
        margin = int(Decimal('2') * dots_per_mm)
        inner = width_dots - 2 * margin

        number = str(item.get('inventory_number') or '').strip()
        description = str(item.get('description') or '').strip()
        owner = str(item.get('owner') or '').strip()
        location = str(item.get('location') or '').strip()
        if description == number:
            description = ''

        lines = [
            f'SIZE {width_mm} mm,{height_mm} mm',
            f'GAP {settings.gap_mm} mm,0 mm',
            f'DENSITY {settings.density}',
            f'SPEED {settings.speed}',
            'DIRECTION 1',
            'CLS',
        ]

        # The rows of the label, top to bottom, and how tall each one is.
        # The bars take 40% of the label; the rest of the height is shared
        # out evenly, so a label without a location is not top heavy.
        head_height = _FONT_CELL[_FONT_NORMAL][1]
        number_height = _FONT_CELL[_FONT_NORMAL][1]
        location_height = _FONT_CELL[_FONT_SMALL][1]
        bar_height = int(Decimal(height_mm) * dots_per_mm * Decimal('0.4'))
        has_head = bool(description or owner)
        rows = [
            head_height if has_head else 0,
            bar_height,
            number_height,
            location_height if location else 0,
        ]
        present = [row for row in rows if row]
        spacing = max((height_dots - sum(present)) // (len(present) + 1), 2)

        y = spacing
        if has_head:
            # The owner keeps its full width on the right, the description
            # gets whatever is left of it.
            owner_width = _text_width(owner, _FONT_NORMAL) if owner else 0
            if owner:
                owner_x = margin + inner - owner_width
                lines.append(
                    f'TEXT {owner_x},{y},"{_FONT_NORMAL}",0,1,1,'
                    f'"{_escape(owner)}"')
            if description:
                room = inner - owner_width - (8 if owner else 0)
                text = _fit(description, _FONT_NORMAL, room)
                if text:
                    lines.append(
                        f'TEXT {margin},{y},"{_FONT_NORMAL}",0,1,1,'
                        f'"{_escape(text)}"')
            y += head_height + spacing

        # The bars are centred; a narrow bar of 2 dots keeps a ten character
        # number well inside a 51 mm label and stays readable for a scanner.
        narrow = 2
        bar_width = LabelPrinterService._code128_width(number, narrow)
        bar_x = margin + max((inner - bar_width) // 2, 0)
        lines.append(
            f'BARCODE {bar_x},{y},"128",{bar_height},0,0,{narrow},'
            f'{narrow * 2},"{_escape(number)}"')
        y += bar_height + spacing

        number_x = margin + max(
            (inner - _text_width(number, _FONT_NORMAL)) // 2, 0)
        lines.append(
            f'TEXT {number_x},{y},"{_FONT_NORMAL}",0,1,1,'
            f'"{_escape(number)}"')
        y += number_height + spacing

        if location:
            text = _fit(location, _FONT_SMALL, inner)
            location_x = margin + max(
                (inner - _text_width(text, _FONT_SMALL)) // 2, 0)
            lines.append(
                f'TEXT {location_x},{y},"{_FONT_SMALL}",0,1,1,'
                f'"{_escape(text)}"')

        lines.append('PRINT 1,1')
        return '\n'.join(lines) + '\n'

    @staticmethod
    def build_job(
        items: Iterable[dict],
        width_mm: int,
        height_mm: int,
        settings: PrinterSettings,
    ) -> bytes:
        """Return the TSPL job for all ``items``, ready to be sent.

        The printer's own character set is selected explicitly, so German
        umlauts in a description arrive as the printer expects them; a
        character outside it is replaced instead of failing the job.
        """
        labels: List[str] = [
            LabelPrinterService.build_label(item, width_mm, height_mm, settings)
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
    ) -> int:
        """Build and send the labels, returning how many were sent."""
        items = list(items)
        if not items:
            return 0
        payload = LabelPrinterService.build_job(
            items, width_mm, height_mm, settings)
        LabelPrinterService.send(payload, settings)
        return len(items)

    @staticmethod
    def _code128_width(value: str, narrow: int) -> int:
        """Return the printed width of a Code 128 barcode in dots.

        Every symbol is 11 modules wide, plus the 13 module stop pattern, and
        the printer adds start and check symbols to the payload. Subset B is
        assumed, which is what the printer picks for mixed content.
        """
        symbols = len(value) + 2
        return (symbols * 11 + 13) * narrow
