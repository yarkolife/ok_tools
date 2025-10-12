# Weekly Folders Support

## Overview

Система автоматически создает недельные папки в playout хранилище при копировании видео для трансляции. Папки создаются в формате `YYYY_KW_WW` (например, `2025_KW_41`).

## How It Works

### Automatic Week Detection
- **Дата планирования**: 8.10.2025 (среда)
- **ISO неделя**: 41 (2025)
- **Папка**: `2025_KW_41`
- **Полный путь**: `/mnt/nas/playout/2025_KW_41/99999_test_video.mp4`

### Auto-Copy from Planning
When you save a broadcast plan (click "Speichern" in planning interface):
1. System detects the planning date
2. Calculates ISO week number
3. Creates week folder if it doesn't exist
4. Copies video to the correct weekly subfolder

### Manual Copy from Admin
When copying videos manually from Django Admin:
- Uses current date if no specific date provided
- Creates appropriate week folder automatically

## Examples

### Planning Date: 8.10.2025 (Wednesday)
```
Video: 99999_test_video.mp4
Destination: /mnt/nas/playout/2025_KW_41/99999_test_video.mp4
```

### Planning Date: 15.10.2025 (Wednesday) 
```
Video: 12345_documentary.mp4
Destination: /mnt/nas/playout/2025_KW_42/12345_documentary.mp4
```

### Manual Copy Today (Current Week)
```
Video: 67890_report.mp4
Destination: /mnt/nas/playout/2025_KW_41/67890_report.mp4
```

## Technical Details

### Function: `get_week_folder_for_date(date)`
```python
def get_week_folder_for_date(date):
    """Get week folder name in format YYYY_KW_WW for given date."""
    iso_year, iso_week, _ = date.isocalendar()
    return f"{iso_year}_KW_{iso_week:02d}"
```

### Modified Functions
- **`copy_videos_for_plan()`**: Uses planning date for week determination
- **`copy_video_to_playout()`**: Uses provided date or current date
- **Automatic folder creation**: `Path(week_folder_path).mkdir(parents=True, exist_ok=True)`

### Database Changes
- **`file_path` field**: Now includes week folder (e.g., `2025_KW_41/filename.mp4`)
- **Backward compatibility**: Existing videos without week folders still work

## Usage

### From Planning Interface
1. Create/edit broadcast plan for specific date
2. Add videos to the plan
3. Click "Speichern" (Save)
4. Videos automatically copied to correct week folder

### From Django Admin
1. Go to Media Files > Video Files
2. Select videos to copy
3. Actions > Copy to playout storage
4. Videos copied to current week folder

### Manual Command
```bash
# Copy specific video to current week
python manage.py copy_to_playout --video-number 99999

# Copy with specific date
python manage.py copy_to_playout --video-number 99999 --date 2025-10-08
```

## Configuration

### Storage Location Setup
Ensure your PLAYOUT storage location points to the root playout directory:
```
Path: /mnt/nas/playout/
```

The system will automatically create weekly subfolders as needed.

### Existing Videos
- Videos already in playout root directory remain accessible
- New copies will go into appropriate week folders
- No migration needed for existing files

## Benefits

1. **Organized Structure**: Videos organized by broadcast week
2. **Easy Cleanup**: Can delete entire weeks after broadcast
3. **Clear History**: Easy to see which videos were used when
4. **Automatic Management**: No manual folder creation needed
5. **Backward Compatible**: Existing videos still work

## Troubleshooting

### Week Folder Not Created
- Check storage location permissions
- Verify playout path is writable
- Check Django logs for errors

### Wrong Week Folder
- Verify planning date is correct
- Check system date/time settings
- ISO week calculation may differ from local calendars

### Video Not Found After Copy
- Check if file_path includes week folder
- Verify full_path property in VideoFile model
- Ensure storage location path is correct

## Calendar Week Reference

For 2025:
- KW 41: 6-12 October (Monday-Sunday)
- KW 42: 13-19 October
- KW 43: 20-26 October
- etc.

The system uses ISO 8601 week numbering (Monday as first day of week).
