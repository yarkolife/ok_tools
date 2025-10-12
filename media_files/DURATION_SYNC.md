# Автоматическая синхронизация длительности из видео

## 🎯 Функционал

Модуль автоматически синхронизирует длительность лицензии (License.duration) с длительностью связанного видеофайла (VideoFile.duration).

## 🤖 Автоматическая синхронизация

### Когда происходит автосинхронизация:

1. **При создании VideoFile** с номером существующей лицензии
2. **При обновлении VideoFile** если изменилась длительность видео
3. **При связывании VideoFile с License**

### Как это работает:

```python
# Сигнал в media_files/signals.py автоматически:
# 1. Находит License по номеру VideoFile
# 2. Сравнивает длительности
# 3. Обновляет License.duration если не совпадает
```

## 📊 Визуальные индикаторы

### В админке License:

В секции **"Status & Metadata"** → поле **"Video File"**:

#### ✅ Если длительности совпадают:
```
🎬 99999_test_video.mp4
0:00:15.568167 • 848x478 • 2.38 MB
✓ Available • Local Test Playout
```

#### ⚠️ Если длительности НЕ совпадают:
```
🎬 99999_test_video.mp4
0:00:15.568167 • 848x478 • 2.38 MB
✓ Available • Local Test Playout
⚠️ Duration mismatch: License (0:00:30)
[🔄 Sync from Video]  ← Кнопка для синхронизации
```

## 🔄 Ручная синхронизация

### Способ 1: Кнопка в админке

1. Открой лицензию: `http://localhost:8000/admin/licenses/license/1/change/`
2. Разверни секцию **"Status & Metadata"**
3. Найди поле **"Video File"**
4. Если видишь предупреждение ⚠️ — кликни кнопку **"🔄 Sync from Video"**
5. Получишь сообщение: `Duration synced from video: 0:00:30 → 0:00:15.568167`

### Способ 2: Пересохрани VideoFile

1. Открой видеофайл: `http://localhost:8000/admin/media_files/videofile/1/change/`
2. Кликни **"Save"**
3. Сигнал автоматически обновит License.duration

### Способ 3: Django Shell

```bash
docker-compose exec web python manage.py shell
```

```python
from licenses.models import License

license = License.objects.get(number=99999)
video = license.get_video_file()

if video and video.duration:
    license.duration = video.duration
    license.save(update_fields=['duration'])
    print(f"✅ Synced: {license.duration}")
```

## 🧪 Тестирование

### Создать тестовую ситуацию с несовпадением:

```bash
docker-compose exec -T web python manage.py shell <<'EOF'
from licenses.models import License
from datetime import timedelta

license = License.objects.get(number=99999)
license.duration = timedelta(seconds=999)  # Неправильное значение
license.save(update_fields=['duration'])
print("Test created: license.duration != video.duration")
EOF
```

### Проверить автосинхронизацию:

1. Открой лицензию в админке
2. Увидишь предупреждение ⚠️
3. Кликни "🔄 Sync from Video"
4. Длительность обновится автоматически

## 📝 Логи

Все операции синхронизации логируются:

```bash
docker-compose logs web | grep "Synced duration"
```

Примеры логов:
```
INFO Synced duration from VideoFile to License #99999: 0:00:15.568167
INFO Auto-linked VideoFile 99999 to License
```

## 🔒 Безопасность

- ✅ Синхронизация происходит только если `video.duration` не `None`
- ✅ Не перезаписывает вручную установленную длительность при создании лицензии
- ✅ Обновляет только поле `duration`, не затрагивая другие поля
- ✅ Использует `update_fields=['duration']` для минимизации обновлений БД

## 🎬 Workflow

### Типичный сценарий использования:

1. **Создать лицензию** с любой начальной длительностью (или оставить пустой)
2. **Добавить видео** с тем же номером через:
   - Ручную загрузку в админке
   - Команду `scan_video_storage`
   - Прямое создание VideoFile
3. **Автоматически** License.duration обновится значением из видео
4. **Если нужно изменить** — используй кнопку "🔄 Sync from Video"

### При обновлении видео:

1. Заменить файл на диске
2. Запустить: `python manage.py update_video_metadata`
3. Длительность лицензии обновится автоматически

## ❓ FAQ

**Q: Что если у лицензии несколько видеофайлов?**  
A: `get_video_file()` возвращает первый найденный VideoFile с совпадающим номером.

**Q: Можно ли отключить автосинхронизацию?**  
A: Да, закомментируй сигнал `auto_link_to_license` в `media_files/signals.py`.

**Q: Как узнать когда последний раз обновлялась длительность?**  
A: Смотри логи или добавь поле `duration_updated_at` в модель License.

**Q: Что если видео удалено?**  
A: Длительность лицензии останется без изменений (не обнулится).

## 🔗 Связанные файлы

- Сигнал: `media_files/signals.py` → `auto_link_to_license()`
- Админка: `licenses/admin.py` → `video_file_info()`, `response_change()`
- Модель: `licenses/models.py` → `get_video_file()`

---

**Версия**: 2.5  
**Дата**: October 2025  
**Статус**: ✅ Production Ready

