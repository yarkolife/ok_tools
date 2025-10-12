# Ручное добавление видеофайлов

## Два способа добавления видео вручную:

### Способ 1: Загрузка файла через админ-панель

1. **Открой**: http://localhost:8000/admin/media_files/videofile/add/

2. **Выбери Storage Location** из выпадающего списка:
   ```
   Storage location: [NAS Archive ▼]
   ```

3. **Загрузи файл**:
   ```
   Upload Video File: [Выбрать файл]
   ```
   
   **Важно**: Имя файла ДОЛЖНО начинаться с номера:
   - ✅ `12345_title.mp4`
   - ✅ `67890_моё_видео.mov`
   - ❌ `video.mp4` (нет номера в начале!)

4. **Нажми Save**

   Что произойдет:
   - Файл загрузится в выбранное хранилище
   - Автоматически извлекутся метаданные (duration, codec, resolution, etc.)
   - Рассчитается checksum
   - Создастся запись VideoFile с номером из имени файла

---

### Способ 2: Указание пути к существующему файлу

Если файл уже есть на сервере в смонтированном NAS:

1. **Открой**: http://localhost:8000/admin/media_files/videofile/add/

2. **Выбери Storage Location**

3. **Укажи полный путь**:
   ```
   Or specify file path: /mnt/nas/archive/12345_title.mp4
   ```
   
   **Важно**:
   - Путь должен быть ВНУТРИ выбранного Storage Location
   - Например, если Storage Location = `/mnt/nas/archive/`
   - То путь может быть `/mnt/nas/archive/12345_title.mp4`

4. **Нажми Save**

   Что произойдет:
   - Django проверит что файл существует
   - Извлечет метаданные
   - Рассчитает checksum
   - Создаст VideoFile без копирования файла

---

## Просмотр в License

После добавления видео:

1. Открой лицензию с тем же номером:
   ```
   http://localhost:8000/admin/licenses/license/НОМЕР/change/
   ```

2. Разверни секцию **"Status & Metadata"**

3. Увидишь информацию о видео:
   ```
   Video File:
   🎬 12345_title.mp4
   00:25:30 • 1920x1080 • 1.2 GB
   ✓ Available • NAS Archive
   ```

4. Кликни на имя файла чтобы открыть VideoFile

---

## Массовое добавление (рекомендуется)

Для добавления множества файлов используй команду сканирования:

```bash
# Development (Docker)
docker-compose exec web python manage.py scan_video_storage

# Production (Debian)
cd /opt/ok-tools && python manage.py scan_video_storage
```

Команда:
- Автоматически найдет все видеофайлы в Storage Locations
- Извлечет метаданные
- Создаст VideoFile записи
- Намного быстрее чем ручное добавление!

---

## Требования к именам файлов

### ✅ Правильный формат:

```
НОМЕР_название.расширение

Примеры:
12345_title.mp4
67890_моё-видео.mov
99999_test_file.mpeg
1_simple.mpg
```

### ❌ Неправильный формат:

```
video.mp4                  (нет номера)
title_12345.mp4           (номер не в начале)
abc12345_video.mov        (начинается с букв)
```

### Поддерживаемые форматы:

- `.mp4` - MP4 (рекомендуется)
- `.mov` - QuickTime
- `.mpeg` - MPEG
- `.mpg` - MPEG

---

## Troubleshooting

### ❌ "Filename must start with a number"

**Решение**: Переименуй файл чтобы он начинался с номера:
```bash
# Старое имя
video.mp4

# Новое имя
12345_video.mp4
```

### ❌ "File already exists"

**Решение**: 
1. Файл с таким именем уже есть в хранилище
2. Либо переименуй файл
3. Либо проверь существующий VideoFile

### ❌ "File does not exist"

Если указываешь путь вручную:
```bash
# Проверь что файл существует
docker-compose exec web ls -la /mnt/nas/archive/12345_title.mp4

# Проверь что путь правильный
docker-compose exec web ls -la /mnt/nas/archive/
```

### ❌ "File must be within storage location"

Если Storage Location = `/mnt/nas/archive/`
То путь должен начинаться с `/mnt/nas/archive/`

**Неправильно**: `/mnt/nas/playout/12345_title.mp4`
**Правильно**: `/mnt/nas/archive/12345_title.mp4`

---

## Примеры использования

### Пример 1: Загрузка нового файла

1. У тебя есть файл `12345_новый-выпуск.mp4` на компьютере
2. Открой http://localhost:8000/admin/media_files/videofile/add/
3. Storage location: `NAS Archive`
4. Upload Video File: выбери файл
5. Save
6. Готово! Видео загружено в `/mnt/nas/archive/12345_новый-выпуск.mp4`

### Пример 2: Добавление существующего файла

1. Файл уже лежит на NAS: `/mnt/nas/archive/67890_старый-выпуск.mp4`
2. Открой http://localhost:8000/admin/media_files/videofile/add/
3. Storage location: `NAS Archive`
4. Or specify file path: `/mnt/nas/archive/67890_старый-выпуск.mp4`
5. Save
6. Готово! VideoFile создан без копирования

### Пример 3: Проверка что видео появилось в License

1. Добавил VideoFile #12345
2. Открой License #12345
3. Разверни "Status & Metadata"
4. Видишь информацию о видео
5. Кликаешь на имя файла
6. Открывается VideoFile с player'ом
7. Можешь посмотреть видео прямо в админке!

---

## Рекомендации

### Для единичных файлов:
✅ **Загрузка через админку** - простой и удобный способ

### Для множества файлов:
✅ **Команда scan_video_storage** - автоматизировано и быстро

### Для файлов уже на NAS:
✅ **Указание пути** - не нужно копировать файл

---

## Автоматическая связь с License

После создания VideoFile автоматически:

1. Django ищет License с таким же номером
2. Если находит - связывает их
3. В License появляется информация о видео
4. В VideoFile появляется ссылка на License

Это работает благодаря методу `get_video_file()` в модели License.

