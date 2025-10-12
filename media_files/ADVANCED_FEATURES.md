# Advanced Media Files Features

## Overview

Дополнительные функции для автоматизации управления видеофайлами: двусторонняя синхронизация лицензий и видео, массовая синхронизация, автоматическое перемещение из playout в архив, и мониторинг файловых атрибутов.

## 1. Двусторонняя синхронизация лицензий и видео

### Автоматические сигналы

**VideoFile → License:**
- При создании `VideoFile` автоматически ищет `License` с тем же номером
- Связывает видео с лицензией
- Синхронизирует длительность (округленную до секунд)

**License → VideoFile:**
- При создании `License` автоматически ищет `VideoFile` с тем же номером
- Связывает лицензию с видео
- Синхронизирует длительность из видео в лицензию

### Порядок создания не важен
- Можно создать лицензию, потом добавить видео → связь установится
- Можно добавить видео, потом создать лицензию → связь установится
- Длительность всегда синхронизируется из видео в лицензию

## 2. Массовая синхронизация

### Management команда
```bash
# Синхронизировать все лицензии и видео
python manage.py sync_licenses_videos

# Тестовый режим (без изменений)
python manage.py sync_licenses_videos --dry-run

# Принудительная синхронизация длительности
python manage.py sync_licenses_videos --force-sync-duration

# Синхронизация конкретного номера
python manage.py sync_licenses_videos --number 99999
```

### Что делает команда
1. Находит все номера, для которых есть и лицензия, и видео
2. Связывает их друг с другом
3. Синхронизирует длительность из видео в лицензию
4. Показывает статистику операций

## 3. Автоматическое перемещение из playout в архив

### Мониторинг файловых атрибутов

**Windows:**
- Проверяет атрибуты `FILE_ATTRIBUTE_HIDDEN` и `FILE_ATTRIBUTE_SYSTEM`
- Если файл имеет эти атрибуты → считается "в использовании"

**Linux:**
- Проверяет специальные права доступа (setuid, setgid, sticky bit)
- Использует `lsof` для проверки блокировки файла

### Management команда для очистки
```bash
# Автоматическая очистка playout
python manage.py cleanup_playout

# Тестовый режим
python manage.py cleanup_playout --dry-run

# Проверка атрибутов файлов
python manage.py cleanup_playout --check-attributes

# Проверка блокировки файлов
python manage.py cleanup_playout --check-locks

# Только файлы старше 14 дней
python manage.py cleanup_playout --older-than 14

# Конкретное хранилище
python manage.py cleanup_playout --storage-id 1
```

### Админ-действие
- **Move to archive storage**: Массовое перемещение выбранных видео в архив
- Проверяет атрибуты и блокировки перед перемещением
- Пропускает файлы, которые все еще используются

## 4. Автоматическое сканирование

### Management команда
```bash
# Автоматическое сканирование всех хранилищ
python manage.py auto_scan

# Только определенный тип хранилища
python manage.py auto_scan --storage-type PLAYOUT

# Принудительное сканирование
python manage.py auto_scan --force

# С расчетом checksums
python manage.py auto_scan --calculate-checksums
```

### Сканирование из админки
**Кнопка в списке хранилищ:**
- В админке Media Files > Storage Locations
- У каждого хранилища кнопка **🔍 Scan**
- Мгновенное сканирование одним кликом
- Показывает статистику найденных/созданных/обновленных видео

**Массовое действие:**
- Выбрать несколько хранилищ
- Actions > "Scan selected storage locations"

### Интеграция с cron
Добавить в crontab для автоматического сканирования:

```bash
# Ежедневно в 2:00
0 2 * * * cd /path/to/project && python manage.py auto_scan

# Еженедельно в воскресенье в 3:00
0 3 * * 0 cd /path/to/project && python manage.py cleanup_playout --older-than 7
```

## 5. Автоматический поиск видео для лицензий

