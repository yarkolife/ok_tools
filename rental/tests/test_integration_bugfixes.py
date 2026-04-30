"""
Integration tests verifying the rental flow works after bug fixes.

All test descriptions are in English per project rules.
"""

import json
from unittest.mock import patch

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from ok_tools.testing import create_user


@pytest.fixture(scope='session', autouse=True)
def _ensure_signature_columns(django_db_setup, django_db_blocker):
    """Add signature columns if missing from the test database.

    Migration 0016 uses SeparateDatabaseAndState with database_operations=[],
    so on a fresh database the signature columns exist only in Django's
    migration state table, not as actual columns in rental_rentalrequest.
    This fixture creates the columns so that ORM inserts work correctly.
    """
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            existing = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor,
                    'rental_rentalrequest',
                )
            }
            if 'signature' not in existing:
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_svg text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_points text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_metadata text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_method varchar(32) NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_signed_at datetime NULL"
                )


def _create_staff_user():
    """Create and return a staff user."""
    user_dict = {
        "email": "staff@example.com",
        "first_name": "Staff",
        "last_name": "User",
        "gender": "m",
        "phone_number": None,
        "mobile_number": None,
        "birthday": "01.01.1990",
        "street": "main street",
        "house_number": "1",
        "zipcode": "12345",
        "city": "example-city",
    }
    return create_user(user_dict, is_staff=True)


def _create_regular_user(email='borrower@example.com', member=False, is_staff=False):
    """Create a regular rental borrower with optional member/staff flags."""
    user_dict = {
        "email": email,
        "first_name": "Rental",
        "last_name": "Borrower",
        "gender": "m",
        "phone_number": None,
        "mobile_number": None,
        "birthday": "01.01.1990",
        "street": "main street",
        "house_number": "1",
        "zipcode": "12345",
        "city": "example-city",
    }
    user = create_user(user_dict, is_staff=is_staff)
    user.profile.member = member
    user.profile.save(update_fields=['member'])
    return user


def _create_inventory_item(number, owner, location, description):
    """Create a rentable in-stock inventory item."""
    from inventory.models import InventoryItem

    return InventoryItem.objects.create(
        inventory_number=number,
        description=description,
        quantity=1,
        status='in_stock',
        available_for_rent=True,
        owner=owner,
        location=location,
    )


@pytest.mark.django_db
def test_rental_creation_without_signature(user):
    """RentalRequest can be created without any signature fields."""
    from rental.models import RentalRequest

    rental = RentalRequest.objects.create(
        user=user,
        created_by=user,
        project_name="Test Project",
        purpose="Testing signature-free creation",
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timezone.timedelta(hours=1),
    )
    assert rental.pk is not None
    # All signature fields must be null when not provided
    assert rental.signature is None
    assert rental.signature_svg is None
    assert rental.signature_points is None
    assert rental.signature_metadata is None
    assert rental.signature_method is None
    assert rental.signature_signed_at is None
    # Default status
    assert rental.status == 'draft'


@pytest.mark.django_db
def test_mark_issued_changes_status(db, client):
    """mark_issued should change rental status to 'issued'."""
    staff_user = _create_staff_user()
    client.force_login(staff_user)

    from rental.models import RentalRequest

    rental = RentalRequest.objects.create(
        user=staff_user,
        created_by=staff_user,
        project_name="Test Project",
        purpose="Testing mark_issued",
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timezone.timedelta(hours=2),
        status='reserved',
    )

    url = reverse('rental:mark_issued', args=[rental.id])
    response = client.post(url)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data.get('ok') is True
    assert data.get('success') is True

    # Verify the rental was actually issued in the database
    rental.refresh_from_db()
    assert rental.status == 'issued'
    assert rental.actual_start_date is not None


@pytest.mark.django_db
def test_email_sent_on_issue(db, client, mailoutbox):
    """Confirmation email should be sent when rental is issued."""
    staff_user = _create_staff_user()
    client.force_login(staff_user)

    from rental.models import RentalRequest

    rental = RentalRequest.objects.create(
        user=staff_user,
        created_by=staff_user,
        project_name="Test Project",
        purpose="Testing email on issue",
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timezone.timedelta(hours=2),
        status='reserved',
    )

    url = reverse('rental:mark_issued', args=[rental.id])
    response = client.post(url)

    assert response.status_code == 200

    # Exactly one email should have been sent
    assert len(mailoutbox) == 1
    # The subject should reference the rental
    assert str(rental.id) in mailoutbox[0].subject

    rental.refresh_from_db()
    assert rental.status == 'issued'


@pytest.mark.django_db
def test_issuance_succeeds_despite_email_failure(db, client):
    """Issuance should succeed even if email sending fails."""
    staff_user = _create_staff_user()
    client.force_login(staff_user)

    from rental.models import RentalRequest

    rental = RentalRequest.objects.create(
        user=staff_user,
        created_by=staff_user,
        project_name="Test Project",
        purpose="Testing email failure resilience",
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timezone.timedelta(hours=2),
        status='reserved',
    )

    url = reverse('rental:mark_issued', args=[rental.id])

    # Mock send_mail within rental_email to raise an exception.
    # send_issued_confirmation_email catches internal exceptions,
    # so the view should still return 200.
    with patch(
        'rental.services.rental_email.send_mail',
        side_effect=Exception("SMTP connection failed"),
    ):
        response = client.post(url)

    # The issuance should succeed despite the email failure
    data = json.loads(response.content)
    assert data.get('ok') is True

    rental.refresh_from_db()
    assert rental.status == 'issued'


