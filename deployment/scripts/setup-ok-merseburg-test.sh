#!/bin/bash
#
# Автоматизированная установка OK Tools для OK Merseburg (тестовый сервер)
# Debian 11/12
#

set -e  # Выход при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    print_error "Запусти скрипт с sudo: sudo bash setup-ok-merseburg-test.sh"
    exit 1
fi

print_header "Установка OK Tools для OK Merseburg (тестовый сервер)"

# ================================
# КОНФИГУРАЦИЯ
# ================================

# Основные параметры
APP_USER="oktools"
APP_DIR="/opt/ok-tools"
VENV_DIR="$APP_DIR/venv"
APP_CODE_DIR="$APP_DIR/app"
CONFIG_DIR="$APP_DIR/config"
LOGS_DIR="$APP_DIR/logs"
STATIC_DIR="$APP_DIR/static"
MEDIA_DIR="$APP_DIR/media"

# База данных
DB_NAME="oktools_test"
DB_USER="oktools"
read -sp "Введи пароль для БД PostgreSQL: " DB_PASSWORD
echo

# Домен
read -p "Введи домен (например test.ok-merseburg.de): " DOMAIN

# NAS конфигурация
read -p "Введи IP адрес NAS для playout (например 192.168.188.1): " NAS_PLAYOUT_IP
read -p "Введи имя share для playout (например sendedaten): " NAS_PLAYOUT_SHARE
read -p "Введи логин для NAS playout: " NAS_PLAYOUT_USER
read -sp "Введи пароль для NAS playout: " NAS_PLAYOUT_PASS
echo

read -p "У тебя отдельный NAS для archive? (y/n): " HAS_SEPARATE_ARCHIVE
if [ "$HAS_SEPARATE_ARCHIVE" = "y" ]; then
    read -p "Введи IP адрес NAS для archive: " NAS_ARCHIVE_IP
    read -p "Введи имя share для archive: " NAS_ARCHIVE_SHARE
    read -p "Введи логин для NAS archive: " NAS_ARCHIVE_USER
    read -sp "Введи пароль для NAS archive: " NAS_ARCHIVE_PASS
    echo
else
    NAS_ARCHIVE_IP=$NAS_PLAYOUT_IP
    NAS_ARCHIVE_SHARE=$NAS_PLAYOUT_SHARE
    NAS_ARCHIVE_USER=$NAS_PLAYOUT_USER
    NAS_ARCHIVE_PASS=$NAS_PLAYOUT_PASS
fi

# Email конфигурация
read -p "Введи email для отправки (например noreply@ok-merseburg.de): " EMAIL_FROM
read -p "Введи SMTP host (например smtp.strato.de): " SMTP_HOST
read -p "Введи SMTP port (например 465): " SMTP_PORT
read -p "Введи SMTP username: " SMTP_USER
read -sp "Введи SMTP password: " SMTP_PASS
echo

# ================================
# ШАГ 1: Обновление системы
# ================================

print_header "Шаг 1: Обновление системы"
apt update
apt upgrade -y
print_success "Система обновлена"

# ================================
# ШАГ 2: Установка пакетов
# ================================

print_header "Шаг 2: Установка необходимых пакетов"

apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    cifs-utils \
    ffmpeg \
    curl \
    build-essential \
    python3.11-dev \
    libpq-dev \
    certbot \
    python3-certbot-nginx

print_success "Все пакеты установлены"

# ================================
# ШАГ 3: Создание пользователя
# ================================

print_header "Шаг 3: Создание пользователя приложения"

if id "$APP_USER" &>/dev/null; then
    print_warning "Пользователь $APP_USER уже существует"
else
    useradd -m -s /bin/bash $APP_USER
    print_success "Пользователь $APP_USER создан"
fi

# ================================
# ШАГ 4: Создание директорий
# ================================

print_header "Шаг 4: Создание структуры директорий"

mkdir -p $APP_DIR/{app,venv,config,logs,static,media}
chown -R $APP_USER:$APP_USER $APP_DIR
print_success "Директории созданы"

# ================================
# ШАГ 5: Монтирование NAS
# ================================

print_header "Шаг 5: Настройка NAS хранилищ"

# Создай точки монтирования
mkdir -p /mnt/nas/playout
mkdir -p /mnt/nas/archive
chmod 755 /mnt/nas

# Создай credentials файлы
cat > /root/.smbcredentials_playout <<EOF
username=$NAS_PLAYOUT_USER
password=$NAS_PLAYOUT_PASS
domain=WORKGROUP
EOF
chmod 600 /root/.smbcredentials_playout

cat > /root/.smbcredentials_archive <<EOF
username=$NAS_ARCHIVE_USER
password=$NAS_ARCHIVE_PASS
domain=WORKGROUP
EOF
chmod 600 /root/.smbcredentials_archive

