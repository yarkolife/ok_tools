# Монтирование NAS на Debian 11 (Production без Docker)

## Сценарий

- **Playout**: `\\192.168.188.1\sendedaten`
- **Archive**: `\\другой_ip\archive_share` (другой сетевой адрес)
- Приложение работает через **gunicorn** на виртуальной машине Debian 11
- **Без Docker** - прямой доступ к файловой системе

---

## Установка необходимых пакетов

```bash
# Обнови систему
sudo apt update

# Установи CIFS utils для монтирования SMB/CIFS
sudo apt install -y cifs-utils

# Проверь установку
dpkg -l | grep cifs-utils
```

---

## Создание точек монтирования

```bash
# Создай директории для монтирования
sudo mkdir -p /mnt/nas/playout
sudo mkdir -p /mnt/nas/archive

# Установи права
sudo chmod 755 /mnt/nas
sudo chmod 755 /mnt/nas/playout
sudo chmod 755 /mnt/nas/archive
```

---

## Создание credentials файла

Для безопасности храни логины/пароли отдельно:

```bash
# Для playout
sudo nano /root/.smbcredentials_playout
```

Содержимое:
```
username=твой_логин_playout
password=твой_пароль_playout
domain=WORKGROUP
```

```bash
# Для archive (если другие credentials)
sudo nano /root/.smbcredentials_archive
```

Содержимое:
```
username=твой_логин_archive
password=твой_пароль_archive
domain=WORKGROUP
```

Защити файлы:
```bash
sudo chmod 600 /root/.smbcredentials_playout
sudo chmod 600 /root/.smbcredentials_archive
```

---

## Ручное монтирование (для тестирования)

### Playout

```bash
sudo mount -t cifs \
  //192.168.188.1/sendedaten \
  /mnt/nas/playout \
  -o credentials=/root/.smbcredentials_playout,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0
```

### Archive

```bash
# ЗАМЕНИ IP и share_name!
sudo mount -t cifs \
  //192.168.XXX.XXX/archive_share \
  /mnt/nas/archive \
  -o credentials=/root/.smbcredentials_archive,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0
```

### Проверь монтирование

```bash
# Проверь что смонтировано
mount | grep cifs

# Посмотри содержимое
ls -la /mnt/nas/playout
ls -la /mnt/nas/archive

# Проверь права доступа
touch /mnt/nas/playout/test.txt  # Если нужна запись
rm /mnt/nas/playout/test.txt
```

---

## Автоматическое монтирование через /etc/fstab

### Вариант 1: Через fstab (простой)

```bash
sudo nano /etc/fstab
```

Добавь в конец файла:

```bash
# NAS Playout
//192.168.188.1/sendedaten  /mnt/nas/playout  cifs  credentials=/root/.smbcredentials_playout,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0

# NAS Archive (ЗАМЕНИ IP и share!)
//192.168.XXX.XXX/archive_share  /mnt/nas/archive  cifs  credentials=/root/.smbcredentials_archive,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0
```

**Параметры:**
- `_netdev` - монтировать после загрузки сети
- `nofail` - продолжить загрузку если NAS недоступен
- `uid=1000,gid=1000` - владелец файлов (замени на пользователя от которого работает gunicorn)
- `vers=3.0` - версия SMB протокола

**Применить:**
```bash
# Размонтируй если уже смонтировано вручную
sudo umount /mnt/nas/playout
sudo umount /mnt/nas/archive

# Монтируй через fstab
sudo mount -a

# Проверь
mount | grep cifs
```

### Вариант 2: Через systemd mount units (более надежный)

Создай systemd unit для playout:

```bash
sudo nano /etc/systemd/system/mnt-nas-playout.mount
```

Содержимое:
```ini
[Unit]
Description=Mount NAS Playout Storage
After=network-online.target
Wants=network-online.target

[Mount]
What=//192.168.188.1/sendedaten
Where=/mnt/nas/playout
Type=cifs
Options=credentials=/root/.smbcredentials_playout,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0,_netdev

[Install]
WantedBy=multi-user.target
```

