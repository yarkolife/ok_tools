# Установка OK Tools на Debian сервер (доступ по IP)

## 🎯 Для OK Merseburg - локальная сеть без домена

**Тип установки:** Gunicorn + Nginx + PostgreSQL (БЕЗ Docker)  
**Доступ:** По IP адресу внутри локальной сети

---

## 🚀 Автоматическая установка (Рекомендуется)

### 1. На сервере через SSH:

```bash
ssh user@YOUR_SERVER_IP
# Введи пароль

# Установи git и клонируй репозиторий
sudo apt update
sudo apt install -y git
cd /opt
sudo git clone https://github.com/yarkolife/ok_tools.git ok-tools
cd ok-tools

# Запусти установку
sudo bash deployment/scripts/setup-ok-merseburg-test-ip.sh
```

### 2. Скрипт спросит:

✓ **Пароль PostgreSQL** - для базы данных  
✓ **IP адрес сервера** - например `192.168.1.100`  
✓ **NAS Playout** - IP, share name, логин/пароль  
✓ **NAS Archive** - отдельный или тот же что playout  
✓ **Email** - настроить или нет (опционально для тестового)  
✓ **Суперпользователь Django** - логин/пароль для админки

### 3. Установка займет ~10-15 минут

Скрипт автоматически:
- Установит Python, PostgreSQL, Nginx, FFmpeg
- Создаст пользователя и директории
- Настроит базу данных
- Смонтирует NAS хранилища
- Установит зависимости Python
- Настроит Gunicorn (bind на 0.0.0.0:8000)
- Настроит Nginx (без SSL, без домена)
- Применит миграции Django

---

## 📋 После установки

### A) Проверь что работает

```bash
# Проверь сервисы
sudo systemctl status oktools
sudo systemctl status nginx

# Проверь доступ
curl http://192.168.1.100  # твой IP

# Или открой в браузере
http://192.168.1.100
```

### B) Импорт дампа базы данных

Если у тебя есть дамп:

```bash
# Скопируй дамп на сервер
scp /path/to/dump.sql user@SERVER_IP:/tmp/

# На сервере импортируй
sudo -u postgres psql oktools_test < /tmp/dump.sql

# Или если нужна только таблица лицензий
sudo -u postgres pg_restore -d oktools_test -t licenses_license /tmp/dump.dump
```

### C) Создай Storage Locations

Открой админку: `http://192.168.1.100/admin/`

**Media Files → Storage locations → Add:**

**Playout:**
- Name: `OK Merseburg Playout`
- Type: `PLAYOUT`
- Path: `/mnt/nas/playout/`
- Is active: ✓

**Archive:**
- Name: `OK Merseburg Archive`
- Type: `ARCHIVE`
- Path: `/mnt/nas/archive/`
- Is active: ✓

### D) Первое сканирование видео

```bash
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg

python manage.py scan_video_storage
```

---

## 🔧 Основные отличия от установки с доменом

