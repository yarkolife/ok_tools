# Руководство по работе с Media Files в Django Admin

## 📋 Содержание

1. [Добавление Storage Locations (хранилищ)](#добавление-storage-locations)
2. [Сканирование видеофайлов](#сканирование-видеофайлов)
3. [Ручное добавление видеофайлов](#ручное-добавление-видеофайлов)
4. [Просмотр и управление видеофайлами](#просмотр-и-управление-видеофайлами)
5. [Операции с файлами](#операции-с-файлами)
6. [История операций](#история-операций)

---

## Добавление Storage Locations

Storage Location - это место хранения видеофайлов (архив, playout, или кастомное хранилище).

### Шаг 1: Открой админ-панель

```
http://localhost:8000/admin/          # Development
https://your-domain.de/admin/         # Production
```

Войди с учетными данными администратора.

### Шаг 2: Перейди в раздел Media Files

```
Главная → Media Files → Storage locations
```

Или напрямую:
```
http://localhost:8000/admin/media_files/storagelocation/
```

### Шаг 3: Нажми "Add Storage Location"

Кнопка в правом верхнем углу: **[+ Add storage location]**

### Шаг 4: Заполни форму

#### Пример 1: Archive (Архив)

```
┌─────────────────────────────────────────────────────┐
│ Name: *                                             │
│ ┌─────────────────────────────────────────────────┐│
│ │ NAS Archive                                     ││
│ └─────────────────────────────────────────────────┘│
│                                                     │
│ Type: *                                             │
│ ┌─────────────────────────────────────────────────┐│
│ │ ARCHIVE ▼                                       ││ ← Выбери из списка
│ └─────────────────────────────────────────────────┘│
│                                                     │
│ Path: *                                             │
│ ┌─────────────────────────────────────────────────┐│
│ │ /mnt/nas/archive/                               ││ ← Путь к монтированному NAS
│ └─────────────────────────────────────────────────┘│
│                                                     │
│ Description:                                        │
│ ┌─────────────────────────────────────────────────┐│
│ │ Архив всех видеофайлов на NAS 192.168.XXX.XXX  ││
│ └─────────────────────────────────────────────────┘│
│                                                     │
│ ☑ Is active                                        │ ← Оставь включенным
│                                                     │
│ Max size (GB):                                      │
│ ┌─────────────────────────────────────────────────┐│
│ │ 5000                                            ││ ← Опционально
│ └─────────────────────────────────────────────────┘│
│                                                     │
│           [Save and add another]  [Save]           │
└─────────────────────────────────────────────────────┘
```

**Поля:**
- **Name** *(обязательно)*: Читаемое название хранилища
  - Примеры: "NAS Archive", "Production Archive", "Архив OKMQ"
  
- **Type** *(обязательно)*: Тип хранилища
  - `ARCHIVE` - для долговременного хранения
  - `PLAYOUT` - для файлов готовых к эфиру
  - `CUSTOM` - для других целей (трейлеры, превью и т.д.)
  
- **Path** *(обязательно)*: Путь к директории в файловой системе
  - Development (Docker): `/mnt/nas/archive/`
  - Production (Debian): `/mnt/nas/archive/`
  - ⚠️ **Важно**: путь ДОЛЖЕН заканчиваться на `/`
  - ⚠️ **Важно**: путь должен быть доступен процессу Django
  
- **Description** *(опционально)*: Описание для справки
  - Можно указать IP, особенности, заметки
  
- **Is active** *(обязательно)*: Активность хранилища
  - ☑ Включено - хранилище используется
  - ☐ Выключено - хранилище игнорируется при сканировании
  
- **Max size (GB)** *(опционально)*: Максимальный размер в гигабайтах
  - Для контроля использования дискового пространства

#### Пример 2: Playout

```
Name: NAS Playout
Type: PLAYOUT
Path: /mnt/nas/playout/
Description: Файлы для трансляции на 192.168.188.1
Is active: ☑
Max size (GB): 1000
```

#### Пример 3: Playout с подпапками

```
Name: Playout - Trailers
Type: CUSTOM
Path: /mnt/nas/playout/trailers/
Description: Трейлеры для эфира
Is active: ☑
```

```
Name: Playout - Week 01
Type: CUSTOM
Path: /mnt/nas/playout/week01/
Description: Видео для недели #01
Is active: ☑
```

### Шаг 5: Проверь путь

После сохранения Django проверит:
- ✅ Существует ли директория
- ✅ Есть ли права на чтение
- ✅ Правильность пути

Если возникает ошибка:
```
❌ Path '/mnt/nas/archive/' does not exist or is not accessible
```

**Решение:**
```bash
# Development (Docker)
docker-compose exec web ls -la /mnt/nas/archive

# Production (Debian)
sudo -u www-data ls -la /mnt/nas/archive
```

---

## Сканирование видеофайлов

После добавления Storage Locations нужно просканировать их для поиска видеофайлов.

### Способ 1: Через командную строку (рекомендуется)

```bash
# Development (Docker)
docker-compose exec web python manage.py scan_video_storage

# Production (Debian)
cd /opt/ok-tools
source venv/bin/activate
python manage.py scan_video_storage
```

**Опции:**

```bash
# Сканировать только конкретное хранилище
python manage.py scan_video_storage --location "NAS Archive"

# Только проверка без сохранения
python manage.py scan_video_storage --dry-run

# С подробным выводом
python manage.py scan_video_storage --verbose
```

**Пример вывода:**

```
Scanning storage locations for video files...

Processing storage: NAS Archive (/mnt/nas/archive/)
  Found 145 video files
  Processing: 12345_title.mp4
    ✓ Extracted metadata
    ✓ Calculated checksum
    → Created VideoFile #12345
  Processing: 67890_another.mov
    ✓ Already exists, updated metadata
  ...

Summary:
  Scanned: 2 locations
  Found: 145 files
  Created: 89 new records
  Updated: 56 existing records
  Errors: 0
  
Duration: 3m 24s
```

### Способ 2: Через Django Admin Actions

1. Перейди в **Media Files → Storage locations**
2. Выбери хранилища (☑ чекбоксы)
3. В выпадающем меню **Action** выбери:
   ```
   Scan selected storage locations for video files
   ```
4. Нажми **[Go]**

⚠️ **Внимание**: Сканирование может занять время для больших хранилищ!

---

## Ручное добавление видеофайлов

Помимо автоматического сканирования, можно добавлять видеофайлы вручную.

> **📖 Подробная инструкция**: См. [MANUAL_UPLOAD.md](./MANUAL_UPLOAD.md) для полного руководства по ручному добавлению.

### Быстрый способ: Загрузка файла

1. Перейди: **Media Files → Video files → Add**
2. Выбери **Storage location**
3. Нажми **Upload Video File** и выбери файл
4. **Важно**: Имя файла должно начинаться с номера (например, `12345_title.mp4`)
5. Нажми **Save**

### Альтернативный способ: Указание пути

Если файл уже есть на сервере:

1. Перейди: **Media Files → Video files → Add**
2. Выбери **Storage location**
3. Заполни **Or specify file path**: `/mnt/nas/archive/12345_title.mp4`
4. Нажми **Save**

**Что происходит автоматически:**
- Извлекаются метаданные (кодек, битрейт, разрешение, FPS, etc.)
- Рассчитывается SHA256 checksum
- Создается VideoFile запись
- Связывается с License по номеру (если есть)

---

## Просмотр и управление видеофайлами

### Открыть список видеофайлов

```
Главная → Media Files → Video files
```

Или:
```
http://localhost:8000/admin/media_files/videofile/
```

### Интерфейс списка

```
┌──────────────────────────────────────────────────────────┐
│ Filters:                                                 │
│   By storage location:                                   │
│     ○ All                                                │
│     ○ NAS Archive (145)                                  │
│     ○ NAS Playout (23)                                   │
│                                                           │
│   By video codec:                                        │
│     ○ All                                                │
│     ○ h264 (98)                                          │
│     ○ hevc (45)                                          │
│     ○ mpeg2 (2)                                          │
│                                                           │
│   By resolution:                                         │
│     ○ All                                                │
│     ○ 1920x1080 (120)                                    │
│     ○ 1280x720 (25)                                      │
│                                                           │
│   Has errors:                                            │
│     ○ All                                                │
│     ○ Yes                                                │
│     ○ No                                                 │
└──────────────────────────────────────────────────────────┘

Search: [_____________] 🔍    Action: [Select...] [Go]

┌─────┬────────┬─────────────────┬──────────────┬──────────┐
│ ☑   │ Number │ Filename        │ Storage      │ Duration │
├─────┼────────┼─────────────────┼──────────────┼──────────┤
│ ☐   │ 12345  │ 12345_title.mp4 │ NAS Archive  │ 00:25:30 │
│ ☐   │ 12346  │ 12346_video.mov │ NAS Archive  │ 01:15:45 │
│ ☐   │ 12347  │ 12347_show.mp4  │ NAS Playout  │ 00:45:12 │
└─────┴────────┴─────────────────┴──────────────┴──────────┘

Showing 1-25 of 168 video files
```

### Открыть конкретный видеофайл

Нажми на номер или название файла.

### Интерфейс детального просмотра

```
┌──────────────────────────────────────────────────────────┐
│                   VIDEO FILE #12345                       │
├──────────────────────────────────────────────────────────┤
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │                                                     │ │
│ │              [▶ Video Player]                      │ │
│ │                                                     │ │
│ │            12345_title.mp4                         │ │
│ │         [===========|=======] 00:10:25 / 00:25:30  │ │
│ │            🔊 Volume: ▮▮▮▮▮▮▮▯▯▯                    │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ Basic Information:                                        │
│   Number: 12345                                          │
│   Filename: 12345_title.mp4                              │
│   Storage location: NAS Archive                          │
│   File path: /mnt/nas/archive/12345_title.mp4           │
│   File size: 1.2 GB                                      │
│   File format: MP4                                       │
│                                                           │
│ Video Information:                                        │
│   Duration: 00:25:30                                     │
│   Codec: h264                                            │
│   Bitrate: 8000 kbps                                     │
│   Resolution: 1920x1080                                  │
│   Frame rate: 25.00 fps                                  │
│   Aspect ratio: 16:9                                     │
│   Color space: yuv420p                                   │
│                                                           │
│ Audio Information:                                        │
│   Codec: aac                                             │
│   Bitrate: 192 kbps                                      │
│   Sample rate: 48000 Hz                                  │
│   Channels: 2 (stereo)                                   │
│                                                           │
│ Verification:                                            │
│   SHA256: a3f5b8c2d9e1f4...                             │
│   Last verified: 2025-10-12 10:30:45                    │
│                                                           │
│ Related:                                                  │
│   License: #12345 "Title of the show"                   │ ← Ссылка на лицензию
│                                                           │
│                 [Delete]  [Save]                         │
└──────────────────────────────────────────────────────────┘
```

---

## Операции с файлами

### Массовые действия (Bulk Actions)

Выбери несколько файлов (☑) и выполни действие:

#### 1. Copy to playout

```
Action: Copy selected video files to playout ▼  [Go]
```

**Что происходит:**
1. Выбирается целевое PLAYOUT хранилище
2. Файлы копируются из текущего места в playout
3. Создаются записи о копировании в FileOperation
4. Обновляется storage_location у VideoFile

**Когда использовать:**
- Перед трансляцией нужно скопировать файл из архива
- Подготовка к эфиру

#### 2. Update video metadata

```
Action: Update metadata for selected video files ▼  [Go]
```

**Что происходит:**
1. Перезапускается ffprobe для каждого файла
2. Обновляются все метаданные (кодек, битрейт, разрешение и т.д.)
3. Обновляется checksum

**Когда использовать:**
- Файл был изменен/обновлен
- Метаданные были извлечены с ошибкой
- После обновления ffmpeg

#### 3. Verify file integrity

```
Action: Verify integrity of selected video files ▼  [Go]
```

**Что происходит:**
1. Пересчитывается SHA256 checksum
2. Сравнивается с сохраненным значением
3. Отмечаются файлы с расхождениями

**Когда использовать:**
- Проверка целостности после копирования
- Регулярная проверка архива
- Подозрение на повреждение файла

#### 4. Mark as archived

```
Action: Mark selected video files as archived ▼  [Go]
```

**Что происходит:**
- Перемещает файлы в ARCHIVE хранилище (если настроено)
- Обновляет storage_location

---

## История операций

### Просмотр истории

```
Главная → Media Files → File operations
```

Или:
```
http://localhost:8000/admin/media_files/fileoperation/
```

### Интерфейс истории

```
┌─────────────────────────────────────────────────────────┐
│ Filters:                                                │
│   By operation type:                                    │
│     ○ All                                               │
│     ○ COPY (89)                                         │
│     ○ MOVE (12)                                         │
│     ○ DELETE (5)                                        │
│     ○ SCAN (145)                                        │
│     ○ VERIFY (145)                                      │
│                                                          │
│   By status:                                            │
│     ○ All                                               │
│     ○ SUCCESS (240)                                     │
│     ○ FAILED (11)                                       │
│     ○ IN_PROGRESS (0)                                   │
│                                                          │
│   By date:                                              │
│     Today | Past 7 days | This month                   │
└─────────────────────────────────────────────────────────┘

┌──────────────┬───────┬──────────┬────────────────────────┐
│ Date/Time    │ Video │ Type     │ Details                │
├──────────────┼───────┼──────────┼────────────────────────┤
│ 10-12 10:30  │ 12345 │ COPY     │ Archive → Playout      │
│ 10-12 09:15  │ 12346 │ SCAN     │ Found in archive       │
│ 10-12 09:14  │ 12347 │ VERIFY   │ Checksum OK            │
│ 10-11 18:45  │ 12340 │ COPY     │ ❌ Failed: No space    │
└──────────────┴───────┴──────────┴────────────────────────┘
```

### Детали операции

```
┌──────────────────────────────────────────────────────────┐
│                FILE OPERATION #456                        │
├──────────────────────────────────────────────────────────┤
│                                                           │
│ Operation type: COPY                                     │
│ Video file: #12345 "12345_title.mp4"                    │
│ Status: ✅ SUCCESS                                       │
│                                                           │
│ Source: /mnt/nas/archive/12345_title.mp4                │
│ Destination: /mnt/nas/playout/12345_title.mp4           │
│                                                           │
│ Started: 2025-10-12 10:30:15                            │
│ Completed: 2025-10-12 10:32:48                          │
│ Duration: 2m 33s                                         │
│                                                           │
│ Details:                                                  │
│   Copied 1.2 GB                                          │
│   Speed: 8.5 MB/s                                        │
│   Checksum verified                                      │
│                                                           │
│ Performed by: admin@example.com                          │
│ Trigger: Manual (admin action)                          │
└──────────────────────────────────────────────────────────┘
```

---

## Поиск и фильтрация

### Поиск по номеру или названию

```
Search: [12345_________] 🔍
```

Ищет по:
- Номеру (number)
- Имени файла (filename)
- Пути к файлу (file_path)

### Расширенные фильтры

**По хранилищу:**
```
Storage location: [NAS Archive ▼]
```

**По кодеку:**
```
Video codec: [h264 ▼]
Audio codec: [aac ▼]
```

**По разрешению:**
```
Resolution: [1920x1080 ▼]
```

**По наличию ошибок:**
```
Has errors: [Yes ▼]
```

**По дате добавления:**
```
Created: From [YYYY-MM-DD] To [YYYY-MM-DD]
```

---

## Интеграция с Licenses

Каждый VideoFile автоматически связывается с License по номеру.

### В интерфейсе License

При просмотре лицензии:

```
┌──────────────────────────────────────────────────────────┐
│                    LICENSE #12345                         │
├──────────────────────────────────────────────────────────┤
│ Number: 12345                                            │
│ Title: My Show                                           │
│ ...                                                       │
│                                                           │
│ 🎬 Video File:                                           │
│   ┌────────────────────────────────────────────────────┐│
│   │ 📁 12345_title.mp4                                ││
│   │ 📍 Location: NAS Archive                          ││
│   │ ⏱️ Duration: 00:25:30                             ││
│   │ 📊 1920x1080 @ 25fps                              ││
│   │ [▶ View in Media Files]                           ││
│   └────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

---

## Автоматическое копирование при планировании

Когда создаешь план трансляции в модуле **Planung**:

1. Выбираешь лицензию #12345 для эфира
2. Сохраняешь план (не draft)
3. **Автоматически**:
   - Находится VideoFile #12345 в архиве
   - Копируется в PLAYOUT хранилище
   - Создается FileOperation запись
   - Отправляется уведомление (если настроено)

**Настройка в config:**
```ini
[media]
auto_copy_on_schedule = True  # Включить автокопирование
```

---

## Советы и рекомендации

### ✅ DO:

1. **Создавай отдельные Storage Locations для разных целей:**
   - Один для архива
   - Один для playout
   - По одному для каждой подпапки если нужно

2. **Регулярно запускай сканирование:**
   ```bash
   # Добавь в cron
   0 2 * * * cd /opt/ok-tools && python manage.py scan_video_storage
   ```

3. **Проверяй целостность файлов:**
   ```bash
   python manage.py scan_video_storage --verify-checksums
   ```

4. **Используй Is active для временного отключения:**
   - Не удаляй Storage Location, просто сними галочку

5. **Добавляй описания:**
   - Указывай IP адреса
   - Особенности хранилища
   - Контактную информацию администратора

### ❌ DON'T:

1. **Не удаляй Storage Location если есть VideoFiles:**
   - Сначала переместите или удалите все файлы

2. **Не меняй путь у активного хранилища:**
   - Создай новое Storage Location
   - Перенеси VideoFiles
   - Удали старое

3. **Не запускай сканирование слишком часто:**
   - Это ресурсоемкая операция
   - 1-2 раза в день достаточно

4. **Не забывай про права доступа:**
   - Django должен иметь доступ к путям
   - Проверяй от имени пользователя gunicorn

---

## Troubleshooting

### ❌ "Storage location path does not exist"

```bash
# Проверь монтирование
mount | grep /mnt/nas

# Проверь права
ls -la /mnt/nas/archive

# От имени Django пользователя
sudo -u www-data ls -la /mnt/nas/archive
```

### ❌ "No video files found during scan"

1. Проверь формат файлов: `*.mp4, *.mov, *.mpeg, *.mpg`
2. Проверь наличие номера в начале имени: `12345_title.mp4`
3. Проверь настройку `VIDEO_SUPPORTED_FORMATS` в settings.py

### ❌ "ffprobe not found"

```bash
# Установи ffmpeg
sudo apt install ffmpeg  # Debian
brew install ffmpeg      # macOS

# В Docker
docker-compose exec web which ffprobe
```

### ❌ "Permission denied" при копировании

1. Проверь права на запись в целевую директорию
2. Убери `:ro` (read-only) из docker-compose.yml
3. Проверь свободное место: `df -h /mnt/nas/playout`

---

## Быстрая справка

```
┌─────────────────────────────────────────────────────────┐
│ QUICK REFERENCE                                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Добавить хранилище:                                     │
│   Admin → Media Files → Storage locations → Add         │
│                                                          │
│ Сканировать:                                            │
│   python manage.py scan_video_storage                   │
│                                                          │
│ Просмотреть видео:                                      │
│   Admin → Media Files → Video files → [номер]          │
│                                                          │
│ Скопировать в playout:                                  │
│   Выбрать файлы → Action → Copy to playout             │
│                                                          │
│ История операций:                                        │
│   Admin → Media Files → File operations                 │
│                                                          │
│ Проверить целостность:                                   │
│   Выбрать файлы → Action → Verify integrity            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

