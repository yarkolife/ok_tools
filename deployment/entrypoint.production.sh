#!/bin/bash
set -e

# Production entrypoint for OK Tools Docker container

echo "Starting OK Tools production entrypoint..."

# Load legacy config file if it exists and is not a comment
if [ -n "$OKTOOLS_CONFIG_FILE" ] && [[ "$OKTOOLS_CONFIG_FILE" != \#* ]] && [ -f "$OKTOOLS_CONFIG_FILE" ]; then
    echo "Loading legacy config file: $OKTOOLS_CONFIG_FILE"
    set -o allexport
    source "$OKTOOLS_CONFIG_FILE"
    set +o allexport
else
    echo "No valid legacy config file found, continuing with environment variables."
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
if [ -n "$SUPERUSER_USERNAME" ] && [ -n "$SUPERUSER_PASSWORD" ] && [ -n "$SUPERUSER_EMAIL" ]; then
    echo "Creating superuser if it doesn't exist..."
    python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$SUPERUSER_USERNAME', '$SUPERUSER_EMAIL', '$SUPERUSER_PASSWORD')
    print(f"Superuser '$SUPERUSER_USERNAME' created successfully")
else:
    print(f"Superuser '$SUPERUSER_USERNAME' already exists")
END
fi

# Setup organizations
echo "Setting up organizations..."
python manage.py setup_organizations || true

# Start gunicorn
echo "Starting gunicorn..."
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-4} \
    --threads ${GUNICORN_THREADS:-2} \
    --worker-class gthread \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --keep-alive 75 \
    --max-requests ${GUNICORN_MAX_REQUESTS:-1000} \
    --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info} \
    ok_tools.wsgi:application