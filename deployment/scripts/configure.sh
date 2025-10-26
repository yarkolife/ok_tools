#!/bin/bash
set -e

# Configuration script for OK Tools production environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

if [ ! -d "$PRODUCTION_DIR" ]; then
    echo "Error: Production directory not found at $PRODUCTION_DIR"
    exit 1
fi

cd "$PRODUCTION_DIR"

echo "=========================================="
echo "OK Tools Production Configuration"
echo "=========================================="
echo ""

# Check if containers are running
if ! docker compose ps | grep -q "web.*Up"; then
    echo "Error: Web container is not running"
    echo "Start containers with: docker compose up -d"
    exit 1
fi

echo "Select configuration task:"
echo "1. Create additional superuser"
echo "2. Setup organizations"
echo "3. Run management command"
echo "4. Database backup"
echo "5. View logs"
echo "6. Exit"
echo ""
read -p "Enter your choice (1-6): " CHOICE

case $CHOICE in
    1)
        echo ""
        read -p "Username: " USERNAME
        read -p "Email: " EMAIL
        read -sp "Password: " PASSWORD
        echo ""
        docker compose exec -T web python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$USERNAME').exists():
    User.objects.create_superuser('$USERNAME', '$EMAIL', '$PASSWORD')
    print(f"Superuser '$USERNAME' created successfully")
else:
    print(f"User '$USERNAME' already exists")
END
        ;;
    2)
        echo "Setting up organizations..."
        docker compose exec -T web python manage.py setup_organizations
        ;;
    3)
        echo ""
        read -p "Enter management command (e.g., 'check_alerts'): " COMMAND
        docker compose exec -T web python manage.py $COMMAND
        ;;
    4)
        echo "Creating database backup..."
        BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
        docker compose exec -T db pg_dump -U oktools oktools > "$PRODUCTION_DIR/$BACKUP_FILE"
        echo "✓ Backup saved to: $BACKUP_FILE"
        ;;
    5)
        docker compose logs -f web
        ;;
    6)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac