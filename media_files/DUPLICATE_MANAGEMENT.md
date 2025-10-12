# Duplicate Video File Management

## Overview

Система управления дубликатами видеофайлов автоматически обнаруживает, анализирует и управляет дубликатами видео с одинаковыми номерами в разных хранилищах.

## Features

### 1. Automatic Detection
- **Качество-ориентированный приоритет**: ARCHIVE > PLAYOUT > CUSTOM
- **Сортировка по битрейту**: При равных типах хранилищ выбирается файл с лучшим качеством
- **Checksum verification**: Проверка идентичности файлов по контрольным суммам

### 2. Prevention System
- **Block duplicate copying**: Предотвращение копирования в архив при наличии дубля
- **Checksum verification**: Проверка контрольных сумм перед копированием
- **Quality prioritization**: Автоматический выбор лучшей версии при копировании

### 3. Admin Interface
- **Duplicate indicator**: Визуальный индикатор статуса дублей в списке
- **Filters**: Фильтрация по наличию дублей и типу версии
- **Bulk actions**: Массовые операции для управления дублями
- **Detailed view**: Детальная информация о всех версиях файла

## Usage

### Management Commands

```bash
# Find all duplicates with detailed analysis
python manage.py find_duplicates

# Find duplicates in specific storage type
python manage.py find_duplicates --storage-type ARCHIVE

# Filter by minimum bitrate
python manage.py find_duplicates --min-bitrate 5000000

# Output JSON format
python manage.py find_duplicates --json

# Report only (summary)
python manage.py find_duplicates --report-only
```

### Admin Interface

#### List View
- **Duplicate Status column**: Shows ✓ PRIMARY (2) or ⚠️ DUPLICATE
- **Has Duplicates filter**: Filter by duplicate status
- **Version Type filter**: Filter primary vs duplicate versions

#### Actions
- **Mark as primary**: Designate selected videos as primary versions
- **Delete duplicates**: Remove duplicate versions (keeps best quality)

#### Change Form
- **Duplicate Management section**: Detailed duplicate information
- **All Versions display**: Links to all versions with quality comparison

### API Integration

#### Auto-copy with Quality Selection
When copying videos for broadcast plans, the system automatically:
1. Selects the best quality version available
2. Prioritizes ARCHIVE > PLAYOUT > CUSTOM storage types
3. Chooses higher bitrate when storage types are equal
4. Logs selection decisions

#### Duplicate Prevention
When copying to ARCHIVE storage:
1. Checks for existing files with same number
2. Compares checksums if available
3. Blocks identical file copying
4. Warns about different files with same number

## Configuration

### Settings (settings.py)
```python
# Storage priority for duplicate resolution
VIDEO_STORAGE_PRIORITY = "ARCHIVE,PLAYOUT,CUSTOM"

# Prevent copying duplicates to archive
VIDEO_PREVENT_ARCHIVE_DUPLICATES = True

# Auto-detect duplicates during scanning
VIDEO_AUTO_DETECT_DUPLICATES = True
```

### Config File (docker.cfg)
```ini
[media]
# ... existing settings ...

# Video duplicate management
storage_priority = ARCHIVE,PLAYOUT,CUSTOM
prevent_archive_duplicates = True
auto_detect_duplicates = True
```

## Quality Criteria

### Primary Version Selection
1. **Storage Type Priority**: ARCHIVE (3) > PLAYOUT (2) > CUSTOM (1)
2. **Bitrate**: Higher total bitrate preferred
3. **Resolution**: Higher resolution preferred
4. **Creation Date**: Newer files preferred (tiebreaker)

### Duplicate Types
- **Identical**: Same checksum (safe to delete)
- **Different**: Different checksum (manual review needed)
- **Similar**: Same number, different characteristics

## Examples

### Finding Duplicates
```bash
$ python manage.py find_duplicates

Found 15 videos with duplicates:

Video #12345 (3 versions):
  * PRIMARY: ARCHIVE/12345_video.mp4 (10Mbps, 1920x1080, 5.2GB) ✓
  - DUPLICATE: PLAYOUT/12345_video.mp4 (10Mbps, 1920x1080, 5.2GB, same checksum)
  - DUPLICATE: CUSTOM/12345_old.mp4 (5Mbps, 1280x720, 2.1GB)

Video #67890 (2 versions):
  * PRIMARY: ARCHIVE/67890.mov (8Mbps, 1920x1080, 3.5GB) ✓
  - DUPLICATE: ARCHIVE/67890_backup.mov (8Mbps, 1920x1080, 3.5GB, different checksum!) ⚠️
```

### Admin Workflow
1. **Scan for duplicates**: Use `find_duplicates` command
2. **Review in admin**: Filter by "Has Duplicates: Yes"
3. **Mark primary**: Select best version and mark as primary
4. **Delete duplicates**: Use bulk action to remove duplicates
5. **Verify**: Check that only primary versions remain

## Technical Details

### Database Impact
- No schema changes required
- Uses existing `VideoFile.number` field for grouping
- Leverages existing `checksum` field for verification

### Performance Considerations
- Duplicate detection methods are optimized for database queries
- Primary version calculation cached per request
- Bulk operations minimize database hits

### Integration Points
- **Planung module**: Auto-copy with quality selection
- **License module**: Shows video availability and duplicates
- **Admin interface**: Comprehensive duplicate management
- **Management commands**: Automated duplicate analysis

## Troubleshooting

### Common Issues
1. **No duplicates found**: Check that videos have same `number` field
2. **Wrong primary selected**: Verify storage type configuration
3. **Copy blocked**: Check if identical file already exists in destination

### Debug Commands
```bash
# Check specific video number
python manage.py find_duplicates --storage-type ARCHIVE

# Verify checksums
python manage.py verify_integrity

# Test auto-copy logic
python manage.py copy_to_playout --dry-run
```

## Future Enhancements

### Planned Features
- **Automatic cleanup**: Scheduled duplicate removal
- **Quality scoring**: Advanced quality metrics
- **Migration tools**: Help migrate from old duplicate management
- **API endpoints**: REST API for duplicate management
- **Notification system**: Alerts for new duplicates

### Configuration Options
- **Custom quality weights**: Adjustable quality scoring
- **Retention policies**: Automatic duplicate cleanup rules
- **Storage quotas**: Prevent excessive duplicates
- **Backup verification**: Cross-storage integrity checks
