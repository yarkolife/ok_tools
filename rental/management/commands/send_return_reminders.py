from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rental.models import RentalConfig
from rental.models import RentalRequest
from rental.services.rental_email import send_reminder_email
import logging


logger = logging.getLogger('django')


class Command(BaseCommand):
    help = _('Send automatic return reminders for issued rentals.')

    def handle(self, **options):
        config = RentalConfig.get_config()
        if not config.auto_reminder_enabled:
            self.stdout.write(self.style.WARNING(_('Auto-reminders are disabled.')))
            return

        hours_before = config.auto_reminder_hours_before
        if hours_before <= 0:
            self.stdout.write(self.style.WARNING(_('Auto-reminder hours must be positive.')))
            return

        now = timezone.now()
        deadline = now + timezone.timedelta(hours=hours_before)

        rentals = RentalRequest.objects.filter(
            status='issued',
            requested_end_date__gte=now,
            requested_end_date__lte=deadline,
            auto_return_reminder_sent_at__isnull=True,
        ).select_related('user')

        count = 0
        for rental in rentals:
            marked = RentalRequest.objects.filter(
                pk=rental.pk,
                auto_return_reminder_sent_at__isnull=True,
            ).update(auto_return_reminder_sent_at=now)
            if not marked:
                continue

            try:
                sent = send_reminder_email(rental_request=rental)
                if sent:
                    count += 1
                else:
                    RentalRequest.objects.filter(pk=rental.pk).update(
                        auto_return_reminder_sent_at=None,
                    )
            except Exception as e:
                RentalRequest.objects.filter(pk=rental.pk).update(
                    auto_return_reminder_sent_at=None,
                )
                logger.error('Failed to send auto-reminder for rental %s: %s', rental.id, e)

        self.stdout.write(self.style.SUCCESS(
            _('Auto-reminders sent: {} rental(s)').format(count)
        ))
