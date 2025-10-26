# Video Format Detection Fix

## Проблема

При переименовании видеофайлов (например, с `.mov` на `.mp4`) система неправильно определяла MIME-тип для воспроизведения, что приводило к скачиванию файла вместо воспроизведения.

### Пример проблемы:
- Файл: `99998_test_video.mp4`
- ffprobe определяет: `mov,mp4,m4a,3gp,3g2,mj2` (берется первое значение: `mov`)
- MIME-тип: `video/quicktime` (для mov)
- Результат: Браузер пытается скачать файл вместо воспроизведения

## Решение

### 1. Исправлена логика определения MIME-типа

**Файл:** `media_files/admin.py`

**Было:**
```python
content_types = {
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    # ...
}
content_type = content_types.get(video.format, 'video/mp4')
```

**Стало:**
```python
import os
file_extension = os.path.splitext(video.filename)[1].lower()
content_types = {
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    # ...
}
content_type = content_types.get(file_extension, 'video/mp4')
```

### 2. Исправлена функция извлечения метаданных

**Файл:** `media_files/utils.py`

**Было:**
```python
metadata['format'] = fmt.get('format_name', '').split(',')[0]
```

**Стало:**
```python
# Get format from ffprobe
ffprobe_format = fmt.get('format_name', '').split(',')[0]

# Determine format based on file extension, not ffprobe
file_extension = os.path.splitext(file_path)[1].lower()
extension_formats = {
    '.mp4': 'mp4',
    '.mov': 'mov', 
    '.mpeg': 'mpeg',
    '.mpg': 'mpeg',
    '.avi': 'avi',
    '.mkv': 'mkv',
    '.webm': 'webm',
}

# Use file extension format if available, otherwise use ffprobe format
metadata['format'] = extension_formats.get(file_extension, ffprobe_format)
```

## Измененные функции

### В `media_files/admin.py`:
1. `stream_video()` - определение MIME-типа для HTTP ответа
2. `video_player()` - определение MIME-типа для HTML5 плеера

### В `media_files/utils.py`:
1. `extract_video_metadata()` - определение формата контейнера

## Логика работы

### Приоритет определения формата:
1. **Расширение файла** (основной приоритет)
2. **ffprobe format_name** (резервный)

### Примеры:

| Файл | Расширение | ffprobe | Результат | MIME-тип |
|------|------------|---------|-----------|----------|
| `video.mp4` | `.mp4` | `mov,mp4,m4a` | `mp4` | `video/mp4` |
| `video.mov` | `.mov` | `mov,mp4,m4a` | `mov` | `video/quicktime` |
| `video.avi` | `.avi` | `avi` | `avi` | `video/x-msvideo` |

## Поддерживаемые форматы

| Расширение | Формат | MIME-тип |
|------------|--------|----------|
| `.mp4` | mp4 | video/mp4 |
| `.mov` | mov | video/quicktime |
| `.mpeg` | mpeg | video/mpeg |
| `.mpg` | mpeg | video/mpeg |
| `.avi` | avi | video/x-msvideo |
| `.mkv` | mkv | video/x-matroska |
| `.webm` | webm | video/webm |

## Исправление существующих файлов

### Для исправления уже существующих файлов:

1. **Через Django shell:**
```python
from media_files.models import VideoFile
from media_files.utils import extract_video_metadata

# Обновить конкретный файл
video = VideoFile.objects.get(number=99998)
metadata = extract_video_metadata(video.full_path)
video.format = metadata.get('format', 'mp4')
video.save()
```

2. **Через админку:**
- Выбрать видео в списке
- Использовать действие "Update metadata"

3. **Через команду:**
```bash
python manage.py shell -c "
from media_files.models import VideoFile
from media_files.utils import extract_video_metadata
for video in VideoFile.objects.all():
    metadata = extract_video_metadata(video.full_path)
    video.format = metadata.get('format', video.format)
    video.save()
"
```

## Тестирование

### Проверка MIME-типа:
```bash
curl -I http://localhost:8000/admin/media_files/videofile/1/stream/
```

**Ожидаемый результат:**
```
Content-Type: video/mp4
```

### Проверка воспроизведения:
1. Открыть видео в админке
2. Нажать "▶️ Play"
3. Видео должно воспроизводиться, а не скачиваться

## Совместимость

- ✅ Обратная совместимость сохранена
- ✅ Новые файлы автоматически используют правильный формат
- ✅ Старые файлы можно обновить через админку или команды
- ✅ Поддержка всех основных видео форматов

## Связанные файлы

- `media_files/admin.py` - исправления MIME-типа
- `media_files/utils.py` - исправления извлечения метаданных
- `media_files/models.py` - модель VideoFile (без изменений)
- `media_files/management/commands/update_video_metadata.py` - команда обновления метаданных
