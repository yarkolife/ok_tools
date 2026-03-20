from .admin import LicenseAdmin
from .admin import WithoutContributionFilter
from .admin import YearFilter
from .tasks import send_license_notification_email
from .models import License
from .models import YouthProtectionCategory
from .models import default_category
from contributions.models import Contribution
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from ok_tools.datetime import TZ
from ok_tools.testing import DOMAIN
from ok_tools.testing import EMAIL
from ok_tools.testing import PWD
from ok_tools.testing import create_contribution
from ok_tools.testing import create_license
from ok_tools.testing import create_user
from ok_tools.testing import pdfToText
from planung.models import TagesPlan
from registration.models import OrganizationConfig
from registration.models import Profile
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from unittest.mock import patch
from django.test import override_settings
from django.utils import timezone
from django.utils import translation
from urllib.error import HTTPError
import datetime
import pytest


User = get_user_model()

HOME_URL = f'{DOMAIN}{reverse_lazy("home")}'
LIST_URL = f'{DOMAIN}{reverse_lazy("licenses:licenses")}'
CREATE_URL = f'{DOMAIN}{reverse_lazy("licenses:create")}'
LOGIN_URL = f'{DOMAIN}{reverse_lazy("login")}'
A_LICENSE_URL = (f'{DOMAIN}'
                 f'{reverse_lazy("admin:licenses_license_changelist")}')


def details_url(id):
    """Return details url."""
    return f'{DOMAIN}{reverse_lazy("licenses:details", args=[id])}'


def edit_url(id):
    """Return edit url."""
    return f'{DOMAIN}{reverse_lazy("licenses:update", args=[id])}'


def print_url(id):
    """Return print url."""
    return f'{DOMAIN}{reverse_lazy("licenses:print", args=[id])}'


def test__licenses__views__ListLicensesView__1(browser, user):
    """A logged in user can access his/her licenses overview."""
    browser.login()
    browser.open(HOME_URL)
    browser.follow('Licenses')
    browser.follow('Overview')

    assert LIST_URL == browser.url
    assert 'Your licenses' in browser.contents


def test__licenses__views__ListLicensesView__2(browser):
    """If no user is logged in the license overview returns a 404."""
    with pytest.raises(HTTPError, match=r'.*404.*'):
        browser.open(LIST_URL)


def test__licenses__views__ListLicensesView__3(db, browser, license):
    """All licenses of the user are listed."""
    browser.login()
    browser.open(LIST_URL)

    assert str(license) in browser.contents
    assert 'No' in browser.contents  # the License is not confirmed


def test__licenses__views__ListLicensesView__4(browser, license):
    """If a LR is confirmed, it is shown in the overview."""
    license.confirmed = True
    license.save()
    browser.login()
    browser.open(LIST_URL)

    assert str(license) in browser.contents
    assert 'Yes' in browser.contents  # the License is confirmed


def test__licenses__views__ListLicensesView__5(browser, user, license):
    """It is possible to edit a license from the list view."""
    browser.login()
    browser.open(LIST_URL)
    browser.follow(id=f'id_edit_{license.id}')

    assert browser.url == edit_url(license.id)


def test__licenses__views__ListLicensesView__6(browser, user, license):
    """It is possible to print a license from the list view."""
    browser.login()
    browser.open(LIST_URL)
    browser.follow(id=f'id_print_{license.id}')

    assert browser.url == print_url(license.id)


def test__licenses__views__ListLicensesView__7(browser):
    """A user without a profile can not see any LRs."""
    User.objects.create_user(email=EMAIL, password=PWD)
    browser.login()
    browser.open(LIST_URL)

    assert 'No licenses yet.' in browser.contents


def test__licenses__views__DetailsLicensesView__1(browser, license):
    """If no user is logged in the details view returns a 404."""
    with pytest.raises(HTTPError, match=r'.*404.*'):
        browser.open(details_url(license.id))


def test__licenses__views__DetailsLicensesView__2(browser, license):
    """The details view can be reached using the Overview."""
    browser.login()
    browser.open(LIST_URL)
    browser.follow(str(license))

    assert f'Details for {str(license)}' in browser.contents
    assert license.description in browser.contents


def test__licenses__views__DetailsLicensesView__3(browser, license):
    """It is possible to edit a LR over the details view."""
    browser.login()
    browser.open(details_url(license.id))
    browser.follow(id='id_edit_LR')

    assert f'Edit {license}:' in browser.contents


def test__licenses__views__UpdateLicensesView__1(browser, license):
    """The Description can be changed using the edit site."""
    browser.login()
    browser.open(edit_url(license.id))

    new_description = "This is the new description."
    browser.getControl('Description').value = new_description
    browser.getControl('Save').click()

    assert License.objects.get(description=new_description)
    assert browser.url == LIST_URL
    assert 'successfully edited.' in browser.contents


