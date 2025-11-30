"""Management command to cleanup deleted Nextcloud videos."""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from licenses.models import NextcloudVideoFile
import logging


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Command to check and clean up deleted videos from Nextcloud."""

    help = _('Check Nextcloud for deleted videos and mark them as deleted in database')

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--delete-records',
            action='store_true',
            help=_('Delete database records after marking as deleted (default: only mark as deleted)'),
        )
        parser.add_argument(
            '--grace-period-days',
            type=int,
            default=30,
            help=_('Days to keep deleted records before removing from database (default: 30)'),
        )

    def handle(self, *args, **options):
        """Execute the command."""
        # Check if Nextcloud is enabled
        if not settings.NEXTCLOUD_ENABLED:
            self.stdout.write(
                self.style.WARNING(
                    _('Nextcloud integration is disabled. Skipping cleanup.')
                )
            )
            return

        try:
            from licenses.services.nextcloud_service import NextcloudService
            nextcloud_service = NextcloudService()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    _('Failed to initialize Nextcloud service: %(error)s') % {'error': str(e)}
                )
            )
            return

        # Get all non-deleted videos
        videos = NextcloudVideoFile.objects.filter(is_deleted=False)
        total_count = videos.count()
        deleted_count = 0
        error_count = 0

        self.stdout.write(
            _('Checking %(count)d videos in Nextcloud...') % {'count': total_count}
        )

        for video in videos:
            try:
                # Check if file exists in Nextcloud
                exists = nextcloud_service.check_file_exists(video.nextcloud_file_id)

                if not exists:
                    # File was deleted from Nextcloud
                    video.is_deleted = True
                    video.deleted_at = timezone.now()
                    video.save()
                    deleted_count += 1

                    self.stdout.write(
                        self.style.WARNING(
                            _('Marked video as deleted: %(filename)s (License %(license)s)') % {
                                'filename': video.filename,
                                'license': video.license.number
                            }
                        )
                    )

            except Exception as e:
                error_count += 1
                logger.error(
                    f'Error checking video {video.id}: {e}',
                    exc_info=True
                )
                self.stdout.write(
                    self.style.ERROR(
                        _('Error checking video %(filename)s: %(error)s') % {
                            'filename': video.filename,
                            'error': str(e)
                        }
                    )
                )

        # Optionally delete old records
        if options['delete_records']:
            grace_period = timezone.now() - timezone.timedelta(days=options['grace_period_days'])
            old_deleted = NextcloudVideoFile.objects.filter(
                is_deleted=True,
                deleted_at__lt=grace_period
            )
            old_count = old_deleted.count()
            old_deleted.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    _('Deleted %(count)d old records (deleted more than %(days)d days ago)') % {
                        'count': old_count,
                        'days': options['grace_period_days']
                    }
                )
            )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                _('Cleanup completed: %(deleted)d marked as deleted, %(errors)d errors') % {
                    'deleted': deleted_count,
                    'errors': error_count
                }
            )
        )

