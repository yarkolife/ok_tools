# Media Files Module - Quick Start Guide

## Быстрый старт

### 1. Применить миграции

```bash
# Внутри Docker контейнера
python manage.py migrate media_files
```

### 2. Создать хранилища через админ-панель

Зайдите в Django Admin → Media Files → Storage Locations:

**Создать Archive:**
- Name: `Video Archive`
- Storage Type: `ARCHIVE`
- Path: `/mnt/archive/` (ваш путь к архиву)
- Is Active: ✓
- Scan Enabled: ✓

**Создать Playout:**
- Name: `Playout Library`
- Storage Type: `PLAYOUT`
- Path: `/mnt/playout/library/` (ваш путь к playout)
- Is Active: ✓

### 3. Сканировать архив

```bash
# Первичное сканирование
python manage.py scan_video_storage --storage-id 1 --update-metadata

# Или все хранилища сразу
python manage.py scan_video_storage --all --update-metadata
```

### 4. Просмотр результатов

Django Admin → Media Files → Video Files

- Просматривайте метаданные
- Воспроизводите видео прямо в админке
- Копируйте в playout через actions

### 5. Интеграция с Planung

При сохранении плана трансляции (не черновика) видео автоматически копируются из архива в playout!

## Требования к файлам

### Формат имени

```
<номер>_<название>.<расширение>
```

Примеры:
- ✅ `12345_my_video.mp4`
- ✅ `00123_test.mov`
- ❌ `my_video_12345.mp4` (номер не в начале)
- ❌ `video.mp4` (нет номера)

### Поддерживаемые форматы

- mp4
- mov
- mpeg
- mpg

## Основные команды

```bash
# Сканирование
python manage.py scan_video_storage --all

# Обновление метаданных
python manage.py update_video_metadata --all

# Копирование в playout
python manage.py copy_to_playout --number 12345
python manage.py copy_to_playout --date 2025-10-15

# Очистка playout
python manage.py cleanup_playout --days-old 7 --dry-run
python manage.py cleanup_playout --days-old 7  # реальное удаление
```

## Troubleshooting

### Видео не найдены

1. Проверьте формат имени: `номер_название.расширение`
2. Проверьте путь в StorageLocation
3. Проверьте права доступа к папке

### Ошибка метаданных

1. Установите ffmpeg: `apt-get install ffmpeg`
2. Проверьте файл: `ffprobe /path/to/video.mp4`

### Видео не воспроизводится

1. Проверьте формат (HTML5 поддерживает mp4, webm, ogg)
2. Проверьте доступность файла: `is_available = True`

## Конфигурация

В `docker.cfg` или другом config файле:

```ini
[media]
archive_path = /mnt/archive/
playout_path = /mnt/playout/library/
auto_scan = False
auto_copy_on_schedule = True
```

## Дополнительная информация

Полная документация: `media_files/README.md`