def test__licenses__views__UpdateLicensesView__2(browser, license):
    """It is not possible to edit a confirmed LR."""
    license.confirmed = True
    license.save()

    browser.login()
    browser.open(edit_url(license.id))

    assert 'Your License is already confirmed and no longer editable.'\
        in browser.contents


def test__licenses__views__UpdateLicensesView__3(browser, license):
    """Even if the form is still available, a confirmed LR is not editable."""
    browser.login()
    browser.open(edit_url(license.id))

    license.confirmed = True
    license.save()

    old_description = license.description
    browser.getControl('Description').value = "This is the new description."
    browser.getControl('Save').click()

    assert 'is already confirmed and therefor no longer editable.'\
        in browser.contents
    lr = License.objects.get(id=license.id)
    assert lr.description == old_description


def test__licenses__views__UpdateLicensesView__4(browser, license):
    """After a license was changed to a screen board, the duration is fixed."""
    browser.login()
    browser.open(edit_url(license.id))

    browser.getControl('Screen Board').click()
    browser.getControl('Save').click()

    assert (License.objects.get(id=license.id).duration ==
            datetime.timedelta(seconds=settings.SCREEN_BOARD_DURATION))  # Using settings for backward compatibility in tests


def test__licenses__views__CreateLicenseView__1(browser, user):
    """A logged in user can access the create site."""
    browser.login()
    browser.open(HOME_URL)
    open('response.html', 'w').write(browser.contents)
    browser.follow('Create license')

    assert CREATE_URL == browser.url
    assert 'Create a license' in browser.contents


def test__licenses__views__CreateLicenseView__2(browser):
    """If no user is logged in the create site returns a 404."""
    with pytest.raises(HTTPError, match=r'.*404.*'):
        browser.open(CREATE_URL)


def test__licenses__views__CreateLicenseView__3(browser, user):
    """A user can create a license."""
    browser.login()
    title = 'Test License'

    browser.open(CREATE_URL)
    browser.getControl('Title').value = title
    browser.getControl('Description').value = 'This is a Test.'
    browser.getControl('Duration').value = '00:00:10'
    browser.getControl('Save').click()

    assert LIST_URL == browser.url
    assert 'Your licenses' in browser.contents
    assert 'successfully created' in browser.contents
    assert License.objects.get(title=title)


def test__licenses__views__CreateLicenseView__4(browser, user):
    """A license needs a Title."""
    browser.login()
    browser.open(CREATE_URL)
    browser.getControl('Description').value = 'This is a Test.'
    browser.getControl('Duration').value = '00:00:10'
    browser.getControl('Save').click()

    assert CREATE_URL == browser.url
    assert 'This field is required' in browser.contents
    assert not License.objects.filter()


def test__licenses__views__CreateLicenseView__5(
        db, browser, user, license_dict):
    """A license representing a Screen Board has a fixed duration."""
    browser.login()
    browser.open(CREATE_URL)
    browser.getControl('Title').value = license_dict['title']
    browser.getControl(
        'Description').value = license_dict['description']
    browser.getControl('Screen Board').click()
    browser.getControl('Save').click()

    assert (lr := License.objects.get(
        title=license_dict['title']))
    assert lr.duration == datetime.timedelta(
        seconds=settings.SCREEN_BOARD_DURATION)


def test__licenses__views__CreateLicenseView__6(browser):
    """It is not possible to create a LR without a Profile."""
    User.objects.create_user(email=EMAIL, password=PWD)
    browser.login()
    browser.open(CREATE_URL)
    assert 'There is no profile' in browser.contents


def test__licenses__forms__CreateLicenseForm__1(
        browser, user, license_dict):
    """A LR needs a duration or needs to be a Screen Board."""
    browser.login()
    browser.open(CREATE_URL)
    browser.getControl('Title').value = license_dict['title']
    browser.getControl(
        'Description').value = license_dict['description']
    browser.getControl('Save').click()

    assert 'The duration field is required.' in browser.contents
    assert not License.objects.filter()


def test__licenses__forms__CreateLicenseForm__2(
        browser, user, license_dict):
    """The duration field gets validated."""
    browser.login()
    browser.open(CREATE_URL)
    browser.getControl('Title').value = license_dict['title']
    browser.getControl(
        'Description').value = license_dict['description']
    browser.getControl('Duration').value = 'invalid00:01:20'
    browser.getControl('Save').click()

    assert ('Invalid format. Please use the format hh:mm:ss or mm:ss.'
            in browser.contents)


