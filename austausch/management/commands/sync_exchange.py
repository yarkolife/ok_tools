"""Management command to manually sync exchange folders."""

from django.core.management.base import BaseCommand
from austausch.tasks import sync_exchange_folders_task


class Command(BaseCommand):
    """Command to sync exchange folders manually."""
    
    help = 'Manually sync exchange folders from Nextcloud'
    
    def handle(self, *args, **options):
        """Execute sync task."""
        self.stdout.write('Starting exchange folders sync...')
        
        try:
            sync_exchange_folders_task()
            self.stdout.write(
                self.style.SUCCESS('Successfully synced exchange folders')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error syncing exchange folders: {e}')
            )
            raise