# Получи UID/GID пользователя
APP_UID=$(id -u $APP_USER)
APP_GID=$(id -g $APP_USER)

# Добавь в fstab если еще нет
if ! grep -q "/mnt/nas/playout" /etc/fstab; then
    cat >> /etc/fstab <<EOF

# OK Merseburg NAS Playout
//$NAS_PLAYOUT_IP/$NAS_PLAYOUT_SHARE  /mnt/nas/playout  cifs  credentials=/root/.smbcredentials_playout,uid=$APP_UID,gid=$APP_GID,file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0

# OK Merseburg NAS Archive
//$NAS_ARCHIVE_IP/$NAS_ARCHIVE_SHARE  /mnt/nas/archive  cifs  credentials=/root/.smbcredentials_archive,uid=$APP_UID,gid=$APP_GID,file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0
EOF
    print_success "NAS записи добавлены в /etc/fstab"
fi

# Монтируй
mount -a || true
sleep 2

# Проверь монтирование
if mountpoint -q /mnt/nas/playout; then
    print_success "NAS Playout смонтирован"
else
    print_warning "NAS Playout не смонтирован, проверь настройки"
fi

if mountpoint -q /mnt/nas/archive; then
    print_success "NAS Archive смонтирован"
else
    print_warning "NAS Archive не смонтирован, проверь настройки"
fi

# ================================
# ШАГ 6: Настройка PostgreSQL
# ================================

print_header "Шаг 6: Настройка PostgreSQL"

sudo -u postgres psql <<EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DB_USER SET timezone TO 'Europe/Berlin';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

print_success "База данных создана"

# ================================
# ШАГ 7: Копирование/клонирование кода
# ================================

print_header "Шаг 7: Копирование приложения"

print_warning "ВНИМАНИЕ: Скопируй код приложения в $APP_CODE_DIR"
print_warning "Например: scp -r /path/to/ok_tools_dev user@server:$APP_CODE_DIR"
read -p "Нажми Enter когда код будет скопирован..."

chown -R $APP_USER:$APP_USER $APP_CODE_DIR

# ================================
# ШАГ 8: Создание виртуального окружения
# ================================

print_header "Шаг 8: Создание виртуального окружения"

sudo -u $APP_USER python3.11 -m venv $VENV_DIR
sudo -u $APP_USER $VENV_DIR/bin/pip install --upgrade pip
sudo -u $APP_USER $VENV_DIR/bin/pip install -r $APP_CODE_DIR/requirements.txt
sudo -u $APP_USER $VENV_DIR/bin/pip install gunicorn psycopg2-binary

print_success "Виртуальное окружение создано"

# ================================
# ШАГ 9: Создание конфигурации
# ================================

print_header "Шаг 9: Создание конфигурации"

# Генерируй секретный ключ
SECRET_KEY=$(python3 -c "from secrets import token_urlsafe; print(token_urlsafe(50))")

cat > $CONFIG_DIR/production.cfg <<EOF
[database]
name = $DB_NAME
user = $DB_USER
password = $DB_PASSWORD
host = localhost
port = 5432

[site]
domain = $DOMAIN
debug = False
allowed_hosts = $DOMAIN,localhost,127.0.0.1
secret_key = $SECRET_KEY
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
host = $SMTP_HOST
port = $SMTP_PORT
use_ssl = True
from_email = $EMAIL_FROM
username = $SMTP_USER
password = $SMTP_PASS

[media]
archive_path = /mnt/nas/archive/
playout_path = /mnt/nas/playout/
auto_scan = False
auto_copy_on_schedule = True
scan_interval_hours = 24
max_file_size_gb = 50

[logging]
level = INFO
file = $LOGS_DIR/oktools.log

[security]
csrf_cookie_secure = True
session_cookie_secure = True
secure_ssl_redirect = False
secure_hsts_seconds = 31536000
EOF

chown $APP_USER:$APP_USER $CONFIG_DIR/production.cfg
chmod 600 $CONFIG_DIR/production.cfg

print_success "Конфигурация создана"

# ================================
# ШАГ 10: Инициализация Django
# ================================

print_header "Шаг 10: Инициализация Django"

export OKTOOLS_CONFIG_FILE=$CONFIG_DIR/production.cfg

# Миграции
sudo -u $APP_USER bash -c "
    source $VENV_DIR/bin/activate && \
    export OKTOOLS_CONFIG_FILE=$CONFIG_DIR/production.cfg && \
    cd $APP_CODE_DIR && \
    python manage.py migrate
"

print_success "Миграции применены"

