# Weekly Folders - Quick Start

## What Changed

Videos are now automatically copied to weekly folders in playout storage:
- **Format**: `YYYY_KW_WW` (e.g., `2025_KW_41`)
- **Example**: `/mnt/nas/playout/2025_KW_41/99999_test_video.mp4`

## How It Works

### 1. Planning Interface
When you save a broadcast plan:
1. System detects planning date (e.g., 8.10.2025)
2. Calculates week number (KW 41)
3. Creates folder `2025_KW_41` if needed
4. Copies videos to correct weekly folder

### 2. Admin Interface
When copying videos manually:
- Uses current date for week determination
- Creates appropriate weekly folder automatically

## Examples

### Planning Date: 8.10.2025 (Wednesday)
```
Video: 99999_test_video.mp4
→ /mnt/nas/playout/2025_KW_41/99999_test_video.mp4
```

### Planning Date: 15.10.2025 (Wednesday)
```
Video: 12345_documentary.mp4  
→ /mnt/nas/playout/2025_KW_42/12345_documentary.mp4
```

## Quick Test

1. **Go to planning**: Create/edit plan for 8.10.2025
2. **Add video**: Add video #99999 to plan
3. **Save plan**: Click "Speichern"
4. **Check result**: Video should be in `/mnt/nas/playout/2025_KW_41/`

## Benefits

- **Organized**: Videos grouped by broadcast week
- **Easy cleanup**: Delete entire weeks after broadcast
- **Clear history**: See which videos used when
- **Automatic**: No manual folder management needed

## Existing Videos

- Videos already in playout root still work
- New copies go to weekly folders
- No migration needed

## Troubleshooting

### Video not found after copy
- Check if `file_path` includes weekly folder in database
- Verify storage location path is correct

### Wrong week folder
- Check planning date is correct
- ISO weeks may differ from local calendars

### Folder not created
- Check storage permissions
- Verify playout path is writable
