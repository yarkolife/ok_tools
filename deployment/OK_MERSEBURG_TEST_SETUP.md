# Установка OK Tools на тестовый Debian сервер
# Организация: OK Merseburg

## 📋 Что нужно

- Debian сервер с SSH доступом
- Пароль для SSH
- Доступ к NAS хранилищам в сети
- Дамп базы данных с лицензиями
- Суперпользовательские права (sudo)

---

## 🚀 Пошаговая установка

### Шаг 1: Подключение к серверу

```bash
# С локальной машины
ssh user@your-debian-server-ip

# Введи пароль
```

### Шаг 2: Подготовка системы

```bash
# Обнови систему
sudo apt update
sudo apt upgrade -y

# Установи необходимые пакеты
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    cifs-utils \
    ffmpeg \
    curl \
    build-essential \
    python3.12-dev \
    libpq-dev

# Если python3.12 нет, используй python3.11 или python3.10
```

### Шаг 3: Создание пользователя и директорий

```bash
# Создай пользователя для приложения
sudo useradd -m -s /bin/bash oktools
sudo passwd oktools  # Установи пароль

# Создай структуру директорий
sudo mkdir -p /opt/ok-tools/{app,venv,config,logs,static,media}
sudo chown -R oktools:oktools /opt/ok-tools
```

### Шаг 4: Клонирование репозитория

```bash
# Переключись на пользователя oktools
sudo su - oktools

# Клонируй проект (замени на актуальный путь)
cd /opt/ok-tools
git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git app

# Или если у тебя dev версия на локальной машине:
# Скопируй через scp с локальной машины:
# scp -r /Users/pavlo/coding/ok_tools_dev user@server-ip:/tmp/ok_tools_dev
# Потом на сервере:
# sudo mv /tmp/ok_tools_dev /opt/ok-tools/app
# sudo chown -R oktools:oktools /opt/ok-tools/app
```

### Шаг 5: Создание виртуального окружения

```bash
# Как пользователь oktools
cd /opt/ok-tools
python3.12 -m venv venv

# Активируй venv
source venv/bin/activate

# Обнови pip
pip install --upgrade pip

# Установи зависимости
cd app
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### Шаг 6: Настройка PostgreSQL

```bash
# Выйди из oktools пользователя
exit

# Как root/sudo
sudo -u postgres psql

# В psql:
CREATE DATABASE oktools_test;
CREATE USER oktools WITH PASSWORD 'strong_password_here';
ALTER ROLE oktools SET client_encoding TO 'utf8';
ALTER ROLE oktools SET default_transaction_isolation TO 'read committed';
ALTER ROLE oktools SET timezone TO 'Europe/Berlin';
GRANT ALL PRIVILEGES ON DATABASE oktools_test TO oktools;
\q
```

### Шаг 7: Импорт дампа базы данных

```bash
# Скопируй дамп на сервер с локальной машины
# scp /path/to/dump.sql user@server-ip:/tmp/

# На сервере импортируй дамп
sudo -u postgres psql oktools_test < /tmp/dump.sql

# Или если дамп в формате pg_dump:
# sudo -u postgres pg_restore -d oktools_test /tmp/dump.dump
```

### Шаг 8: Монтирование NAS хранилищ

```bash
# Создай точки монтирования
sudo mkdir -p /mnt/nas/playout
sudo mkdir -p /mnt/nas/archive

# Создай credentials файлы
sudo nano /root/.smbcredentials_playout
```

Содержимое `/root/.smbcredentials_playout`:
```
username=nas_user
password=nas_password
domain=WORKGROUP
```

```bash
# Защити файл
sudo chmod 600 /root/.smbcredentials_playout

# Если archive на другом NAS с другими credentials:
sudo nano /root/.smbcredentials_archive
# (такое же содержимое с другими данными)
sudo chmod 600 /root/.smbcredentials_archive
```

#### Настрой автомонтирование через fstab

```bash
sudo nano /etc/fstab
```

Добавь в конец:
```
# OK Merseburg NAS Playout
//192.168.188.1/sendedaten  /mnt/nas/playout  cifs  credentials=/root/.smbcredentials_playout,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0

