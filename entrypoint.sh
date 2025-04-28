#!/bin/bash
set -e

echo "🕒 Ждём PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  sleep 1
done

echo "✅ PostgreSQL готов. Запускаем миграции и collectstatic..."
OKTOOLS_CONFIG_FILE=docker.cfg python manage.py migrate
OKTOOLS_CONFIG_FILE=docker.cfg python manage.py collectstatic --noinput

echo "🚀 Запускаем сервер Django"
OKTOOLS_CONFIG_FILE=docker.cfg python manage.py runserver 0.0.0.0:8000
