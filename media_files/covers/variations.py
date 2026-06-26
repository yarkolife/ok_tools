"""Deterministic per-video variation.

Neighboring covers should look different, but the cover for one video must be
stable across regenerations. We derive a stable seed from the license number
so the same number always picks the same variation.
"""

import hashlib


def _seed(number) -> int:
    """Return a stable non-negative integer seed for a number/key."""
    digest = hashlib.md5(str(number).encode('utf-8')).hexdigest()
    return int(digest[:8], 16)


def variant_index(number, count: int) -> int:
    """Pick a stable index in ``range(count)`` for the given number."""
    if count <= 1:
        return 0
    return _seed(number) % count


def pick(number, choices):
    """Pick a stable element from ``choices`` for the given number."""
    if not choices:
        return None
    return choices[variant_index(number, len(choices))]
