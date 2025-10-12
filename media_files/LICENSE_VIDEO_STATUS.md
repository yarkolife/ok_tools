# License Video Status Column

## Обзор

Добавлена новая колонка "Video" в список лицензий (`/admin/licenses/license/`), которая показывает статус видеофайла и предоставляет ссылку для воспроизведения.

## Расположение

**Путь:** Licenses > License (список лицензий)

**Позиция:** После колонки "GENEHMIGT" (Genehmigt)

## Отображение

### 🎬 Available (Есть видео, доступно)
```
🎬 Available
▶️ Play
```
- **Иконка:** 🎬 зеленого цвета
- **Статус:** "Available"
- **Ссылка:** ▶️ Play (синяя ссылка, открывается в новой вкладке)

### ⚠️ Not available (Есть видео, недоступно)
```
⚠️ Not available
```
- **Иконка:** ⚠️ желтого цвета
- **Статус:** "Not available"
- **Причина:** Файл помечен как `is_available=False`

### ❌ No video (Нет видео)
```
❌ No video
```
- **Иконка:** ❌ серого цвета
- **Статус:** "No video"
- **Причина:** Нет связанного VideoFile с этим номером лицензии

## Технические детали

### Файлы изменены:
- `licenses/admin.py` - добавлен метод `video_status()` и обновлен `list_display`

### Метод `video_status(obj)`:
```python
def video_status(self, obj):
    """Display video status and play link in list view."""
    try:
        video_file = obj.get_video_file()
        if video_file:
            if video_file.is_available:
                play_url = reverse('admin:media_files_videofile_stream', args=[video_file.id])
                return format_html(
                    '<span style="color: #28a745;">🎬 {}</span><br>'
                    '<a href="#" onclick="window.open(\'{}\', \'video\', \'width=800,height=600\'); return false;">▶️ {}</a>',
                    _('Available'), play_url, _('Play')
                )
            else:
                return format_html('<span style="color: #ffc107;">⚠️ {}</span>', _('Not available'))
        else:
            return format_html('<span style="color: #999;">❌ {}</span>', _('No video'))
    except Exception:
        return format_html('<span style="color: #999;">-</span>')
```

### Оптимизация производительности:
```python
def get_queryset(self, request):
    """Optimize queryset with select_related and prefetch_related."""
    return super().get_queryset(request).prefetch_related(
        Prefetch(
            'videofile_set',
            queryset=VideoFile.objects.select_related('storage_location').filter(is_available=True),
            to_attr='available_videos'
        )
    )
```

## Использование

### Просмотр статуса видео:
1. Открыть Licenses > License
2. Посмотреть колонку "Video" после "GENEHMIGT"
3. Определить статус по иконке и тексту

### Воспроизведение видео:
1. Найти лицензию с статусом "🎬 Available"
2. Нажать на ссылку "▶️ Play"
3. Видео откроется во всплывающем окне (800x600px) с встроенным плеером

### Поиск видео для лицензии:
1. Найти лицензию с статусом "❌ No video"
2. Открыть лицензию (кликнуть на название)
3. В поле "Video File" нажать "🔍 Search for Video"
4. Или использовать массовое действие "Search for videos in storage"

## Интеграция с другими функциями

### Автоматическая синхронизация:
- При сканировании хранилищ видео автоматически связываются с лицензиями
- Статус обновляется автоматически

### System Management:
- Команда "Link Orphan Licenses" находит видео для лицензий без файлов
- После выполнения статус изменится с "❌ No video" на "🎬 Available"

### Копирование видео:
- При копировании видео в playout статус остается "🎬 Available"
- При перемещении в архив статус может измениться на "⚠️ Not available" если файл недоступен

## Примеры

### Список лицензий:
```
TITEL          | UNTERTITEL | PROFIL | NUMMER | DAUER  | ERSTELLT AM | GENEHMIGT | VIDEO
Тестовое видео | Test Video | None   | 99999  | 0:00:20| 12.10.2025  | ✗        | 🎬 Available
                                                                               ▶️ Play
```

### После поиска видео:
```
TITEL          | UNTERTITEL | PROFIL | NUMMER | DAUER  | ERSTELLT AM | GENEHMIGT | VIDEO
Тестовое видео | Test Video | None   | 99999  | 0:00:20| 12.10.2025  | ✗        | 🎬 Available
                                                                               ▶️ Play
```

### Всплывающее окно:
- **Размер:** 800x600 пикселей
- **Поведение:** Открывается в новом окне с именем 'video'
- **Плеер:** HTML5 video с контролами
- **Поддержка:** Range requests для перемотки

## Устранение проблем

### Видео не отображается:
1. Проверить, что файл начинается с номера лицензии (например, `99999_video.mp4`)
2. Запустить сканирование хранилища
3. Использовать поиск видео для конкретной лицензии

### Ссылка Play не работает:
1. Проверить, что видео помечено как `is_available=True`
2. Убедиться, что файл существует на диске
3. Проверить права доступа к файлу

### Медленная загрузка списка:
- Оптимизация уже реализована через `prefetch_related`
- При большом количестве лицензий может потребоваться пагинация
