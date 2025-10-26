# Video Availability Fix in Scan Command

## Проблема

При сканировании хранилищ существующие видеофайлы не обновлялись как доступные (`is_available=True`), если они уже были в базе данных. Это приводило к тому, что после добавления новых файлов или переименования существующих, они отображались как недоступные в админке.

### Симптомы:
- Видеофайлы физически существуют в хранилище
- Счетчик видео в Storage Locations обновляется корректно
- Но в списке Video Files видео помечены как недоступные (❌)
- Ссылки "Play" не отображаются для недоступных видео

## Причина

В команде `scan_video_storage` была логика, которая обновляла `is_available=True` только для:
1. Новых файлов (при создании записи)
2. Существующих файлов только при использовании флагов `--force` или `--update-metadata`

Кнопка "Scan" в админке не передавала эти флаги, поэтому существующие файлы не обновлялись.

## Решение

### 1. Исправлена логика обновления существующих файлов

**Файл:** `media_files/management/commands/scan_video_storage.py`

**Было:**
```python
if created:
    # Создание нового файла
elif force or update_metadata:
    # Обновление только при флагах
    video_file.is_available = True
else:
    # Пропуск существующих файлов
    continue
```

**Стало:**
```python
if created:
    # Создание нового файла
else:
    # Всегда обновляем существующие файлы
    video_file.is_available = True  # Файл существует, значит доступен
```

### 2. Добавлена проверка отсутствующих файлов

**Новая логика:**
```python
# Помечаем файлы как недоступные, если их нет в хранилище
found_numbers = set()
for filename, rel_path, abs_path in found_files:
    number = extract_number_from_filename(filename)
    if number:
        found_numbers.add(number)

# Помечаем отсутствующие файлы как недоступные
existing_videos = VideoFile.objects.filter(storage_location=storage)
for video in existing_videos:
    if video.number not in found_numbers and video.is_available:
        video.is_available = False
        video.save(update_fields=['is_available'])
```

## Изменения в коде

### В `scan_video_storage.py`:

1. **Убрана условная логика обновления:**
   - Теперь все найденные файлы всегда обновляются как доступные
   - Убрана зависимость от флагов `--force` и `--update-metadata`

2. **Добавлена проверка отсутствующих файлов:**
   - Собираем номера всех найденных файлов
   - Помечаем файлы, которых нет в хранилище, как недоступные
   - Выводим предупреждения о недоступных файлах

3. **Улучшено логирование:**
   - Добавлено сообщение "Updated: {number} - {filename}" для обновленных файлов
   - Добавлено предупреждение "Marked unavailable: {number} - {filename}" для недоступных

## Результат

### До исправления:
```
Video 99998: available=True, format=mp4
Video 99999: available=False, format=mp4  ❌
```

### После исправления:
```
Video 99998: available=True, format=mp4   ✅
Video 99999: available=True, format=mp4   ✅
```

## Тестирование

### 1. Проверка через команду:
```bash
python manage.py scan_video_storage --storage-id 1
```

**Ожидаемый вывод:**
```
Scanning storage: Local Test Playout (/app/playout/)
Found 2 video files
Updated: 99999 - 99999_test_video.mp4
Updated: 99998 - 99998_test_video.mp4
=== Scan Complete ===
Total files found: 2
Records updated: 2
```

### 2. Проверка через админку:
- Открыть Storage Locations
- Нажать кнопку "Scan" для нужного хранилища
- Проверить, что все видео помечены как доступные

### 3. Проверка в списке Video Files:
- Все видео должны иметь зеленую галочку (✅) в колонке "VERFÜGBAR"
- Должны отображаться ссылки "▶️ Play" для всех доступных видео

## Совместимость

- ✅ Обратная совместимость сохранена
- ✅ Флаги `--force` и `--update-metadata` по-прежнему работают
- ✅ Автоматическое сканирование теперь корректно обновляет статус
- ✅ Кнопка "Scan" в админке теперь работает правильно

## Связанные файлы

- `media_files/management/commands/scan_video_storage.py` - основное исправление
- `media_files/admin.py` - кнопка "Scan" в админке
- `media_files/models.py` - модель VideoFile (без изменений)
- `media_files/utils.py` - утилиты сканирования (без изменений)

## Примеры использования

### Сканирование через админку:
1. Открыть MEDIA FILES → Storage Locations
2. Нажать кнопку "Scan" рядом с нужным хранилищем
3. Проверить сообщение об успешном сканировании

### Сканирование через командную строку:
```bash
# Сканировать конкретное хранилище
python manage.py scan_video_storage --storage-id 1

# Сканировать все активные хранилища
python manage.py scan_video_storage --all

# Принудительное сканирование с обновлением метаданных
python manage.py scan_video_storage --all --force --update-metadata
```

### Проверка статуса видео:
```python
from media_files.models import VideoFile

# Проверить все видео
for video in VideoFile.objects.all():
    print(f'Video {video.number}: available={video.is_available}')

# Найти недоступные видео
unavailable = VideoFile.objects.filter(is_available=False)
print(f'Unavailable videos: {unavailable.count()}')
```
