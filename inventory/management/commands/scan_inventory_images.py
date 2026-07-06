"""Scan the mounted photos folder and index inventory item images.

Photos are expected under ``<base_dir>/<inventory_number>/`` where the
sub-folder name matches an :class:`InventoryItem.inventory_number`. Every image
file with a supported extension is upserted into
:class:`InventoryItemImage`. Records whose files disappeared are marked
unavailable (or removed with ``--prune``).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.images import delete_thumbnail
from inventory.images import ensure_thumbnail
from inventory.models import InventoryImageConfig
from inventory.models import InventoryItem
from inventory.models import InventoryItemImage


class Command(BaseCommand):
    """Index inventory item photos from the configured mounted folder."""

    help = 'Scan the configured photos folder and index inventory item images.'

    def add_arguments(self, parser):
        """Register command line arguments."""
        parser.add_argument(
            '--prune',
            action='store_true',
            help='Delete DB records whose files are no longer on disk '
                 '(default: mark them unavailable).',
        )

    def handle(self, *args, **options):
        """Run the scan."""
        config = InventoryImageConfig.get_config()

        if not config.enabled:
            self.stdout.write(self.style.WARNING(
                'Inventory photo scanning is disabled in settings.'))
            return

        base_dir = config.get_base_dir()
        if base_dir is None:
            self.stdout.write(self.style.WARNING(
                'No valid photos folder configured (base directory missing '
                'or does not exist).'))
            return

        extensions = config.get_extensions()
        if not extensions:
            self.stdout.write(self.style.WARNING(
                'No supported image formats configured.'))
            return

        prune = options.get('prune', False)
        now = timezone.now()

        # Map inventory_number -> item id for folders we encounter.
        items_by_number = dict(
            InventoryItem.objects.values_list('inventory_number', 'id')
        )

        created = 0
        updated = 0
        thumbs = 0
        seen_ids = set()

        for sub in sorted(base_dir.iterdir()):
            if not sub.is_dir():
                continue
            item_id = items_by_number.get(sub.name)
            if item_id is None:
                self.stdout.write(
                    f'  skip: no item for folder "{sub.name}"')
                continue

            for file in sorted(sub.iterdir()):
                if not file.is_file():
                    continue
                if file.suffix.lstrip('.').lower() not in extensions:
                    continue

                relative_path = f'{sub.name}/{file.name}'
                try:
                    file_size = file.stat().st_size
                except OSError:
                    file_size = None

                obj, was_created = InventoryItemImage.objects.update_or_create(
                    item_id=item_id,
                    relative_path=relative_path,
                    defaults={
                        'filename': file.name,
                        'file_size': file_size,
                        'is_available': True,
                        'last_scanned': now,
                    },
                )
                seen_ids.add(obj.id)
                if was_created:
                    created += 1
                else:
                    updated += 1

                # Build/refresh the cached thumbnail for fast, uniform display.
                if ensure_thumbnail(obj) is not None:
                    thumbs += 1

        # Handle records whose files were not seen this run.
        stale = InventoryItemImage.objects.exclude(id__in=seen_ids)
        for image in stale:
            delete_thumbnail(image)
        if prune:
            missing = stale.count()
            stale.delete()
        else:
            missing = stale.filter(is_available=True).update(
                is_available=False)

        self.stdout.write(self.style.SUCCESS(
            f'Scan complete: {created} created, {updated} updated, '
            f'{thumbs} thumbnails, '
            f'{missing} {"pruned" if prune else "marked unavailable"}.'))
