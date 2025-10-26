#!/bin/bash
set -e

# Update script for OK Tools production environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
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
git pull

# Update docker-compose files and configs in production directory
echo "Updating docker-compose files and configs..."
cd "$PROJECT_DIR"

# Determine which docker-compose file to use based on existing installation
if [ -f "$PRODUCTION_DIR/nginx.conf.template" ]; then
    echo "Detected: Production with Nginx and SSL"
    cp -f deployment/docker-compose.production.yml "$PRODUCTION_DIR/docker-compose.yml"
else
    echo "Detected: Local Network or Localhost (without Nginx)"
    cp -f deployment/docker-compose.production.no-nginx.yml "$PRODUCTION_DIR/docker-compose.yml"
fi

cp -f deployment/production.Dockerfile "$PRODUCTION_DIR/"
cp -f deployment/nginx.conf.template "$PRODUCTION_DIR/"
cp -f deployment/nginx-entrypoint.sh "$PRODUCTION_DIR/"
cp -f deployment/entrypoint.production.sh "$PRODUCTION_DIR/"

# Create configs directory if it doesn't exist and copy config files
mkdir -p "$PRODUCTION_DIR/configs"
cp -f deployment/configs/* "$PRODUCTION_DIR/configs/"

# Rebuild Docker images
echo "Rebuilding Docker images..."
cd "$PRODUCTION_DIR"
docker compose build --no-cache

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