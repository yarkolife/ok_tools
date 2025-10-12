# Media Files Management Module

Модуль управления видеофайлами для OK Tools с автоматическим поиском, хранением метаданных и интеграцией с планировщиком трансляций.

> **📖 Настройка NAS хранилища**: См. [NAS_SETUP.md](./NAS_SETUP.md) для подключения сетевых хранилищ SMB/CIFS.

## Возможности

- 📁 **Гибкое хранение**: Управление несколькими местами хранения (архив, playout, custom)
- 🔍 **Автоматическое сканирование**: Поиск видеофайлов по номеру в имени файла
- 📊 **Подробные метаданные**: Извлечение всех технических параметров через ffprobe
  - Видео: кодек, битрейт, FPS, разрешение, цветовое пространство, chroma subsampling
  - Аудио: кодек, битрейт, количество каналов, sample rate
- 🎬 **Просмотр видео**: Встроенный плеер в админ-панели
- 🔄 **Автокопирование**: Автоматическое копирование из архива в playout при планировании эфира
- ✅ **Проверка целостности**: Checksum для верификации файлов
- 📝 **История операций**: Полное логирование всех действий с файлами

## Установка

### 1. Зависимости

Убедитесь, что установлены:
- **ffmpeg/ffprobe**: Для извлечения метаданных
  ```bash
  # Ubuntu/Debian
  sudo apt-get install ffmpeg
  
  # macOS
  brew install ffmpeg
  ```

### 2. Миграции

```bash
python manage.py migrate media_files
```

### 3. Конфигурация

Добавьте в config файл (например, `docker.cfg`):

```ini
[media]
# Archive path - where video files are stored long-term
archive_path = /mnt/archive/

# Playout path - where video files are copied for broadcasting
playout_path = /mnt/playout/library/

# Auto-scan storage locations for new files
auto_scan = False

# Auto-copy videos to playout when broadcast plan is saved
auto_copy_on_schedule = True
```

### 4. Создание хранилищ

Через Django Admin создайте `StorageLocation`:

1. **Archive** (storage_type=ARCHIVE):
   - Name: "Video Archive"
   - Path: `/mnt/archive/`
   - Is Active: ✓
   - Scan Enabled: ✓

2. **Playout** (storage_type=PLAYOUT):
   - Name: "Playout Library"
   - Path: `/mnt/playout/library/`
   - Is Active: ✓

## Использование

### Management команды

#### 1. Сканирование хранилища

```bash
# Сканировать конкретное хранилище
python manage.py scan_video_storage --storage-id 1

# Сканировать все активные хранилища
python manage.py scan_video_storage --all

# Принудительное пересканирование с обновлением метаданных
python manage.py scan_video_storage --all --force --update-metadata

# С расчетом checksum (медленно для больших файлов)
python manage.py scan_video_storage --all --calculate-checksum
```

#### 2. Обновление метаданных

```bash
# Обновить метаданные для конкретного видео
python manage.py update_video_metadata --number 12345

# Обновить все видео
python manage.py update_video_metadata --all

# Обновить только файлы с отсутствующими метаданными
python manage.py update_video_metadata --all --missing-only

# С пересчетом checksum
python manage.py update_video_metadata --all --calculate-checksum
```

#### 3. Копирование в playout

```bash
# Скопировать конкретные видео
python manage.py copy_to_playout --number 12345 17890

# Скопировать видео из плана трансляций для конкретной даты
python manage.py copy_to_playout --date 2025-10-15

# В конкретное хранилище
python manage.py copy_to_playout --number 12345 --destination-id 2

# Пропустить уже существующие
python manage.py copy_to_playout --date 2025-10-15 --skip-existing
```

#### 4. Очистка playout

```bash
# Удалить файлы старше 7 дней (по умолчанию)
python manage.py cleanup_playout

# Удалить файлы старше 30 дней
python manage.py cleanup_playout --days-old 30

# Предпросмотр без удаления
python manage.py cleanup_playout --dry-run

# Оставить записи в БД, удалить только физические файлы
python manage.py cleanup_playout --keep-in-database
```

### Работа через Django Admin

> **📖 Полное руководство по Django Admin**: См. [ADMIN_GUIDE.md](./ADMIN_GUIDE.md) для детальных инструкций со скриншотами.

#### Быстрый старт: Добавление хранилища

1. Открой админ-панель: `http://localhost:8000/admin/`
2. Перейди: **Media Files → Storage locations → Add**
3. Заполни форму:
   ```
   Name: NAS Archive
   Type: ARCHIVE
   Path: /mnt/nas/archive/
   Description: Архив на NAS 192.168.XXX.XXX
   Is active: ☑
   ```
4. Сохрани
5. Запусти сканирование:
   ```bash
   python manage.py scan_video_storage
   ```

#### Управление хранилищами (StorageLocation)

