"""Tests for the notification framework (stage 1).

They cover the mechanisms, not the catalogue: registry synchronisation, the
three gate levels, deduplication, the fact/expectation split and visibility.
"""

from datetime import time as dt_time
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from notifications import config
from notifications import registry
from notifications import selectors
from notifications.models import NotificationEvent
from notifications.models import NotificationEventTypeConfig
from notifications.models import Subscription
from notifications.models import UserNotification
from notifications.services import emit
from notifications.services import mark_done
from notifications.services import snooze
from notifications.services import suppress
from notifications.services import suppress_events
from notifications.services import wake
from notifications.tasks import run_scan
from notifications.visibility import can_view
import pytest


AGING = 'licenses.unconfirmed_aging'
NEW_LICENSE = 'licenses.new_unconfirmed'
RETURN_DUE = 'rental.return_due_today'


@pytest.fixture(scope='function')
def staff_user(db):
    """Return a staff user without any special permission."""
    User = get_user_model()
    return User.objects.create_user(
        'staff@example.org', password='secret', is_staff=True)


@pytest.fixture(scope='function')
def licenses_staff(staff_user):
    """Return a staff user who may view licenses in the admin."""
    permission = Permission.objects.get(
        content_type__app_label='licenses', codename='view_license')
    staff_user.user_permissions.add(permission)
    # Permissions are cached on the instance after the first check.
    return get_user_model().objects.get(pk=staff_user.pk)


@pytest.fixture(scope='function')
def synced(db):
    """Make sure the configuration table mirrors the registry."""
    config.sync_event_type_configs()


@pytest.fixture(scope='function')
def aged_license(license):
    """Return a license old enough for the aging check to report it."""
    # update() bypasses both auto_now_add and the save() guard.
    license.__class__.objects.filter(pk=license.pk).update(
        created_at=timezone.now() - timedelta(days=60))
    return license.__class__.objects.get(pk=license.pk)


def test_registry_declares_all_three_mechanisms():
    """Every mechanism of stage 1 is represented in the registry."""
    codes = {event_type.code for event_type in registry.all_types()}
    assert {NEW_LICENSE, AGING, RETURN_DUE} <= codes

    assert registry.get(NEW_LICENSE).source == registry.SOURCE_SIGNAL
    assert registry.get(AGING).source == registry.SOURCE_SCAN
    assert registry.get(RETURN_DUE).expectation is True


def test_sync_creates_a_row_per_event_type(db):
    """Synchronisation fills the configuration table from the registry."""
    NotificationEventTypeConfig.objects.all().delete()
    config.sync_event_type_configs()

    stored = set(
        NotificationEventTypeConfig.objects.values_list('code', flat=True))
    assert {event_type.code for event_type in registry.all_types()} <= stored


def test_sync_keeps_administrator_decisions(db, synced):
    """A second run must not switch a disabled check back on."""
    NotificationEventTypeConfig.objects.filter(code=AGING).update(enabled=False)

    config.sync_event_type_configs()

    assert config.is_enabled(AGING) is False


def test_emit_is_idempotent(db, synced, license):
    """The same deduplication key must not create a second event."""
    first = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    second = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})

    assert first is not None
    assert first.pk == second.pk
    assert NotificationEvent.objects.filter(event_type=NEW_LICENSE).count() == 1


def test_disabled_type_produces_nothing(db, synced, license):
    """Gate level 2 stops the event from being created at all."""
    NotificationEventTypeConfig.objects.filter(
        code=NEW_LICENSE).update(enabled=False)

    assert emit(NEW_LICENSE, obj=license) is None
    assert not NotificationEvent.objects.filter(event_type=NEW_LICENSE).exists()


def test_scan_skips_disabled_checks(db, synced):
    """A disabled check is not executed, and the scan reports it as skipped."""
    NotificationEventTypeConfig.objects.filter(code=AGING).update(enabled=False)

    result = run_scan()

    assert result['skipped'] >= 1
    assert AGING not in result['per_type']


def test_expectations_are_never_stored(db, synced):
    """Expectation checks produce no rows, whatever they find."""
    run_scan()

    assert not NotificationEvent.objects.filter(
        event_type=RETURN_DUE).exists()


def test_message_is_rendered_from_the_payload(db, synced, license):
    """The text is built at read time, not stored in the database."""
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})

    assert str(license.number) in event.message
    assert license.title in event.message


