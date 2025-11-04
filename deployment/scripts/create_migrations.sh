#!/bin/bash
# Script to create Django migrations for media_files and registration apps
# Run this inside the Docker container or with docker compose exec

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRODUCTION_DIR="$(dirname "$SCRIPT_DIR")/.."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Creating Django Migrations${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Check if running inside Docker or use docker compose
if [ -f /.dockerenv ] || [ -n "$DJANGO_SETTINGS_MODULE" ]; then
    echo "Running inside Docker container..."
    PYTHON_CMD="python"
    MANAGE_CMD="python manage.py"
else
    echo "Running via docker compose..."
    cd "$PRODUCTION_DIR" || exit 1
    PYTHON_CMD="docker compose exec -T web python"
    MANAGE_CMD="docker compose exec -T web python manage.py"
fi

echo ""
echo "Step 1: Checking for unapplied migrations..."
echo "=============================================="
$MANAGE_CMD makemigrations --dry-run media_files registration

echo ""
echo "Step 2: Creating migrations..."
echo "=============================="
if $MANAGE_CMD makemigrations media_files registration; then
    echo -e "${GREEN}✓ Migrations created successfully${NC}"
else
    echo -e "${RED}✗ Error creating migrations${NC}"
    exit 1
fi

echo ""
echo "Step 3: Showing migration plan..."
echo "=================================="
$MANAGE_CMD migrate --plan | grep -E "media_files|registration" | head -20

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Migrations created successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Review the created migration files in:"
echo "   - media_files/migrations/"
echo "   - registration/migrations/"
echo ""
echo "2. Apply migrations:"
echo "   docker compose exec -T web python manage.py migrate"
echo ""