def test__licenses__forms__CreateLicenseForm__3(
        browser, user, license_dict):
    """The duration field can have the input format mm:ss."""
    browser.login()
    browser.open(CREATE_URL)
    browser.getControl('Title').value = license_dict['title']
    browser.getControl(
        'Description').value = license_dict['description']
    browser.getControl('Duration').value = '30:20'
    browser.getControl('Save').click()

    assert (License.objects.get(
            title=license_dict['title']).duration ==
            datetime.timedelta(minutes=30, seconds=20))


def test__licenses__models__1(
        browser, user, license, license_dict):
    """
    String representation.

    A License gets represented by its title and subtitle.
    A Category get represented by its name.
    """
    browser.login()
    subtitle = 'Test Subtitle'
    license_dict['subtitle'] = subtitle
    license_with_subtitle = create_license(user.profile, license_dict)

    assert str(license) == license.title
    assert str(license_with_subtitle) in str(license_with_subtitle)
    assert license.category.__str__() == default_category().name


def test__licenses__models__2(
        db, license, license_dict, user):
    """Each new LR gets a unique, visible number."""
    lr1 = license
    lr2 = create_license(user.profile, license_dict)

    assert lr1.number == 1
    assert lr2.number == 2


def test__licenses__models__3(db, license):
    """The LR number always stays the same."""
    n1 = license.number
    license.subtitle = 'new_subtitle'
    license.save()
    n2 = license.number

    assert n1 == n2


def test__licenses__models__4(browser, license_dict, user):
    """A new LR must have a duration greater zero."""
    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow('Add License')

    browser.getControl('Title').value = license_dict['title']
    browser.getControl(
        'Description').value = license_dict['description']
    browser.getControl('Duration').value = '00:00'
    # select profile
    browser.getControl('Profile')._control.force_value(user.profile.id)

    browser.getControl(name='_save').click()

    assert 'Duration must not be null.' in browser.contents


def test__licenses__generate_file__1(browser, user, license):
    """The printed license contains the necessary data."""
    browser.login()
    browser.open(details_url(license.id))
    browser.follow(id='id_print_LR')

    assert browser.headers['Content-Type'] == 'application/pdf'
    pdftext = pdfToText(browser.contents)
    assert user.email in pdftext
    assert license.title in pdftext
    assert 'x' in pdftext


def test__licenses__views__FilledLicenseFile__1(browser, license):
    """If no user is logged in the site returns a 404."""
    with pytest.raises(HTTPError, match=r'.*404.*'):
        browser.open(print_url(license.id))


def test__licenses__views__FilledLicenseFile__2(db, user, browser):
    """Try printing a not existing LR produces an error message."""
    browser.login()
    browser.open(print_url(1))

    assert browser.url == LIST_URL
    assert 'License not found.' in browser.contents


def test__licenses__views__FilledLicenseFile__3(
        browser, user, user_dict, license, license_dict):
    """A LR from another user can not be printed."""
    user_dict['email'] = f'new_{user_dict["email"]}'
    second_user = create_user(user_dict)
    second_lr = create_license(second_user.profile, license_dict)

    browser.login()  # login with user
    browser.open(print_url(second_lr.id))

    assert browser.url == LIST_URL
    assert 'License not found.' in browser.contents


def test__licenses__admin__LicenseAdmin__1(
        browser, user, license, license_dict):
    """Confirm multiple LRs."""
    license.confirmed = True
    license.save()
    for _ in range(3):
        create_license(user.profile, license_dict)

    browser.login_admin()
    browser.open(A_LICENSE_URL)
    for i in range(4):
        # select all LRs
        browser.getControl(name='_selected_action').controls[i].click()
    browser.getControl('Action').value = 'confirm'
    browser.getControl('Go').click()

    assert ('3 Licenses were successfully confirmed.'
            in browser.contents)
    for lr in License.objects.filter():
        assert lr.confirmed


def test__licenses__admin__LicenseAdmin__2(
        browser, user, license, license_dict):
    """Unconfirm multiple LRs."""
    license.save()
    for _ in range(3):
        lr = create_license(user.profile, license_dict)
        lr.confirmed = True
        lr.save()

    browser.login_admin()
    browser.open(A_LICENSE_URL)
    for i in range(4):
        # select all LRs
        browser.getControl(name='_selected_action').controls[i].click()
    browser.getControl('Action').value = 'unconfirm'
    browser.getControl('Go').click()

    assert ('3 Licenses were successfully unconfirmed.'
            in browser.contents)
    for lr in License.objects.filter():
        assert not lr.confirmed


def test__licenses__admin__LicenseAdmin__3(browser, license):
    """Try to edit an confirmed License."""
    license.confirmed = True
    license.save()

    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow(license.title)

    assert 'Confirmed licenses are not editable!' in browser.contents


