#!/bin/bash
#
# Автоматическая установка OK Tools через Docker
# Для локальной сети - доступ по IP, без nginx, без SSL
#

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
    print_error "Запусти скрипт с sudo: sudo bash setup-docker-local.sh"
    exit 1
fi

print_header "Установка OK Tools через Docker (локальная сеть)"

# ================================
# ШАГ 1: Проверка Docker
# ================================

print_header "Шаг 1: Проверка Docker"

if ! command -v docker &> /dev/null; then
    print_warning "Docker не установлен. Устанавливаю..."
    
    # Установка Docker
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    systemctl enable docker
    systemctl start docker
    
    print_success "Docker установлен"
else
    print_success "Docker уже установлен"
fi

# Проверка docker compose
if ! docker compose version &> /dev/null; then
    print_error "Docker Compose не установлен"
    exit 1
fi

print_success "Docker и Docker Compose готовы"

# ================================
# ШАГ 2: Получить параметры
# ================================

print_header "Шаг 2: Настройка параметров"

# IP адрес сервера
CURRENT_IP=$(hostname -I | awk '{print $1}')
print_warning "Обнаружен IP адрес: $CURRENT_IP"
read -p "IP адрес сервера [$CURRENT_IP]: " SERVER_IP
SERVER_IP=${SERVER_IP:-$CURRENT_IP}

# NAS конфигурация
echo ""
print_warning "Настройка NAS хранилищ"
read -p "IP адрес NAS для playout (например 192.168.188.1): " NAS_PLAYOUT_IP
read -p "Имя share для playout (например sendedaten): " NAS_PLAYOUT_SHARE
read -p "Логин для NAS playout: " NAS_PLAYOUT_USER
read -sp "Пароль для NAS playout: " NAS_PLAYOUT_PASS
echo

read -p "У тебя отдельный NAS для archive? (y/n): " HAS_SEPARATE_ARCHIVE
if [ "$HAS_SEPARATE_ARCHIVE" = "y" ]; then
    read -p "IP адрес NAS для archive: " NAS_ARCHIVE_IP
    read -p "Имя share для archive: " NAS_ARCHIVE_SHARE
    read -p "Логин для NAS archive: " NAS_ARCHIVE_USER
    read -sp "Пароль для NAS archive: " NAS_ARCHIVE_PASS
    echo
else
    NAS_ARCHIVE_IP=$NAS_PLAYOUT_IP
    NAS_ARCHIVE_SHARE=$NAS_PLAYOUT_SHARE
    NAS_ARCHIVE_USER=$NAS_PLAYOUT_USER
    NAS_ARCHIVE_PASS=$NAS_PLAYOUT_PASS
fi

# ================================
# ШАГ 3: Установка cifs-utils
# ================================

print_header "Шаг 3: Установка cifs-utils для NAS"

if ! command -v mount.cifs &> /dev/null; then
    apt-get update
    apt-get install -y cifs-utils
    print_success "cifs-utils установлен"
else
    print_success "cifs-utils уже установлен"
fi

# ================================
# ШАГ 4: Монтирование NAS
# ================================

print_header "Шаг 4: Монтирование NAS хранилищ"

# Создай точки монтирования
mkdir -p /mnt/nas/playout
mkdir -p /mnt/nas/archive
chmod 755 /mnt/nas

# Создай credentials
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

# Добавь в fstab если нет
if ! grep -q "/mnt/nas/playout" /etc/fstab; then
    cat >> /etc/fstab <<EOF

# OK Merseburg NAS
//$NAS_PLAYOUT_IP/$NAS_PLAYOUT_SHARE  /mnt/nas/playout  cifs  credentials=/root/.smbcredentials_playout,uid=0,gid=0,file_mode=0755,dir_mode=0755,vers=2.0,_netdev,nofail  0  0
//$NAS_ARCHIVE_IP/$NAS_ARCHIVE_SHARE  /mnt/nas/archive  cifs  credentials=/root/.smbcredentials_archive,uid=0,gid=0,file_mode=0755,dir_mode=0755,vers=2.0,_netdev,nofail  0  0
EOF
fi

# Монтируй
mount -a || true
sleep 2

if mountpoint -q /mnt/nas/playout; then
    print_success "NAS Playout смонтирован"
else
    print_warning "NAS Playout не смонтирован (продолжаю, можно настроить позже)"
fi

if mountpoint -q /mnt/nas/archive; then
    print_success "NAS Archive смонтирован"
else
    print_warning "NAS Archive не смонтирован (продолжаю, можно настроить позже)"
fi

# ================================
# ШАГ 5: Клонирование репозитория
# ================================

print_header "Шаг 5: Получение кода приложения"

INSTALL_DIR="/opt/ok_tools"

