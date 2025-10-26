#!/bin/bash
set -e

# Emergency Rollback Script for OK-Tools
# Quickly reverts to previous configuration in case of issues

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

echo "=========================================="
echo "OK-Tools EMERGENCY ROLLBACK"
echo "=========================================="
echo ""

# Safety check
if [ ! -d "$PRODUCTION_DIR" ]; then
    echo "Error: Production directory not found at $PRODUCTION_DIR"
    exit 1
fi

# Function to find most recent backup
find_latest_backup() {
    local backup_type="$1"
    local pattern="$2"
    
    local latest=$(find "$PRODUCTION_DIR" -maxdepth 1 -name "$pattern" -type f 2>/dev/null | sort -r | head -n 1)
    
    if [ -z "$latest" ]; then
        echo "Warning: No $backup_type backup found"
        return 1
    fi
    
    echo "$latest"
    return 0
}

# Function to confirm action
confirm_action() {
    local message="$1"
    
    echo ""
    echo "⚠️  WARNING: $message"
    read -p "Are you absolutely sure? (type 'yes' to confirm): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        echo "Rollback cancelled"
        exit 0
    fi
}

# Confirm rollback
confirm_action "This will revert to previous configuration and restart services"

cd "$PRODUCTION_DIR"

echo ""
echo "Step 1: Stopping services"
echo "=========================="
docker compose down
echo "✓ Services stopped"

echo ""
echo "Step 2: Creating emergency backup of current state"
echo "==================================================="
EMERGENCY_BACKUP_DIR="emergency_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EMERGENCY_BACKUP_DIR"

# Backup current files
if [ -f ".env" ]; then
    cp ".env" "$EMERGENCY_BACKUP_DIR/.env"
    echo "✓ Backed up current .env"
fi

if [ -f "docker-compose.yml" ]; then
    cp "docker-compose.yml" "$EMERGENCY_BACKUP_DIR/docker-compose.yml"
    echo "✓ Backed up current docker-compose.yml"
fi

echo ""
echo "Step 3: Restoring from backups"
echo "================================"

# Restore .env
ENV_BACKUP=$(find_latest_backup ".env" ".env.backup.*")
if [ $? -eq 0 ]; then
    cp "$ENV_BACKUP" ".env"
    chmod 600 ".env"
    echo "✓ Restored .env from: $(basename "$ENV_BACKUP")"
else
    echo "✗ No .env backup found - using current"
fi

# Restore docker-compose.yml
COMPOSE_BACKUP=$(find_latest_backup "docker-compose.yml" "docker-compose.yml.backup.*")
if [ $? -eq 0 ]; then
    cp "$COMPOSE_BACKUP" "docker-compose.yml"
    echo "✓ Restored docker-compose.yml from: $(basename "$COMPOSE_BACKUP")"
else
    echo "✗ No docker-compose.yml backup found - using current"
fi

# Restore Dockerfile if backup exists
DOCKERFILE_BACKUP=$(find_latest_backup "Dockerfile" "Dockerfile.backup.*")
if [ $? -eq 0 ]; then
    cp "$DOCKERFILE_BACKUP" "Dockerfile"
    echo "✓ Restored Dockerfile from: $(basename "$DOCKERFILE_BACKUP")"
fi

echo ""
echo "Step 4: Rebuilding containers with old configuration"
echo "====================================================="
docker compose build --no-cache
echo "✓ Containers rebuilt"

echo ""
echo "Step 5: Starting services"
echo "=========================="
docker compose up -d
echo "✓ Services started"

echo ""
echo "Step 6: Waiting for services to be ready"
echo "=========================================="
sleep 10

echo ""
echo "Step 7: Verifying services"
echo "==========================="

# Check service status
echo "Checking service status..."
docker compose ps

# Check web service
echo ""
echo "Checking web service..."
if docker compose exec -T web python manage.py check > /dev/null 2>&1; then
    echo "✓ Web service is healthy"
else
    echo "⚠️  Web service check failed - review logs"
fi

# Check database
echo ""
echo "Checking database connection..."
if docker compose exec -T web python manage.py migrate --plan > /dev/null 2>&1; then
    echo "✓ Database is accessible"
else
    echo "⚠️  Database check failed - review logs"
fi

echo ""
echo "=========================================="
echo "Rollback Complete!"
echo "=========================================="
echo ""
echo "Emergency backup of previous state saved to:"
echo "  $PRODUCTION_DIR/$EMERGENCY_BACKUP_DIR"
echo ""
echo "Next steps:"
echo "1. Check service logs: docker compose logs -f web"
echo "2. Verify application is accessible"
echo "3. Monitor for errors"
echo "4. Review what caused the need for rollback"
echo ""
echo "Recent logs (last 50 lines):"
echo "----------------------------"
docker compose logs --tail=50 web
echo ""
echo "If issues persist, check:"
echo "  - docker compose ps"
echo "  - docker compose logs web"
echo "  - docker compose logs celery_worker"
echo "  - docker compose logs db"