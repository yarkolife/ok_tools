"""Print the adoption figures of the notification system."""

from django.core.management.base import BaseCommand
from notifications import stats
import json


class Command(BaseCommand):
    """Show whether the notification page is read and the items are closed."""

    help = 'Report notification usage: reads, closures and silenced entries'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Observation window in days (default: 30)',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Print the raw report as JSON',
        )

    def handle(self, *args, **options):
        """Build the report and write it to stdout."""
        days = max(options['days'], 1)
        report = stats.full_report(days)

        if options['json']:
            self.stdout.write(json.dumps(report, indent=2, default=str))
            return

        summary = report['summary']
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Notification usage, last {days} days'))
        self.stdout.write(
            f"  staff accounts:        {summary['staff']}\n"
            f"  with subscriptions:    {summary['with_subscriptions']}\n"
            f"  ever opened the page:  {summary['ever_opened']}\n"
            f"  opened in last 7 days: {summary['opened_last_week']}\n"
            f"  events:                {summary['events']}\n"
            f"  action items:          {summary['action_items']}\n"
            f"  marked as handled:     {summary['dismissed']}"
            f" ({summary['closed_share']}%)" if summary['closed_share']
            is not None else f"  marked as handled:     {summary['dismissed']}"
        )
        self.stdout.write(
            f"  permanently silenced:  {summary['suppressed']}\n"
            f"  enabled types:         {summary['enabled_types']}"
            f" of {summary['types']}"
        )

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Per event type'))
        header = (f'{"code":42} {"on":>3} {"events":>7} {"items":>6} '
                  f'{"done":>5} {"open":>5} {"silenced":>9} {"median h":>9}')
        self.stdout.write(header)
        for row in report['types']:
            median = '-' if row['median_hours'] is None else row['median_hours']
            events = '-' if row['expectation'] else row['events']
            self.stdout.write(
                f"{row['code']:42} {'y' if row['enabled'] else 'n':>3} "
                f"{events:>7} {row['items']:>6} {row['dismissed']:>5} "
                f"{row['open']:>5} {row['suppressed']:>9} {median:>9}"
            )

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Per staff member'))
        self.stdout.write(
            f'{"account":40} {"subs":>5} {"last opened":>13} '
            f'{"open":>5} {"done":>5}')
        for row in report['users']:
            last = ('never' if row['days_since'] is None
                    else f"{row['days_since']}d ago")
            self.stdout.write(
                f"{row['email']:40} {row['subscriptions']:>5} {last:>13} "
                f"{row['open_items']:>5} {row['dismissed_items']:>5}"
            )