### Management команда
```bash
# Найти видео для всех лицензий без связки
python manage.py link_orphan_licenses

# Тестовый режим
python manage.py link_orphan_licenses --dry-run

# Сначала просканировать хранилища, потом искать
python manage.py link_orphan_licenses --scan-first

# Для конкретной лицензии
python manage.py link_orphan_licenses --number 99999
```

### Поиск видео из админки

**Для одной лицензии:**
- В админке Licenses > License > открыть лицензию
- Поле "Video File" → кнопка **🔍 Search for Video**
- Автоматический поиск по номеру лицензии
- Связывание и синхронизация длительности

**Для нескольких лицензий:**
- В списке лицензий выбрать несколько
- Actions > "Search for videos in storage"
- Массовый поиск и связывание

### Периодический поиск
Добавить в crontab для автоматического поиска:

```bash
# Ежедневно в 3:00 - поиск видео для новых лицензий
0 3 * * * cd /path/to/project && python manage.py link_orphan_licenses --scan-first
```

## 6. Workflow для playout системы

### Типичный сценарий
1. **Планирование**: Видео копируется в playout (с недельными папками)
2. **Использование**: Playout система устанавливает атрибуты "скрытый" и "системный"
3. **Завершение**: Playout система снимает атрибуты
4. **Очистка**: Команда `cleanup_playout` перемещает видео в архив

### Мониторинг использования
```bash
# Проверить статус файлов в playout
python manage.py cleanup_playout --dry-run --check-attributes --check-locks
```

## 7. Настройки и конфигурация

### Docker Compose интеграция
```yaml
# docker-compose.yml
services:
  cron:
    # ... existing config ...
    volumes:
      - ./cron.d:/etc/cron.d
```

### Cron файл
```bash
# cron.d/auto-scan
# Ежедневное сканирование в 2:00
0 2 * * * root cd /app && python manage.py auto_scan >> /var/log/auto-scan.log 2>&1

# Еженедельная очистка в воскресенье в 3:00
0 3 * * 0 root cd /app && python manage.py cleanup_playout --older-than 7 >> /var/log/cleanup.log 2>&1
```

## 8. Логирование и мониторинг

### Файлы логов
- **Автосканирование**: `/var/log/auto-scan.log`
- **Очистка**: `/var/log/cleanup.log`
- **Django логи**: `ok_tools-debug.log`

### Мониторинг операций
Все операции записываются в `FileOperation`:
- `SCAN`: Сканирование хранилища
- `COPY`: Копирование файлов
- `MOVE`: Перемещение файлов
- `DELETE`: Удаление записей

## 9. Устранение неполадок

### Проблемы с атрибутами файлов
```bash
# Проверить атрибуты файла (Windows)
attrib filename.mp4

# Снять атрибуты (Windows)
attrib -h -s filename.mp4

# Проверить блокировку (Linux)
lsof filename.mp4
```

### Проблемы с синхронизацией
```bash
# Принудительная синхронизация конкретного номера
python manage.py sync_licenses_videos --number 99999 --force-sync-duration
```

### Проблемы с перемещением
```bash
# Тестовый режим для диагностики
python manage.py cleanup_playout --dry-run --check-attributes --check-locks
```

## 10. Примеры использования

### Ежедневный workflow
```bash
# 1. Сканирование новых файлов
python manage.py auto_scan

# 2. Синхронизация лицензий и видео
python manage.py sync_licenses_videos

# 3. Очистка старых файлов из playout
python manage.py cleanup_playout --older-than 7 --check-attributes
```

### Ручное управление
```bash
# Переместить конкретные видео в архив (из админки)
# 1. Выбрать видео в Media Files > Video Files
# 2. Actions > Move to archive storage

# Синхронизировать конкретный номер
python manage.py sync_licenses_videos --number 12345
```

## 11. Интеграция с существующими функциями

### С дубликатами
- Автоматическое перемещение учитывает дубликаты
- Не перемещает файлы, если в архиве уже есть такая же версия

### С недельными папками
- Перемещение из playout в архив убирает недельную папку
- Файл попадает в корень архива: `archive/99999_video.mp4`

### С лицензиями
- При перемещении связь VideoFile ↔ License сохраняется
- Длительность остается синхронизированной
