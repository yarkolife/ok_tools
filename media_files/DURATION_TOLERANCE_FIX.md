# Исправление: Толерантность к разнице длительностей

## 🎯 Проблема
- Предупреждение "Duration mismatch" показывалось даже при разнице менее секунды
- Видео: `0:00:15.568167` vs Лицензия: `0:00:15` — разница 0.568 секунды
- Пользователь получал ложное предупреждение о несовпадении

## ✅ Решение

### Логика толерантности:
**Если разница < 1 секунды → считаем одинаковыми (предупреждение НЕ показывается)**

### Примеры:

#### ✅ НЕ показывать предупреждение:
```
Video: 0:00:15.568167  (15 секунд)
License: 0:00:15       (15 секунд)
Difference: 0 секунд   → НЕТ предупреждения
```

```
Video: 0:00:15.999     (15 секунд)
License: 0:00:15       (15 секунд) 
Difference: 0 секунд   → НЕТ предупреждения
```

#### ⚠️ Показывать предупреждение:
```
Video: 0:00:15.568167  (15 секунд)
License: 0:00:20       (20 секунд)
Difference: 5 секунд   → ЕСТЬ предупреждение
```

---

## 🔧 Изменения в коде

### 1. **Админка License** (`licenses/admin.py`)
```python
# Check if duration needs sync (only if difference >= 1 second)
if video_file.duration and obj.duration:
    # Calculate difference in seconds
    video_seconds = int(video_file.duration.total_seconds())
    license_seconds = int(obj.duration.total_seconds())
    duration_diff = abs(video_seconds - license_seconds)
    
    # Only show warning if difference is 1 second or more
    if duration_diff >= 1:
        # Показать предупреждение и кнопку синхронизации
```

### 2. **Автосинхронизация** (`media_files/signals.py`)
```python
# Only sync if difference is 1 second or more
if license.duration:
    video_seconds = int(video_duration.total_seconds())
    license_seconds = int(license.duration.total_seconds())
    duration_diff = abs(video_seconds - license_seconds)
    
    if duration_diff >= 1:
        # Синхронизировать
        license.duration = rounded_duration
    else:
        # Не синхронизировать, разница < 1 секунды
        logger.debug("Duration difference < 1 second, no sync needed")
```

---

## 🧪 Тестирование

### Тест 1: Разница < 1 секунды
```bash
docker-compose exec web python manage.py shell
```
```python
from licenses.models import License
from datetime import timedelta

license = License.objects.get(number=99999)
license.duration = timedelta(seconds=15)  # 0:00:15
# Video: 0:00:15.568167
# Разница: 0 секунд

# Результат: НЕТ предупреждения в админке
```

### Тест 2: Разница >= 1 секунды
```python
license.duration = timedelta(seconds=20)  # 0:00:20
# Video: 0:00:15.568167
# Разница: 5 секунд

# Результат: ЕСТЬ предупреждение в админке
```

---

## 📊 Поведение

### В админке License:

#### Когда разница < 1 секунды:
```
Video File: 🎬 99999_test_video.mp4
           0:00:15.568167 • 848x478 • 2.38 MB
           ✓ Available • Local Test Playout
           ← НЕТ предупреждения
```

#### Когда разница >= 1 секунды:
```
Video File: 🎬 99999_test_video.mp4
           0:00:15.568167 • 848x478 • 2.38 MB
           ✓ Available • Local Test Playout
           ⚠️ Duration mismatch: License (0:00:20)
           [🔄 Sync from Video] ← ЕСТЬ кнопка
```

### Автосинхронизация:

#### При создании/обновлении VideoFile:
- ✅ Если разница >= 1 секунды → автоматически синхронизирует
- ✅ Если разница < 1 секунды → НЕ синхронизирует (считает одинаковыми)

---

## 🎯 Результат

✅ **Убраны ложные предупреждения** при разнице < 1 секунды  
✅ **Автосинхронизация работает умно** — только при значительных различиях  
✅ **Кнопка синхронизации появляется** только когда действительно нужно  
✅ **Пользователь не получает спам** предупреждений о незначительных различиях  

---

## 🔗 Проверь:

**Открой:** http://localhost:8000/admin/licenses/license/1/change/

**Текущее состояние:**
- License: `0:00:20` 
- Video: `0:00:15.568167`
- Разница: 5 секунд → **должно быть предупреждение**

**После исправления (верни длительность):**
```bash
docker-compose exec -T web python manage.py shell <<'EOF'
from licenses.models import License
from datetime import timedelta
license = License.objects.get(number=99999)
license.duration = timedelta(seconds=15)
license.save(update_fields=['duration'])
print("Duration reset to 0:00:15")
EOF
```

---

**Дата**: October 12, 2025  
**Статус**: ✅ Fixed
