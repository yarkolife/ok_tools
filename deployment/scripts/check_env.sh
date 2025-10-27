#!/bin/bash
# Скрипт для проверки переменных окружения внутри Django
echo ">>> Проверка переменных окружения в Django..."
docker compose exec web python manage.py shell_plus --command 'import os; from django.conf import settings; print(f"DATABASE_URL: {os.environ.get("DATABASE_URL")}"); print(f"DEBUG: {settings.DEBUG}"); print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")'