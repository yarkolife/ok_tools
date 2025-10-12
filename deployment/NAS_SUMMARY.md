# Итоговое резюме: Настройка NAS для OK Tools

## 📋 Обзор решения

Создано **полное решение** для работы с сетевыми хранилищами (NAS) через SMB/CIFS протокол в двух сценариях:

### 1️⃣ Development (Docker на macOS)
- NAS монтируется на хост-машине
- Docker контейнеры получают доступ через bind mount
- Идеально для разработки и тестирования

### 2️⃣ Production (Gunicorn на Debian 11)
- Прямое монтирование NAS в файловую систему сервера
- Автоматическое монтирование через fstab/systemd
- Поддержка **нескольких NAS** с **разными IP-адресами**

---

## 📦 Созданные файлы

### Development (Docker)
```
scripts/
├── mount_nas.sh              # Монтирование NAS на macOS
├── umount_nas.sh             # Размонтирование
└── test_nas_access.sh        # Проверка доступа из Docker

media_files/
└── NAS_SETUP.md              # Полная инструкция для Docker

docker-compose.yml             # ✅ Обновлен с volumes для NAS
docker.cfg                     # ✅ Обновлен с путями к NAS
NAS_QUICK_START.txt           # Краткая шпаргалка
```

### Production (Debian)
```
deployment/
├── NAS_DEBIAN_SETUP.md              # Полная инструкция для Debian 11
├── PRODUCTION_NAS_QUICKSTART.txt    # Краткая шпаргалка для production
├── NAS_SUMMARY.md                   # Этот файл
├── README.md                        # ✅ Обновлен с разделом о NAS
├── configs/
│   ├── ok-bayern-production.cfg    # ✅ Добавлена секция [media]
│   ├── ok-nrw-production.cfg       # ✅ Добавлена секция [media]
│   └── okmq-production.cfg         # ✅ Добавлена секция [media]
└── scripts/
    └── setup-nas-debian.sh         # 🆕 Автоматизированная установка
```

---

## 🎯 Ключевые возможности

### ✅ Поддержка нескольких NAS
- **Playout**: `\\192.168.188.1\sendedaten`
- **Archive**: `\\другой_ip\archive` (может быть на другом сервере!)

### ✅ Разные credentials
- Отдельные файлы credentials для каждого NAS
- Защита через `chmod 600`

### ✅ Автоматическое монтирование
- **macOS**: через скрипты или LaunchAgent
- **Debian**: через `/etc/fstab` или systemd mount units

### ✅ Права доступа
- Автоматическая настройка `uid`/`gid` для пользователя gunicorn
- Поддержка read-only и read-write режимов

### ✅ Мониторинг
- Скрипты проверки здоровья
- Автоматическое ремонтирование
- Логирование через systemd

---

## 🚀 Быстрый старт

### Development (Docker на macOS)

```bash
# 1. Настрой credentials
nano scripts/mount_nas.sh

# 2. Монтируй NAS
./scripts/mount_nas.sh

# 3. Перезапусти Docker
docker-compose down && docker-compose up -d

# 4. Проверь доступ
./scripts/test_nas_access.sh
```

📖 **Подробно**: `NAS_QUICK_START.txt`

### Production (Debian 11)

```bash
# Вариант 1: Автоматическая установка
sudo deployment/scripts/setup-nas-debian.sh

# Вариант 2: Ручная установка
# Следуй инструкциям в deployment/PRODUCTION_NAS_QUICKSTART.txt
```

📖 **Подробно**: `deployment/NAS_DEBIAN_SETUP.md`

---

## 📝 Пример конфигурации

### Debian `/etc/fstab`

```bash
# NAS Playout - 192.168.188.1
//192.168.188.1/sendedaten  /mnt/nas/playout  cifs  \
  credentials=/root/.smbcredentials_playout,\
  uid=1000,gid=1000,\
  file_mode=0755,dir_mode=0755,\
  vers=3.0,_netdev,nofail  0  0

# NAS Archive - другой IP!
//192.168.XXX.XXX/archive  /mnt/nas/archive  cifs  \
  credentials=/root/.smbcredentials_archive,\
  uid=1000,gid=1000,\
  file_mode=0755,dir_mode=0755,\
  vers=3.0,_netdev,nofail  0  0
```

### Production config (`.cfg`)

