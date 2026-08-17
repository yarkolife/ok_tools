"""
Integration tests verifying the rental flow works after bug fixes.

All test descriptions are in English per project rules.
"""

from datetime import datetime
from datetime import time
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from ok_tools.testing import create_user
from unittest.mock import patch
import json
import pytest


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


@pytest.mark.django_db
def test_change_period_rejects_room_conflict_and_synchronizes_free_period(
        db, client):
    """Editing a rental period is atomic and keeps its room dates aligned."""
    from rental.models import RentalRequest
    from rental.models import Room
    from rental.models import RoomRental

    staff_user = _create_staff_user()
    borrower = _create_regular_user('period-borrower@example.com')
    other_borrower = _create_regular_user('other-period-borrower@example.com')
    client.force_login(staff_user)
    room = Room.objects.create(name='Editing Room', capacity=4, is_active=True)

    original_day = timezone.localdate() + timezone.timedelta(days=1)
    while original_day.weekday() >= 5:
        original_day += timezone.timedelta(days=1)
    conflict_day = original_day + timezone.timedelta(days=1)
    while conflict_day.weekday() >= 5:
        conflict_day += timezone.timedelta(days=1)

    original_start = timezone.make_aware(
        datetime.combine(original_day, time(hour=10)))
    original_end = original_start + timezone.timedelta(hours=1)
    rental = RentalRequest.objects.create(
        user=borrower,
        created_by=staff_user,
        project_name='Period to edit',
        purpose='Test conflict validation',
        requested_start_date=original_start,
        requested_end_date=original_end,
        status='reserved',
        rental_type='room',
    )
    room_rental = RoomRental.objects.create(
        rental_request=rental,
        room=room,
        people_count=2,
        requested_start_date=original_start,
        requested_end_date=original_end,
    )

    conflict_start = timezone.make_aware(
        datetime.combine(conflict_day, time(hour=11)))
    conflict_end = conflict_start + timezone.timedelta(hours=2)
    conflicting_rental = RentalRequest.objects.create(
        user=other_borrower,
        created_by=staff_user,
        project_name='Existing reservation',
        purpose='Blocks the room',
        requested_start_date=conflict_start,
        requested_end_date=conflict_end,
        status='reserved',
        rental_type='room',
    )
    RoomRental.objects.create(
        rental_request=conflicting_rental,
        room=room,
        people_count=1,
        requested_start_date=conflict_start,
        requested_end_date=conflict_end,
    )

    response = client.post(
        reverse('rental:api_change_rental_period', args=[rental.pk]),
        data=json.dumps({
            'from': timezone.localtime(conflict_start).strftime('%Y-%m-%dT%H:%M'),
            'to': timezone.localtime(conflict_end).strftime('%Y-%m-%dT%H:%M'),
        }),
        content_type='application/json',
    )

    assert response.status_code == 409
    rental.refresh_from_db()
    room_rental.refresh_from_db()
    assert rental.requested_start_date == original_start
    assert room_rental.requested_start_date == original_start

    free_start = timezone.make_aware(
        datetime.combine(conflict_day, time(hour=14)))
    free_end = free_start + timezone.timedelta(hours=1)
    response = client.post(
        reverse('rental:api_change_rental_period', args=[rental.pk]),
        data=json.dumps({
            'from': timezone.localtime(free_start).strftime('%Y-%m-%dT%H:%M'),
            'to': timezone.localtime(free_end).strftime('%Y-%m-%dT%H:%M'),
        }),
        content_type='application/json',
    )

    assert response.status_code == 200
    rental.refresh_from_db()
    room_rental.refresh_from_db()
    assert rental.requested_start_date == free_start.replace(second=0, microsecond=0)
    assert rental.requested_end_date == free_end.replace(second=0, microsecond=0)
    assert room_rental.requested_start_date == rental.requested_start_date
    assert room_rental.requested_end_date == rental.requested_end_date


@pytest.mark.django_db
def test_room_schedule_marks_past_slots_and_links_reservations(db, client):
    """The day API distinguishes past time and exposes booking detail links."""
    from rental.models import RentalRequest
    from rental.models import Room
    from rental.models import RoomRental

    staff_user = _create_staff_user()
    borrower = _create_regular_user('calendar-borrower@example.com')
    client.force_login(staff_user)
    room = Room.objects.create(name='Calendar Room', capacity=2, is_active=True)
    now = timezone.now()
    past_start = now - timezone.timedelta(hours=1)
    past_end = past_start + timezone.timedelta(minutes=30)
    future_start = now + timezone.timedelta(days=1)
    future_end = future_start + timezone.timedelta(hours=1)
    rental = RentalRequest.objects.create(
        user=borrower,
        created_by=staff_user,
        project_name='Linked reservation',
        purpose='Test calendar link',
        requested_start_date=future_start,
        requested_end_date=future_end,
        status='reserved',
        rental_type='room',
    )
    RoomRental.objects.create(
        rental_request=rental,
        room=room,
        people_count=2,
        requested_start_date=future_start,
        requested_end_date=future_end,
    )

    with patch('rental.views._iter_time_slots', return_value=[
        (past_start, past_end),
    ]):
        response = client.get(reverse('rental:api_room_schedule'), {
            'start_date': timezone.localdate().isoformat(),
            'end_date': timezone.localdate().isoformat(),
        })

    assert response.status_code == 200
    assert response.json()['rooms'][0]['schedule'][0]['slots'][0]['status'] == 'past'

    future_date = timezone.localtime(future_start).date()
    slot_end = future_start + timezone.timedelta(minutes=30)
    with patch('rental.views._iter_time_slots', return_value=[
        (future_start, slot_end),
    ]):
        response = client.get(reverse('rental:api_room_schedule'), {
            'start_date': future_date.isoformat(),
            'end_date': future_date.isoformat(),
        })

    slot = response.json()['rooms'][0]['schedule'][0]['slots'][0]
    assert slot['status'] == 'occupied'
    assert slot['info']['detail_url'] == reverse(
        'rental:rental_detail', args=[rental.pk])
