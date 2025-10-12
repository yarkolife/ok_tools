# Настройка тестового видео в Django Admin

## ✅ Что уже сделано:

1. Создана папка `playout/` в корне проекта
2. Видео переименовано и перемещено:
   - Было: `VID-20250905-WA0047.mp4`
   - Стало: `playout/99999_test_video.mp4`
3. Видео доступно в Docker контейнере: `/app/playout/99999_test_video.mp4`

---

## 📋 Настройка через Django Admin

### Шаг 1: Открой админ-панель

```
http://localhost:8000/admin/
```

Логин: `admin@example.com`  
Пароль: `admin123`

---

### Шаг 2: Создай Storage Location

1. В меню слева выбери: **Media Files → Storage locations**
2. Нажми кнопку **[+ Add storage location]** (справа вверху)
3. Заполни форму:

```
┌─────────────────────────────────────────────┐
│ Add storage location                        │
├─────────────────────────────────────────────┤
│                                             │
│ Name: *                                     │
│ ┌─────────────────────────────────────────┐│
│ │ Local Test Playout                      ││ ← Любое название
│ └─────────────────────────────────────────┘│
│                                             │
│ Storage type: *                             │
│ ┌─────────────────────────────────────────┐│
│ │ PLAYOUT ▼                               ││ ← Выбери PLAYOUT
│ └─────────────────────────────────────────┘│
│                                             │
│ Path: *                                     │
│ ┌─────────────────────────────────────────┐│
│ │ /app/playout/                           ││ ← Путь внутри контейнера
│ └─────────────────────────────────────────┘│
│                                             │
│ ☑ Active                                   │ ← Оставь включенным
│                                             │
│ ☐ Scan enabled                             │ ← Можно не включать
│                                             │
│ Scan schedule:                              │
│ ┌─────────────────────────────────────────┐│
│ │                                         ││ ← Оставь пустым
│ └─────────────────────────────────────────┘│
│                                             │
│              [Save and continue]   [Save]  │
└─────────────────────────────────────────────┘
```

4. Нажми **[Save]**

---

### Шаг 3: Добавь VideoFile (2 способа)

#### Способ A: Автоматическое сканирование (рекомендуется)

1. Открой терминал:
```bash
docker-compose exec web python manage.py scan_video_storage
```

2. Увидишь:
```
Scanning storage locations for video files...

Processing storage: Local Test Playout (/app/playout/)
  Found 1 video files
  Processing: 99999_test_video.mp4
    ✓ Extracted metadata
    ✓ Calculated checksum
    → Created VideoFile #99999

Summary:
  Scanned: 1 locations
  Found: 1 files
  Created: 1 new records
```

3. Готово! Видео добавлено автоматически.

#### Способ B: Ручное добавление через админку

1. В меню слева: **Media Files → Video files**
2. Нажми **[+ Add video file]**
3. Заполни форму:

```
┌─────────────────────────────────────────────┐
│ Add video file                              │
├─────────────────────────────────────────────┤
│                                             │
│ Storage location: *                         │
│ ┌─────────────────────────────────────────┐│
│ │ Local Test Playout ▼                    ││ ← Выбери созданное хранилище
│ └─────────────────────────────────────────┘│
│                                             │
│ Or specify file path:                       │
│ ┌─────────────────────────────────────────┐│
│ │ /app/playout/99999_test_video.mp4       ││ ← Полный путь к файлу
│ └─────────────────────────────────────────┘│
│                                             │
│ ☑ Is available                             │
│                                             │
│                        [Save and continue] │
│                                    [Save]  │
└─────────────────────────────────────────────┘
```

4. Нажми **[Save]**

⚙️ **Что произойдет автоматически:**
- Номер извлечется из имени файла: `99999`
- Метаданные извлекутся через ffprobe (duration, codec, resolution, etc.)
- Рассчитается SHA256 checksum
- Создастся VideoFile запись

---

### Шаг 4: Просмотр видео

1. После добавления перейди в: **Media Files → Video files**
2. Найди VideoFile #99999
3. Кликни на номер `99999`
4. Увидишь страницу с детальной информацией:

