from datetime import datetime
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from ok_tools.testing import DOMAIN
from ok_tools.testing import EMAIL
from ok_tools.testing import PWD
from ok_tools.testing import create_contribution
from ok_tools.testing import create_user


User = get_user_model()

CONTRIBUTION_URL = f'{DOMAIN}{reverse_lazy("contributions:contributions")}'


def test__contributions__admin__ContributionsAdmin__1(browser, contribution):
    """Contributions get shown in the admin interface."""
    browser.login_admin()
    browser.follow(url="/admin/contributions/contribution")

    assert str(contribution) in browser.contents
    assert contribution.license.profile.first_name in browser.contents
    assert contribution.license.profile.last_name in browser.contents


def test__contributions__view__ListContributionsView__1(
        browser, contribution_dict, license_request):
    """A user can see his/her contributions."""
    con1 = create_contribution(license_request, contribution_dict)

    contribution_dict['broadcast_date'] = datetime(
        year=2022, month=9, day=12, hour=12)
    con2 = create_contribution(license_request, contribution_dict)

    browser.login()
    browser.open(CONTRIBUTION_URL)

    assert str(con1) in browser.contents
    assert str(con2) in browser.contents


def test__contributions__view__ListContributionsView__2(browser):
    """If the user doesn't have a profile, no contribution is shown."""
    User.objects.create_user(email=EMAIL, password=PWD)
    browser.login()
    browser.open(CONTRIBUTION_URL)

    assert 'No contributions yet' in browser.contents


def test__contributions__view__ListContributionsView__3(
        browser, contribution, user_dict):
    """Only the own contributions are shown to the user."""
    user_dict['email'] = f'new_{EMAIL}'
    user2 = create_user(user_dict)

    browser.login(email=user2.email)
    browser.open(CONTRIBUTION_URL)

    assert str(contribution) not in browser.contents
    assert 'No contributions yet' in browser.contents
