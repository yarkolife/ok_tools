# Duplicate Management - Quick Start

## 1. Find Duplicates

```bash
# Basic scan
python manage.py find_duplicates

# Filter by storage type
python manage.py find_duplicates --storage-type ARCHIVE

# JSON output for scripting
python manage.py find_duplicates --json
```

## 2. Admin Interface

### List View
- Go to **Media Files > Video Files**
- Use **Has Duplicates** filter: "Yes - has duplicates"
- Look for **Duplicate Status** column:
  - ✓ PRIMARY (2) = Best version, 2 duplicates exist
  - ⚠️ DUPLICATE = Not the best version

### Manage Duplicates
1. **Select videos** with duplicates
2. **Actions** → **Mark selected as primary version** (to designate best version)
3. **Actions** → **Delete duplicate versions** (removes duplicates, keeps best)

## 3. Auto-Copy Quality Selection

When videos are automatically copied for broadcast:
- **ARCHIVE** videos preferred over PLAYOUT
- **PLAYOUT** videos preferred over CUSTOM
- **Higher bitrate** preferred when storage types equal
- **Newer files** preferred as tiebreaker

## 4. Configuration

### Enable Duplicate Prevention
```ini
# docker.cfg
[media]
prevent_archive_duplicates = True
auto_detect_duplicates = True
storage_priority = ARCHIVE,PLAYOUT,CUSTOM
```

### Test Settings
```bash
# Restart after config changes
docker-compose restart web

# Test duplicate detection
python manage.py find_duplicates --report-only
```

## 5. Common Tasks

### Clean Up Duplicates
```bash
# 1. Find all duplicates
python manage.py find_duplicates

# 2. Review in admin interface
# 3. Use bulk actions to delete duplicates
```

### Verify Quality Selection
```bash
# Check auto-copy will select best version
python manage.py copy_to_playout --dry-run
```

### Monitor Duplicates
- Check **Video Files** list regularly
- Filter by **Has Duplicates: Yes**
- Review **Duplicate Status** column

## 6. Troubleshooting

### No Duplicates Found
- Ensure videos have same `number` field
- Check that videos are in different storage locations
- Verify `is_available=True` for all versions

### Wrong Primary Selected
- Check storage type priority in config
- Verify bitrate values are populated
- Review creation dates

### Copy Blocked
- Check if identical file exists (same checksum)
- Review error messages in admin
- Verify destination storage permissions

## 7. Best Practices

1. **Regular scanning**: Run `find_duplicates` weekly
2. **Monitor admin**: Check for new duplicates after imports
3. **Quality first**: Always prefer ARCHIVE over other storage types
4. **Verify before delete**: Review duplicates before bulk deletion
5. **Backup important**: Ensure primary versions are backed up

## 8. Integration Points

### Planung Module
- Auto-copy automatically selects best quality version
- No manual intervention needed for quality selection

### License Module
- Shows video availability including duplicates
- Links to primary version in storage

### Admin Interface
- Comprehensive duplicate management tools
- Visual indicators for easy identification
- Bulk operations for efficient cleanup
