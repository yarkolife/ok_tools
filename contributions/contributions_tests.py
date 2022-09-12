from datetime import datetime
from django.conf import settings
from django.urls import reverse_lazy
from ok_tools.testing import DOMAIN
from ok_tools.testing import create_contribution
from zoneinfo import ZoneInfo


def con_change_url(id: int) -> str:
    """Create the change url for the given id."""
    url = reverse_lazy("admin:contributions_contribution_change", args=[id])
    return (f'{DOMAIN}'f'{url}')


def test__contributions__admin__ContributionsAdmin__1(browser, contribution):
    """Contributions get shown in the admin interface."""
    browser.login_admin()
    browser.follow(url="/admin/contributions/contribution")

    assert str(contribution) in browser.contents
    assert contribution.license.profile.first_name in browser.contents
    assert contribution.license.profile.last_name in browser.contents


def test__contributions__admin__ContributionsAdmin__2(
        db, license_request, contribution_dict, browser):
    """Show primary contributions as those."""
    contribution_dict['broadcast_date'] = datetime(
        year=2022,
        month=9,
        day=12,
        hour=8,
        tzinfo=ZoneInfo(settings.TIME_ZONE),
    )
    early_contr = create_contribution(license_request, contribution_dict)

    contribution_dict['broadcast_date'] = datetime(
        year=2022,
        month=9,
        day=12,
        hour=18,
        tzinfo=ZoneInfo(settings.TIME_ZONE),
    )
    late_contr = create_contribution(license_request, contribution_dict)

    browser.login_admin()

    browser.open(con_change_url(early_contr.id))
    assert 'alt="True"' in browser.contents

    browser.open(con_change_url(late_contr.id))
    assert 'alt="False"' in browser.contents


def test__contributions__models__1(db, license_request, contribution_dict):
    """Mark the primary contribution."""
    contribution_dict['broadcast_date'] = datetime(
        year=2022,
        month=9,
        day=12,
        hour=8,
        tzinfo=ZoneInfo(settings.TIME_ZONE),
    )
    early_contr = create_contribution(license_request, contribution_dict)

    contribution_dict['broadcast_date'] = datetime(
        year=2022,
        month=9,
        day=12,
        hour=18,
        tzinfo=ZoneInfo(settings.TIME_ZONE),
    )
    late_contr = create_contribution(license_request, contribution_dict)

    assert early_contr.is_primary()
    assert not late_contr.is_primary()