| Параметр | С доменом | По IP (эта установка) |
|----------|-----------|----------------------|
| URL доступа | https://domain.de | http://192.168.1.100 |
| SSL/HTTPS | Да (Let's Encrypt) | Нет |
| Nginx bind | server_name domain | server_name IP _ |
| Gunicorn bind | 127.0.0.1:8000 | 0.0.0.0:8000 |
| CSRF protection | Да | Упрощенная |
| Allowed hosts | domain.de | IP, localhost |

---

## 🛠️ Конфигурация

### Файл: `/opt/ok-tools/config/production.cfg`

```ini
[site]
domain = 192.168.1.100        # Твой IP
allowed_hosts = 192.168.1.100,localhost,127.0.0.1

[security]
csrf_cookie_secure = False    # Нет HTTPS
session_cookie_secure = False # Нет HTTPS
secure_ssl_redirect = False   # Не редиректим на HTTPS
secure_hsts_seconds = 0       # HSTS отключен
```

### Nginx: `/etc/nginx/sites-available/oktools`

```nginx
server {
    listen 80;
    server_name 192.168.1.100 _;  # Слушаем на любом IP
    
    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### Gunicorn: `/etc/systemd/system/oktools.service`

```ini
ExecStart=/opt/ok-tools/venv/bin/gunicorn \
    --bind 0.0.0.0:8000 \  # Слушаем на всех интерфейсах
    ok_tools.wsgi:application
```

---

## 🔒 Безопасность в локальной сети

### Что настроено:

✓ PostgreSQL слушает только на localhost  
✓ Файрволл можно настроить для доступа только из локальной сети  
✓ Nginx работает без SSL (HTTP only)  
✓ Gunicorn доступен через Nginx reverse proxy  

### Рекомендации:

```bash
# Настрой firewall (опционально)
sudo apt install -y ufw

# Разреши SSH
sudo ufw allow 22/tcp

# Разреши HTTP только из локальной сети
sudo ufw allow from 192.168.0.0/16 to any port 80

# Включи firewall
sudo ufw enable
```

---

## 📊 Структура установки

```
/opt/ok-tools/
├── app/                    # Код Django приложения
│   ├── ok_tools/          # Настройки
│   ├── licenses/          # Модули
│   ├── media_files/
│   └── manage.py
├── venv/                   # Виртуальное окружение Python
├── config/
│   └── production.cfg     # Конфигурация
├── logs/                   # Логи
│   ├── oktools.log
│   ├── access.log
│   └── error.log
├── static/                 # Статика (после collectstatic)
└── media/                  # Загружаемые файлы

/mnt/nas/
├── playout/               # NAS Playout
└── archive/               # NAS Archive

/etc/systemd/system/
└── oktools.service        # Systemd service

/etc/nginx/sites-available/
└── oktools                # Nginx конфигурация
```

---

## 🧪 Проверка установки

### 1. Проверь сервисы

```bash
sudo systemctl status oktools       # должен быть active (running)
sudo systemctl status nginx         # должен быть active (running)
sudo systemctl status postgresql    # должен быть active (running)
```

### 2. Проверь порты

```bash
sudo netstat -tulpn | grep :80      # nginx
sudo netstat -tulpn | grep :8000    # gunicorn
sudo netstat -tulpn | grep :5432    # postgresql
```

### 3. Проверь NAS

```bash
mount | grep cifs                   # должны быть 2 маунта
ls -la /mnt/nas/playout            # должны видеть файлы
ls -la /mnt/nas/archive            # должны видеть файлы
```

### 4. Проверь веб-доступ

```bash
# С сервера
curl http://localhost
curl http://192.168.1.100  # твой IP

# С другого компьютера в сети
curl http://192.168.1.100
# Или открой в браузере
```

### 5. Проверь логи

```bash
# Gunicorn/Django
sudo journalctl -u oktools -n 50

# Nginx
sudo tail -f /var/log/nginx/oktools-error.log

# Django application
tail -f /opt/ok-tools/logs/oktools.log
```

---

## 🔧 Полезные команды

### Управление сервисами

```bash
# Перезапуск
sudo systemctl restart oktools
sudo systemctl restart nginx

# Остановка
sudo systemctl stop oktools

# Запуск
sudo systemctl start oktools

# Статус
sudo systemctl status oktools

# Логи в реальном времени
sudo journalctl -u oktools -f
```

### Django команды

```bash
# Переключись на пользователя oktools
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg

# Миграции
python manage.py migrate

# Создать суперпользователя
python manage.py createsuperuser

# Сканирование видео
python manage.py scan_video_storage

# Синхронизация лицензий и видео
python manage.py sync_licenses_videos

# Django shell
python manage.py shell

# Собрать статику
python manage.py collectstatic --noinput
```

### Обновление с GitHub

```bash
sudo su - oktools
cd /opt/ok-tools/app

# Получи обновления
git pull origin main

# Обнови зависимости
source /opt/ok-tools/venv/bin/activate
pip install -r requirements.txt

# Миграции
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg
python manage.py migrate

# Статика
python manage.py collectstatic --noinput

# Выйди и перезапусти
exit
sudo systemctl restart oktools
```

### Работа с NAS

```bash
# Проверь монтирование
mount | grep cifs

# Ремонтируй если нужно
sudo umount /mnt/nas/playout
sudo umount /mnt/nas/archive
sudo mount -a

# Проверь доступ от имени oktools
sudo -u oktools ls -la /mnt/nas/playout
sudo -u oktools touch /mnt/nas/playout/test.txt
sudo -u oktools rm /mnt/nas/playout/test.txt
```

### Бэкапы

```bash
# Бэкап базы
sudo -u postgres pg_dump oktools_test > /backup/oktools_$(date +%Y%m%d_%H%M%S).sql

# Бэкап конфигурации
sudo cp /opt/ok-tools/config/production.cfg /backup/

# Восстановление
sudo -u postgres psql oktools_test < /backup/oktools_YYYYMMDD.sql
```

---

## 🐛 Troubleshooting

### Приложение не открывается в браузере

```bash
# 1. Проверь что сервисы работают
sudo systemctl status oktools
sudo systemctl status nginx

# 2. Проверь порты
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :8000

# 3. Проверь firewall (если настроен)
sudo ufw status

# 4. Проверь логи
sudo journalctl -u oktools -n 50
sudo tail -f /var/log/nginx/oktools-error.log

# 5. Тест с сервера
curl http://127.0.0.1:8000  # напрямую gunicorn
curl http://localhost       # через nginx
```

### 502 Bad Gateway

```bash
# Gunicorn не работает
sudo systemctl restart oktools
sudo journalctl -u oktools -n 50

# Проверь что gunicorn слушает
sudo netstat -tulpn | grep :8000
```

### NAS не монтируется

```bash
# Проверь доступность
ping 192.168.188.1

# Проверь credentials
sudo cat /root/.smbcredentials_playout

# Тестовое монтирование
sudo mount -t cifs //192.168.188.1/sendedaten /mnt/nas/playout \
  -o credentials=/root/.smbcredentials_playout,uid=1000,gid=1000,vers=3.0

# Проверь логи
dmesg | grep -i cifs
```

### База данных не подключается

```bash
# Проверь PostgreSQL
sudo systemctl status postgresql

# Проверь подключение
sudo -u postgres psql oktools_test

# В psql:
\l                    # список баз
\du                   # список пользователей
\dt                   # список таблиц
\q                    # выход
```

### Email не отправляются

```bash
# Проверь конфигурацию
sudo cat /opt/ok-tools/config/production.cfg | grep -A 10 "\[email\]"

# Если не настроил SMTP, email будут в консоль (логи)
sudo journalctl -u oktools -f | grep -i email
```

---

## 📚 Дополнительная документация

- [Полная инструкция с доменом](OK_MERSEBURG_TEST_SETUP.md)
- [Настройка NAS на Debian](NAS_DEBIAN_SETUP.md)
- [Media Files руководство](../media_files/ADMIN_GUIDE.md)
- [Краткое руководство](../media_files/ADMIN_QUICKSTART.txt)

---

## ✅ Checklist установки

- [ ] SSH доступ к серверу работает
- [ ] Git установлен, репозиторий клонирован
- [ ] Скрипт установки выполнен успешно
- [ ] PostgreSQL работает, база создана
- [ ] NAS хранилища смонтированы
- [ ] Gunicorn запущен (sudo systemctl status oktools)
- [ ] Nginx запущен (sudo systemctl status nginx)
- [ ] Приложение доступно по http://IP
- [ ] Вход в админку работает
- [ ] Storage Locations созданы
- [ ] Дамп импортирован (если нужно)
- [ ] Первое сканирование видео выполнено

---

## 🎯 Доступ к приложению

После установки:

```
Админка:     http://192.168.1.100/admin/
API:         http://192.168.1.100/api/
Dashboard:   http://192.168.1.100/dashboard/
```

**Готово! Тестовый сервер OK Merseburg работает в локальной сети.**