def test__licenses__admin__LicenseAdmin__4(browser, license):
    """Change a license in the admin view."""
    new_title = f'new_{license.title}'

    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow(license.title)
    browser.getControl('Title').value = new_title
    browser.getControl(name='_save').click()

    lr = License.objects.get(id=license.id)
    assert 'was changed successfully' in browser.contents
    assert lr.title == new_title


def test__licenses__admin__LicenseAdmin__5(browser, license):
    """Change a LR without an actual change."""
    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow(license.title)
    browser.getControl(name='_save').click()

    lr = License.objects.get(id=license.id)
    assert 'was changed successfully' in browser.contents
    assert license == lr


def test__licenses__admin__LicenseAdmin__6(browser):
    """The number field is not visible when a LR gets add by an admin."""
    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow('Add License')

    assert 'Number:' not in browser.contents


def test__licenses__admin__LicenseAdmin__7(browser, license):
    """The number field is not visible when a LR gets add by an admin."""
    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow(license.title)

    assert 'Number:' in browser.contents


def test__licenses__admin__LicenseAdmin__8(
        browser, license_dict, user_dict):
    """Show LRs with a profile without user."""
    profile = Profile.objects.create(
        first_name=user_dict['first_name'],
        last_name=user_dict['last_name']
    )
    create_license(profile, license_dict)

    browser.login_admin()
    browser.follow('License')

    assert '-' in browser.contents


def test__licenses__admin__LicenseAdmin__10(browser, license):
    """Try to confirm a LR with unverified profile."""
    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow(license.title)

    profile = license.profile
    profile.verified = False
    profile.save()

    browser.getControl('Confirmed').click()
    browser.getControl(name='_save').click()

    assert 'corresponding profile is not verified' in browser.contents
    assert not license.confirmed


def test__licenses__admin__LicenseAdmin__11(browser, license):
    """Try to confirm LRs with unverified profiles."""
    profile = license.profile
    profile.verified = False
    profile.save()

    browser.login_admin()
    browser.open(A_LICENSE_URL)

    browser.getControl(name='_selected_action').controls[0].selected = True
    browser.getControl('Action').value = 'confirm'
    browser.getControl('Go').click()

    assert f'profile of {license} is not verified' in browser.contents
    assert '0 Licenses were successfully confirmed' in browser.contents


def test__licenses__admin__LicenseAdmin__response_change__1(
        db, user, license: License, browser):
    """Print license form in admin change view."""
    browser.login_admin()
    browser.follow('Licenses', index=1)
    open('response.html', 'w').write(browser.contents)
    browser.follow(license.title)
    browser.getControl('Print license').click()

    assert browser.headers['Content-Type'] == 'application/pdf'
    text_result = pdfToText(browser.contents)
    assert user.profile.first_name in text_result
    assert user.profile.last_name in text_result
    assert license.title in text_result


def test__licenses__admin__YearFilter__1(browser, user, license_dict):
    """Licenses can be filtered by the year of its creation date."""
    created_at = datetime.datetime(
        day=8, month=9, year=datetime.datetime.now().year, tzinfo=TZ)
    license_dict['title'] = 'new_title'
    lr1 = create_license(user.profile, license_dict)
    lr1.created_at = created_at
    lr1.save()

    created_at = datetime.datetime(
        day=8, month=9, year=(datetime.datetime.now().year-1), tzinfo=TZ)
    license_dict['title'] = 'old_title'
    lr2 = create_license(user.profile, license_dict)
    lr2.created_at = created_at
    lr2.save()

    browser.login_admin()
    browser.open(A_LICENSE_URL)

    browser.follow('This year')
    assert str(lr1) in browser.contents
    assert str(lr2) not in browser.contents

    browser.follow('Last year')
    assert str(lr1) not in browser.contents
    assert str(lr2) in browser.contents


def test__licenses__admin__YearFilter__2():
    """Handle invalid values."""
    with patch.object(YearFilter, 'value', return_value='invalid'):
        with pytest.raises(ValueError, match=r'Invalid value .*'):
            filter = YearFilter(
                {}, {}, License, LicenseAdmin)
            filter.queryset(None, None)


def test__licenses__admin__WithoutContribution__1(
        browser, user, license_dict, contribution_dict):
    """Filter licenses by their contributions."""
    license_dict['title'] = "License Without Contribution"
    without_contr: License = create_license(user.profile, license_dict)

    license_dict['title'] = "License With Contribution"
    with_contr: License = create_license(user.profile, license_dict)
    create_contribution(with_contr, contribution_dict)

    browser.login_admin()
    browser.open(A_LICENSE_URL)

    browser.follow('Yes')
    assert without_contr.title in browser.contents
    assert with_contr.title not in browser.contents

    browser.follow('No')
    assert without_contr.title not in browser.contents
    assert with_contr.title in browser.contents


