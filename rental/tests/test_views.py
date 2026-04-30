# All test descriptions are in English per project rules.

import json
import pytest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from rental.models import RentalRequest
from rental.views import (
    RENTAL_PROCESS_INITIAL_USER_LIMIT,
    StaffRequiredMixin,
    api_create_rental_user,
    api_create_rental,
    api_cancel_rental,
    api_get_staff_users,
    get_initial_rental_process_users,
    serialize_user,
)


User = get_user_model()


def create_rental_request(user, created_by, status='returned'):
    return RentalRequest.objects.create(
        user=user,
        created_by=created_by,
        project_name='Test Project',
        purpose='Test Purpose',
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timedelta(days=1),
        status=status,
    )


class DummyView(StaffRequiredMixin):
    """Minimal subclass to exercise StaffRequiredMixin.handle_no_permission."""
    def __init__(self, user):
        self.request = SimpleNamespace(user=user)


@pytest.mark.django_db
def test__rental__views__get_initial_rental_process_users__limits_default_selection():
    """Initial rental-process users are capped and prioritize active borrowers."""
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    active_user = User.objects.create_user(email="active@example.com", password="pwd")
    frequent_user = User.objects.create_user(email="frequent@example.com", password="pwd")
    recent_user = User.objects.create_user(email="recent@example.com", password="pwd")
    draft_only_user = User.objects.create_user(email="draft-only@example.com", password="pwd")
    create_rental_request(active_user, staff, status='issued')
    old_rental = create_rental_request(frequent_user, staff, status='returned')
    old_rental.created_at = timezone.now() - timedelta(days=30)
    old_rental.save(update_fields=['created_at'])
    older_rental = create_rental_request(frequent_user, staff, status='returned')
    older_rental.created_at = timezone.now() - timedelta(days=31)
    older_rental.save(update_fields=['created_at'])
    create_rental_request(recent_user, staff, status='returned')
    create_rental_request(draft_only_user, staff, status='draft')

    zero_history_staff = None
    for index in range(25):
        zero_history_staff = User.objects.create_user(
            email=f"staff{index}@example.com",
            password="pwd",
            is_staff=True,
        )

    for index in range(25):
        user = User.objects.create_user(email=f"user{index}@example.com", password="pwd")
        if index < 3:
            create_rental_request(user, staff)

    users = list(get_initial_rental_process_users())
    user_ids = {user.pk for user in users}

    assert len(users) == RENTAL_PROCESS_INITIAL_USER_LIMIT
    assert active_user.pk in user_ids
    assert frequent_user.pk in user_ids
    assert recent_user.pk in user_ids
    assert zero_history_staff.pk in user_ids
    assert draft_only_user.pk not in user_ids
    assert users[0].pk == active_user.pk
    assert users.index(recent_user) < users.index(frequent_user)
    assert users.index(recent_user) < users.index(zero_history_staff)


@pytest.mark.django_db
def test__rental__views__serialize_user__uses_annotated_rental_count():
    """Serialized users use annotated rental counts for the initial page payload."""
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    user = User.objects.create_user(email="borrower@example.com", password="pwd")
    create_rental_request(user, staff)
    create_rental_request(user, staff)

    annotated_user = next(
        candidate for candidate in get_initial_rental_process_users(limit=10)
        if candidate.pk == user.pk
    )
    serialized = serialize_user(annotated_user)

    assert serialized['past'] == 2
    assert serialized['past_count'] == 2


@pytest.mark.django_db
def test__rental__views__serialize_user__shows_single_annotated_rental():
    """Initial/search user cards show one real rental as one rental, not zero."""
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    user = User.objects.create_user(email="single@example.com", password="pwd")
    create_rental_request(user, staff)

    annotated_user = next(
        candidate for candidate in get_initial_rental_process_users(limit=10)
        if candidate.pk == user.pk
    )
    serialized = serialize_user(annotated_user)

    assert serialized['past'] == 1
    assert serialized['past_count'] == 1


@pytest.mark.django_db
def test__rental__mixins__StaffRequiredMixin__unauthenticated_redirects_to_login():
    """Unauthenticated user is redirected to login."""
    user = SimpleNamespace(is_authenticated=False, is_staff=False)
    view = DummyView(user)
    response = view.handle_no_permission()
    assert response.status_code == 302
    # Expect redirect to login URL
    assert "login" in response.url


@pytest.mark.django_db
def test__rental__mixins__StaffRequiredMixin__nonstaff_redirects_access_denied():
    """Authenticated non-staff user is redirected to access denied."""
    user = SimpleNamespace(is_authenticated=True, is_staff=False)
    view = DummyView(user)
    response = view.handle_no_permission()
    assert response.status_code == 302
    # Expect redirect to rental:access_denied
    assert "access_denied" in response.url


@pytest.mark.django_db
def test__rental__views__api_create_rental_user__method_not_allowed():
    """Non-POST method returns 405."""
    rf = RequestFactory()
    # Create authenticated user
    user = User.objects.create_user(email="user@example.com", password="pwd")
    request = rf.get("/rental/api/create_rental_user")
    request.user = user
    response = api_create_rental_user(request)
    assert response.status_code == 405
    data = response.json()
    assert data["error"] == "Method not allowed"


