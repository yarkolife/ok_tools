from .disa_import import disa_import
from .disa_import import validate
from .models import Contribution
from .models import DisaImport
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from ok_tools.testing import DOMAIN
from ok_tools.testing import _open
from ok_tools.testing import create_disaimport
import pytest


A_CON_URL = (f'{DOMAIN}'
             f'{reverse_lazy("admin:contributions_contribution_changelist")}')
DISA_CREATE_URL = (f'{DOMAIN}'
                   f'{reverse_lazy("admin:contributions_disaimport_add")}')
DISA_URL = (f'{DOMAIN}'
            f'{reverse_lazy("admin:contributions_disaimport_changelist")}')

XLSX_CT = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def disa_url_change(id: int) -> str:
    """Create the change url for the given id."""
    url = reverse_lazy("admin:contributions_disaimport_change", args=[id])
    return (f'{DOMAIN}'f'{url}')


def _raises(match):
    return pytest.raises(ValidationError, match=match)


def test__contributions__admin__ContributionsAdmin__1(browser, contribution):
    """Contributions get shown in the admin interface."""
    browser.login_admin()
    browser.open(A_CON_URL)

    assert str(contribution) in browser.contents
    assert contribution.license.profile.first_name in browser.contents
    assert contribution.license.profile.last_name in browser.contents


# möglichst nur in Funktion testen
def test__contributions__disa_import__validate__1(browser):
    """It is possible to upload a valid DISA export file."""
    browser.login_admin()
    browser.open(DISA_CREATE_URL)

    with _open('valid.xlsx') as file:
        browser.getControl(
            'DISA export file').add_file(file, XLSX_CT, 'test.xlsx')

    browser.getControl(name='_save').click()

    assert 'added successfully' in browser.contents
    assert DisaImport.objects.filter()


def test__contributions__disa_import__validate__2():
    """The file needs to have the right column names."""
    with _raises(r'.*Anfang.*Ende.*Länge.*Titel.*Typ'):
        with _open('invalid_header.xlsx') as f:
            validate(f)


def test__contributions__disa_import__validate__3():
    """The Worksheet needs the right name."""
    with _raises(r'.*Auftragsfenster.*'):
        with _open('wrong_ws.xlsx') as f:
            validate(f)


def test__contributions__disa_import__validate__4():
    """Files without a blank line after the header are not valid."""
    with _raises(r'.*is not empty.*'):
        with _open('no_blank.xlsx') as f:
            validate(f)


def test__contributions__disa_import__validate__5():
    """Files with an invalid title are not valid."""
    with _raises(r'.*Title needs the format <nr>_<title>.*'):
        with _open('invalid_number.xlsx') as f:
            validate(f)


def test__contributions__disa_import__1(db, license_request):
    """Import a contribution from DISA export."""
    with _open('valid.xlsx') as f:
        disa_import(None, f)

    assert Contribution.objects.filter()


def test__contributions__disa_import__2(db, license_request):
    """Do not create duplicated contributions."""
    with _open('valid.xlsx') as f:
        disa_import(None, f)
        disa_import(None, f)

    assert len(Contribution.objects.filter()) == 1


def test__contributions__disa_import__3(db, license_request):
    """Ignore everything after a blank line."""
    with _open('blank_line.xlsx') as f:
        disa_import(None, f)

    assert len(Contribution.objects.filter()) == 1


def test__contributions__disa_import__4(browser, disaimport):
    """Show an error message if no license exits."""
    browser.login_admin()
    browser.open(disa_url_change(disaimport.id))
    browser.getControl(name='_import_disa').click()

    assert not Contribution.objects.filter()
    assert 'No license with number 1 found.' in browser.contents


def test__contributions__admin__1(browser, db, license_request):
    """Import multiple DISA export files."""
    # create 3 DISA export files
    for _ in range(3):
        create_disaimport()

    browser.login_admin()
    browser.open(DISA_URL)
    for i in range(3):
        # select all disaimports
        browser.getControl(name='_selected_action').controls[i].click()
    browser.getControl('Action').value = 'import_files'
    browser.getControl('Go').click()

    assert '3 files successfully imported.' in browser.contents
    assert Contribution.objects.filter()


def test__contributions__admin__2(browser, disaimport):
    """Just mark a DISA export file as imported."""
    browser.login_admin()
    browser.open(disa_url_change(disaimport.id))

    browser.getControl('Imported').click()

    browser.getControl(name=('_save')).click()

    assert DisaImport.objects.get(id=disaimport.id).imported
    assert not Contribution.objects.filter()