```
┌──────────────────────────────────────────────┐
│            VIDEO FILE #99999                 │
├──────────────────────────────────────────────┤
│                                              │
│ ┌──────────────────────────────────────────┐│
│ │                                          ││
│ │       [▶ HTML5 Video Player]            ││
│ │                                          ││
│ │   99999_test_video.mp4                  ││
│ │   [=========|========] 00:00:15/00:00:30││
│ │        🔊 Volume: ▮▮▮▮▮▮▮▯▯▯            ││
│ │                                          ││
│ └──────────────────────────────────────────┘│
│                                              │
│ Basic Information:                           │
│   Number: 99999                             │
│   Filename: 99999_test_video.mp4            │
│   Storage: Local Test Playout               │
│   Size: 2.4 MB                              │
│                                              │
│ Video Properties:                            │
│   Duration: 00:00:30                        │
│   Codec: h264                               │
│   Resolution: 720x480                       │
│   Frame rate: 30.00 fps                     │
│   ...                                        │
└──────────────────────────────────────────────┘
```

5. Видео можно смотреть прямо в админке!

---

### Шаг 5: Проверь связь с License (опционально)

Если создашь License с номером 99999:

1. Перейди: **Licenses → Add license**
2. Создай лицензию с любыми данными
3. Разверни секцию **"Status & Metadata"**
4. В поле **"Video File"** увидишь:

```
Video File:
🎬 99999_test_video.mp4
00:00:30 • 720x480 • 2.4 MB
✓ Available • Local Test Playout
```

Кликни на имя файла → откроется VideoFile с плеером!

---

## 🎯 Быстрая проверка (все в одном)

```bash
# 1. Проверь что файл доступен
docker-compose exec web ls -la /app/playout/

# 2. Запусти автосканирование
docker-compose exec web python manage.py scan_video_storage

# 3. Проверь что VideoFile создан
docker-compose exec web python manage.py shell -c "from media_files.models import VideoFile; v = VideoFile.objects.get(number=99999); print(f'✅ Found: {v.filename}')"

# Должно вывести:
# ✅ Found: 99999_test_video.mp4
```

---

## 📁 Структура проекта

```
ok_tools_dev/
├── playout/                          ← Новая папка
│   └── 99999_test_video.mp4         ← Тестовое видео
├── docker-compose.yml                ← Уже монтирует .:/app
├── media_files/                      ← Модуль видео
└── ...
```

Внутри Docker контейнера:
```
/app/
├── playout/                          ← Доступно здесь!
│   └── 99999_test_video.mp4
└── ...
```

---

## ⚠️ Важные моменты

### 1. Путь должен заканчиваться на `/`
```
✅ /app/playout/
❌ /app/playout
```

### 2. Имя файла должно начинаться с номера
```
✅ 99999_test_video.mp4
✅ 12345_название.mp4
❌ video.mp4
❌ test_99999.mp4
```

### 3. Поддерживаемые форматы
```
✅ .mp4
✅ .mov
✅ .mpeg
✅ .mpg
```

---

## 🔧 Troubleshooting

### ❌ "Path does not exist or is not accessible"

Проверь путь в контейнере:
```bash
docker-compose exec web ls -la /app/playout/
```

Если папка пустая - проверь на хосте:
```bash
ls -la playout/
```

### ❌ "No video files found"

Причины:
1. Файл не начинается с номера → переименуй
2. Неправильный путь в Storage Location → проверь
3. Неподдерживаемый формат → используй mp4/mov/mpeg/mpg

### ❌ "ffprobe not found"

ffprobe уже установлен в Docker образе. Если ошибка - пересобери контейнер:
```bash
docker-compose down
docker-compose up -d --build
```

---

## ✅ Готово!

Теперь у тебя:
1. ✅ Локальная папка `playout/` с тестовым видео
2. ✅ Storage Location настроен в Django Admin
3. ✅ VideoFile #99999 доступен для просмотра
4. ✅ Можно смотреть видео прямо в админке

**Следующие шаги:**
- Добавь больше видео в `playout/`
- Создай Storage Location для архива
- Протестируй копирование между хранилищами
- Создай License #99999 и посмотри связь

---

📖 **Документация:**
- `media_files/ADMIN_GUIDE.md` - Полное руководство
- `media_files/MANUAL_UPLOAD.md` - Ручное добавление видео
- `QUICK_ANSWERS.md` - Быстрые ответы