# OK Merseburg NAS Archive (если другой IP)
//192.168.XXX.XXX/archive  /mnt/nas/archive  cifs  credentials=/root/.smbcredentials_archive,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0
```

⚠️ **Важно:** Замени `uid=1000,gid=1000` на ID пользователя oktools:
```bash
id -u oktools  # запомни число
id -g oktools  # запомни число
```

```bash
# Смонтируй
sudo mount -a

# Проверь
mount | grep cifs
ls -la /mnt/nas/playout
ls -la /mnt/nas/archive
```

### Шаг 9: Конфигурация приложения

```bash
# Создай конфигурационный файл
sudo nano /opt/ok-tools/config/production.cfg
```

Содержимое:
```ini
[database]
name = oktools_test
user = oktools
password = strong_password_here
host = localhost
port = 5432

[site]
domain = test.ok-merseburg.de
debug = False
allowed_hosts = test.ok-merseburg.de,192.168.X.X
secret_key = generate_very_long_random_string_here
language = de
time_zone = Europe/Berlin

[organization]
name = OK Merseburg
abbreviation = OKMB
state = Sachsen-Anhalt
authority = MSA
default_license_duration_months = 12
address_line_1 = Geusaer Straße 86b
address_line_2 = 
postal_code = 06217
city = Merseburg
phone = +49 (0) 3461 23 23 0
email = info@ok-merseburg.de
website = https://www.ok-merseburg.de

[email]
backend = django.core.mail.backends.smtp.EmailBackend
host = smtp.strato.de
port = 465
use_ssl = True
from_email = noreply@ok-merseburg.de
username = your_email@ok-merseburg.de
password = your_email_password

[media]
archive_path = /mnt/nas/archive/
playout_path = /mnt/nas/playout/
auto_scan = False
auto_copy_on_schedule = True
scan_interval_hours = 24
max_file_size_gb = 50

[logging]
level = INFO
file = /opt/ok-tools/logs/oktools.log

[security]
csrf_cookie_secure = True
session_cookie_secure = True
secure_ssl_redirect = True
secure_hsts_seconds = 31536000
```

⚠️ **Важно:** Сгенерируй секретный ключ:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Шаг 10: Инициализация Django

```bash
# Переключись на oktools пользователя
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate

# Установи переменную окружения
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg

# Примени миграции (внутри Docker если используется)
python manage.py migrate

# Собери статику
python manage.py collectstatic --noinput

# Создай суперпользователя
python manage.py createsuperuser
```

### Шаг 11: Настройка Gunicorn

```bash
# Создай systemd service файл
sudo nano /etc/systemd/system/oktools.service
```

Содержимое:
```ini
[Unit]
Description=OK Tools Merseburg - Django Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=oktools
Group=oktools
WorkingDirectory=/opt/ok-tools/app
Environment="PATH=/opt/ok-tools/venv/bin"
Environment="OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg"
Environment="DJANGO_SETTINGS_MODULE=ok_tools.settings"
ExecStart=/opt/ok-tools/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /opt/ok-tools/logs/access.log \
    --error-logfile /opt/ok-tools/logs/error.log \
    --log-level info \
    ok_tools.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Включи и запусти сервис
sudo systemctl daemon-reload
sudo systemctl enable oktools.service
sudo systemctl start oktools.service

# Проверь статус
sudo systemctl status oktools.service