def test__licenses__admin__WithoutContribution__2():
    """Handle invalid values."""
    with patch.object(
            WithoutContributionFilter, 'value', return_value='invalid'):
        with pytest.raises(ValueError, match=r'Invalid value .*'):
            filter = WithoutContributionFilter(
                {}, {}, License, LicenseAdmin)
            filter.queryset(None, None)


def test__licenses__admin__LicenseResource__1(browser, license):
    """Export the datetime properties using the current time zone."""
    license.suggested_date = datetime.datetime(
        year=2022,
        month=9,
        day=21,
        hour=0,
        tzinfo=TZ,
    )

    license.created_at = datetime.datetime(
        year=2022,
        month=9,
        day=20,
        hour=0,
        tzinfo=TZ,
    )

    license.save()

    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow('Export')
    browser.getControl('csv').click()
    browser.getControl('Submit').click()

    assert browser.headers['Content-Type'] == 'text/csv'
    assert str(license.suggested_date.date()) in str(browser.contents)
    assert str(license.suggested_date.time()) in str(browser.contents)
    assert str(license.created_at.date()) in str(browser.contents)
    assert str(license.created_at.time()) in str(browser.contents)


def test__licenses__admin__LicenseResource__2(browser, license):
    """Export a license without a suggested broadcast date."""
    license.suggested_date = None
    license.save()

    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow('Export')
    browser.getControl('csv').click()
    browser.getControl('Submit').click()

    assert browser.headers['Content-Type'] == 'text/csv'
    assert str(license.title) in str(browser.contents)


def test__licenses__admin__LicenseResource__3(browser, license: License):
    """Export a license with all necessary data."""
    license.subtitle = 'Subtitle'
    license.further_persons = 'cut: another person'
    license.suggested_date = datetime.datetime(
        year=2022,
        month=10,
        day=10,
        hour=9,
        tzinfo=TZ,
    )
    license.save()

    browser.login_admin()
    browser.open(A_LICENSE_URL)
    browser.follow('Export')
    browser.getControl('csv').click()
    browser.getControl('Submit').click()

    assert browser.headers['Content-Type'] == 'text/csv'
    export = str(browser.contents)

    assert str(license.number) in export
    assert license.title in export
    assert license.subtitle in export
    assert license.description in export
    assert (f'{license.profile.first_name} {license.profile.last_name}' in
            export)
    assert license.further_persons in export
    assert str(license.duration) in export
    assert str(license.suggested_date.astimezone(TZ).date()) in export
    assert str(license.suggested_date.astimezone(TZ).time()) in export
    assert str(license.repetitions_allowed) in export
    assert str(license.media_authority_exchange_allowed) in export
    assert str(license.youth_protection_necessary) in export
    assert str(license.store_in_ok_media_library) in export


def test__licenses__admin__DurationRangeFilter__1(
        browser, license_dict, user):
    """Filter licenses after duration."""
    license_dict['duration'] = datetime.timedelta(minutes=5)
    license_dict['title'] = 'license1'
    license1 = create_license(user.profile, license_dict)

    license_dict['duration'] = datetime.timedelta(minutes=10)
    license_dict['title'] = 'license2'
    license2 = create_license(user.profile, license_dict)

    license_dict['title'] = 'license3'
    license_dict['duration'] = datetime.timedelta(minutes=15)
    license3 = create_license(user.profile, license_dict)

    browser.login_admin()
    browser.open(A_LICENSE_URL)

    browser.getControl(name='duration_from').value = 6
    browser.getControl(name='duration_to').value = 10
    browser.getControl('Search', index=2).click()

    assert license1.title not in browser.contents
    assert license2.title in browser.contents
    assert license3.title not in browser.contents


