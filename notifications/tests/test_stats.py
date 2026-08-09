"""Tests for the adoption report (stage 4).

The report is what the decision about the postponed modules rests on, so
the numbers have to be right even when nothing has happened yet.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from notifications import config
from notifications import selectors
from notifications import stats
from notifications.models import UserNotification
from notifications.services import emit
from notifications.services import mark_done
from notifications.services import snooze
from notifications.services import suppress_events
import pytest


NEW_LICENSE = 'licenses.new_unconfirmed'


@pytest.fixture(scope='function')
def synced(db):
    """Make sure the configuration table mirrors the registry."""
    config.sync_event_type_configs()


@pytest.fixture(scope='function')
def staff_user(db):
    """Return a staff user allowed to view licenses."""
    from django.contrib.auth.models import Permission

    User = get_user_model()
    user = User.objects.create_user(
        'reader@example.org', password='secret', is_staff=True)
    user.user_permissions.add(Permission.objects.get(
        content_type__app_label='licenses', codename='view_license'))
    return User.objects.get(pk=user.pk)


def test_report_is_empty_but_valid_without_any_activity(synced, db):
    """A fresh installation must not crash the report or invent numbers."""
    report = stats.full_report()

    assert report['summary']['events'] == 0
    assert report['summary']['closed_share'] is None
    assert len(report['types']) == len(stats.registry.all_types())
    assert all(row['median_hours'] is None for row in report['types'])


def test_per_type_counts_items_and_closures(synced, staff_user, license):
    """Volume and completion are counted per event type."""
    selectors.set_subscriptions(staff_user, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    mark_done(staff_user, [event.pk])

    row = next(item for item in stats.per_type_report()
               if item['code'] == NEW_LICENSE)

    assert row['events'] == 1
    assert row['items'] == 1
    assert row['dismissed'] == 1
    assert row['open'] == 0
    assert row['closed_share'] == 100
    assert row['median_hours'] is not None


def test_per_type_separates_postponed_from_open(synced, staff_user, license):
    """Postponing is not closing, and the report must not mix them up."""
    selectors.set_subscriptions(staff_user, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    snooze(staff_user, [event.pk])

    row = next(item for item in stats.per_type_report()
               if item['code'] == NEW_LICENSE)

    assert row['snoozed'] == 1
    assert row['dismissed'] == 0
    assert row['open'] == 1


def test_suppressions_are_counted_as_noise(synced, staff_user, license):
    """A type with many silenced entries is reporting the wrong thing."""
    selectors.set_subscriptions(staff_user, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    suppress_events([event.pk], user=staff_user)

    row = next(item for item in stats.per_type_report()
               if item['code'] == NEW_LICENSE)

    assert row['suppressed'] == 1
    assert stats.summary()['suppressed'] == 1


def test_window_excludes_older_events(synced, staff_user, license):
    """The observation window is what makes the numbers comparable."""
    from notifications.models import NotificationEvent

    selectors.set_subscriptions(staff_user, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    NotificationEvent.objects.filter(pk=event.pk).update(
        occurred_at=timezone.now() - timedelta(days=90))

    assert stats.summary(days=30)['events'] == 0
    assert stats.summary(days=180)['events'] == 1


def test_per_user_report_shows_reads_and_workload(synced, staff_user, license):
    """The first question of stage 4: does anybody open the page at all."""
    selectors.set_subscriptions(staff_user, ['licenses'], [])
    emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})

    row = next(item for item in stats.per_user_report()
               if item['email'] == staff_user.email)
    assert row['last_seen_at'] is None
    assert row['days_since'] is None
    assert row['open_items'] == 1

    selectors.mark_seen(staff_user)

    row = next(item for item in stats.per_user_report()
               if item['email'] == staff_user.email)
    assert row['last_seen_at'] is not None
    assert row['days_since'] == 0


def test_stats_page_is_superuser_only(synced, staff_user, client):
    """Reading who works how much is a superuser matter."""
    client.force_login(staff_user)
    response = client.get('/admin/notifications/stats/')

    assert response.status_code == 302
    assert response['Location'].endswith('/admin/notifications/')

    staff_user.is_superuser = True
    staff_user.save()
    assert client.get('/admin/notifications/stats/').status_code == 200


def test_dismissed_items_of_other_users_do_not_leak_into_a_user_row(
        synced, staff_user, license, db):
    """Per-user figures must be per user."""
    User = get_user_model()
    other = User.objects.create_user(
        'other@example.org', password='secret', is_staff=True)
    selectors.set_subscriptions(staff_user, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    mark_done(staff_user, [event.pk])

    rows = {item['email']: item for item in stats.per_user_report()}

    assert rows[staff_user.email]['dismissed_items'] == 1
    assert rows[other.email]['dismissed_items'] == 0
    assert UserNotification.objects.filter(user=other).count() == 0