- **Действия**:
  - "Scan now" - Запустить сканирование выбранных хранилищ
  - "Test connection" - Проверить доступность путей

#### Управление видеофайлами (VideoFile)

- **Поиск**: По номеру, имени файла, кодекам
- **Фильтры**: По хранилищу, формату, доступности, дате создания
- **Действия**:
  - "Copy to playout storage" - Скопировать в playout
  - "Update metadata" - Обновить метаданные
  - "Verify file integrity" - Проверить checksum
- **Просмотр видео**: Встроенный HTML5 плеер с поддержкой seeking

### API Интеграция

#### Автокопирование при планировании

При сохранении плана трансляций (не черновика) в модуле `planung`, видео автоматически копируются из архива в playout:

```python
# Это происходит автоматически в planung/views.py
# при сохранении TagesPlan с draft=False
```

#### Программное использование

```python
from media_files.models import VideoFile, StorageLocation
from media_files.tasks import copy_video_to_playout

# Найти видео
video = VideoFile.objects.get(number=12345)

# Копировать в playout
success, message = copy_video_to_playout(video)

# Получить видео для License
from licenses.models import License
license = License.objects.get(number=12345)
video_file = license.get_video_file()
```

## Структура файлов

### Соглашения об именовании

Видеофайлы должны следовать формату:
```
<number>_<название>.<расширение>
```

Примеры:
- `12345_моё_видео.mp4`
- `17890_репортаж_2025.mov`
- `99999_интервью.mpg`

### Поддерживаемые форматы

По умолчанию: `mp4`, `mov`, `mpeg`, `mpg`

Можно изменить в `settings.py`:
```python
VIDEO_SUPPORTED_FORMATS = ['mp4', 'mov', 'mpeg', 'mpg', 'avi', 'mkv']
```

## Метаданные видео

Модуль извлекает и хранит следующие метаданные:

### Общие
- Формат контейнера
- Размер файла
- Длительность
- Общий битрейт
- Checksum (SHA256)

### Видео
- Кодек (короткое и полное название)
- Профиль кодека
- Битрейт
- FPS (частота кадров)
- Разрешение (ширина x высота)
- Соотношение сторон
- Формат пикселей (pixel format)
- Цветовое пространство (bt709, bt2020, etc.)
- Диапазон цвета (tv, pc)
- Chroma subsampling (4:2:0, 4:2:2, 4:4:4)

### Аудио
- Кодек (короткое и полное название)
- Битрейт
- Sample rate
- Количество каналов
- Channel layout (stereo, 5.1, mono, etc.)

## Архитектура

### Модели

#### StorageLocation
Место хранения видеофайлов (архив, playout, custom).

#### VideoFile
Запись о видеофайле с полными метаданными.

#### FileOperation
История операций с файлами (сканирование, копирование, удаление).

### Утилиты (utils.py)

- `extract_number_from_filename()` - Извлечение номера из имени
- `scan_directory()` - Сканирование папки
- `extract_video_metadata()` - Извлечение метаданных через ffprobe
- `calculate_checksum()` - Расчет SHA256
- `copy_file_with_progress()` - Копирование с верификацией
- `verify_file_integrity()` - Проверка целостности

### Tasks (tasks.py)

- `copy_videos_for_plan()` - Автокопирование для плана эфира
- `copy_video_to_playout()` - Копирование одного видео

## Troubleshooting

### Видео не находятся при сканировании

1. Проверьте формат имени файла: `<число>_название.расширение`
2. Проверьте поддерживаемые форматы в `VIDEO_SUPPORTED_FORMATS`
3. Проверьте доступность пути в StorageLocation

### Ошибка извлечения метаданных

1. Убедитесь, что установлен ffmpeg/ffprobe:
   ```bash
   ffprobe -version
   ```
2. Проверьте права доступа к файлам
3. Проверьте, что файл не поврежден

### Видео не воспроизводится в админке

1. Проверьте поддержку формата в браузере
2. Убедитесь, что `is_available = True`
3. Проверьте путь к файлу

### Автокопирование не работает

1. Проверьте настройку `VIDEO_AUTO_COPY_ON_SCHEDULE = True`
2. Убедитесь, что план сохранен с `draft=False`
3. Проверьте логи: `ok_tools-debug.log`

## Безопасность

- Все операции логируются в `FileOperation`
- Checksum для проверки целостности при копировании
- Физические файлы не удаляются при удалении записи из БД (только через cleanup команду)
- Только staff пользователи имеют доступ к управлению

## Performance

- Используйте `--calculate-checksum` только когда необходимо (медленно для больших файлов)
- При больших объемах данных запускайте сканирование в фоне
- Регулярно очищайте playout от старых файлов

## Лицензия

Часть проекта OK Tools.

## Поддержка

Для вопросов и проблем создавайте issues в репозитории проекта.