# API Tests


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def api_token(user):
    """Create an authentication token for the user."""
    token, created = Token.objects.get_or_create(user=user)
    return token.key


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__unauthorized(api_client, license):
    """API endpoint returns 401 when no token is provided."""
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    response = api_client.get(url)
    
    assert response.status_code == 401


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__authorized(
        api_client, api_token, license):
    """API endpoint returns license metadata when valid token is provided."""
    config = OrganizationConfig.get_config()
    config.bundesland = 'Sachsen-Anhalt'
    config.save()

    license.subtitle = 'Untertitel'
    license.further_persons = 'Person A, Person B'
    license.tags = ['tag1', 'tag2']
    license.repetitions_allowed = True
    license.media_authority_exchange_allowed_other_states = True
    license.store_in_ok_media_library = True
    license.youth_protection_necessary = True
    license.youth_protection_category = YouthProtectionCategory.FROM_16
    license.save()
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['name'] == license.title
    assert data['subtitle'] == 'Untertitel'
    assert data['description'] == license.description
    assert data['category'] == license.category.name
    assert data['profile'] == f"{license.profile.first_name} {license.profile.last_name}".strip()
    assert data['furtherInvolvedPersons'] == 'Person A, Person B'
    assert data['furtherPersons'] == 'Person A, Person B'
    assert data['tags'] == ['tag1', 'tag2']
    assert data['senderResponsible'] == (
        f"{license.profile.first_name} {license.profile.last_name}"
    )
    assert data['videoNumber'] == license.number
    assert data['saveToMediathek'] == license.store_in_ok_media_library
    assert data['bundesland'] == 'Sachsen-Anhalt'
    assert data['bundesland_code'] == 'ST'
    assert data['allowExchange'] == license.media_authority_exchange_allowed
    assert data['allowExchangeOtherStates'] is True
    assert data['repetitionsAllowed'] is True
    assert data['youthProtectionNecessary'] is True
    assert data['youthProtectionCategory'] == YouthProtectionCategory.FROM_16


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__not_found(
        api_client, api_token):
    """API endpoint returns 404 when license number doesn't exist."""
    url = reverse_lazy('licenses:api-metadata', args=[99999])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 404


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__tags_limit(
        api_client, api_token, license):
    """API endpoint limits tags to maximum 4."""
    license.tags = ['tag1', 'tag2', 'tag3', 'tag4', 'tag5', 'tag6']
    license.save()
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data['tags']) == 4
    assert data['tags'] == ['tag1', 'tag2', 'tag3', 'tag4']


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__originallyPublishedAt_from_planung(
        api_client, api_token, license):
    """API endpoint gets originallyPublishedAt from planung when available."""
    # Create a plan with this license
    plan_date = datetime.date(2025, 1, 15)
    plan = TagesPlan.objects.create(
        datum=plan_date,
        json_plan={
            'items': [
                {'number': license.number, 'title': license.title, 'duration': 300}
            ],
            'draft': False,
            'planned': True
        }
    )
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['originallyPublishedAt'] is not None
    # Check that it contains the date from planung
    assert '2025-01-15' in data['originallyPublishedAt']


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__originallyPublishedAt_from_contribution(
        api_client, api_token, license):
    """API endpoint gets originallyPublishedAt from contribution when not in planung."""
    # Create a contribution for this license
    contribution_date = datetime.datetime(
        2025, 2, 10, 18, 0, 0, tzinfo=TZ
    )
    contribution = Contribution.objects.create(
        license=license,
        broadcast_date=contribution_date,
        live=False
    )
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['originallyPublishedAt'] is not None
    # Check that it contains the date from contribution
    assert '2025-02-10' in data['originallyPublishedAt']


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__originallyPublishedAt_priority(
        api_client, api_token, license):
    """API endpoint prioritizes planung over contribution for originallyPublishedAt."""
    # Create both a plan and a contribution
    plan_date = datetime.date(2025, 1, 15)
    plan = TagesPlan.objects.create(
        datum=plan_date,
        json_plan={
            'items': [
                {'number': license.number, 'title': license.title, 'duration': 300}
            ],
            'draft': False,
            'planned': True
        }
    )
    
    contribution_date = datetime.datetime(
        2025, 2, 10, 18, 0, 0, tzinfo=TZ
    )
    contribution = Contribution.objects.create(
        license=license,
        broadcast_date=contribution_date,
        live=False
    )
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['originallyPublishedAt'] is not None
    # Should use date from planung (January), not contribution (February)
    assert '2025-01-15' in data['originallyPublishedAt']
    assert '2025-02-10' not in data['originallyPublishedAt']


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__no_tags(
        api_client, api_token, license):
    """API endpoint returns empty list when license has no tags."""
    license.tags = None
    license.save()
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['tags'] == []


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__empty_tags_list(
        api_client, api_token, license):
    """API endpoint returns empty list when license has empty tags list."""
    license.tags = []
    license.save()
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data['tags'] == []


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__planung_time_extraction(
        api_client, api_token, license):
    """API endpoint extracts correct time from planung TagesPlan."""
    from datetime import date
    from planung.models import TagesPlan
    
    # Create a TagesPlan with specific time
    plan_date = date(2025, 9, 27)
    plan_data = {
        'items': [
            {
                'number': license.number,
                'start': '18:00',  # 6 PM
                'duration': 3948,  # 65:48 in seconds
                'title': license.title,
                'author': 'Klaus Treuter'
            }
        ],
        'draft': False,
        'planned': True
    }
    
    TagesPlan.objects.create(
        datum=plan_date,
        json_plan=plan_data
    )
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should extract time from planung, not use midnight
    assert data['originallyPublishedAt'] == '2025-09-27T18:00:00+02:00'


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__target_channel(
        api_client, api_token, license):
    """API endpoint returns targetChannel from profile.media_authority or settings."""
    from django.conf import settings
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    # If profile has media_authority with target_channel, should return that targetChannel
    if license.profile and license.profile.media_authority:
        expected_channel = license.profile.media_authority.target_channel
        if expected_channel:
            assert data['targetChannel'] == expected_channel
            return
    
    # Otherwise should return PeerTube channel from settings
    expected_channel = getattr(settings, 'PEERTUBE_CHANNEL', '')
    assert data['targetChannel'] == expected_channel