Создай systemd unit для archive:

```bash
sudo nano /etc/systemd/system/mnt-nas-archive.mount
```

Содержимое:
```ini
[Unit]
Description=Mount NAS Archive Storage
After=network-online.target
Wants=network-online.target

[Mount]
What=//192.168.XXX.XXX/archive_share
Where=/mnt/nas/archive
Type=cifs
Options=credentials=/root/.smbcredentials_archive,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0,_netdev

[Install]
WantedBy=multi-user.target
```

**Активировать:**
```bash
# Перезагрузи systemd
sudo systemctl daemon-reload

# Включи автозапуск
sudo systemctl enable mnt-nas-playout.mount
sudo systemctl enable mnt-nas-archive.mount

# Запусти сейчас
sudo systemctl start mnt-nas-playout.mount
sudo systemctl start mnt-nas-archive.mount

# Проверь статус
sudo systemctl status mnt-nas-playout.mount
sudo systemctl status mnt-nas-archive.mount
```

---

## Настройка OK Tools для работы без Docker

### 1. Обнови конфигурацию

Для production используй файл из `deployment/configs/`:

```bash
# Например для OK NRW
sudo nano /path/to/production.cfg
```

Секция `[media]`:
```ini
[media]
# Прямые пути без /mnt/nas префикса если нужно
# Или с префиксом если используешь /mnt/nas
archive_path = /mnt/nas/archive/
playout_path = /mnt/nas/playout/

auto_scan = False
auto_copy_on_schedule = True
```

### 2. Проверь права доступа для gunicorn

```bash
# Узнай от какого пользователя работает gunicorn
ps aux | grep gunicorn

# Например если это пользователь 'www-data' или 'oktools'
# Проверь что он может читать/писать
sudo -u www-data ls -la /mnt/nas/playout
sudo -u www-data touch /mnt/nas/playout/test.txt
sudo -u www-data rm /mnt/nas/playout/test.txt
```

Если права не подходят, исправь в fstab/systemd units:
- Замени `uid=1000,gid=1000` на `uid=$(id -u www-data),gid=$(id -g www-data)`

### 3. Установи ffmpeg

```bash
# Установи ffmpeg для извлечения метаданных
sudo apt install -y ffmpeg

# Проверь
ffprobe -version
which ffprobe
```

### 4. Создай Storage Locations в Django Admin

После монтирования:

1. Открой админку: `https://your-domain.de/admin/`
2. **Media Files → Storage locations → Add**

**Playout:**
```
Name: Production Playout
Type: PLAYOUT
Path: /mnt/nas/playout/
Description: Sendedaten - 192.168.188.1
```

**Archive:**
```
Name: Production Archive
Type: ARCHIVE  
Path: /mnt/nas/archive/
Description: Archive - 192.168.XXX.XXX
```

### 5. Первое сканирование

```bash
# Активируй virtualenv если используешь
source /path/to/venv/bin/activate

# Запусти сканирование
cd /path/to/ok_tools
python manage.py scan_video_storage

# Или через systemd если настроен
sudo systemctl start oktools-scan-videos.service
```

---

## Скрипты для management

### Скрипт проверки монтирования

```bash
sudo nano /usr/local/bin/check-nas-mounts.sh
```

Содержимое:
```bash
#!/bin/bash
# Check if NAS shares are mounted

PLAYOUT="/mnt/nas/playout"
ARCHIVE="/mnt/nas/archive"

check_mount() {
    local path=$1
    local name=$2
    
    if mountpoint -q "$path"; then
        echo "✅ $name is mounted"
        return 0
    else
        echo "❌ $name is NOT mounted"
        return 1
    fi
}

echo "Checking NAS mounts..."
check_mount "$PLAYOUT" "Playout"
playout_status=$?

check_mount "$ARCHIVE" "Archive"
archive_status=$?

if [ $playout_status -eq 0 ] && [ $archive_status -eq 0 ]; then
    echo "✅ All NAS shares mounted successfully"
    exit 0
else
    echo "❌ Some NAS shares are not mounted"
    echo "Try: sudo systemctl start mnt-nas-*.mount"
    exit 1
fi
```