if [ -d "$INSTALL_DIR/.git" ]; then
    print_warning "Директория $INSTALL_DIR уже существует"
    read -p "Обновить код из GitHub? (y/n): " UPDATE_CODE
    if [ "$UPDATE_CODE" = "y" ]; then
        cd $INSTALL_DIR
        git pull origin main
        print_success "Код обновлен"
    fi
else
    # Установи git если нет
    if ! command -v git &> /dev/null; then
        apt-get install -y git
    fi
    
    git clone https://github.com/yarkolife/ok_tools.git $INSTALL_DIR
    print_success "Код клонирован в $INSTALL_DIR"
fi

cd $INSTALL_DIR

# Скопируй Docker файлы из deployment/docker/ в корень для установки
cp deployment/docker/Dockerfile ./
cp deployment/docker/docker-compose-root.yml ./docker-compose.yml
print_success "Docker файлы скопированы в корень для установки"

# ================================
# ШАГ 6: Создание конфигурации
# ================================

print_header "Шаг 6: Создание конфигурации"

mkdir -p deployment/docker/config

# Генерируй секретный ключ
SECRET_KEY=$(python3 -c "from secrets import token_urlsafe; print(token_urlsafe(50))" 2>/dev/null || openssl rand -base64 50)

cat > deployment/docker/config/production.cfg <<EOF
[database]
name = oktools
user = oktools
password = oktools123
host = db
port = 5432

[site]
domain = $SERVER_IP
debug = False
allowed_hosts = $SERVER_IP,localhost,127.0.0.1
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
backend = django.core.mail.backends.console.EmailBackend
host = localhost
port = 25
use_ssl = False
from_email = noreply@ok-merseburg.de
username = 
password = 

[media]
archive_path = /mnt/nas/archive/
playout_path = /mnt/nas/playout/
auto_scan = False
auto_copy_on_schedule = True
scan_interval_hours = 24
max_file_size_gb = 50

[logging]
level = INFO
file = /app/logs/oktools.log

[security]
csrf_cookie_secure = False
session_cookie_secure = False
secure_ssl_redirect = False
secure_hsts_seconds = 0
EOF

chmod 600 deployment/docker/config/production.cfg
print_success "Конфигурация создана"

# ================================
# ШАГ 7: Запуск Docker контейнеров
# ================================

print_header "Шаг 7: Запуск Docker контейнеров"

cd $INSTALL_DIR

# Останови старые контейнеры если есть
docker compose down 2>/dev/null || true

# Собери и запусти
print_warning "Сборка Docker образа (может занять несколько минут)..."
docker compose build

print_warning "Запуск контейнеров..."
docker compose up -d

sleep 5

# Проверь статус
docker compose ps

print_success "Docker контейнеры запущены"

# ================================
# ШАГ 8: Создание суперпользователя
# ================================

print_header "Шаг 8: Создание суперпользователя Django"

print_warning "Подожди 10 секунд пока применятся миграции..."
sleep 10

print_warning "Сейчас создадим суперпользователя для админки"
docker compose exec web python manage.py createsuperuser

# ================================
# ФИНАЛ
# ================================

print_header "Установка завершена!"

echo ""
print_success "OK Tools успешно установлен через Docker!"
echo ""
echo -e "${GREEN}Доступ к приложению:${NC}"
echo -e "  URL: http://$SERVER_IP:8000"
echo -e "  Админка: http://$SERVER_IP:8000/admin/"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo -e "  1. Открой http://$SERVER_IP:8000/admin/ в браузере"
echo -e "  2. Создай Storage Locations (Media Files → Storage locations):"
echo -e "     - Name: OK Merseburg Playout, Type: PLAYOUT, Path: /mnt/nas/playout/"
echo -e "     - Name: OK Merseburg Archive, Type: ARCHIVE, Path: /mnt/nas/archive/"
echo -e "  3. Импортируй дамп базы данных (если нужно):"
echo -e "     cd $INSTALL_DIR && docker compose exec -T db psql -U oktools oktools < dump.sql"
echo -e "  4. Запусти первое сканирование видео:"
echo -e "     cd $INSTALL_DIR && docker compose exec web python manage.py scan_video_storage"
echo ""
echo -e "${BLUE}Полезные команды:${NC}"
echo -e "  cd $INSTALL_DIR"
echo -e "  docker compose ps          # статус"
echo -e "  docker compose logs -f     # логи"
echo -e "  docker compose restart     # перезапуск"
echo -e "  docker compose down        # остановка"
echo -e "  docker compose up -d       # запуск"
echo ""
echo -e "${YELLOW}Примечание:${NC} Docker файлы скопированы из deployment/docker/ в корень"
echo -e "  Для обновления перезапусти скрипт установки"
echo ""
print_success "Готово!"

