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

# Compile translation messages
echo "Compiling translation messages..."
python manage.py compilemessages || echo "Warning: Failed to compile translation messages, continuing anyway..."

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Download RNN models for audio denoising (if script exists)
if [ -f "tools/rnn_models/download_models.sh" ]; then
    echo "Downloading RNN models for audio denoising..."
    bash tools/rnn_models/download_models.sh || echo "Warning: Failed to download RNN models, continuing anyway..."
fi

# Create superuser if it doesn't exist
if [ -n "$SUPERUSER_EMAIL" ] && [ -n "$SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser if it doesn't exist..."
    python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='$SUPERUSER_EMAIL').exists():
    User.objects.create_superuser(email='$SUPERUSER_EMAIL', password='$SUPERUSER_PASSWORD')
    print(f"Superuser with email '$SUPERUSER_EMAIL' created successfully")
else:
    print(f"Superuser with email '$SUPERUSER_EMAIL' already exists")
END
fi

# Setup organizations
echo "Setting up organizations..."
python manage.py setup_organizations || true

# Migrate module configs from env to database (one-time migration for empty/default values)
echo "Migrating module configs from environment variables (if empty/default in DB)..."
python manage.py migrate_module_configs || echo "Warning: Failed to migrate module configs, continuing anyway..."

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