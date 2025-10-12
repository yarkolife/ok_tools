# Исправление видеоплеера

## Проблема
- Видеоплеер показывал черный экран
- При попытке воспроизведения браузер пытался скачать файл
- Ссылка "Open in new window" вызывала диалог сохранения

## Причины
1. **Неправильный MIME-type**: Использовался `type="video/mov"` вместо `type="video/quicktime"`
2. **Формат видео**: В БД был формат `mov`, хотя файл имел расширение `.mp4`
3. **Streaming**: Недостаточная поддержка range requests для HTML5 video

## Исправления

### 1. Правильный MIME-type в video теге

**Было:**
```python
<source src="{}" type="video/{}">
# Использовался format напрямую: type="video/mov"
```

**Стало:**
```python
content_types = {
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    'mpeg': 'video/mpeg',
    'mpg': 'video/mpeg',
}
mime_type = content_types.get(obj.format, 'video/mp4')
<source src="{}" type="{}">
# Теперь: type="video/mp4" или type="video/quicktime"
```

### 2. Формат видео обновлен

```python
# Файл: 99999_test_video.mp4
# Было: format = 'mov'
# Стало: format = 'mp4'
```

Файл `.mp4` должен иметь формат `mp4` в БД для правильного MIME-type.

### 3. Улучшен stream_video()

**Изменения:**
- Использован `FileResponse` для полного ответа
- Правильная поддержка range requests (HTTP 206)
- `Content-Disposition: inline` (не `attachment`)
- `Accept-Ranges: bytes`
- Добавлен `preload="metadata"` в video тег

```python
# Range request support
if range_header:
    # HTTP 206 Partial Content
    response = HttpResponse(data, status=206, content_type=content_type)
    response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
else:
    # Full file
    response = FileResponse(file_handle, content_type=content_type)

response['Accept-Ranges'] = 'bytes'
response['Content-Disposition'] = 'inline'  # Не скачивать!
```

## Проверка

### 1. Формат видео
```bash
docker-compose exec web python manage.py shell
```
```python
from media_files.models import VideoFile
video = VideoFile.objects.get(number=99999)
print(f"Format: {video.format}")  # Должно быть: mp4
```

### 2. Stream URL
```
http://localhost:8000/admin/media_files/videofile/1/stream/
```

Должен:
- Отдавать `Content-Type: video/mp4`
- Поддерживать range requests
- НЕ скачивать файл

### 3. Плеер в админке
```
http://localhost:8000/admin/media_files/videofile/1/change/
```

Должен:
- Показывать видео в плеере (не черный экран)
- Воспроизводить видео по клику Play
- Работать seeking (перемотка)

## Как избежать в будущем

### При добавлении видео вручную:
1. Если файл `.mp4` → установи `format = 'mp4'`
2. Если файл `.mov` → установи `format = 'mov'`
3. Расширение файла должно соответствовать формату

### При автоматическом сканировании:
```python
# media_files/utils.py
def extract_video_metadata(file_path):
    # Должен правильно определять формат из ffprobe
    # Или использовать расширение файла как fallback
```

### Поддерживаемые форматы:
- `mp4` → `video/mp4` ✅ Работает в большинстве браузеров
- `mov` → `video/quicktime` ⚠️ Не все браузеры
- `webm` → `video/webm` ✅ Хорошая поддержка
- `mpeg/mpg` → `video/mpeg` ✅ Хорошая поддержка

**Рекомендация**: Использовать MP4 (H.264) для максимальной совместимости.

## Результат

✅ Видеоплеер работает  
✅ Воспроизведение в браузере  
✅ Seeking поддерживается  
✅ Не скачивает файл  
✅ Правильный MIME-type  

## Файлы изменены
- `media_files/admin.py` → `video_player()`, `stream_video()`
- База данных → VideoFile #99999 format: `mov` → `mp4`

---

**Дата**: October 12, 2025  
**Статус**: ✅ Fixed

