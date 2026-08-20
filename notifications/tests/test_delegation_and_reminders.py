"""Manual reminders and delegating an action item to a colleague."""

from datetime import date
from django.contrib.auth import get_user_model
from django.utils import timezone
from notifications import selectors
from notifications.checks import check_manual_reminders
from notifications.models import ManualReminder
from notifications.models import NotificationEvent
from notifications.models import Subscription
from notifications.models import UserNotification
from notifications.services import delegate
from notifications.services import revoke_delegation
import pytest


REMINDER = 'reminders.manual'


def _staff(email):
    User = get_user_model()
    return User.objects.create_user(email, password='secret', is_staff=True)


@pytest.fixture(scope='function')
def alice(db):
    return _staff('alice@example.org')


@pytest.fixture(scope='function')
def bob(db):
    return _staff('bob@example.org')


def _event(code=REMINDER, key='k1'):
    return NotificationEvent.objects.create(
        module=code.split('.')[0], event_type=code,
        category='action_required', occurred_at=timezone.now(),
        dedup_key=key, payload={},
    )


# --------------------------------------------------------------- reminders

class TestManualReminderSchedule:
    """The repeat rules decide which day a reminder is due on."""

    @pytest.mark.django_db
    def test_weekly_reminder_is_due_on_its_weekday(self):
        reminder = ManualReminder.objects.create(
            title='Send TV listings', frequency=ManualReminder.FREQUENCY_WEEKLY,
            weekday=2)
        assert reminder.is_due(date(2026, 8, 19)) is True    # Wednesday
        assert reminder.is_due(date(2026, 8, 20)) is False   # Thursday

    @pytest.mark.django_db
    def test_one_off_reminder_is_due_only_on_its_date(self):
        reminder = ManualReminder.objects.create(
            title='Yearly report', frequency=ManualReminder.FREQUENCY_ONCE,
            run_date=date(2026, 8, 20))
        assert reminder.is_due(date(2026, 8, 20)) is True
        assert reminder.is_due(date(2026, 8, 21)) is False

    @pytest.mark.django_db
    def test_monthly_reminder_falls_back_to_the_last_day(self):
        reminder = ManualReminder.objects.create(
            title='Monthly invoice',
            frequency=ManualReminder.FREQUENCY_MONTHLY, day_of_month=31)
        assert reminder.is_due(date(2026, 1, 31)) is True
        # February has no 31st, so the last day of the month is used.
        assert reminder.is_due(date(2026, 2, 28)) is True
        assert reminder.is_due(date(2026, 2, 27)) is False

    @pytest.mark.django_db
    def test_inactive_reminder_is_never_due(self):
        reminder = ManualReminder.objects.create(
            title='Paused', frequency=ManualReminder.FREQUENCY_WEEKLY,
            weekday=timezone.localdate().weekday(), active=False)
        assert reminder.is_due(timezone.localdate()) is False


class TestManualReminderCheck:

    @pytest.mark.django_db
    def test_due_reminder_produces_one_finding_per_day(self):
        ManualReminder.objects.create(
            title='Send TV listings', message='To the newspaper',
            frequency=ManualReminder.FREQUENCY_WEEKLY,
            weekday=timezone.localdate().weekday())
        findings = check_manual_reminders({})
        assert len(findings) == 1
        assert findings[0].payload['title'] == 'Send TV listings'
        assert timezone.localdate().strftime('%Y-%m-%d') in findings[0].dedup_key

    @pytest.mark.django_db
    def test_reminder_due_another_day_is_not_reported(self):
        ManualReminder.objects.create(
            title='Other day', frequency=ManualReminder.FREQUENCY_WEEKLY,
            weekday=(timezone.localdate().weekday() + 1) % 7)
        assert check_manual_reminders({}) == []


# -------------------------------------------------------------- delegation

@pytest.mark.django_db
class TestDelegation:

    def _assigned(self, alice, bob):
        event = _event()
        UserNotification.objects.create(user=alice, event=event)
        Subscription.objects.create(user=alice, module='reminders',
                                    event_type=REMINDER)
        return event

    def test_delegating_moves_the_item_to_the_colleague(self, alice, bob):
        event = self._assigned(alice, bob)
        assert delegate(alice, [event.pk], bob) == 1

        senders = UserNotification.objects.get(user=alice, event=event)
        assert senders.delegated_to_id == bob.pk
        assert senders.delegated_at is not None

        receivers = UserNotification.objects.get(user=bob, event=event)
        assert receivers.delegated_by_id == alice.pk
        assert receivers.dismissed_at is None

    def test_sender_no_longer_has_it_open_but_still_sees_it(
            self, alice, bob, rf):
        event = self._assigned(alice, bob)
        delegate(alice, [event.pk], bob)
        request = rf.get('/')
        request.user = alice

        open_ids = list(selectors.open_action_items(alice, request)
                        .values_list('event_id', flat=True))
        delegated_ids = list(selectors.delegated_action_items(alice, request)
                             .values_list('event_id', flat=True))
        assert event.pk not in open_ids
        assert event.pk in delegated_ids

    def test_receiver_sees_it_without_being_subscribed(self, alice, bob, rf):
        event = self._assigned(alice, bob)
        delegate(alice, [event.pk], bob)
        request = rf.get('/')
        request.user = bob

        assert not Subscription.objects.filter(user=bob).exists()
        open_ids = list(selectors.open_action_items(bob, request)
                        .values_list('event_id', flat=True))
        assert event.pk in open_ids

    def test_taking_it_back_restores_the_sender(self, alice, bob, rf):
        event = self._assigned(alice, bob)
        delegate(alice, [event.pk], bob)
        assert revoke_delegation(alice, [event.pk]) == 1

        senders = UserNotification.objects.get(user=alice, event=event)
        assert senders.delegated_to_id is None
        assert not UserNotification.objects.filter(
            user=bob, event=event).exists()

        request = rf.get('/')
        request.user = alice
        assert event.pk in list(selectors.open_action_items(alice, request)
                                .values_list('event_id', flat=True))

    def test_taking_back_keeps_a_copy_the_receiver_already_had(
            self, alice, bob):
        event = self._assigned(alice, bob)
        UserNotification.objects.create(user=bob, event=event)
        delegate(alice, [event.pk], bob)
        revoke_delegation(alice, [event.pk])
        # Bob was a subscriber in his own right; that copy must survive.
        assert UserNotification.objects.filter(user=bob, event=event).exists()

    def test_delegating_to_yourself_does_nothing(self, alice):
        event = self._assigned(alice, alice)
        assert delegate(alice, [event.pk], alice) == 0

    def test_delegating_to_a_non_staff_user_does_nothing(self, alice, db):
        User = get_user_model()
        outsider = User.objects.create_user('out@example.org', password='x')
        event = self._assigned(alice, outsider)
        assert delegate(alice, [event.pk], outsider) == 0