```ini
[media]
# Пути к смонтированным NAS
archive_path = /mnt/nas/archive/
playout_path = /mnt/nas/playout/

# Настройки сканирования
auto_scan = False
auto_copy_on_schedule = True
```

### Docker config (`docker.cfg`)

```ini
[media]
# Внутри контейнера все под /mnt/nas
archive_path = /mnt/nas/archive/
playout_path = /mnt/nas/playout/

auto_scan = False
auto_copy_on_schedule = True
```

---

## 🔧 Техническая информация

### Протокол
- **SMB/CIFS** версия 3.0
- Поддержка Windows Server / NAS / Samba

### Монтирование
- **macOS**: `mount_smbfs` (нативный)
- **Linux**: `cifs-utils` пакет

### Опции монтирования
- `_netdev` - монтировать после загрузки сети
- `nofail` - продолжить загрузку если NAS недоступен
- `vers=3.0` - использовать SMB v3.0
- `uid/gid` - владелец смонтированных файлов

### Безопасность
- Credentials хранятся в `/root/.smbcredentials_*`
- Права доступа: `600` (только root может читать)
- Поддержка domain аутентификации

---

## 🎬 Workflow использования

### 1. Настройка (один раз)

```bash
# Development
./scripts/mount_nas.sh

# Production
sudo deployment/scripts/setup-nas-debian.sh
```

### 2. Создание Storage Locations в Django Admin

```
http://localhost:8000/admin/
→ Media Files → Storage locations

Playout:
  Name: Production Playout
  Type: PLAYOUT
  Path: /mnt/nas/playout/

Archive:
  Name: Production Archive  
  Type: ARCHIVE
  Path: /mnt/nas/archive/
```

### 3. Сканирование видеофайлов

```bash
# Development
docker-compose exec web python manage.py scan_video_storage

# Production
cd /opt/ok-tools && python manage.py scan_video_storage
```

### 4. Автоматическое копирование

При создании плана трансляции в модуле **Planung**:
- Видео автоматически копируются из Archive → Playout
- Используется номер лицензии для поиска файла
- Логируется через `FileOperation` модель

---

## 🆘 Troubleshooting

### ❌ "Host is down"
```bash
# Проверь доступность
ping 192.168.188.1

# Проверь доступные shares
smbclient -L //192.168.188.1 -U username
```

### ❌ "Permission denied"
```bash
# Проверь credentials
sudo cat /root/.smbcredentials_playout

# Проверь uid/gid в fstab
id -u www-data && id -g www-data
```

### ❌ NAS не монтируется при загрузке
```bash
# Debian
sudo systemctl enable mnt-nas-playout.mount
sudo systemctl enable mnt-nas-archive.mount

# Или через fstab с опциями _netdev,nofail
```

### ❌ Контейнер не видит NAS
```bash
# Проверь монтирование на хосте
mount | grep sendedaten

# Перезапусти Docker
docker-compose restart
```

---

## 📚 Документация

| Файл | Описание |
|------|----------|
| `media_files/NAS_SETUP.md` | Полная инструкция для Docker/macOS |
| `deployment/NAS_DEBIAN_SETUP.md` | Полная инструкция для Debian 11 |
| `NAS_QUICK_START.txt` | Краткая шпаргалка для Docker |
| `deployment/PRODUCTION_NAS_QUICKSTART.txt` | Краткая шпаргалка для Production |
| `media_files/README.md` | Документация модуля media_files |
| `deployment/README.md` | Общая документация по деплойменту |

---

## ✅ Тестирование

### Docker
```bash
./scripts/test_nas_access.sh
```

### Production
```bash
# Проверка монтирования
mount | grep cifs

# Проверка доступа
sudo -u www-data ls -la /mnt/nas/playout
sudo -u www-data ls -la /mnt/nas/archive

# Проверка работы модуля
cd /opt/ok-tools
python manage.py check
python manage.py scan_video_storage --dry-run
```

---

## 🎉 Итог

**Полностью готовое решение** для работы с сетевыми хранилищами:

✅ Поддержка нескольких NAS с разными IP  
✅ Автоматическое монтирование  
✅ Скрипты для automation  
✅ Полная документация  
✅ Интеграция с Django media_files модулем  
✅ Работает в Docker и на bare metal  

**Следующий шаг**: Запусти `scan_video_storage` и начни работать с видеофайлами! 🎬

