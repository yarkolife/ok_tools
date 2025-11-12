"""Management command to cleanup old FileOperation records."""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from media_files.models import FileOperation


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Cleanup old FileOperation records to prevent database bloat."""

    help = 'Delete old FileOperation records based on retention policy'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without making changes'
        )
        parser.add_argument(
            '--older-than-days',
            type=int,
            default=30,
            help='Delete SCAN operations older than N days (default: 30)'
        )
        parser.add_argument(
            '--keep-failed',
            action='store_true',
            help='Keep failed operations regardless of age'
        )
        parser.add_argument(
            '--operation-type',
            type=str,
            choices=['SCAN', 'COPY', 'MOVE', 'DELETE', 'METADATA_UPDATE', 'VERIFY'],
            help='Cleanup only specific operation type (default: SCAN only)'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        older_than_days = options['older_than_days']
        keep_failed = options['keep_failed']
        operation_type = options.get('operation_type', 'SCAN')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=older_than_days)
        
        # Build query
        query = FileOperation.objects.filter(
            operation_type=operation_type,
            performed_at__lt=cutoff_date
        )
        
        # Keep failed operations if requested
        if keep_failed:
            query = query.filter(status='SUCCESS')
        
        # Get count before deletion
        count = query.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'No {operation_type} operations older than {older_than_days} days found')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'Would delete {count} {operation_type} operation(s) older than {older_than_days} days'
                )
            )
            
            # Show sample of what would be deleted
            sample = query[:10]
            self.stdout.write('\nSample of operations that would be deleted:')
            for op in sample:
                self.stdout.write(
                    f'  - {op.operation_type} for {op.video_file.number} '
                    f'({op.performed_at.date()}, {op.get_status_display()})'
                )
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            # Delete old operations
            deleted_count, _ = query.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Deleted {deleted_count} {operation_type} operation(s) older than {older_than_days} days'
                )
            )
            logger.info(
                f'Cleaned up {deleted_count} old {operation_type} FileOperation records '
                f'(older than {older_than_days} days)'
            )
        
        # Show remaining count
        remaining = FileOperation.objects.filter(operation_type=operation_type).count()
        self.stdout.write(f'Remaining {operation_type} operations: {remaining}')