def test_feed_only_shows_subscribed_modules(db, synced, licenses_staff,
                                            license):
    """Without a subscription the feed stays empty."""
    emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})

    assert selectors.feed(licenses_staff).count() == 0

    Subscription.objects.create(
        user=licenses_staff, module='licenses',
        event_type=Subscription.ALL_TYPES)

    assert selectors.feed(licenses_staff).count() == 1


def test_visibility_mirrors_the_admin(db, synced, staff_user, license):
    """A subscription cannot show what the admin itself would hide."""
    emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    Subscription.objects.create(
        user=staff_user, module='licenses',
        event_type=Subscription.ALL_TYPES)

    # The user is staff but has no permission on licenses.
    assert can_view(staff_user, registry.get(NEW_LICENSE)) is False
    assert selectors.feed(staff_user).count() == 0


def test_subscribing_backfills_open_action_items(db, synced, licenses_staff,
                                                 license):
    """Somebody who subscribes later still sees what is still open."""
    emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    assert UserNotification.objects.filter(user=licenses_staff).count() == 0

    selectors.set_subscriptions(licenses_staff, ['licenses'], [])

    assert UserNotification.objects.filter(user=licenses_staff).count() == 1


def test_non_staff_sees_nothing(db, synced, user):
    """A subscription may never widen access beyond the admin itself."""
    assert can_view(user, registry.get(NEW_LICENSE)) is False


def test_suppressed_object_produces_no_event(db, synced, license):
    """A silenced object stops producing events, also in a later period."""
    suppress(NEW_LICENSE, license)

    assert emit(NEW_LICENSE, obj=license) is None
    assert not NotificationEvent.objects.filter(event_type=NEW_LICENSE).exists()


def test_suppressing_clears_the_item_for_everyone(db, synced, licenses_staff,
                                                  license):
    """Silencing closes the open item instead of leaving it hanging."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    assert selectors.action_count(licenses_staff) == 1

    silenced = suppress_events([event.pk], user=licenses_staff)

    assert silenced == 1
    assert selectors.action_count(licenses_staff) == 0
    assert selectors.feed(licenses_staff).count() == 0


def test_suppression_survives_the_next_scan(db, synced, licenses_staff,
                                            aged_license):
    """The point of silencing: the periodic check stops raising it again."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    run_scan()
    event = NotificationEvent.objects.filter(event_type=AGING).first()
    assert event is not None

    suppress_events([event.pk], user=licenses_staff)
    NotificationEvent.objects.filter(pk=event.pk).delete()
    run_scan()

    assert not NotificationEvent.objects.filter(
        event_type=AGING, object_id=event.object_id).exists()


def test_filter_by_age_narrows_the_list(db, synced, licenses_staff, license):
    """Filtering by age is what makes a bulk action usable."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})

    assert selectors.open_action_items(
        licenses_staff, None, {'older': 30}).count() == 0

    NotificationEvent.objects.filter(pk=event.pk).update(
        occurred_at=timezone.now() - timedelta(days=90))

    assert selectors.open_action_items(
        licenses_staff, None, {'older': 30}).count() == 1


def test_filter_by_module_and_type(db, synced, licenses_staff, license):
    """Module and type filters address the right rows."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})

    assert selectors.open_action_items(
        licenses_staff, None, {'module': 'licenses'}).count() == 1
    assert selectors.open_action_items(
        licenses_staff, None, {'module': 'rental'}).count() == 0
    assert selectors.open_action_items(
        licenses_staff, None, {'type': AGING}).count() == 0


def test_mark_done_handles_several_entries(db, synced, licenses_staff,
                                           aged_license):
    """The bulk action closes every selected entry in one statement."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    run_scan()
    ids = list(
        selectors.open_action_items(licenses_staff)
        .values_list('event_id', flat=True))
    assert len(ids) >= 1

    changed = mark_done(licenses_staff, ids)

    assert changed == len(ids)
    assert selectors.action_count(licenses_staff) == 0


def test_snoozing_hides_an_item_until_tomorrow(db, synced, licenses_staff,
                                               license):
    """Postponing takes the entry out of today's list, not out of the world."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    assert selectors.action_count(licenses_staff) == 1

    postponed = snooze(licenses_staff, [event.pk])

    assert postponed == 1
    assert selectors.action_count(licenses_staff) == 0
    assert selectors.snoozed_action_items(licenses_staff).count() == 1


def test_snooze_wakes_up_at_the_summary_time(db, synced, licenses_staff,
                                             license):
    """The item comes back for tomorrow's summary, not after 24 hours."""
    from notifications.models import NotificationConfig
    from notifications.services import next_digest_moment

    config_obj = NotificationConfig.get_config()
    config_obj.digest_time = dt_time(10, 0)
    config_obj.save()

    moment = next_digest_moment()

    assert moment.date() == timezone.localdate() + timedelta(days=1)
    assert timezone.localtime(moment).hour == 10


