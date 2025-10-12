"""Management command for automated scanning of video storage."""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from media_files.models import StorageLocation


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Automated scanning of video storage locations."""

    help = 'Automatically scan all active storage locations for new videos'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--storage-type',
            type=str,
            help='Scan only specific storage type (ARCHIVE, PLAYOUT, CUSTOM)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rescan even if recently scanned'
        )
        parser.add_argument(
            '--calculate-checksums',
            action='store_true',
            help='Calculate checksums for found files (slow)'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        storage_type = options.get('storage_type')
        force = options['force']
        calculate_checksums = options['calculate_checksums']
        
        # Get storage locations to scan
        storages = StorageLocation.objects.filter(is_active=True)
        if storage_type:
            storages = storages.filter(storage_type=storage_type)
        
        if not storages.exists():
            self.stdout.write(self.style.ERROR(f'No active storage locations found'))
            return
        
        self.stdout.write(f'Starting automatic scan of {storages.count()} storage location(s)')
        
        total_scanned = 0
        total_created = 0
        total_updated = 0
        total_errors = 0
        
        for storage in storages:
            self.stdout.write(f'\nScanning: {storage.name} ({storage.storage_type})')
            
            # Import here to avoid circular imports
            from django.core.management import call_command
            from io import StringIO
            
            # Capture output from scan command
            out = StringIO()
            err = StringIO()
            
            try:
                # Build command arguments
                cmd_args = ['scan_video_storage', '--storage-id', str(storage.id)]
                if force:
                    cmd_args.append('--force')
                if calculate_checksums:
                    cmd_args.append('--calculate-checksum')
                
                # Run scan command
                call_command(*cmd_args, stdout=out, stderr=err)
                
                output = out.getvalue()
                errors = err.getvalue()
                
                if errors:
                    self.stdout.write(self.style.ERROR(f'Errors in {storage.name}: {errors}'))
                    total_errors += 1
                else:
                    # Parse output for statistics
                    lines = output.split('\n')
                    for line in lines:
                        if 'Created:' in line:
                            total_created += 1
                        elif 'Updated:' in line:
                            total_updated += 1
                        elif 'Error processing' in line:
                            total_errors += 1
                    
                    self.stdout.write(self.style.SUCCESS(f'Completed: {storage.name}'))
                    total_scanned += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to scan {storage.name}: {str(e)}'))
                total_errors += 1
                logger.error(f'Failed to scan storage {storage.name}: {str(e)}', exc_info=True)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Auto Scan Complete ==='))
        self.stdout.write(f'Storage locations scanned: {total_scanned}')
        self.stdout.write(f'New videos found: {total_created}')
        self.stdout.write(f'Videos updated: {total_updated}')
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {total_errors}'))
        
        # Log completion
        logger.info(
            f'Auto scan completed: {total_scanned} storages, '
            f'{total_created} created, {total_updated} updated, {total_errors} errors'
        )
