"""Purge VideoFile database records without touching physical files.

This command is meant for production maintenance: you may want to reset the
database state after an accidental scan/import, while keeping the actual video
files on the storage untouched.
"""

from __future__ import annotations

from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db.models.signals import pre_delete
from django.utils.translation import gettext as _

from media_files.models import StorageLocation, VideoFile
from media_files.signals import log_video_deletion


def _batched_ids(qs, *, chunk_size: int) -> Iterable[list[int]]:
    """Yield primary key batches from a queryset without loading everything."""
    last_id = 0
    while True:
        batch = list(
            qs.filter(id__gt=last_id).order_by("id").values_list("id", flat=True)[:chunk_size]
        )
        if not batch:
            return
        last_id = batch[-1]
        yield batch


class Command(BaseCommand):
    """Delete VideoFile rows (database only), keeping files on disk."""

    help = _(
        "Purge VideoFile database records without deleting any physical video files."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--storage-id",
            type=int,
            help=_("Only purge records from this storage location ID."),
        )
        parser.add_argument(
            "--storage-name",
            type=str,
            help=_("Only purge records from storage locations with this exact name."),
        )
        parser.add_argument(
            "--storage-type",
            choices=["ARCHIVE", "PLAYOUT", "CUSTOM"],
            help=_("Only purge records from storages of this type."),
        )
        parser.add_argument(
            "--only-available",
            action="store_true",
            help=_("Only purge records currently marked as available."),
        )
        parser.add_argument(
            "--only-unavailable",
            action="store_true",
            help=_("Only purge records currently marked as unavailable."),
        )
        parser.add_argument(
            "--preview",
            type=int,
            default=20,
            help=_("How many records to print in dry-run preview (default: 20)."),
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=2000,
            help=_("Delete in chunks of N rows (default: 2000)."),
        )
        parser.add_argument(
            "--with-delete-log",
            action="store_true",
            help=_(
                "Keep the pre_delete logging signal enabled (slower). "
                "By default, deletion logging is disabled during purge."
            ),
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help=_("Actually delete records. Without this flag, runs in dry-run mode."),
        )

    def handle(self, *args, **options):
        storage_id: int | None = options.get("storage_id")
        storage_name: str | None = options.get("storage_name")
        storage_type: str | None = options.get("storage_type")
        only_available: bool = bool(options.get("only_available"))
        only_unavailable: bool = bool(options.get("only_unavailable"))
        preview: int = int(options.get("preview") or 0)
        chunk_size: int = int(options.get("chunk_size") or 0)
        with_delete_log: bool = bool(options.get("with_delete_log"))
        apply: bool = bool(options.get("yes"))

        if only_available and only_unavailable:
            raise CommandError(_("Use only one of --only-available / --only-unavailable."))
        if chunk_size <= 0:
            raise CommandError(_("--chunk-size must be a positive integer."))

        storages = StorageLocation.objects.all()
        if storage_id is not None:
            storages = storages.filter(id=storage_id)
        if storage_name:
            storages = storages.filter(name=storage_name)
        if storage_type:
            storages = storages.filter(storage_type=storage_type)

        if (storage_id is not None or storage_name or storage_type) and not storages.exists():
            raise CommandError(_("No storage locations match the provided filter(s)."))

        qs = VideoFile.objects.all()
        if storage_id is not None or storage_name or storage_type:
            qs = qs.filter(storage_location__in=storages)
        if only_available:
            qs = qs.filter(is_available=True)
        if only_unavailable:
            qs = qs.filter(is_available=False)

        total = qs.count()
        self.stdout.write(self.style.MIGRATE_HEADING(_("VideoFile purge summary")))
        if storage_id is not None:
            self.stdout.write(_("Storage id filter: {}").format(storage_id))
        if storage_name:
            self.stdout.write(_("Storage name filter: {}").format(storage_name))
        if storage_type:
            self.stdout.write(_("Storage type filter: {}").format(storage_type))
        if only_available:
            self.stdout.write(_("Availability filter: available only"))
        if only_unavailable:
            self.stdout.write(_("Availability filter: unavailable only"))
        self.stdout.write(_("Matched VideoFile records: {}").format(total))

        if not apply:
            self.stdout.write(self.style.WARNING(_("DRY RUN - no changes will be made (pass --yes to apply).")))
            if preview > 0 and total > 0:
                self.stdout.write(_("Preview (newest first):"))
                for v in (
                    qs.select_related("storage_location")
                    .order_by("-created_at", "-id")[:preview]
                ):
                    self.stdout.write(
                        "- id={id} number={num} storage={storage} path={path}".format(
                            id=v.id,
                            num=v.number,
                            storage=v.storage_location.name if v.storage_location_id else "-",
                            path=v.file_path,
                        )
                    )
            return

        if total == 0:
            self.stdout.write(self.style.SUCCESS(_("Nothing to delete.")))
            return

        # Speed: disable per-row delete logging by default (it creates a FileOperation
        # row for each deleted video and then cascades it away).
        if not with_delete_log:
            pre_delete.disconnect(log_video_deletion, sender=VideoFile)

        deleted_videofiles = 0
        for id_batch in _batched_ids(qs, chunk_size=chunk_size):
            # Count VideoFile rows explicitly: QuerySet.delete() returns the total number
            # of deleted objects across all cascaded models (e.g. FileOperation too).
            batch_qs = VideoFile.objects.filter(id__in=id_batch)
            deleted_videofiles += batch_qs.count()

            # Note: This deletes database rows only. Physical files are untouched.
            batch_qs.delete()

        self.stdout.write(self.style.SUCCESS(_("Deleted VideoFile records: {}").format(deleted_videofiles)))
