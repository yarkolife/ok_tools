#!/bin/bash
set -e

# Production entrypoint for Celery worker/beat containers

echo "Starting Celery entrypoint..."

# Load legacy config file if it exists and is not a comment
if [ -n "$OKTOOLS_CONFIG_FILE" ] && [[ "$OKTOOLS_CONFIG_FILE" != \#* ]] && [ -f "$OKTOOLS_CONFIG_FILE" ]; then
    echo "Loading legacy config file: $OKTOOLS_CONFIG_FILE"
    set -o allexport
    source "$OKTOOLS_CONFIG_FILE"
    set +o allexport
else
    echo "No valid legacy config file found, continuing with environment variables."
fi

# Ensure backup directory exists and has correct permissions
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
echo "Ensuring backup directory exists: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Get current user info
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)
CURRENT_USER=$(id -un)

# Check directory permissions and ownership
if [ -d "$BACKUP_DIR" ]; then
    DIR_UID=$(stat -c '%u' "$BACKUP_DIR" 2>/dev/null || echo "unknown")
    DIR_GID=$(stat -c '%g' "$BACKUP_DIR" 2>/dev/null || echo "unknown")
    DIR_PERMS=$(stat -c '%a' "$BACKUP_DIR" 2>/dev/null || echo "unknown")
    
    echo "Backup directory info:"
    echo "  Path: $BACKUP_DIR"
    echo "  Current user: $CURRENT_USER (UID: $CURRENT_UID, GID: $CURRENT_GID)"
    echo "  Directory owner: UID $DIR_UID, GID $DIR_GID"
    echo "  Directory permissions: $DIR_PERMS"
    
    # Check if directory is writable
    if [ -w "$BACKUP_DIR" ]; then
        echo "  Status: Directory is writable"
    else
        echo "  WARNING: Directory is NOT writable by current user!"
        echo "  This will cause backup failures."
        echo ""
        echo "To fix this on the host system, run:"
        echo "  sudo chown -R $CURRENT_UID:$CURRENT_GID $BACKUP_DIR"
        echo "  sudo chmod -R 755 $BACKUP_DIR"
        echo ""
        echo "Or if the host user has a different UID, check the UID with:"
        echo "  id -u s-oktools"
        echo "and ensure the directory owner matches that UID, or change the container user UID."
    fi
else
    echo "Warning: Backup directory $BACKUP_DIR does not exist and could not be created."
fi

# Execute the command passed to the entrypoint (celery worker or beat)
echo "Executing: $@"
exec "$@"