@pytest.mark.django_db
def test__rental__views__api_create_rental_user__success():
    """POST success returns success json from service."""
    rf = RequestFactory()
    user = User.objects.create_user(email="user@example.com", password="pwd")
    payload = {"project_name": "Test Project"}
    request = rf.post(
        "/rental/api/create_rental_user",
        data=json.dumps(payload),
        content_type="application/json",
    )
    request.user = user

    with patch("rental.views.RentalService") as MockService:
        instance = MockService.return_value
        instance.create_rental_request.return_value = {"success": True, "id": 42}
        response = api_create_rental_user(request)
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["id"] == 42
        instance.create_rental_request.assert_called_once()


@pytest.mark.django_db
def test__rental__views__api_create_rental_user__service_error():
    """POST when service returns error should be 400."""
    rf = RequestFactory()
    user = User.objects.create_user(email="user@example.com", password="pwd")
    payload = {"project_name": "Test Project"}
    request = rf.post(
        "/rental/api/create_rental_user",
        data=json.dumps(payload),
        content_type="application/json",
    )
    request.user = user

    with patch("rental.views.RentalService") as MockService:
        instance = MockService.return_value
        instance.create_rental_request.return_value = {"success": False, "error": "Invalid"}
        response = api_create_rental_user(request)
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid"


@pytest.mark.django_db
def test__rental__views__api_create_rental__method_not_allowed():
    """Non-POST method returns 405."""
    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    request = rf.get("/rental/api/create_rental")
    request.user = staff
    response = api_create_rental(request)
    assert response.status_code == 405
    assert response.json()["error"] == "Method not allowed"


@pytest.mark.django_db
def test__rental__views__api_create_rental__success():
    """POST success calls service and returns success."""
    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    target_user = User.objects.create_user(email="user2@example.com", password="pwd")
    payload = {"user_id": target_user.id, "project_name": "Proj"}
    request = rf.post(
        "/rental/api/create_rental",
        data=json.dumps(payload),
        content_type="application/json",
    )
    request.user = staff

    with patch("rental.views.RentalService") as MockService:
        instance = MockService.return_value
        instance.create_rental_request.return_value = {"success": True, "id": 99}
        response = api_create_rental(request)
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["id"] == 99
        instance.create_rental_request.assert_called_once()


@pytest.mark.django_db
def test__rental__views__api_create_rental__service_error():
    """POST when service returns error should be 400."""
    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    target_user = User.objects.create_user(email="user3@example.com", password="pwd")
    payload = {"user_id": target_user.id, "project_name": "Proj"}
    request = rf.post(
        "/rental/api/create_rental",
        data=json.dumps(payload),
        content_type="application/json",
    )
    request.user = staff

    with patch("rental.views.RentalService") as MockService:
        instance = MockService.return_value
        instance.create_rental_request.return_value = {"success": False, "error": "Bad"}
        response = api_create_rental(request)
        assert response.status_code == 400
        assert response.json()["error"] == "Bad"


@pytest.mark.django_db
def test__rental__views__api_cancel_rental__missing_id():
    """Missing rental_id returns 400."""
    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    request = rf.post("/rental/api/cancel_rental", data=json.dumps({}), content_type="application/json")
    request.user = staff
    response = api_cancel_rental(request)
    assert response.status_code == 400
    assert response.json()["error"] == "Rental ID is required"


@pytest.mark.django_db
def test__rental__views__api_get_staff_users__method_not_allowed():
    """Non-GET returns 405."""
    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    request = rf.post("/rental/api/get_staff_users")
    request.user = staff
    response = api_get_staff_users(request)
    assert response.status_code == 405
    assert response.json()["error"] == "Method not allowed"


@pytest.mark.django_db
def test__rental__views__api_get_staff_users__returns_list():
    """GET returns list of staff users."""
    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    # Create additional staff users
    s1 = User.objects.create_user(email="s1@example.com", password="pwd", is_staff=True)
    s2 = User.objects.create_user(email="s2@example.com", password="pwd", is_staff=True)

    request = rf.get("/rental/api/get_staff_users")
    request.user = staff
    response = api_get_staff_users(request)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["users"], list)
    # At least the two created staff users should be present (names may be emails)
    emails = {u["email"] for u in data["users"]}
    assert "s1@example.com" in emails
    assert "s2@example.com" in emails

# Additional coverage tests appended.

import json
import pytest
from django.test import RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test__rental__mixins__StaffRequiredMixin__test_func_flags():
    """StaffRequiredMixin.test_func returns True only for authenticated staff users."""
    from rental.views import StaffRequiredMixin
    from types import SimpleNamespace

    class _View(StaffRequiredMixin):
        def __init__(self, user):
            self.request = SimpleNamespace(user=user)

    # Unauthenticated
    v1 = _View(SimpleNamespace(is_authenticated=False, is_staff=False))
    assert v1.test_func() is False

    # Authenticated but non-staff
    v2 = _View(SimpleNamespace(is_authenticated=True, is_staff=False))
    assert v2.test_func() is False

    # Authenticated staff
    v3 = _View(SimpleNamespace(is_authenticated=True, is_staff=True))
    assert v3.test_func() is True


