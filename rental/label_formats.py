"""
The label layouts :class:`~rental.views.BarcodePrintView` can print.

Two of them are fixed: the A4 sheets, whose geometry lives in their own
templates. Every roll size is a :class:`~rental.models.LabelFormat` row, so a
new roll needs nothing but its millimetres entered in the admin.

The barcode geometry and the type sizes are derived from the label width and
height rather than stored per format. The two roll sizes the module started
with — 51 x 25 and 70 x 32 mm — were tuned by hand on the printer, and the
factors below reproduce them, so a size between or beyond them lands on the
same visual proportions instead of needing its own tuning session.
"""

from decimal import Decimal
from typing import Dict
from typing import List
from typing import Optional


ROLL_TEMPLATE = 'rental/barcode_print_roll.html'

# Sheet layouts, printed many-up on A4. They have no physical label size, so
# they can be neither rotated nor sent to a label printer.
SHEET_FORMATS: Dict[str, dict] = {
    'standard': {
        'template': 'rental/barcode_print.html',
        'name': 'A4 sheet',
        'size_label': '50 × 30 mm',
        'writer': {
            'module_width': 0.3,
            'module_height': 12.0,
            'quiet_zone': 2.0,
            'write_text': False,
        },
    },
    'compact': {
        'template': 'rental/barcode_print_compact.html',
        'name': 'A4 sheet, compact',
        'size_label': '40 × 15 mm',
        'writer': {
            'module_width': 0.22,
            'module_height': 7.0,
            'quiet_zone': 1.0,
            'write_text': False,
        },
    },
}
DEFAULT_FORMAT = 'standard'

# Anchors the derived values interpolate between: the two hand tuned formats.
_ANCHOR_NARROW_WIDTH = 51
_ANCHOR_WIDE_WIDTH = 70


def _between(width_mm: int, at_narrow: float, at_wide: float) -> float:
    """Return the value for ``width_mm`` on the line through both anchors.

    Beyond the anchors the line simply continues, which keeps a 100 mm label
    proportional instead of clamping it to the 70 mm look.
    """
    span = _ANCHOR_WIDE_WIDTH - _ANCHOR_NARROW_WIDTH
    slope = (at_wide - at_narrow) / span
    return at_narrow + (width_mm - _ANCHOR_NARROW_WIDTH) * slope


def writer_options(width_mm: int, height_mm: int) -> dict:
    """Return the ``SVGWriter`` options for a label of this size.

    The layout prints the inventory number itself, so ``write_text`` stays
    off and python-barcode does not repeat it under the bars.
    """
    return {
        'module_width': round(_between(width_mm, 0.28, 0.38), 3),
        'module_height': round(max(height_mm * 0.35, 4.0), 1),
        'quiet_zone': round(_between(width_mm, 1.5, 2.0), 2),
        'write_text': False,
    }


def typography(width_mm: int, height_mm: int) -> dict:
    """Return the type sizes and padding the roll stylesheet needs.

    Returned in the units the stylesheet uses: millimetres for the padding,
    points for the font sizes.
    """
    return {
        'pad_mm': round(_between(width_mm, 1.5, 2.0), 2),
        'fs_desc_pt': round(_between(width_mm, 6.0, 7.5), 2),
        'fs_num_pt': round(_between(width_mm, 7.5, 9.0), 2),
        'fs_meta_pt': round(_between(width_mm, 5.5, 6.5), 2),
    }


def _from_row(row) -> dict:
    """Return the layout definition for a ``LabelFormat`` row."""
    return {
        'key': row.slug,
        'template': ROLL_TEMPLATE,
        'name': row.name,
        'size_label': row.size_label,
        'width': row.width_mm,
        'height': row.height_mm,
        'gap_mm': row.gap_mm,
        'writer': writer_options(row.width_mm, row.height_mm),
        'typography': typography(row.width_mm, row.height_mm),
    }


def _from_sheet(key: str) -> dict:
    """Return the layout definition for one of the fixed sheet formats."""
    sheet = dict(SHEET_FORMATS[key])
    sheet.update({'key': key, 'width': None, 'height': None, 'gap_mm': None})
    return sheet


def resolve(key: Optional[str]) -> Optional[dict]:
    """Return the layout for ``key``, or ``None`` when there is no such format.

    Args:
        key: A sheet format key or the slug of a ``LabelFormat`` row.

    Returns:
        The layout definition, or ``None`` for an unknown or inactive format.
    """
    from .models import LabelFormat

    if not key:
        return None
    if key in SHEET_FORMATS:
        return _from_sheet(key)
    row = LabelFormat.objects.filter(slug=key, is_active=True).first()
    return _from_row(row) if row else None


def resolve_or_default(key: Optional[str]) -> dict:
    """Return the layout for ``key``, falling back to the A4 sheet."""
    return resolve(key) or _from_sheet(DEFAULT_FORMAT)


def choices() -> List[dict]:
    """Return every format the print dialog offers, sheets first."""
    from .models import LabelFormat

    formats = [_from_sheet(key) for key in SHEET_FORMATS]
    formats += [
        _from_row(row) for row in LabelFormat.objects.filter(is_active=True)
    ]
    return formats


def gap_for(layout: dict, config) -> Decimal:
    """Return the roll gap to print ``layout`` with.

    A format may carry the gap of its own roll; without one the gap from the
    printer settings applies.
    """
    return layout.get('gap_mm') or config.label_gap_mm
