from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from licenses.models import SigningSession
from licenses.models import SigningSessionStatus
from typing import Any
from datetime import timedelta


class Command(BaseCommand):
    help = _('Delete old signing sessions and expire stale pending sessions.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--retention-days',
            type=int,
            default=7,
            help='Retention in days for signed/expired/cancelled sessions (default: 7).',
        )

    def handle(self, *args: Any, **options: Any):
        retention_days = max(int(options.get('retention_days', 7)), 1)
        now = timezone.now()

        expired_pending = SigningSession.objects.filter(
            status=SigningSessionStatus.PENDING,
            expires_at__lte=now,
        )
        expired_count = expired_pending.update(status=SigningSessionStatus.EXPIRED)

        delete_before = now - timedelta(days=retention_days)
        deleted_count, _ = SigningSession.objects.filter(
            created_at__lt=delete_before,
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Expired pending sessions: {expired_count}. Deleted old sessions: {deleted_count}.'
            )
        )