@pytest.mark.django_db
def test__rental__views__api_create_rental_user__exception_results_400():
    """Service exception in api_create_rental_user is handled and returns 400."""
    from rental.views import api_create_rental_user
    from unittest.mock import patch

    rf = RequestFactory()
    user = User.objects.create_user(email="user@example.com", password="pwd")
    request = rf.post(
        "/rental/api/create_rental_user",
        data=json.dumps({"project_name": "X"}),
        content_type="application/json",
    )
    request.user = user

    with patch("rental.views.RentalService") as MockService:
        instance = MockService.return_value
        instance.create_rental_request.side_effect = Exception("boom")
        response = api_create_rental_user(request)
        assert response.status_code == 400
        assert "boom" in response.json()["error"]


@pytest.mark.django_db
def test__rental__views__api_create_rental__exception_results_400():
    """Service exception in api_create_rental is handled and returns 400."""
    from rental.views import api_create_rental
    from unittest.mock import patch

    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    target_user = User.objects.create_user(email="target@example.com", password="pwd")
    request = rf.post(
        "/rental/api/create_rental",
        data=json.dumps({"user_id": target_user.id, "project_name": "X"}),
        content_type="application/json",
    )
    request.user = staff

    with patch("rental.views.RentalService") as MockService:
        instance = MockService.return_value
        instance.create_rental_request.side_effect = Exception("boom")
        response = api_create_rental(request)
        assert response.status_code == 400
        assert "boom" in response.json()["error"]


@pytest.mark.django_db
def test__rental__views__api_get_filter_options_user__returns_data():
    """api_get_filter_options_user returns owners, locations, categories from inventory_service."""
    from rental.views import api_get_filter_options_user
    from unittest.mock import patch

    rf = RequestFactory()
    user = User.objects.create_user(email="user@example.com", password="pwd")
    request = rf.get("/rental/api/filter_options_user")
    request.user = user

    with patch("rental.views.inventory_service.get_item_organizations", return_value=[{"name": "MSA"}]), \
         patch("rental.views.inventory_service.get_item_locations", return_value=[{"name": "HQ", "full_path": "HQ"}]), \
         patch("rental.views.inventory_service.get_item_categories", return_value=[{"name": "Camera"}]):
        response = api_get_filter_options_user(request)
        assert response.status_code == 200
        data = response.json()
        assert "owners" in data and data["owners"] == [{"name": "MSA"}]
        assert "locations" in data and data["locations"] == [{"name": "HQ", "full_path": "HQ"}]
        assert "categories" in data and data["categories"] == [{"name": "Camera"}]


@pytest.mark.django_db
def test__rental__views__api_get_filter_options__returns_data():
    """api_get_filter_options (staff) returns owners, locations, categories from inventory_service."""
    from rental.views import api_get_filter_options
    from unittest.mock import patch

    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    request = rf.get("/rental/api/filter_options")
    request.user = staff

    with patch("rental.views.inventory_service.get_item_organizations", return_value=[{"name": "OKMQ"}]), \
         patch("rental.views.inventory_service.get_item_locations", return_value=[{"name": "Studio", "full_path": "HQ/Studio"}]), \
         patch("rental.views.inventory_service.get_item_categories", return_value=[{"name": "Audio"}]):
        response = api_get_filter_options(request)
        assert response.status_code == 200
        data = response.json()
        assert data["owners"] == [{"name": "OKMQ"}]
        assert data["locations"] == [{"name": "Studio", "full_path": "HQ/Studio"}]
        assert data["categories"] == [{"name": "Audio"}]


@pytest.mark.django_db
def test__rental__views__api_save_template__method_not_allowed():
    """api_save_template returns 405 on non-POST method."""
    from rental.views import api_save_template

    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    request = rf.get("/rental/api/save_template")
    request.user = staff

    response = api_save_template(request)
    assert response.status_code == 405
    assert response.json()["error"] == "Method not allowed"


@pytest.mark.django_db
def test__rental__views__api_save_template__invalid_json():
    """api_save_template returns 400 for invalid JSON body."""
    from rental.views import api_save_template

    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    request = rf.post("/rental/api/save_template", data="not-json", content_type="application/json")
    request.user = staff

    response = api_save_template(request)
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid JSON data"


@pytest.mark.django_db
def test__rental__views__api_cancel_rental__success():
    """api_cancel_rental returns success when service cancels rental."""
    from rental.views import api_cancel_rental
    from unittest.mock import patch

    rf = RequestFactory()
    staff = User.objects.create_user(email="staff@example.com", password="pwd", is_staff=True)
    request = rf.post("/rental/api/cancel_rental", data=json.dumps({"rental_id": 1}), content_type="application/json")
    request.user = staff

    with patch("rental.views.RentalService") as MockService:
        instance = MockService.return_value
        instance.cancel_rental.return_value = {"success": True, "message": "cancelled"}
        response = api_cancel_rental(request)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"]
