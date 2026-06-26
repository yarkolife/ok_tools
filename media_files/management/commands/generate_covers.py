"""Management command to (re)generate video covers in bulk."""

import logging

from django.core.management.base import BaseCommand

from media_files.covers.config import get_cover_config
from media_files.covers.service import generate_cover
from media_files.models import VideoFile

logger = logging.getLogger('django')


class Command(BaseCommand):
    """Generate cover images for video files."""

    help = 'Generate cover images ({number}_cover.jpg) for video files.'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--number',
            type=int,
            help='Generate cover for a specific video/license number.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Generate covers for all available video files.',
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Only generate for video files without a thumbnail yet.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate even if a thumbnail already exists.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of covers to generate in this run.',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        config = get_cover_config()
        if not config.enabled:
            self.stderr.write(self.style.ERROR(
                'Cover generation is disabled. Enable it in Media Files '
                'Configuration (cover_enabled).'))
            return
        if not config.output_dir:
            self.stderr.write(self.style.ERROR(
                'No cover output directory configured. Set MediaFilesConfig.'
                'cover_output_dir or the austausch thumbnail storage path.'))
            return

        qs = VideoFile.objects.filter(is_available=True).exclude(is_preview=True)

        if options.get('number') is not None:
            qs = qs.filter(number=options['number'])
        elif not options.get('all') and not options.get('missing_only'):
            self.stderr.write(self.style.ERROR(
                'Specify --number N, --all, or --missing-only.'))
            return

        if options.get('missing_only'):
            qs = qs.filter(thumbnail='')

        qs = qs.order_by('number')
        if options.get('limit'):
            qs = qs[:options['limit']]

        force = bool(options.get('force'))
        generated = skipped = failed = 0

        for video_file in qs:
            try:
                path = generate_cover(video_file, force=force, config=config)
            except Exception:
                failed += 1
                logger.exception('Cover: failed for %s', video_file.number)
                self.stderr.write(self.style.ERROR(
                    f'  [FAIL] {video_file.number}'))
                continue

            if path:
                generated += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK]   {video_file.number} -> {path}'))
            else:
                skipped += 1
                self.stdout.write(f'  [SKIP] {video_file.number}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. generated={generated} skipped={skipped} failed={failed}'))
