"""Version of OK-Tools, shown in the admin and used by the manual.

Raise ``VERSION`` together with README.rst and CHANGES.md (see CLAUDE.md).
The commit comes from ``BUILD_COMMIT``, written by deployment/scripts/update.sh
before the image is built (the image has no .git); in development it is read
from the repository itself.
"""

from functools import lru_cache
from pathlib import Path


VERSION = '4.74.0'

BASE_DIR = Path(__file__).resolve().parent.parent


def _git_commit():
    """Short hash of HEAD read from .git without calling git; None if unknown."""
    git = BASE_DIR / '.git'
    try:
        head = (git / 'HEAD').read_text().strip()
        if not head.startswith('ref: '):
            return head[:7]
        ref = head[5:]
        ref_file = git / ref
        if ref_file.exists():
            return ref_file.read_text().strip()[:7]
        for line in (git / 'packed-refs').read_text().splitlines():
            if line.endswith(' ' + ref):
                return line.split(' ', 1)[0][:7]
    except OSError:
        pass
    return None


@lru_cache(maxsize=1)
def commit():
    """Short commit hash of the running code, or '' when unknown."""
    try:
        value = (BASE_DIR / 'BUILD_COMMIT').read_text().strip()
    except OSError:
        value = ''
    return (value or _git_commit() or '')[:7]


def version_tuple(value: str):
    """'4.72.0' -> (4, 72, 0); unknown parts count as 0."""
    parts = []
    for piece in (value or '').split('.')[:3]:
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts + [0] * (3 - len(parts)))