# Статика
sudo -u $APP_USER bash -c "
    source $VENV_DIR/bin/activate && \
    export OKTOOLS_CONFIG_FILE=$CONFIG_DIR/production.cfg && \
    cd $APP_CODE_DIR && \
    python manage.py collectstatic --noinput
"

print_success "Статика собрана"

# ================================
# ШАГ 11: Настройка Gunicorn
# ================================

print_header "Шаг 11: Настройка Gunicorn"

cat > /etc/systemd/system/oktools.service <<EOF
[Unit]
Description=OK Tools Merseburg - Django Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_CODE_DIR
Environment="PATH=$VENV_DIR/bin"
Environment="OKTOOLS_CONFIG_FILE=$CONFIG_DIR/production.cfg"
Environment="DJANGO_SETTINGS_MODULE=ok_tools.settings"
ExecStart=$VENV_DIR/bin/gunicorn \\
    --workers 4 \\
    --bind 127.0.0.1:8000 \\
    --timeout 120 \\
    --access-logfile $LOGS_DIR/access.log \\
    --error-logfile $LOGS_DIR/error.log \\
    --log-level info \\
    ok_tools.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable oktools.service
systemctl start oktools.service

print_success "Gunicorn настроен и запущен"

# ================================
# ШАГ 12: Настройка Nginx
# ================================

print_header "Шаг 12: Настройка Nginx"

cat > /etc/nginx/sites-available/oktools <<EOF
upstream oktools {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name $DOMAIN;
    
    client_max_body_size 100M;
    
    access_log /var/log/nginx/oktools-access.log;
    error_log /var/log/nginx/oktools-error.log;
    
    location /static/ {
        alias $STATIC_DIR/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias $MEDIA_DIR/;
        expires 7d;
    }
    
    location / {
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Host \$http_host;
        proxy_redirect off;
        proxy_pass http://oktools;
        
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }
}
EOF

ln -sf /etc/nginx/sites-available/oktools /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl restart nginx
systemctl enable nginx

print_success "Nginx настроен и запущен"

# ================================
# ШАГ 13: Настройка SSL
# ================================

print_header "Шаг 13: Настройка SSL сертификата"

read -p "Хочешь установить SSL сертификат сейчас? (y/n): " INSTALL_SSL

if [ "$INSTALL_SSL" = "y" ]; then
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email info@ok-merseburg.de
    
    # Обнови конфигурацию для включения HTTPS редиректа
    sed -i 's/secure_ssl_redirect = False/secure_ssl_redirect = True/' $CONFIG_DIR/production.cfg
    
    systemctl restart oktools.service
    
    print_success "SSL сертификат установлен"
else
    print_warning "SSL не установлен, установи его позже командой: sudo certbot --nginx -d $DOMAIN"
fi

# ================================
# ШАГ 14: Создание суперпользователя
# ================================

print_header "Шаг 14: Создание суперпользователя Django"

print_warning "Сейчас нужно создать суперпользователя для входа в админку"

sudo -u $APP_USER bash -c "
    source $VENV_DIR/bin/activate && \
    export OKTOOLS_CONFIG_FILE=$CONFIG_DIR/production.cfg && \
    cd $APP_CODE_DIR && \
    python manage.py createsuperuser
"

# ================================
# ФИНАЛ
# ================================

print_header "Установка завершена!"

echo ""
print_success "OK Tools для OK Merseburg успешно установлен!"
echo ""
echo -e "${GREEN}Доступ к приложению:${NC}"
echo -e "  URL: http://$DOMAIN (или https:// если SSL установлен)"
echo -e "  Админка: http://$DOMAIN/admin/"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo -e "  1. Открой админку и войди с созданными credentials"
echo -e "  2. Создай Storage Locations (Media Files → Storage locations):"
echo -e "     - Name: OK Merseburg Playout"
echo -e "       Type: PLAYOUT"
echo -e "       Path: /mnt/nas/playout/"
echo -e "     - Name: OK Merseburg Archive"
echo -e "       Type: ARCHIVE"
echo -e "       Path: /mnt/nas/archive/"
echo -e "  3. Импортируй дамп базы данных если нужно:"
echo -e "     sudo -u postgres psql $DB_NAME < /path/to/dump.sql"
echo -e "  4. Запусти первое сканирование видео:"
echo -e "     sudo -u $APP_USER bash -c 'source $VENV_DIR/bin/activate && cd $APP_CODE_DIR && python manage.py scan_video_storage'"
echo ""
echo -e "${BLUE}Полезные команды:${NC}"
echo -e "  Статус сервиса: sudo systemctl status oktools"
echo -e "  Логи: sudo journalctl -u oktools -f"
echo -e "  Перезапуск: sudo systemctl restart oktools"
echo -e "  Nginx логи: sudo tail -f /var/log/nginx/oktools-error.log"
echo ""
print_success "Готово!"