def test_a_passed_snooze_shows_the_item_again(db, synced, licenses_staff,
                                              license):
    """Once the moment has come the entry is back in the list by itself."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    snooze(licenses_staff, [event.pk])
    assert selectors.action_count(licenses_staff) == 0

    UserNotification.objects.filter(user=licenses_staff).update(
        snoozed_until=timezone.now() - timedelta(minutes=1))

    assert selectors.action_count(licenses_staff) == 1


def test_select_all_on_the_postponed_view_takes_the_postponed(
        db, synced, licenses_staff, license, client):
    """"Everything" means the postponed items there; the open list is empty."""
    licenses_staff.is_superuser = True
    licenses_staff.save()
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    snooze(licenses_staff, [event.pk])

    client.force_login(licenses_staff)
    client.post('/admin/notifications/', {
        'action': 'wake', 'select_all': '1', 'view': 'snoozed',
        'filter_query': ''})

    assert selectors.action_count(licenses_staff) == 1
    assert selectors.snoozed_action_items(licenses_staff).count() == 0


def test_reopening_undoes_marking_as_handled(db, synced, licenses_staff,
                                             license, client):
    """Closing is one click, often a bulk one — it has to be reversible."""
    licenses_staff.is_superuser = True
    licenses_staff.save()
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    mark_done(licenses_staff, [event.pk])
    assert selectors.action_count(licenses_staff) == 0

    client.force_login(licenses_staff)
    client.post('/admin/notifications/', {
        'action': 'reopen', 'select_all': '1', 'view': 'handled',
        'filter_query': ''})

    assert selectors.action_count(licenses_staff) == 1
    assert selectors.handled_action_items(licenses_staff).count() == 0


def test_the_chronicle_shows_the_personal_state(db, synced, licenses_staff,
                                                license):
    """A chronicle full of finished work must say so, not look actionable."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})

    assert selectors.status_by_event(
        licenses_staff, [event]) == {event.pk: 'open'}

    mark_done(licenses_staff, [event.pk])

    assert selectors.status_by_event(
        licenses_staff, [event]) == {event.pk: 'handled'}


def test_waking_brings_a_postponed_item_back(db, synced, licenses_staff,
                                             license):
    """Postponing must be reversible without waiting for tomorrow."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    event = emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    snooze(licenses_staff, [event.pk])

    assert wake(licenses_staff, [event.pk]) == 1
    assert selectors.action_count(licenses_staff) == 1
    assert selectors.snoozed_action_items(licenses_staff).count() == 0


def test_unsubscribing_empties_the_counter(db, synced, licenses_staff,
                                           license):
    """The counter has to follow the subscriptions, or the switch is a lie."""
    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    emit(NEW_LICENSE, obj=license, payload={
        'number': license.number, 'title': license.title})
    assert selectors.action_count(licenses_staff) == 1

    selectors.set_subscriptions(licenses_staff, ['rental'], [])
    assert selectors.action_count(licenses_staff) == 0

    selectors.set_subscriptions(licenses_staff, ['licenses'], [])
    assert selectors.action_count(licenses_staff) == 1


def test_subscriptions_live_on_their_own_page(db, synced, licenses_staff,
                                              client):
    """Subscriptions are set once; they must not clutter the daily screen."""
    licenses_staff.is_superuser = True
    licenses_staff.save()
    client.force_login(licenses_staff)

    feed = client.get('/admin/notifications/').content.decode()
    assert 'name="codes"' not in feed
    assert '/admin/notifications/subscriptions/' in feed

    page = client.get('/admin/notifications/subscriptions/')
    assert page.status_code == 200
    assert 'name="codes"' in page.content.decode()

    client.post('/admin/notifications/subscriptions/', {
        'action': 'preset', 'preset': 'verleih'})

    assert set(
        Subscription.objects.filter(user=licenses_staff)
        .values_list('module', flat=True)) == {'rental'}


def test_preset_subscribes_to_its_modules(db, synced, staff_user):
    """Presets are just a set of checkboxes, applied in one click."""
    applied = selectors.apply_preset(staff_user, 'redaktion')

    assert applied == ['licenses', 'planung', 'austausch']
    assert set(
        Subscription.objects.filter(user=staff_user)
        .values_list('module', flat=True)
    ) == {'licenses', 'planung', 'austausch'}
