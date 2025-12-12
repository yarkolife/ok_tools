"""Management command to find duplicate video files."""

import json
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from media_files.models import VideoFile, StorageLocation


class Command(BaseCommand):
    """Find and analyze duplicate video files."""

    help = 'Find duplicate video files and analyze their quality'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--storage-type',
            type=str,
            help='Filter by storage type (ARCHIVE, PLAYOUT, CUSTOM)'
        )
        parser.add_argument(
            '--min-bitrate',
            type=int,
            help='Minimum bitrate threshold in bps'
        )
        parser.add_argument(
            '--report-only',
            action='store_true',
            help='Only show report, no detailed analysis'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        # Find videos with duplicates
        duplicated_numbers = VideoFile.objects.values('number').annotate(
            count=Count('number')
        ).filter(count__gt=1).values_list('number', flat=True)

        if not duplicated_numbers:
            self.stdout.write(
                self.style.SUCCESS('No duplicate videos found.')
            )
            return

        # Filter by storage type if specified
        queryset = VideoFile.objects.filter(number__in=duplicated_numbers)
        if options['storage_type']:
            queryset = queryset.filter(storage_location__storage_type=options['storage_type'])

        # Group by number
        videos_by_number = {}
        for video in queryset.select_related('storage_location'):
            if video.number not in videos_by_number:
                videos_by_number[video.number] = []
            videos_by_number[video.number].append(video)

        # Filter by bitrate if specified
        if options['min_bitrate']:
            filtered_numbers = []
            for number, videos in videos_by_number.items():
                if any(v.total_bitrate and v.total_bitrate >= options['min_bitrate'] for v in videos):
                    filtered_numbers.append(number)
            videos_by_number = {k: v for k, v in videos_by_number.items() if k in filtered_numbers}

        if not videos_by_number:
            self.stdout.write(
                self.style.WARNING('No videos found matching criteria.')
            )
            return

        total_duplicates = sum(len(videos) - 1 for videos in videos_by_number.values())

        if options['json']:
            self._output_json(videos_by_number, total_duplicates)
        elif options['report_only']:
            self._output_report_only(videos_by_number, total_duplicates)
        else:
            self._output_detailed(videos_by_number, total_duplicates)

    def _output_json(self, videos_by_number, total_duplicates):
        """Output results in JSON format."""
        results = {
            'total_videos_with_duplicates': len(videos_by_number),
            'total_duplicate_files': total_duplicates,
            'videos': {}
        }

        for number, videos in videos_by_number.items():
            # Sort by priority: ARCHIVE > PLAYOUT > CUSTOM, then by quality
            storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
            sorted_videos = sorted(videos, key=lambda v: (
                storage_priority.get(v.storage_location.storage_type, 0),
                v.total_bitrate or 0,
                v.created_at
            ), reverse=True)

            primary = sorted_videos[0]
            duplicates = sorted_videos[1:]

            video_info = {
                'primary': {
                    'id': primary.id,
                    'filename': primary.filename,
                    'storage_location': primary.storage_location.name,
                    'storage_type': primary.storage_location.storage_type,
                    'bitrate': primary.total_bitrate,
                    'resolution': f"{primary.width}x{primary.height}" if primary.width and primary.height else None,
                    'file_size_mb': primary.file_size_mb,
                    'checksum': primary.checksum,
                },
                'duplicates': []
            }

            for dup in duplicates:
                video_info['duplicates'].append({
                    'id': dup.id,
                    'filename': dup.filename,
                    'storage_location': dup.storage_location.name,
                    'storage_type': dup.storage_location.storage_type,
                    'bitrate': dup.total_bitrate,
                    'resolution': f"{dup.width}x{dup.height}" if dup.width and dup.height else None,
                    'file_size_mb': dup.file_size_mb,
                    'checksum': dup.checksum,
                    'is_identical': primary.checksum and dup.checksum and primary.checksum == dup.checksum,
                })

            results['videos'][str(number)] = video_info

        self.stdout.write(json.dumps(results, indent=2, default=str))

    def _output_report_only(self, videos_by_number, total_duplicates):
        """Output summary report only."""
        self.stdout.write(
            self.style.SUCCESS(
                f'Found {len(videos_by_number)} videos with duplicates ({total_duplicates} duplicate files):'
            )
        )

        for number in sorted(videos_by_number.keys()):
            videos = videos_by_number[number]
            self.stdout.write(f'  Video #{number}: {len(videos)} versions')

    def _output_detailed(self, videos_by_number, total_duplicates):
        """Output detailed analysis."""
        self.stdout.write(
            self.style.SUCCESS(
                f'Found {len(videos_by_number)} videos with duplicates ({total_duplicates} duplicate files):'
            )
        )
        self.stdout.write('')

        for number in sorted(videos_by_number.keys()):
            videos = videos_by_number[number]
            
            # Sort by priority: ARCHIVE > PLAYOUT > CUSTOM, then by quality
            storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
            sorted_videos = sorted(videos, key=lambda v: (
                storage_priority.get(v.storage_location.storage_type, 0),
                v.total_bitrate or 0,
                v.created_at
            ), reverse=True)

            primary = sorted_videos[0]
            duplicates = sorted_videos[1:]

            self.stdout.write(
                self.style.SUCCESS(f'Video #{number} ({len(videos)} versions):')
            )

            # Primary version
            bitrate_str = f"{primary.total_bitrate:,} bps" if primary.total_bitrate else "Unknown"
            resolution_str = f"{primary.width}x{primary.height}" if primary.width and primary.height else "Unknown"
            size_str = f"{primary.file_size_mb} MB" if primary.file_size_mb else "Unknown"
            duration_str = str(primary.duration) if primary.duration else "Unknown"
            checksum_str = primary.checksum[:16] + "..." if primary.checksum and len(primary.checksum) > 16 else (primary.checksum or "None")
            
            self.stdout.write(
                f'  * PRIMARY (id={primary.id}): {primary.storage_location.name}/{primary.filename}'
            )
            self.stdout.write(
                f'      Path: {primary.file_path}'
            )
            self.stdout.write(
                f'      Size: {size_str}, Duration: {duration_str}, Bitrate: {bitrate_str}, Resolution: {resolution_str}'
            )
            self.stdout.write(
                f'      Checksum: {checksum_str}, Created: {primary.created_at}, Updated: {primary.updated_at}'
            )
            self.stdout.write(
                f'      Available: {primary.is_available}, Linked to license: {primary.license_id or "None"}'
            )

            # Duplicate versions
            for dup in duplicates:
                bitrate_str = f"{dup.total_bitrate:,} bps" if dup.total_bitrate else "Unknown"
                resolution_str = f"{dup.width}x{dup.height}" if dup.width and dup.height else "Unknown"
                size_str = f"{dup.file_size_mb} MB" if dup.file_size_mb else "Unknown"
                duration_str = str(dup.duration) if dup.duration else "Unknown"
                checksum_str = dup.checksum[:16] + "..." if dup.checksum and len(dup.checksum) > 16 else (dup.checksum or "None")
                
                # Check if identical by checksum
                identical_marker = ""
                if primary.checksum and dup.checksum:
                    if primary.checksum == dup.checksum:
                        identical_marker = " (IDENTICAL CHECKSUM - safe to delete)"
                    else:
                        identical_marker = " (DIFFERENT CHECKSUM - manual review needed)"
                        identical_marker = self.style.WARNING(identical_marker)
                elif not primary.checksum and not dup.checksum:
                    identical_marker = " (no checksum for comparison)"

                self.stdout.write(
                    f'  - DUPLICATE (id={dup.id}): {dup.storage_location.name}/{dup.filename}{identical_marker}'
                )
                self.stdout.write(
                    f'      Path: {dup.file_path}'
                )
                self.stdout.write(
                    f'      Size: {size_str}, Duration: {duration_str}, Bitrate: {bitrate_str}, Resolution: {resolution_str}'
                )
                self.stdout.write(
                    f'      Checksum: {checksum_str}, Created: {dup.created_at}, Updated: {dup.updated_at}'
                )
                self.stdout.write(
                    f'      Available: {dup.is_available}, Linked to license: {dup.license_id or "None"}'
                )
                
                # Show differences
                differences = []
                if primary.file_size != dup.file_size:
                    differences.append(f"size ({primary.file_size} vs {dup.file_size})")
                if primary.duration != dup.duration:
                    differences.append(f"duration ({primary.duration} vs {dup.duration})")
                if primary.file_path != dup.file_path:
                    differences.append("path")
                if primary.storage_location != dup.storage_location:
                    differences.append("storage_location")
                if primary.checksum and dup.checksum and primary.checksum != dup.checksum:
                    differences.append("checksum")
                
                if differences:
                    self.stdout.write(
                        self.style.WARNING(f'      Differences: {", ".join(differences)}')
                    )

            self.stdout.write('')

        # Summary statistics
        self._output_summary_statistics(videos_by_number)

    def _output_summary_statistics(self, videos_by_number):
        """Output summary statistics."""
        total_videos = len(videos_by_number)
        total_files = sum(len(videos) for videos in videos_by_number.values())
        total_duplicates = total_files - total_videos

        # Count by storage type
        storage_counts = {}
        identical_checksums = 0
        different_checksums = 0

        for videos in videos_by_number.values():
            for video in videos:
                storage_type = video.storage_location.storage_type
                storage_counts[storage_type] = storage_counts.get(storage_type, 0) + 1

            # Check checksums for this video
            if len(videos) > 1:
                primary = videos[0]
                for dup in videos[1:]:
                    if primary.checksum and dup.checksum:
                        if primary.checksum == dup.checksum:
                            identical_checksums += 1
                        else:
                            different_checksums += 1

        self.stdout.write(self.style.SUCCESS('Summary Statistics:'))
        self.stdout.write(f'  Total videos with duplicates: {total_videos}')
        self.stdout.write(f'  Total duplicate files: {total_duplicates}')
        self.stdout.write(f'  Total files analyzed: {total_files}')
        
        if storage_counts:
            self.stdout.write('  Files by storage type:')
            for storage_type, count in sorted(storage_counts.items()):
                self.stdout.write(f'    {storage_type}: {count}')

        if identical_checksums > 0 or different_checksums > 0:
            self.stdout.write('  Checksum analysis:')
            if identical_checksums > 0:
                self.stdout.write(f'    Identical files (safe to delete): {identical_checksums}')
            if different_checksums > 0:
                self.stdout.write(
                    self.style.WARNING(f'    Different files (manual review needed): {different_checksums}')
                )
