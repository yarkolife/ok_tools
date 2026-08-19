"""Close out Celery tasks whose worker disappeared mid-run."""

from django.core.management.base import BaseCommand
from ok_tools.celery_health import cleanup_orphaned_task_results


class Command(BaseCommand):
    help = (
        'Mark TaskResult rows that are still PROGRESS/STARTED, but are not held '
        'by any live Celery worker, as FAILURE.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than-minutes',
            type=int,
            default=60,
            help='Only consider tasks created more than this many minutes ago (default: 60).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be closed without changing anything.',
        )

    def handle(self, *args, **options):
        summary = cleanup_orphaned_task_results(
            older_than_minutes=options['older_than_minutes'],
            dry_run=options['dry_run'],
        )
        if summary['skipped']:
            self.stdout.write(self.style.WARNING(
                'No Celery worker answered; nothing was changed.'
            ))
            return
        if options['dry_run']:
            self.stdout.write(
                f"Would close {summary['orphaned']} orphaned task(s)."
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Closed {summary['closed']} orphaned task(s)."
            ))
