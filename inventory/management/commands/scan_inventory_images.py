"""Scan the mounted photos folder and index inventory item images.

Two layouts are supported side by side:

* ``<base_dir>/<inventory_number>/photo.jpg`` -- a sub-folder named after an
  :class:`InventoryItem.inventory_number` holding one or more photos.
* ``<base_dir>/<inventory_number>.jpg`` -- a photo placed directly in the base
  folder whose filename (without extension) equals the inventory number.
  Multiple photos of the same item use an ``_`` suffix, e.g.
  ``<inventory_number>_1.jpg``, ``<inventory_number>_2.jpg``.

Every image file with a supported extension is upserted into
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

        self.created = 0
        self.updated = 0
        self.thumbs = 0
        self.seen_ids = set()

        for entry in sorted(base_dir.iterdir()):
            if entry.is_dir():
                # Layout A: <base>/<inventory_number>/photo.jpg
                item_id = items_by_number.get(entry.name)
                if item_id is None:
                    self.stdout.write(
                        f'  skip: no item for folder "{entry.name}"')
                    continue
                for file in sorted(entry.iterdir()):
                    if not file.is_file():
                        continue
                    if file.suffix.lstrip('.').lower() not in extensions:
                        continue
                    self._index_file(
                        item_id, f'{entry.name}/{file.name}', file, now)
            elif entry.is_file():
                # Layout B: <base>/<inventory_number>[_suffix].jpg
                if entry.suffix.lstrip('.').lower() not in extensions:
                    continue
                item_id = self._match_root_file(entry.stem, items_by_number)
                if item_id is None:
                    self.stdout.write(
                        f'  skip: no item for file "{entry.name}"')
                    continue
                self._index_file(item_id, entry.name, entry, now)

        # Handle records whose files were not seen this run.
        stale = InventoryItemImage.objects.exclude(id__in=self.seen_ids)
        for image in stale:
            delete_thumbnail(image)
        if prune:
            missing = stale.count()
            stale.delete()
        else:
            missing = stale.filter(is_available=True).update(
                is_available=False)

        self.stdout.write(self.style.SUCCESS(
            f'Scan complete: {self.created} created, {self.updated} updated, '
            f'{self.thumbs} thumbnails, '
            f'{missing} {"pruned" if prune else "marked unavailable"}.'))

    @staticmethod
    def _match_root_file(stem, items_by_number):
        """Resolve an item id from a base-folder filename stem.

        Tries the full stem first (``OK-000001``), then strips ``_`` suffixes
        from the right one at a time (``OK-000001_1`` -> ``OK-000001``) so
        multiple photos of one item are all attributed to it. Returns the item
        id or ``None`` when no inventory number matches.
        """
        candidate = stem
        while True:
            item_id = items_by_number.get(candidate)
            if item_id is not None:
                return item_id
            if '_' not in candidate:
                return None
            candidate = candidate.rsplit('_', 1)[0]

    def _index_file(self, item_id, relative_path, file, now):
        """Upsert one image file and refresh its thumbnail."""
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
        self.seen_ids.add(obj.id)
        if was_created:
            self.created += 1
        else:
            self.updated += 1

        # Build/refresh the cached thumbnail for fast, uniform display.
        if ensure_thumbnail(obj) is not None:
            self.thumbs += 1
