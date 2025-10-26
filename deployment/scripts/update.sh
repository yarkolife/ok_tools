#!/bin/bash
set -e

# Update script for OK Tools production environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

if [ ! -d "$PRODUCTION_DIR" ]; then
    echo "Error: Production directory not found at $PRODUCTION_DIR"
    echo "Please run install.sh first"
    exit 1
fi

echo "=========================================="
echo "OK Tools Production Update"
echo "=========================================="
echo ""

# Pull latest code
echo "Pulling latest code from repository..."
cd "$PROJECT_DIR"
git pull origin main

# Rebuild Docker images
echo "Rebuilding Docker images..."
cd "$PRODUCTION_DIR"
docker compose build --no-cache web

# Restart containers
echo "Restarting containers..."
docker compose down
docker compose up -d

# Run migrations
echo "Running database migrations..."
docker compose exec -T web python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput

echo ""
echo "=========================================="
echo "Update Complete!"
echo "=========================================="
echo "Check logs: docker compose logs -f web"