@pytest.mark.django_db
def test__licenses__admin__tags_validation__max_tags():
    """Admin form validates maximum 4 tags."""
    from .admin import LicenseAdminForm
    from .models import License
    from registration.models import Profile, OKUser
    from django.core.exceptions import ValidationError
    
    # Create test data
    user = OKUser.objects.create_user(email='test@example.com')
    profile = Profile.objects.create(
        okuser=user,
        first_name='Test',
        last_name='User'
    )
    
    # Test with 5 tags (should fail)
    form_data = {
        'title': 'Test License',
        'description': 'Test Description',
        'profile': profile.id,
        'tags': ['tag1', 'tag2', 'tag3', 'tag4', 'tag5']
    }
    
    form = LicenseAdminForm(data=form_data)
    assert not form.is_valid()
    assert 'tags' in form.errors
    assert 'Maximum 4 tags allowed' in str(form.errors['tags'])


@pytest.mark.django_db
def test__licenses__admin__tags_validation__valid_tags():
    """Admin form accepts valid tags."""
    from .admin import LicenseAdminForm
    from .models import License
    from registration.models import Profile, OKUser
    
    # Create test data
    user = OKUser.objects.create_user(email='test@example.com')
    profile = Profile.objects.create(
        okuser=user,
        first_name='Test',
        last_name='User'
    )
    
    # Test with 3 valid tags
    form_data = {
        'title': 'Test License',
        'description': 'Test Description',
        'profile': profile.id,
        'tags': ['documentary', 'local', 'culture']
    }
    
    form = LicenseAdminForm(data=form_data)
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data['tags'] == ['documentary', 'local', 'culture']


@pytest.mark.django_db
def test__licenses__widget__tags_input__null_handling():
    """Tags input widget properly handles null values."""
    from .widgets import TagsInputWidget
    
    widget = TagsInputWidget()
    
    # Test None value
    assert widget.format_value(None) == ''
    
    # Test empty list
    assert widget.format_value([]) == ''
    
    # Test string "null"
    assert widget.format_value('null') == ''
    
    # Test string "None"
    assert widget.format_value('None') == ''
    
    # Test valid list
    assert widget.format_value(['tag1', 'tag2']) == 'tag1, tag2'
    
    # Test valid string
    assert widget.format_value('tag1, tag2') == 'tag1, tag2'

@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__invalid_token(license):
    """API endpoint returns 401 when invalid token is provided."""
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token invalidtokenvalue')
    response = client.get(url)
    assert response.status_code == 401


@pytest.mark.django_db
def test__licenses__admin__DurationRangeFilter__no_results(browser, license_dict, user):
    """DurationRangeFilter returns no results when range excludes all durations."""
    # Create licenses outside filter range
    license_dict['duration'] = datetime.timedelta(minutes=5)
    license_dict['title'] = 'short_license'
    create_license(user.profile, license_dict)

    license_dict['duration'] = datetime.timedelta(minutes=10)
    license_dict['title'] = 'medium_license'
    create_license(user.profile, license_dict)

    license_dict['duration'] = datetime.timedelta(minutes=15)
    license_dict['title'] = 'long_license'
    create_license(user.profile, license_dict)

    browser.login_admin()
    browser.open(A_LICENSE_URL)

    # Filter with range that excludes all (e.g., 60..120 minutes)
    browser.getControl(name='duration_from').value = 60
    browser.getControl(name='duration_to').value = 120
    browser.getControl('Search', index=2).click()

    # None of the created licenses should be visible
    assert 'short_license' not in browser.contents
    assert 'medium_license' not in browser.contents

