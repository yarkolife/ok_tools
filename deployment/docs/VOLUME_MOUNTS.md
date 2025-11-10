# Volume Mounts Configuration

This document explains how to configure custom volume mounts (e.g., NAS storage) for Docker containers without modifying git-tracked files.

## Overview

The base `docker-compose.yml` files (`docker-compose.production.yml` and `docker-compose.production.no-nginx.yml`) are universal and stored in git. Individual server-specific volume mounts are configured via `docker-compose.override.yml`, which is **not** tracked in git.

## How It Works

1. **Base configuration** (`docker-compose.yml`): Contains standard mounts (static files, media, logs, backups)
2. **Override file** (`docker-compose.override.yml`): Auto-generated from `.env` variables, contains server-specific mounts
3. **Docker Compose**: Automatically merges both files when running commands

## Configuration

### Step 1: Check What's Mounted on Your Server

```bash
# Check mounted filesystems
mount | grep -E "^/dev|^/mnt"

# Check specific mount point (e.g., NAS)
ls -la /mnt/nas

# Check if mount is persistent (in /etc/fstab)
cat /etc/fstab | grep nas
```

### Step 2: Configure in `.env` File

Edit your `.env` file in the production directory and add:

```bash
# NAS mount (most common use case)
NAS_MOUNT_PATH=/mnt/nas
NAS_MOUNT_MODE=ro

# Custom mounts (optional, for additional storage)
CUSTOM_MOUNT_1_PATH=/mnt/storage1
CUSTOM_MOUNT_1_CONTAINER_PATH=/mnt/storage1
CUSTOM_MOUNT_1_MODE=ro
CUSTOM_MOUNT_1_SERVICES=web,celery_worker

CUSTOM_MOUNT_2_PATH=/mnt/storage2
CUSTOM_MOUNT_2_CONTAINER_PATH=/mnt/storage2
CUSTOM_MOUNT_2_MODE=rw
CUSTOM_MOUNT_2_SERVICES=web
```

**Variables:**
- `NAS_MOUNT_PATH`: Host path to mount (e.g., `/mnt/nas`)
- `NAS_MOUNT_MODE`: Mount mode (`ro` for read-only, `rw` for read-write)
- `CUSTOM_MOUNT_N_PATH`: Host path for custom mount #N
- `CUSTOM_MOUNT_N_CONTAINER_PATH`: Path inside container
- `CUSTOM_MOUNT_N_MODE`: Mount mode (`ro` or `rw`)
- `CUSTOM_MOUNT_N_SERVICES`: Comma-separated list of services (e.g., `web,celery_worker`)

**Note:** Leave variables empty or unset if you don't need that mount.

### Step 3: Generate Override File

The override file is automatically generated during installation and updates. To regenerate manually:

```bash
cd /path/to/production/directory
./deployment/scripts/generate-override.sh
```

Or from the project directory:

```bash
cd /path/to/ok_tools_v3
bash deployment/scripts/generate-override.sh
```

### Step 4: Apply Changes

After generating the override file, restart containers:

```bash
cd /path/to/production/directory
docker compose down
docker compose up -d
```

Or use the update script:

```bash
./update.sh
```

## Example: Mounting NAS Storage

### Server Setup (One-Time)

1. **Mount NAS on host** (if not already mounted):
   ```bash
   sudo mkdir -p /mnt/nas
   sudo mount -t cifs //nas-server/share /mnt/nas -o username=user,password=pass,uid=$(id -u),gid=$(id -g)
   ```

2. **Make mount persistent** (add to `/etc/fstab`):
   ```
   //nas-server/share /mnt/nas cifs username=user,password=pass,uid=1000,gid=1000 0 0
   ```

### Application Configuration

1. **Add to `.env`**:
   ```bash
   NAS_MOUNT_PATH=/mnt/nas
   NAS_MOUNT_MODE=ro
   ```

2. **Generate override**:
   ```bash
   ./deployment/scripts/generate-override.sh
   ```

3. **Restart containers**:
   ```bash
   docker compose down && docker compose up -d
   ```

4. **Verify mount**:
   ```bash
   docker compose exec web ls -la /mnt/nas
   ```

## Troubleshooting

### Override File Not Generated

- Check that `.env` file exists and is readable
- Verify `generate-override.sh` script exists and is executable
- Check script output for errors

### Mount Not Visible in Container

- Verify host path exists and is accessible
- Check Docker Compose logs: `docker compose logs web`
- Verify override file was generated: `cat docker-compose.override.yml`
- Check if containers were restarted after generating override

### Permission Denied

- Ensure host mount has correct permissions
- Check that user running Docker has access to mount point
- For CIFS mounts, verify `uid` and `gid` options in `/etc/fstab`

### Mount Path Doesn't Exist

The script will warn if the host path doesn't exist, but will still create the override file. Ensure the path exists before starting containers, or Docker will fail to start.

## File Locations

- **Base compose files**: `deployment/docker-compose.production.yml`, `deployment/docker-compose.production.no-nginx.yml`
- **Override file**: `docker-compose.override.yml` (in production directory, not in git)
- **Generator script**: `deployment/scripts/generate-override.sh`
- **Environment template**: `deployment/configs/*.env.template`

## Notes

- The override file is **auto-generated** - do not edit it manually
- Changes to `.env` require regenerating the override file
- The override file is **not tracked in git** (in `.gitignore`)
- Docker Compose automatically uses `docker-compose.override.yml` if it exists
- Multiple custom mounts are supported (up to 10 via `CUSTOM_MOUNT_1` through `CUSTOM_MOUNT_10`)

