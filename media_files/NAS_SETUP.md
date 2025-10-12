# Настройка NAS хранилища для видеофайлов

## Обзор

Модуль `media_files` поддерживает работу с сетевыми хранилищами (NAS) через протокол SMB/CIFS.

## Сценарий использования

NAS хранилище: `\\192.168.188.1\sendedaten`
- Протокол: SMB/CIFS (Windows share)
- Требуется аутентификация (логин/пароль)

## Способ 1: Монтирование на хост-машине (Рекомендуется)

### Шаг 1: Настрой скрипт монтирования

Отредактируй `scripts/mount_nas.sh`:

```bash
NAS_IP="192.168.188.1"
NAS_SHARE="sendedaten"
NAS_USERNAME="твой_логин"  # Замени!
NAS_PASSWORD="твой_пароль"  # Замени!
```

### Шаг 2: Монтируй NAS

```bash
# Запусти скрипт
./scripts/mount_nas.sh

# Проверь монтирование
ls -la /Volumes/sendedaten
```

### Шаг 3: Структура папок на NAS

Создай необходимую структуру:

```
/Volumes/sendedaten/
├── archive/          # Архив всех видеофайлов
│   ├── 12345_title1.mp4
│   └── 67890_title2.mov
└── playout/          # Файлы для трансляции
    ├── week01/
    ├── week02/
    └── trailers/
```

### Шаг 4: Настрой пути в docker.cfg

Отредактируй `docker.cfg`:

```ini
[media]
# Пути относительно /mnt/nas внутри контейнера
archive_path = /mnt/nas/archive/
playout_path = /mnt/nas/playout/
```

### Шаг 5: Обнови docker-compose.yml

Уже настроено в:
```yaml
volumes:
  - /Volumes/sendedaten:/mnt/nas:ro  # :ro = read-only
```

Для записи измени на:
```yaml
  - /Volumes/sendedaten:/mnt/nas:rw  # :rw = read-write
```

### Шаг 6: Перезапусти контейнеры

```bash
docker-compose down
docker-compose up -d
```

### Шаг 7: Проверь доступ

```bash
# Проверь что контейнер видит NAS
docker-compose exec web ls -la /mnt/nas

# Проверь пути к архиву и playout
docker-compose exec web ls -la /mnt/nas/archive
docker-compose exec web ls -la /mnt/nas/playout
```

## Автоматическое монтирование при загрузке macOS

Создай файл `~/Library/LaunchAgents/com.okmq.mount-nas.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.okmq.mount-nas</string>
    <key>ProgramArguments</key>
    <array>
        <string>/путь/к/ok_tools_dev/scripts/mount_nas.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/mount-nas.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/mount-nas.out</string>
</dict>
</plist>
```

Загрузи agent:
```bash
launchctl load ~/Library/LaunchAgents/com.okmq.mount-nas.plist
```

## Способ 2: Монтирование через Finder (GUI)

1. Открой Finder
2. Нажми `Cmd+K` (Подключение к серверу)
3. Введи: `smb://192.168.188.1/sendedaten`
4. Нажми "Подключиться"
5. Введи логин/пароль
6. NAS будет доступен в `/Volumes/sendedaten`

## Способ 3: Docker CIFS volume (Альтернатива)

Если не хочешь монтировать на хост-машине, используй Docker plugin:

### Установи CIFS plugin

```bash
docker plugin install --alias cifs vieux/sshfs
```

### Обнови docker-compose.yml

```yaml
volumes:
  nas_storage:
    driver: cifs
    driver_opts:
      share: "//192.168.188.1/sendedaten"
      username: "твой_логин"
      password: "твой_пароль"
      vers: "3.0"

services:
  web:
    volumes:
      - nas_storage:/mnt/nas
```

## Troubleshooting

### Ошибка монтирования

```bash
# Проверь доступность NAS
ping 192.168.188.1

# Проверь доступные shares
smbutil view //192.168.188.1

# Тест подключения с логином
smbutil view //логин@192.168.188.1
```

### NAS недоступен в Docker

```bash
# Проверь монтирование на хосте
mount | grep sendedaten

# Проверь права доступа
ls -la /Volumes/sendedaten

# Перезапусти Docker
docker-compose restart
```

### Ошибки доступа к файлам

1. Убери `:ro` из docker-compose.yml (сделай `:rw`)
2. Проверь права на NAS
3. Убедись что пользователь в Docker имеет доступ

## Настройка Storage Locations в Django Admin

После монтирования:

1. Открой http://localhost:8000/admin/
2. Перейди в **Media Files → Storage locations**
3. Создай **Archive**:
   - Name: "NAS Archive"
   - Type: ARCHIVE
   - Path: `/mnt/nas/archive/`
4. Создай **Playout**:
   - Name: "NAS Playout"
   - Type: PLAYOUT
   - Path: `/mnt/nas/playout/`
5. Сохрани

## Сканирование видео

```bash
# Сканируй все storage locations
docker-compose exec web python manage.py scan_video_storage

# Сканируй конкретную location
docker-compose exec web python manage.py scan_video_storage --location "NAS Archive"
```

## Полезные команды

```bash
# Монтировать NAS
./scripts/mount_nas.sh

# Размонтировать NAS
./scripts/umount_nas.sh

# Проверить статус монтирования
mount | grep sendedaten

# Просмотр содержимого
ls -lah /Volumes/sendedaten

# Тест доступа из Docker
docker-compose exec web ls -lah /mnt/nas
```

