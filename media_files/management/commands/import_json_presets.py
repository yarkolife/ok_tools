"""Import JSON presets from video_presets/style into database."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from media_files.models import VideoPreset, PresetOverlay


class Command(BaseCommand):
    """Import JSON presets from video_presets/style into database."""

    help = 'Import JSON presets from video_presets/style into database as templates'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--preset-name',
            type=str,
            help='Specific preset name to import (without .json extension)',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        preset_name = options.get('preset_name')
        
        style_dir = Path(settings.BASE_DIR) / 'media_files' / 'video_presets' / 'style'
        
        if not style_dir.exists():
            self.stdout.write(self.style.ERROR(f'Style directory not found: {style_dir}'))
            return
        
        # Get list of JSON files
        if preset_name:
            json_files = [style_dir / f'{preset_name}.json']
        else:
            json_files = list(style_dir.glob('*.json'))
        
        imported_count = 0
        
        for json_file in json_files:
            if not json_file.exists():
                self.stdout.write(self.style.WARNING(f'File not found: {json_file}'))
                continue
            
            try:
                self.import_preset(json_file)
                imported_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error importing {json_file.name}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully imported {imported_count} preset(s)')
        )

    def import_preset(self, json_file: Path):
        """Import a single JSON preset file."""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        name = data.get('name')
        if not name:
            raise ValueError('Preset name is required')
        
        # Check if preset already exists
        preset, created = VideoPreset.objects.get_or_create(
            name=name,
            defaults={
                'display_name': name.replace('_', ' ').title(),
                'description': f'Imported from {json_file.name}',
                'is_template': True,
                'is_public': True,
                'segment_duration': data.get('segment_duration', 5.0),
                'intro_clip_path': data.get('intro_clip') or '',
                'outro_clip_path': data.get('outro_clip') or '',
            }
        )
        
        if not created:
            # Update existing preset
            preset.segment_duration = data.get('segment_duration', 5.0)
            preset.intro_clip_path = data.get('intro_clip') or ''
            preset.outro_clip_path = data.get('outro_clip') or ''
            preset.save()
            # Delete existing overlays
            preset.overlays.all().delete()
        
        # Import overlays
        overlays_data = data.get('overlays', {})
        
        # Import intro overlays
        intro_overlays = overlays_data.get('intro', [])
        for order, overlay_data in enumerate(intro_overlays):
            self.create_overlay(preset, 'intro', order, overlay_data)
        
        # Import outro overlays
        outro_overlays = overlays_data.get('outro', [])
        for order, overlay_data in enumerate(outro_overlays):
            self.create_overlay(preset, 'outro', order, overlay_data)
        
        action = 'Created' if created else 'Updated'
        self.stdout.write(
            self.style.SUCCESS(f'{action} preset: {preset.display_name}')
        )

    def create_overlay(self, preset, segment, order, data):
        """Create a PresetOverlay from JSON data."""
        overlay_type = data.get('type', 'text')
        
        overlay = PresetOverlay(
            preset=preset,
            overlay_type=overlay_type,
            segment=segment,
            order=order,
            text_template=data.get('template', ''),
            image_path=data.get('path', ''),
            image_width=data.get('scale_w'),
            image_height=data.get('scale_h'),
            position_preset='custom',
            x_position=data.get('x', '(w-text_w)/2'),
            y_position=data.get('y', '(h-text_h)/2'),
            start_time=data.get('start', 0.0),
            end_time=data.get('end', 5.0),
            animation=data.get('animation', 'fade'),
            fade_in_duration=data.get('fade_in', 0.4),
            fade_out_duration=data.get('fade_out', 0.4),
            font_file=data.get('fontfile', 'fonts/Roboto-Regular.ttf'),
            font_size=data.get('fontsize', 48),
            font_color=data.get('fontcolor', 'white'),
            has_box=data.get('box', False),
            box_color=data.get('boxcolor', 'black@0.5'),
            box_border_width=data.get('boxborderw', 12),
        )
        overlay.save()

