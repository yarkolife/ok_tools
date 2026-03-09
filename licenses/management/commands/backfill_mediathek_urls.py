from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q

from licenses.models import License
from licenses.tasks import refresh_license_mediathek_url


class Command(BaseCommand):
    help = 'Queue mediathek URL backfill tasks for licenses in a date range.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--from-date',
            dest='from_date',
            default='2025-01-01',
            help='Start date YYYY-MM-DD (default: 2025-01-01).',
        )
        parser.add_argument(
            '--to-date',
            dest='to_date',
            default=None,
            help='End date YYYY-MM-DD (default: today).',
        )
        parser.add_argument(
            '--only-store',
            action='store_true',
            default=True,
            help='Include only licenses with store_in_ok_media_library=True (default: enabled).',
        )

    def handle(self, *args, **options):
        from licenses.tasks import _parse_iso_date  # local import to reuse existing parser

        start_date = _parse_iso_date(options['from_date'])
        end_date = _parse_iso_date(options['to_date']) if options.get('to_date') else date.today()
        if not start_date or not end_date or start_date > end_date:
            self.stderr.write(self.style.ERROR('Invalid date range'))
            return

        numbers = set()

        try:
            from contributions.models import Contribution

            contribution_numbers = Contribution.objects.filter(
                broadcast_date__date__gte=start_date,
                broadcast_date__date__lte=end_date,
            ).values_list('license__number', flat=True)
            numbers.update(int(n) for n in contribution_numbers if n is not None)
        except (ImportError, RuntimeError, ModuleNotFoundError):
            pass

        try:
            from licenses.tasks import _collect_license_numbers_from_planung

            numbers.update(_collect_license_numbers_from_planung(start_date, end_date))
        except Exception:
            pass

        filters = Q(number__in=list(numbers))
        if options.get('only_store', True):
            filters &= Q(store_in_ok_media_library=True)

        queryset = License.objects.filter(filters).only('number')
        queued = 0
        for license_obj in queryset:
            refresh_license_mediathek_url.delay(int(license_obj.number), force=False)
            queued += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Queued {queued} mediathek URL refresh tasks for {start_date}..{end_date}.'
            )
        )
