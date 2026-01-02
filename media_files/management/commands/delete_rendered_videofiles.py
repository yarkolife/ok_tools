"""Delete rendered/preview VideoFile records (optionally with physical files).

This command is meant to clean up generated versions created by the rendering pipeline,
e.g. entries under `file_path` starting with `rendered/`.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from media_files.models import StorageLocation, VideoFile


class Command(BaseCommand):
    """Delete rendered/preview VideoFile records."""

    help = _("Delete rendered/preview VideoFile records (optionally delete physical files).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--number",
            type=int,
            help=_("Only delete rendered records for this video number."),
        )
        parser.add_argument(
            "--storage-id",
            type=int,
            help=_("Only delete records in this StorageLocation ID."),
        )
        parser.add_argument(
            "--storage-name",
            type=str,
            help=_("Only delete records in StorageLocation with this exact name."),
        )
        parser.add_argument(
            "--only-preview",
            action="store_true",
            help=_("Only delete preview outputs (file_path contains '__preview__')."),
        )
        parser.add_argument(
            "--style",
            type=str,
            help=_("Only delete records under rendered/<style>/... (matches substring)."),
        )
        parser.add_argument(
            "--encode",
            type=str,
            help=_("Only delete records under rendered/.../<encode>/... (matches substring)."),
        )
        parser.add_argument(
            "--delete-files",
            action="store_true",
            help=_("Also delete physical files from disk when they exist."),
        )
        parser.add_argument(
            "--preview",
            type=int,
            default=25,
            help=_("How many records to print in dry-run preview (default: 25)."),
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help=_("Actually delete records. Without this flag, runs in dry-run mode."),
        )

    def handle(self, *args, **options):
        number = options.get("number")
        storage_id = options.get("storage_id")
        storage_name = options.get("storage_name")
        only_preview = bool(options.get("only_preview"))
        style = (options.get("style") or "").strip()
        encode = (options.get("encode") or "").strip()
        delete_files = bool(options.get("delete_files"))
        preview_n = int(options.get("preview") or 0)
        apply = bool(options.get("yes"))

        storages = StorageLocation.objects.all()
        if storage_id is not None:
            storages = storages.filter(id=storage_id)
        if storage_name:
            storages = storages.filter(name=storage_name)
        if (storage_id is not None or storage_name) and not storages.exists():
            raise CommandError(_("No storage locations match the provided filter(s)."))

        qs = VideoFile.objects.select_related("storage_location").filter(file_path__startswith="rendered/")
        if storage_id is not None or storage_name:
            qs = qs.filter(storage_location__in=storages)
        if number is not None:
            qs = qs.filter(number=int(number))
        if only_preview:
            qs = qs.filter(file_path__contains="__preview__")
        if style:
            qs = qs.filter(file_path__contains=f"/{style}/")
        if encode:
            qs = qs.filter(file_path__contains=f"/{encode}/")

        total = qs.count()
        self.stdout.write(self.style.MIGRATE_HEADING(_("Rendered VideoFile deletion summary")))
        self.stdout.write(_("Matched rendered VideoFile records: {}").format(total))
        if only_preview:
            self.stdout.write(_("Mode: preview only"))
        if number is not None:
            self.stdout.write(_("Number filter: {}").format(number))
        if storage_id is not None:
            self.stdout.write(_("Storage id filter: {}").format(storage_id))
        if storage_name:
            self.stdout.write(_("Storage name filter: {}").format(storage_name))
        if style:
            self.stdout.write(_("Style filter: {}").format(style))
        if encode:
            self.stdout.write(_("Encode filter: {}").format(encode))
        if delete_files:
            self.stdout.write(_("Physical file deletion: enabled"))

        if not apply:
            self.stdout.write(self.style.WARNING(_("DRY RUN - no changes will be made (pass --yes to apply).")))
            if preview_n > 0 and total > 0:
                self.stdout.write(_("Preview (newest first):"))
                for v in qs.order_by("-created_at", "-id")[:preview_n]:
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

        deleted_records = 0
        deleted_files = 0
        failed_files = 0

        # Delete newest first (mostly irrelevant, but nicer for logs).
        for v in qs.order_by("-created_at", "-id"):
            if delete_files:
                full_path = None
                try:
                    full_path = v.full_path
                except Exception:
                    full_path = None

                if full_path and os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        deleted_files += 1
                    except Exception:
                        failed_files += 1

            v.delete()
            deleted_records += 1

        self.stdout.write(self.style.SUCCESS(_("Deleted VideoFile records: {}").format(deleted_records)))
        if delete_files:
            self.stdout.write(_("Deleted files from disk: {}").format(deleted_files))
            if failed_files:
                self.stdout.write(self.style.WARNING(_("Failed to delete files: {}").format(failed_files)))