@pytest.mark.django_db
def test_signed_issued_rental_can_be_extended(db, client):
    """Issued rentals can be extended even when they already have a signature."""
    staff_user = _create_staff_user()
    client.force_login(staff_user)

    from rental.models import RentalRequest

    current_end = timezone.now() + timezone.timedelta(hours=2)
    rental = RentalRequest.objects.create(
        user=staff_user,
        created_by=staff_user,
        project_name="Signed issued rental",
        purpose="Testing extension",
        requested_start_date=timezone.now(),
        requested_end_date=current_end,
        status='issued',
        signature='signed',
    )

    with patch('rental.views.RentalService.extend_rental', return_value=True) as mocked_extend:
        response = client.post(
            reverse('rental:extend', args=[rental.id]),
            data=json.dumps({'to': (current_end + timezone.timedelta(hours=2)).isoformat()}),
            content_type='application/json',
        )

    assert response.status_code == 200
    assert json.loads(response.content).get('success') is True
    mocked_extend.assert_called_once()


@pytest.mark.django_db
def test_return_flags_close_rental_create_audit_and_send_receipt(db, client):
    """Return workflow honors close, audit, and email receipt flags."""
    staff_user = _create_staff_user()
    client.force_login(staff_user)

    from inventory.models import InventoryItem
    from inventory.models import Location
    from inventory.models import Organization
    from rental.models import RentalIssue
    from rental.models import RentalItem
    from rental.models import RentalRequest

    organization = Organization.objects.create(name='Test Organization')
    location = Location.objects.create(name='Return Shelf')
    inventory_item = InventoryItem.objects.create(
        inventory_number='OK-RETURN-001',
        description='Return Test Item',
        quantity=1,
        status='in_stock',
        available_for_rent=True,
        owner=organization,
        location=location,
    )
    rental = RentalRequest.objects.create(
        user=staff_user,
        created_by=staff_user,
        project_name='Return Flags',
        purpose='Testing return flags',
        requested_start_date=timezone.now() - timezone.timedelta(hours=2),
        requested_end_date=timezone.now() + timezone.timedelta(hours=2),
        status='issued',
        actual_start_date=timezone.now() - timezone.timedelta(hours=1),
    )
    rental_item = RentalItem.objects.create(
        rental_request=rental,
        inventory_item=inventory_item,
        quantity_requested=1,
        quantity_issued=1,
    )

    with patch('rental.views.send_return_receipt_email') as mocked_receipt:
        response = client.post(
            reverse('rental:api_return_rental_items'),
            data=json.dumps({
                'rental_id': rental.id,
                'items': [{
                    'id': rental_item.id,
                    'qty_returned': 1,
                    'condition': 'ok',
                }],
                'note': 'Returned at front desk.',
                'email_receipt': True,
                'close_rental': True,
                'flag_audit': True,
            }),
            content_type='application/json',
        )

    assert response.status_code == 200
    rental.refresh_from_db()
    rental_item.refresh_from_db()
    assert rental.status == 'closed'
    assert rental_item.quantity_returned == 1
    assert RentalIssue.objects.filter(rental_item=rental_item, issue_type='other').exists()
    mocked_receipt.assert_called_once()


@pytest.mark.django_db
def test_inventory_search_with_rental_id_uses_borrower_access_config(db, client):
    """Add-items inventory search uses the rental borrower access tier, not staff access."""
    from inventory.models import Location
    from inventory.models import Organization
    from rental.models import RentalConfig
    from rental.models import RentalRequest

    staff_user = _create_staff_user()
    borrower = _create_regular_user('restricted-borrower@example.com')
    client.force_login(staff_user)

    user_org = Organization.objects.create(name='User Access Org')
    member_org = Organization.objects.create(name='Member Only Org')
    employee_org = Organization.objects.create(name='Employee Only Org')
    location = Location.objects.create(name='Access Shelf')
    visible_item = _create_inventory_item('OK-ACCESS-USER', user_org, location, 'Visible user item')
    _create_inventory_item('OK-ACCESS-MEMBER', member_org, location, 'Hidden member item')
    _create_inventory_item('OK-ACCESS-EMPLOYEE', employee_org, location, 'Hidden employee item')

    config = RentalConfig.get_config()
    config.user_organizations.set([user_org])
    config.member_organizations.set([member_org])
    config.employee_organizations.set([employee_org])

    rental = RentalRequest.objects.create(
        user=borrower,
        created_by=staff_user,
        project_name='Access-filtered add items',
        purpose='Testing borrower-scoped inventory search',
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timezone.timedelta(hours=2),
        status='reserved',
    )

    response = client.get(
        reverse('rental:api_inventory_search'),
        {'rental_id': rental.id},
    )

    assert response.status_code == 200
    data = response.json()
    item_numbers = {item['num'] for item in data['items']}
    assert item_numbers == {visible_item.inventory_number}
    assert data['categories'][0]['count'] == 1


@pytest.mark.django_db
def test_inventory_access_check_uses_rental_config_organizations(db):
    """Final add-items access validation follows RentalConfig organization rules."""
    from inventory.models import Location
    from inventory.models import Organization
    from rental.models import RentalConfig
    from rental.services import RentalService

    borrower = _create_regular_user('service-borrower@example.com')
    allowed_org = Organization.objects.create(name='Configured User Org')
    denied_org = Organization.objects.create(name='Configured Denied Org')
    location = Location.objects.create(name='Service Access Shelf')
    allowed_item = _create_inventory_item('OK-SERVICE-ALLOW', allowed_org, location, 'Allowed item')
    denied_item = _create_inventory_item('OK-SERVICE-DENY', denied_org, location, 'Denied item')

    config = RentalConfig.get_config()
    config.user_organizations.set([allowed_org])
    config.member_organizations.clear()
    config.employee_organizations.clear()

    assert RentalService.check_user_inventory_access(borrower, allowed_item.id) is True
    assert RentalService.check_user_inventory_access(borrower, denied_item.id) is False
