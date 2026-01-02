"""Export a VideoPreset from database to JSON file."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from media_files.models import VideoPreset


class Command(BaseCommand):
    """Export a VideoPreset from database to JSON file."""

    help = 'Export a VideoPreset from database to JSON file'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--preset-id',
            type=int,
            help='VideoPreset ID to export',
        )
        parser.add_argument(
            '--preset-name',
            type=str,
            help='VideoPreset name to export',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output JSON file path (default: video_presets/style/<name>.json)',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        preset_id = options.get('preset_id')
        preset_name = options.get('preset_name')
        output_path = options.get('output')

        # Get preset
        if preset_id:
            try:
                preset = VideoPreset.objects.get(id=preset_id)
            except VideoPreset.DoesNotExist:
                raise CommandError(f'VideoPreset with ID {preset_id} not found')
        elif preset_name:
            try:
                preset = VideoPreset.objects.get(name=preset_name)
            except VideoPreset.DoesNotExist:
                raise CommandError(f'VideoPreset with name "{preset_name}" not found')
        else:
            raise CommandError('Either --preset-id or --preset-name is required')

        # Export to JSON
        json_data = preset.to_json_preset()

        # Determine output path
        if not output_path:
            output_dir = Path(settings.BASE_DIR) / 'media_files' / 'video_presets' / 'style'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'{preset.name}.json'
        else:
            output_path = Path(output_path)

        # Write JSON file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully exported preset "{preset.display_name}" to {output_path}'
            )
        )

