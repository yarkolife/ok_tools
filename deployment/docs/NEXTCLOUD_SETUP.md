# Nextcloud Integration Setup Guide

This guide explains how to configure Nextcloud for video upload integration with OK Tools.

## Prerequisites

- Nextcloud server installed and accessible
- Admin access to Nextcloud
- Docker environment with OK Tools (for running migrations)

## Step 1: Create Service Account in Nextcloud

1. Log in to your Nextcloud instance as administrator
2. Go to **Settings** → **Users**
3. Click **Add user** or **Create user**
4. Create a dedicated service account user:
   - **Username**: `ok_tools_service` (or your preferred name)
   - **Password**: Generate a strong password (you'll use App Password instead)
   - **Display name**: `OK Tools Service Account`
   - **Email**: (optional, but recommended for notifications)

## Step 2: Generate App Password

For security, use an App Password instead of the main password:

1. Log in as the service account user (`ok_tools_service`)
2. Go to **Settings** → **Security** → **Devices & sessions**
3. Scroll down to **App passwords** section
4. Click **Create new app password**
5. Enter a name: `OK Tools Video Upload`
6. Click **Create new app password**
7. **Copy the generated password immediately** - it will only be shown once!
   - Format: `xxxx-xxxx-xxxx-xxxx` (4 groups of 4 characters)

## Step 3: Create Upload Folder Structure

1. Log in as the service account user
2. Navigate to the root of your files
3. Create the folder structure:
   - Create folder: `Freistellungen`
   - Inside `Freistellungen`, create folder: `Videos`
   
   Or use the web interface:
   - Click **+** → **New folder**
   - Name: `Freistellungen`
   - Open `Freistellungen`
   - Click **+** → **New folder**
   - Name: `Videos`

4. Verify the path: `Freistellungen/Videos/` exists

**Note**: The folder will be created automatically by the application if it doesn't exist, but it's better to create it manually to ensure proper permissions.

## Step 4: Set Folder Permissions (Optional but Recommended)

If you want administrators to manage videos:

1. Right-click on the `Freistellungen` folder
2. Click **Sharing** or **Details**
3. Share with admin users/groups as needed
4. Set permissions: **Read & Write** for administrators

## Step 5: Verify WebDAV Access

WebDAV should be enabled by default in Nextcloud. To verify:

1. Check Nextcloud version (WebDAV is standard in all versions)
2. Test WebDAV URL format:
   ```
   https://your-nextcloud.com/remote.php/dav/files/USERNAME/
   ```
   Replace `USERNAME` with your service account username

3. You can test with curl (optional):
   ```bash
   curl -u ok_tools_service:APP_PASSWORD \
     https://your-nextcloud.com/remote.php/dav/files/ok_tools_service/
   ```
   Should return XML listing of files (or empty if no files)

## Step 6: Configure Environment Variables

Add the following variables to your `.env` file or Docker environment:

```bash
# Enable Nextcloud integration
NEXTCLOUD_ENABLED=true

# Nextcloud server URL (without trailing slash)
NEXTCLOUD_URL=https://your-nextcloud.example.com

# Service account username
NEXTCLOUD_USERNAME=ok_tools_service

# App password (from Step 2)
NEXTCLOUD_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Upload folder path (relative to user's root)
NEXTCLOUD_UPLOAD_FOLDER=Freistellungen/Videos

# WebDAV path template (usually don't need to change)
NEXTCLOUD_WEBDAV_PATH=/remote.php/dav/files/{username}/
```

### For Docker Deployment

If using Docker Compose, add to `docker-compose.yml`:

```yaml
services:
  web:
    environment:
      - NEXTCLOUD_ENABLED=true
      - NEXTCLOUD_URL=https://your-nextcloud.example.com
      - NEXTCLOUD_USERNAME=ok_tools_service
      - NEXTCLOUD_PASSWORD=xxxx-xxxx-xxxx-xxxx
      - NEXTCLOUD_UPLOAD_FOLDER=Freistellungen/Videos
```

Or use `.env` file in the same directory as `docker-compose.yml`.

## Step 7: Run Database Migration

After setting environment variables, run the migration:

```bash
# Inside Docker container
docker compose exec web python manage.py migrate licenses

# Or if using docker-compose directly
docker-compose exec web python manage.py migrate licenses
```

## Step 8: Test the Integration

1. Start/restart your Django application
2. Log in to OK Tools
3. Go to **Create License** (Freistellung)
4. You should see a **Video Upload** section (if `NEXTCLOUD_ENABLED=true`)
5. Try uploading a small test video file
6. Check Nextcloud to verify the file was uploaded to `Freistellungen/Videos/`

## Troubleshooting

### Issue: "Nextcloud integration is disabled"

**Solution**: Check that `NEXTCLOUD_ENABLED=true` in your environment variables.

### Issue: "Failed to upload video to Nextcloud: 401 Unauthorized"

**Solutions**:
- Verify `NEXTCLOUD_USERNAME` is correct
- Verify `NEXTCLOUD_PASSWORD` is the App Password (not the main password)
- Check that the App Password hasn't been revoked
- Ensure the service account user is active

### Issue: "Failed to upload video to Nextcloud: 404 Not Found"

**Solutions**:
- Verify `NEXTCLOUD_URL` is correct (no trailing slash)
- Check that WebDAV is enabled on your Nextcloud server
- Verify the WebDAV path format: `/remote.php/dav/files/{username}/`
- Test the WebDAV URL manually with curl

### Issue: "Failed to upload video to Nextcloud: 403 Forbidden"

**Solutions**:
- Check folder permissions in Nextcloud
- Ensure the service account has write access to the upload folder
- Verify the folder path is correct

### Issue: "Failed to ensure upload folder exists"

**Solutions**:
- The folder will be created automatically, but you can create it manually in Nextcloud
- Check that the service account has permission to create folders
- Verify the folder path doesn't contain invalid characters

### Issue: Videos upload but don't appear in Nextcloud

**Solutions**:
- Check the Nextcloud logs for errors
- Verify the upload folder path is correct
- Check file permissions in Nextcloud
- Ensure the service account has proper access

## Security Best Practices

1. **Use App Passwords**: Never use the main account password
2. **Limit Permissions**: The service account only needs access to the upload folder
3. **Regular Rotation**: Periodically rotate the App Password
4. **Monitor Access**: Check Nextcloud logs for unusual activity
5. **HTTPS Only**: Always use HTTPS for Nextcloud URL
6. **Environment Variables**: Never commit credentials to version control

## File Naming Convention

Uploaded videos are automatically named with the format:
```
{license_number}_{timestamp}_{original_filename}
```

Example:
```
12345_20250115_143022_my_video.mp4
```

This ensures:
- Unique filenames (no overwrites)
- Easy identification by license number
- Preservation of original filename

## Cleanup of Deleted Videos

The system includes an automatic cleanup command that:
- Checks if files still exist in Nextcloud
- Marks deleted files in the database
- Optionally removes old database records

To run manually:
```bash
docker compose exec web python manage.py cleanup_deleted_nextcloud_videos
```

To schedule automatic cleanup, add to Celery Beat (if Nextcloud is enabled):
```python
'cleanup_nextcloud_videos': {
    'task': 'licenses.management.commands.cleanup_deleted_nextcloud_videos',
    'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
},
```

## Disabling Nextcloud Integration

To disable the feature:

1. Set `NEXTCLOUD_ENABLED=false` in environment variables
2. Restart the application
3. Video upload forms will disappear from the UI
4. No Nextcloud-related code will execute

## Support

For issues specific to:
- **Nextcloud configuration**: Consult Nextcloud documentation
- **OK Tools integration**: Check application logs and Django admin
- **WebDAV problems**: Test WebDAV access manually with curl or a WebDAV client

