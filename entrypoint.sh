#!/bin/bash

# Set PYTHONPATH to include the project root directory
export PYTHONPATH="/app:$PYTHONPATH"

# Run database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start the Django development server
PYTHONPATH=/app:$PYTHONPATH gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 60 --max-requests 1000 --max-requests-jitter 100 ok_tools.wsgi:application