```bash
sudo chmod +x /usr/local/bin/check-nas-mounts.sh
```

### Скрипт ремонтирования

```bash
sudo nano /usr/local/bin/remount-nas.sh
```

Содержимое:
```bash
#!/bin/bash
# Remount NAS shares

echo "Remounting NAS shares..."

sudo systemctl restart mnt-nas-playout.mount
sudo systemctl restart mnt-nas-archive.mount

sleep 2

/usr/local/bin/check-nas-mounts.sh
```

```bash
sudo chmod +x /usr/local/bin/remount-nas.sh
```

---

## Мониторинг и автовосстановление

### Systemd timer для проверки (опционально)

```bash
sudo nano /etc/systemd/system/check-nas-mounts.service
```

```ini
[Unit]
Description=Check NAS mounts health
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/check-nas-mounts.sh
```

```bash
sudo nano /etc/systemd/system/check-nas-mounts.timer
```

```ini
[Unit]
Description=Check NAS mounts every 5 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

Активируй:
```bash
sudo systemctl daemon-reload
sudo systemctl enable check-nas-mounts.timer
sudo systemctl start check-nas-mounts.timer
```

---

## Troubleshooting

### Проблема: "mount error(112): Host is down"

```bash
# Проверь доступность NAS
ping 192.168.188.1
ping 192.168.XXX.XXX

# Проверь доступные shares
smbclient -L //192.168.188.1 -U username
```

### Проблема: "Permission denied"

```bash
# Проверь credentials
sudo cat /root/.smbcredentials_playout

# Попробуй подключиться вручную для диагностики
smbclient //192.168.188.1/sendedaten -U username
```

### Проблема: "Operation not permitted"

```bash
# Проверь SELinux (если включен)
sudo sestatus

# Временно отключи для теста
sudo setenforce 0

# Или настрой SELinux context
sudo chcon -t cifs_t /mnt/nas/playout
```

### Размонтирование

```bash
# Через systemd
sudo systemctl stop mnt-nas-playout.mount
sudo systemctl stop mnt-nas-archive.mount

# Или напрямую
sudo umount /mnt/nas/playout
sudo umount /mnt/nas/archive

# Принудительно если зависло
sudo umount -f /mnt/nas/playout
```

---

## Настройка для gunicorn systemd service

Убедись что gunicorn запускается ПОСЛЕ монтирования NAS:

```bash
sudo nano /etc/systemd/system/oktools.service
```

Добавь зависимости:
```ini
[Unit]
Description=OK Tools Gunicorn Service
After=network.target postgresql.service mnt-nas-playout.mount mnt-nas-archive.mount
Requires=mnt-nas-playout.mount mnt-nas-archive.mount

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/ok_tools
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn ok_tools.wsgi:application --bind 0.0.0.0:8000

[Install]
WantedBy=multi-user.target
```

---

## Резюме команд

```bash
# 1. Установка
sudo apt install cifs-utils ffmpeg

# 2. Создание credentials
sudo nano /root/.smbcredentials_playout
sudo nano /root/.smbcredentials_archive
sudo chmod 600 /root/.smbcredentials_*

# 3. Создание mount points
sudo mkdir -p /mnt/nas/{playout,archive}

# 4. Настройка fstab ИЛИ systemd units
sudo nano /etc/fstab
# или
sudo nano /etc/systemd/system/mnt-nas-*.mount

# 5. Монтирование
sudo mount -a
# или
sudo systemctl start mnt-nas-*.mount

# 6. Проверка
mount | grep cifs
ls -la /mnt/nas/playout
ls -la /mnt/nas/archive

# 7. Перезапуск gunicorn
sudo systemctl restart oktools.service
```

---

Готово! Теперь NAS будет автоматически монтироваться при загрузке сервера.

