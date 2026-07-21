"""Fixtures for the inventory tests."""

import pytest


# The `browser` fixture is transactional, so every browser test flushes the
# test database. That also removes the rows created by data migrations, and
# with --reuse-db they never come back. Inventory number validation depends on
# the default series seeded by inventory.0042_seed_inventory_series, so restore
# it for every inventory test instead of depending on the test run order.
DEFAULT_SERIES = {
    'prefix': 'OK-',
    'description': 'Offener Kanal equipment (default series)',
    'padding': 6,
    'active': True,
}


@pytest.fixture(autouse=True)
def default_inventory_series(db):
    """Make sure the seeded default inventory number series exists."""
    from inventory.models import InventorySeries

    series, _ = InventorySeries.objects.get_or_create(
        prefix=DEFAULT_SERIES['prefix'],
        defaults={
            'description': DEFAULT_SERIES['description'],
            'padding': DEFAULT_SERIES['padding'],
            'active': DEFAULT_SERIES['active'],
        },
    )
    return series