@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__no_planung_no_contribution_date(
        api_client, api_token, license):
    """API endpoint returns None for originallyPublishedAt when no planung or contribution exists."""
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return None when no planung or contribution dates are available
    assert data['originallyPublishedAt'] is None


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__planung_not_planned(
        api_client, api_token, license):
    """API endpoint ignores planung entries that are not planned (draft=True)."""
    # Create a draft plan (not planned) with this license
    plan_date = datetime.date(2025, 1, 15)
    TagesPlan.objects.create(
        datum=plan_date,
        json_plan={
            'items': [
                {'number': license.number, 'title': license.title, 'duration': 300}
            ],
            'draft': True,  # This is a draft, not planned
            'planned': False
        }
    )
    
    # Also create a contribution for this license
    contribution_date = datetime.datetime(
        2025, 2, 10, 18, 0, 0, tzinfo=TZ
    )
    contribution = Contribution.objects.create(
        license=license,
        broadcast_date=contribution_date,
        live=False
    )
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should use contribution date since planung is not planned
    assert data['originallyPublishedAt'] is not None
    assert '2025-02-10' in data['originallyPublishedAt']  # From contribution, not planung
    assert '2025-01-15' not in data['originallyPublishedAt']  # Planung draft should be ignored


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__planung_multiple_matches(
        api_client, api_token, license):
    """API endpoint uses earliest planung date when multiple matches exist."""
    # Create multiple plans for this license
    plan_date1 = datetime.date(2025, 3, 15)  # Later date
    TagesPlan.objects.create(
        datum=plan_date1,
        json_plan={
            'items': [
                {'number': license.number, 'title': license.title, 'duration': 300}
            ],
            'draft': False,
            'planned': True
        }
    )
    
    plan_date2 = datetime.date(2025, 1, 15)  # Earlier date, should be selected
    TagesPlan.objects.create(
        datum=plan_date2,
        json_plan={
            'items': [
                {'number': license.number, 'title': license.title, 'duration': 300}
            ],
            'draft': False,
            'planned': True
        }
    )
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should use the earlier date (January), not the later one (March)
    assert data['originallyPublishedAt'] is not None
    assert '2025-01-15' in data['originallyPublishedAt']
    assert '2025-03-15' not in data['originallyPublishedAt']


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__empty_category_name(
        api_client, api_token, license):
    """API endpoint handles license with empty category name."""
    license.category.name = ""
    license.save()
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    # Category should be an empty string when name is empty
    assert data['category'] == ""


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__null_category(
        api_client, api_token, license):
    """API endpoint handles license with null category."""
    license.category = None
    license.save()
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should handle null category gracefully, probably defaulting to a string representation
    assert data['category'] is not None  # Should not crash


@pytest.mark.django_db
def test__licenses__api__LicenseMetadataView__null_profile(
        api_client, api_token, license):
    """API endpoint handles license with null profile."""
    license.profile = None
    license.save()
    
    url = reverse_lazy('licenses:api-metadata', args=[license.number])
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {api_token}')
    response = api_client.get(url)
    
    assert response.status_code == 404  # Should return 404 since license can't exist without profile in this context


@pytest.mark.django_db
def test__licenses__admin__tags_validation__invalid_json():
    """Admin form handles invalid JSON in tags field."""
    from .admin import LicenseAdminForm
    from registration.models import Profile, OKUser
    
    # Create test data
    user = OKUser.objects.create_user(email='test@example.com')
    profile = Profile.objects.create(
        okuser=user,
        first_name='Test',
        last_name='User'
    )
    
    # Test with invalid JSON in tags field
    form_data = {
        'title': 'Test License',
        'description': 'Test Description',
        'profile': profile.id,
        'tags': 'invalid json string'
    }
    
    form = LicenseAdminForm(data=form_data)
    # Form should be invalid due to invalid JSON
    assert not form.is_valid()
    # Should have error in tags field
    assert 'tags' in form.errors
    assert 'long_license' not in browser.contents


@pytest.mark.django_db
def test__licenses__models__confirmed_license_allows_mediathek_url_update(license):
    """Confirmed license accepts mediathek URL update via update_fields allowlist."""
    license.confirmed = True
    license.save(update_fields=['confirmed'])

    new_url = 'https://lokalmedial.de/w/test123'
    now = timezone.now()
    license.mediathek_url = new_url
    license.mediathek_url_updated_at = now
    license.save(update_fields=['mediathek_url', 'mediathek_url_updated_at'])

    license.refresh_from_db()
    assert license.mediathek_url == new_url
    assert license.mediathek_url_updated_at is not None


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', LANGUAGE_CODE='de')
def test__licenses__tasks__send_license_notification_email__subject_translated_to_german(
        user_dict, license_dict, mail_outbox):
    """License notification email subject is rendered in German for organization language."""
    user = create_user(user_dict, verified=True)
    license_obj = create_license(user.profile, license_dict)

    with translation.override('en'):
        send_license_notification_email(
            event_type='contributions_available',
            license_number=license_obj.number,
            payload={
                'premiere_datetime': '2026-02-01 20:15',
                'repeats_text': '2026-02-02 10:00',
            },
        )

    assert len(mail_outbox) == 1
    assert f'Sendetermine verfügbar für Freistellung #{license_obj.number}' in mail_outbox[0].subject
