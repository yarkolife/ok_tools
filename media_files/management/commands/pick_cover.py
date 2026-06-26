"""Promote a reviewed cover candidate to the canonical cover."""

import logging

from django.core.management.base import BaseCommand

from media_files.covers.config import get_cover_config
from media_files.covers.storage import promote_variant
from media_files.models import VideoFile

logger = logging.getLogger('django')


class Command(BaseCommand):
    """Pick one of the generated candidate variants as the final cover."""

    help = ('Promote candidate vN to {number}_cover.jpg and record it on the '
            'matching VideoFiles.')

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument('--number', type=int, required=True,
                            help='License/video number.')
        parser.add_argument('--variant', type=int, required=True,
                            help='Candidate variant index (1-based).')

    def handle(self, *args, **options):
        """Execute the command."""
        config = get_cover_config()
        if not config.enabled:
            self.stderr.write(self.style.ERROR(
                'Cover generation is disabled (cover_enabled).'))
            return
        if not config.output_dir:
            self.stderr.write(self.style.ERROR('No cover output directory configured.'))
            return

        number = options['number']
        try:
            path = promote_variant(number, options['variant'], config.output_dir)
        except FileNotFoundError as exc:
            self.stderr.write(self.style.ERROR(f'Variant not found: {exc}'))
            return

        updated = (
            VideoFile.objects
            .filter(number=number)
            .exclude(is_preview=True)
            .update(thumbnail=path)
        )
        self.stdout.write(self.style.SUCCESS(
            f'Picked variant {options["variant"]} for {number} -> {path} '
            f'({updated} VideoFile(s) updated)'))
