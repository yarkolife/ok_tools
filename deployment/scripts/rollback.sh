#!/bin/bash
set -e

# Emergency Rollback Script for OK-Tools
# Quickly reverts to previous configuration in case of issues

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

# Color functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

print_header "OK-Tools EMERGENCY ROLLBACK"

# Safety check
if [ ! -d "$PRODUCTION_DIR" ]; then
    print_error "Production directory not found at $PRODUCTION_DIR"
    exit 1
fi

# Function to find most recent backup directory
find_latest_backup_dir() {
    local latest=$(ls -1td "$PRODUCTION_DIR/backups/backup-"* 2>/dev/null | head -n 1)
    if [ -z "$latest" ]; then
        print_error "No backup found in $PRODUCTION_DIR/backups/"
        return 1
    fi
    echo "$latest"
    return 0
}

# Function to confirm action
confirm_action() {
    local message="$1"
    
    echo ""
    print_warning "WARNING: $message"
    read -p "Are you absolutely sure? (type 'yes' to confirm): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        print_info "Rollback cancelled"
        exit 0
    fi
}

# Confirm rollback
confirm_action "This will revert to previous configuration and restart services"

cd "$PRODUCTION_DIR"

# Find backup directory
BACKUP_DIR=$(find_latest_backup_dir)
if [ $? -ne 0 ]; then
    print_error "Cannot proceed without backup directory"
    exit 1
fi

print_success "Found backup: $(basename "$BACKUP_DIR")"

print_header "Step 1: Stopping Services"
docker compose down
print_success "Services stopped"

print_header "Step 2: Creating Emergency Backup of Current State"
EMERGENCY_BACKUP_DIR="$PRODUCTION_DIR/backups/emergency_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EMERGENCY_BACKUP_DIR"

# Backup current files
if [ -f ".env" ]; then
    cp ".env" "$EMERGENCY_BACKUP_DIR/.env"
    print_success "Backed up current .env"
fi

if [ -f "docker-compose.yml" ]; then
    cp "docker-compose.yml" "$EMERGENCY_BACKUP_DIR/docker-compose.yml"
    print_success "Backed up current docker-compose.yml"
fi

print_header "Step 3: Restoring from Backup"

# Restore .env
if [ -f "$BACKUP_DIR/.env.backup" ]; then
    cp "$BACKUP_DIR/.env.backup" ".env"
    chmod 600 ".env"
    print_success "Restored .env from backup"
else
    print_warning "No .env backup found - using current"
fi

# Restore docker-compose.yml
if [ -f "$BACKUP_DIR/docker-compose.yml.backup" ]; then
    cp "$BACKUP_DIR/docker-compose.yml.backup" "docker-compose.yml"
    print_success "Restored docker-compose.yml from backup"
else
    print_warning "No docker-compose.yml backup found - using current"
fi

# Restore database
if [ -f "$BACKUP_DIR/database.sql" ]; then
    print_info "Restoring database..."
    docker compose up -d db
    sleep 5
    
    # Wait for database to be ready
    for i in {1..30}; do
        if docker compose exec -T db pg_isready -U oktools > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Drop and recreate database
    docker compose exec -T db psql -U oktools -c "DROP DATABASE IF EXISTS oktools;" postgres 2>/dev/null || true
    docker compose exec -T db psql -U oktools -c "CREATE DATABASE oktools;" postgres 2>/dev/null || true
    
    # Restore database from backup
    docker compose exec -T db psql -U oktools oktools < "$BACKUP_DIR/database.sql" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Database restored"
    else
        print_warning "Database restoration may have failed - check logs"
    fi
else
    print_warning "No database backup found - skipping database restoration"
fi

print_header "Step 4: Rebuilding Containers with Old Configuration"
docker compose build --no-cache
print_success "Containers rebuilt"

print_header "Step 5: Starting Services"
docker compose up -d --build
print_success "Services started"

print_info "Waiting for services to be ready..."
sleep 10

print_header "Step 6: Verifying Services"

# Check service status
print_info "Checking service status..."
docker compose ps

# Check web service
print_info "Checking web service..."
if docker compose exec -T web python manage.py check > /dev/null 2>&1; then
    print_success "Web service is healthy"
else
    print_warning "Web service check failed - review logs"
fi

# Check database
print_info "Checking database connection..."
if docker compose exec -T web python manage.py migrate --plan > /dev/null 2>&1; then
    print_success "Database is accessible"
else
    print_warning "Database check failed - review logs"
fi

print_header "Rollback Complete!"

print_info "Emergency backup of previous state saved to:"
echo "  $EMERGENCY_BACKUP_DIR"
echo ""
print_info "Next steps:"
echo "1. Check service logs: docker compose logs -f web"
echo "2. Verify application is accessible"
echo "3. Monitor for errors"
echo "4. Review what caused the need for rollback"
echo ""
print_info "Recent logs (last 50 lines):"
echo "----------------------------"
docker compose logs --tail=50 web
echo ""
print_info "If issues persist, check:"
echo "  - docker compose ps"
echo "  - docker compose logs web"
echo "  - docker compose logs celery_worker"
echo "  - docker compose logs db"