# Просмотр логов
sudo journalctl -u oktools.service -f
```

### Шаг 12: Настройка Nginx

```bash
# Создай конфигурацию nginx
sudo nano /etc/nginx/sites-available/oktools
```

Содержимое:
```nginx
upstream oktools {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name test.ok-merseburg.de;
    
    # Редирект на HTTPS (после установки SSL)
    # return 301 https://$server_name$request_uri;
    
    client_max_body_size 100M;
    
    access_log /var/log/nginx/oktools-access.log;
    error_log /var/log/nginx/oktools-error.log;
    
    location /static/ {
        alias /opt/ok-tools/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /opt/ok-tools/media/;
        expires 7d;
    }
    
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        proxy_pass http://oktools;
        
        # Таймауты для больших файлов
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }
}
```

```bash
# Активируй конфигурацию
sudo ln -s /etc/nginx/sites-available/oktools /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # удали дефолтный конфиг

# Проверь конфигурацию
sudo nginx -t

# Перезапусти nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Шаг 13: Настройка Storage Locations в Django Admin

```bash
# Открой в браузере
http://test.ok-merseburg.de/admin/

# Логин с созданными credentials

# Перейди: Media Files → Storage locations → Add storage location
```

Создай:

**Playout:**
- Name: `OK Merseburg Playout`
- Type: `PLAYOUT`
- Path: `/mnt/nas/playout/`
- Description: `Sendedaten NAS`
- Is active: ✓

**Archive:**
- Name: `OK Merseburg Archive`
- Type: `ARCHIVE`
- Path: `/mnt/nas/archive/`
- Description: `Archive NAS`
- Is active: ✓

### Шаг 14: Первое сканирование видео

```bash
# Как oktools пользователь
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg

# Запусти сканирование
python manage.py scan_video_storage

# Или сканируй конкретную location
python manage.py scan_video_storage --location "OK Merseburg Archive"
```

### Шаг 15: Настройка Cron задач (опционально)

```bash
# Создай systemd timer для expire_rentals
sudo nano /etc/systemd/system/oktools-expire-rentals.service
```

Содержимое:
```ini
[Unit]
Description=OK Tools - Expire Rentals Job

[Service]
Type=oneshot
User=oktools
Group=oktools
WorkingDirectory=/opt/ok-tools/app
Environment="PATH=/opt/ok-tools/venv/bin"
Environment="OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg"
ExecStart=/opt/ok-tools/venv/bin/python manage.py expire_rentals
```

```bash
sudo nano /etc/systemd/system/oktools-expire-rentals.timer
```

Содержимое:
```ini
[Unit]
Description=Run expire rentals every 30 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min

[Install]
WantedBy=timers.target
```

```bash
# Активируй timer
sudo systemctl daemon-reload
sudo systemctl enable oktools-expire-rentals.timer
sudo systemctl start oktools-expire-rentals.timer

# Проверь статус
sudo systemctl status oktools-expire-rentals.timer
```

---

## 🔒 Настройка SSL (Let's Encrypt)

```bash
# Установи certbot
sudo apt install -y certbot python3-certbot-nginx

# Получи сертификат
sudo certbot --nginx -d test.ok-merseburg.de

# Certbot автоматически обновит nginx конфиг для HTTPS
# И настроит автообновление сертификата

# Проверь автообновление
sudo certbot renew --dry-run
```

---

## 🧪 Проверка установки

### 1. Проверь сервисы
```bash
sudo systemctl status oktools.service
sudo systemctl status nginx.service
sudo systemctl status postgresql.service
```

### 2. Проверь NAS
```bash
mount | grep cifs
sudo -u oktools ls -la /mnt/nas/playout
sudo -u oktools ls -la /mnt/nas/archive
```

### 3. Проверь веб-доступ
```bash
curl http://test.ok-merseburg.de
curl http://test.ok-merseburg.de/admin/
```

### 4. Проверь логи
```bash
# Gunicorn логи
sudo journalctl -u oktools.service -n 50

# Nginx логи
sudo tail -f /var/log/nginx/oktools-error.log
sudo tail -f /var/log/nginx/oktools-access.log

# Django логи
tail -f /opt/ok-tools/logs/oktools.log
```

---

## 📦 Импорт данных

