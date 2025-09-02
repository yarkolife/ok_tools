#!/usr/bin/env python
import os
import sys
import django
from django.core.management import execute_from_command_line
from django.core.management.commands.runserver import Command as RunserverCommand

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ok_tools.settings")
    
    # Отключаем проверки миграций
    RunserverCommand.check_migrations = lambda self: None
    
    django.setup()
    
    # Запуск Django сервера
    sys.argv = ['manage.py', 'runserver', '0.0.0.0:8000']
    execute_from_command_line(sys.argv)
