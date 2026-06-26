"""Cover layout templates."""

from media_files.covers.templates.base import BaseCover  # noqa: F401
from media_files.covers.templates.journal import JournalCover  # noqa: F401
from media_files.covers.templates.trailer import TrailerCover  # noqa: F401

# Registry so config / resolver can reference templates by name.
TEMPLATE_REGISTRY = {
    BaseCover.name: BaseCover,
    JournalCover.name: JournalCover,
    TrailerCover.name: TrailerCover,
}


def get_template(name: str):
    """Return a template class by name, defaulting to BaseCover."""
    return TEMPLATE_REGISTRY.get(name, BaseCover)
