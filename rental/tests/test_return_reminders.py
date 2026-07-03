from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rental.models import RentalConfig
from rental.models import RentalRequest
import pytest


@pytest.mark.django_db
def test__rental__return_reminders__sends_once(django_user_model, settings):
    """Automatic return reminders are sent once per issued rental."""
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    user = django_user_model.objects.create_user(email='borrower@example.com', password='pwd')
    staff = django_user_model.objects.create_user(
        email='staff@example.com',
        password='pwd',
        is_staff=True,
    )
    config = RentalConfig.get_config()
    config.auto_reminder_enabled = True
    config.auto_reminder_hours_before = 24
    config.save()
    rental = RentalRequest.objects.create(
        user=user,
        created_by=staff,
        project_name='Reminder Project',
        purpose='Testing reminders',
        requested_start_date=timezone.now() - timezone.timedelta(hours=1),
        requested_end_date=timezone.now() + timezone.timedelta(hours=23),
        status='issued',
        rental_type='equipment',
    )

    call_command('send_return_reminders')

    rental.refresh_from_db()
    assert rental.auto_return_reminder_sent_at is not None
    assert len(mail.outbox) == 1

    call_command('send_return_reminders')

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test__rental__return_reminders__does_not_mark_failed_send(django_user_model, monkeypatch):
    """Failed reminder sends remain eligible for the next scheduled run."""
    user = django_user_model.objects.create_user(email='borrower-failed@example.com', password='pwd')
    staff = django_user_model.objects.create_user(
        email='staff@example.com',
        password='pwd',
        is_staff=True,
    )
    config = RentalConfig.get_config()
    config.auto_reminder_enabled = True
    config.auto_reminder_hours_before = 24
    config.save()
    rental = RentalRequest.objects.create(
        user=user,
        created_by=staff,
        project_name='Failed Reminder Project',
        purpose='Testing failed reminders',
        requested_start_date=timezone.now() - timezone.timedelta(hours=1),
        requested_end_date=timezone.now() + timezone.timedelta(hours=23),
        status='issued',
        rental_type='equipment',
    )

    monkeypatch.setattr(
        'rental.management.commands.send_return_reminders.send_reminder_email',
        lambda rental_request: False,
    )

    call_command('send_return_reminders')

    rental.refresh_from_db()
    assert rental.auto_return_reminder_sent_at is None