### Если у тебя dump всех лицензий:

```bash
# 1. Через psql (SQL dump)
sudo -u postgres psql oktools_test < /tmp/licenses_dump.sql

# 2. Через pg_restore (binary dump)
sudo -u postgres pg_restore -d oktools_test -t licenses_license /tmp/dump.dump

# 3. Через Django loaddata (JSON)
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate
python manage.py loaddata /tmp/licenses.json
```

---

## 🔧 Полезные команды

### Управление сервисами
```bash
# Перезапуск приложения
sudo systemctl restart oktools.service

# Перезапуск nginx
sudo systemctl restart nginx

# Просмотр логов
sudo journalctl -u oktools.service -f
```

### Работа с Django
```bash
# Переключиться на oktools
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

# Django shell
python manage.py shell
```

### Обновление приложения
```bash
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate

# Получи обновления
git pull origin main

# Обнови зависимости
pip install -r requirements.txt

# Миграции
python manage.py migrate

# Статика
python manage.py collectstatic --noinput

# Выйди и перезапусти
exit
sudo systemctl restart oktools.service
```

### Бэкапы
```bash
# Бэкап базы данных
sudo -u postgres pg_dump oktools_test > /backup/oktools_$(date +%Y%m%d).sql

# Бэкап конфигурации
sudo cp /opt/ok-tools/config/production.cfg /backup/production.cfg.$(date +%Y%m%d)
```

---

## 🐛 Troubleshooting

### Приложение не запускается
```bash
# Проверь логи
sudo journalctl -u oktools.service -n 100 --no-pager

# Проверь конфигурацию
sudo -u oktools cat /opt/ok-tools/config/production.cfg

# Проверь права
ls -la /opt/ok-tools/
```

### NAS не монтируется
```bash
# Проверь доступность NAS
ping 192.168.188.1

# Проверь credentials
sudo cat /root/.smbcredentials_playout

# Тестовое монтирование вручную
sudo mount -t cifs //192.168.188.1/sendedaten /mnt/nas/playout -o credentials=/root/.smbcredentials_playout,uid=1000,gid=1000

# Проверь что смонтировано
mount | grep cifs
```

### 502 Bad Gateway
```bash
# Проверь что gunicorn работает
sudo systemctl status oktools.service

# Проверь что nginx правильно проксирует
sudo nginx -t
curl http://127.0.0.1:8000
```

### База данных не подключается
```bash
# Проверь PostgreSQL
sudo systemctl status postgresql

# Проверь подключение
sudo -u postgres psql oktools_test

# В psql проверь пользователя:
\du
```

---

## 📚 Дополнительная документация

- [NAS Setup](NAS_DEBIAN_SETUP.md) - Подробная настройка NAS
- [Media Files Guide](../media_files/ADMIN_GUIDE.md) - Работа с видеофайлами
- [Deployment README](README.md) - Общая информация о деплое

---

## ✅ Checklist установки

- [ ] SSH доступ к серверу работает
- [ ] Установлены все системные пакеты
- [ ] Создан пользователь oktools
- [ ] Клонирован/скопирован репозиторий
- [ ] Создано виртуальное окружение
- [ ] Установлены Python зависимости
- [ ] Настроена PostgreSQL
- [ ] Импортирован дамп базы данных
- [ ] Смонтированы NAS хранилища
- [ ] Создан production.cfg
- [ ] Применены миграции Django
- [ ] Собрана статика
- [ ] Создан суперпользователь
- [ ] Настроен и запущен gunicorn
- [ ] Настроен и запущен nginx
- [ ] Получен SSL сертификат
- [ ] Созданы Storage Locations в админке
- [ ] Выполнено первое сканирование видео
- [ ] Настроены cron задачи
- [ ] Проверена работа приложения

---

**Готово! Тестовый сервер OK Merseburg установлен и готов к работе.**

Доступ: `https://test.ok-merseburg.de/admin/`

