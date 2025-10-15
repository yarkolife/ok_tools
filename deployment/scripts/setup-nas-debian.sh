#!/bin/bash
# Automated NAS setup script for Debian 11 production environment
# Usage: sudo ./setup-nas-debian.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MOUNT_BASE="/mnt/nas"
PLAYOUT_MOUNT="${MOUNT_BASE}/playout"
ARCHIVE_MOUNT="${MOUNT_BASE}/archive"
CREDS_PLAYOUT="/root/.smbcredentials_playout"
CREDS_ARCHIVE="/root/.smbcredentials_archive"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  OK Tools - NAS Setup Script for Debian 11${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Пожалуйста, запусти скрипт от root: sudo $0${NC}"
    exit 1
fi

# Step 1: Install packages
echo -e "${YELLOW}[1/8] Установка необходимых пакетов...${NC}"
apt update -qq
apt install -y cifs-utils ffmpeg > /dev/null 2>&1
echo -e "${GREEN}✅ Пакеты установлены${NC}"
echo ""

# Step 2: Create mount points
echo -e "${YELLOW}[2/8] Создание точек монтирования...${NC}"
mkdir -p "${PLAYOUT_MOUNT}"
mkdir -p "${ARCHIVE_MOUNT}"
chmod 755 "${MOUNT_BASE}"
chmod 755 "${PLAYOUT_MOUNT}"
chmod 755 "${ARCHIVE_MOUNT}"
echo -e "${GREEN}✅ Точки монтирования созданы:${NC}"
echo "   ${PLAYOUT_MOUNT}"
echo "   ${ARCHIVE_MOUNT}"
echo ""

# Step 3: Configure Playout credentials
echo -e "${YELLOW}[3/8] Настройка credentials для Playout...${NC}"
if [ -f "${CREDS_PLAYOUT}" ]; then
    echo -e "${YELLOW}⚠️  Файл ${CREDS_PLAYOUT} уже существует${NC}"
    read -p "Перезаписать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Пропускаем..."
    else
        rm "${CREDS_PLAYOUT}"
    fi
fi

if [ ! -f "${CREDS_PLAYOUT}" ]; then
    echo "Введи credentials для Playout NAS (192.168.188.1):"
    read -p "Username: " playout_user
    read -sp "Password: " playout_pass
    echo ""
    
    cat > "${CREDS_PLAYOUT}" <<EOF
username=${playout_user}
password=${playout_pass}
domain=WORKGROUP
EOF
    chmod 600 "${CREDS_PLAYOUT}"
    echo -e "${GREEN}✅ Credentials для Playout сохранены${NC}"
fi
echo ""

# Step 4: Configure Archive credentials
echo -e "${YELLOW}[4/8] Настройка credentials для Archive...${NC}"
if [ -f "${CREDS_ARCHIVE}" ]; then
    echo -e "${YELLOW}⚠️  Файл ${CREDS_ARCHIVE} уже существует${NC}"
    read -p "Перезаписать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Пропускаем..."
    else
        rm "${CREDS_ARCHIVE}"
    fi
fi

if [ ! -f "${CREDS_ARCHIVE}" ]; then
    echo "Введи credentials для Archive NAS:"
    read -p "IP адрес: " archive_ip
    read -p "Share name: " archive_share
    read -p "Username: " archive_user
    read -sp "Password: " archive_pass
    echo ""
    
    cat > "${CREDS_ARCHIVE}" <<EOF
username=${archive_user}
password=${archive_pass}
domain=WORKGROUP
EOF
    chmod 600 "${CREDS_ARCHIVE}"
    echo -e "${GREEN}✅ Credentials для Archive сохранены${NC}"
    
    # Save for later use
    echo "${archive_ip}" > /tmp/nas_archive_ip
    echo "${archive_share}" > /tmp/nas_archive_share
fi
echo ""

# Step 5: Get gunicorn user
echo -e "${YELLOW}[5/8] Определение пользователя для gunicorn...${NC}"
read -p "Пользователь от которого работает gunicorn (по умолчанию: www-data): " gunicorn_user
gunicorn_user=${gunicorn_user:-www-data}

if id "${gunicorn_user}" &>/dev/null; then
    uid=$(id -u "${gunicorn_user}")
    gid=$(id -g "${gunicorn_user}")
    echo -e "${GREEN}✅ Пользователь: ${gunicorn_user} (uid=${uid}, gid=${gid})${NC}"
else
    echo -e "${RED}❌ Пользователь ${gunicorn_user} не найден!${NC}"
    exit 1
fi
echo ""

# Step 6: Configure fstab
echo -e "${YELLOW}[6/8] Настройка /etc/fstab...${NC}"

# Read archive info
if [ -f /tmp/nas_archive_ip ] && [ -f /tmp/nas_archive_share ]; then
    archive_ip=$(cat /tmp/nas_archive_ip)
    archive_share=$(cat /tmp/nas_archive_share)
else
    read -p "IP адрес Archive NAS: " archive_ip
    read -p "Share name для Archive: " archive_share
fi

# Backup fstab
cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)

# Check if entries already exist
if grep -q "${PLAYOUT_MOUNT}" /etc/fstab; then
    echo -e "${YELLOW}⚠️  Запись для Playout уже есть в fstab, пропускаем${NC}"
else
    echo "" >> /etc/fstab
    echo "# OK Tools - NAS Playout" >> /etc/fstab
    echo "//192.168.188.1/sendedaten  ${PLAYOUT_MOUNT}  cifs  credentials=${CREDS_PLAYOUT},uid=${uid},gid=${gid},file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0" >> /etc/fstab
    echo -e "${GREEN}✅ Playout добавлен в fstab${NC}"
fi

if grep -q "${ARCHIVE_MOUNT}" /etc/fstab; then
    echo -e "${YELLOW}⚠️  Запись для Archive уже есть в fstab, пропускаем${NC}"
else
    echo "# OK Tools - NAS Archive" >> /etc/fstab
    echo "//${archive_ip}/${archive_share}  ${ARCHIVE_MOUNT}  cifs  credentials=${CREDS_ARCHIVE},uid=${uid},gid=${gid},file_mode=0755,dir_mode=0755,vers=3.0,_netdev,nofail  0  0" >> /etc/fstab
    echo -e "${GREEN}✅ Archive добавлен в fstab${NC}"
fi
echo ""

# Step 7: Mount
echo -e "${YELLOW}[7/8] Монтирование NAS...${NC}"
mount -a
sleep 2

# Check if mounted
if mountpoint -q "${PLAYOUT_MOUNT}"; then
    echo -e "${GREEN}✅ Playout смонтирован${NC}"
    file_count=$(find "${PLAYOUT_MOUNT}" -maxdepth 1 -type f | wc -l)
    echo "   Файлов в корне: ${file_count}"
else
    echo -e "${RED}❌ Playout НЕ смонтирован!${NC}"
    echo "   Проверь: mount | grep ${PLAYOUT_MOUNT}"
fi

if mountpoint -q "${ARCHIVE_MOUNT}"; then
    echo -e "${GREEN}✅ Archive смонтирован${NC}"
    file_count=$(find "${ARCHIVE_MOUNT}" -maxdepth 1 -type f | wc -l)
    echo "   Файлов в корне: ${file_count}"
else
    echo -e "${RED}❌ Archive НЕ смонтирован!${NC}"
    echo "   Проверь: mount | grep ${ARCHIVE_MOUNT}"
fi
echo ""

# Step 8: Test access
echo -e "${YELLOW}[8/8] Тест доступа от имени ${gunicorn_user}...${NC}"
if sudo -u "${gunicorn_user}" test -r "${PLAYOUT_MOUNT}"; then
    echo -e "${GREEN}✅ ${gunicorn_user} может читать ${PLAYOUT_MOUNT}${NC}"
else
    echo -e "${RED}❌ ${gunicorn_user} НЕ может читать ${PLAYOUT_MOUNT}${NC}"
fi

if sudo -u "${gunicorn_user}" test -r "${ARCHIVE_MOUNT}"; then
    echo -e "${GREEN}✅ ${gunicorn_user} может читать ${ARCHIVE_MOUNT}${NC}"
else
    echo -e "${RED}❌ ${gunicorn_user} НЕ может читать ${ARCHIVE_MOUNT}${NC}"
fi
echo ""

# Cleanup temp files
rm -f /tmp/nas_archive_ip /tmp/nas_archive_share

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Настройка NAS завершена!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Смонтированные точки:"
mount | grep cifs
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo "1. Обнови production.cfg:"
echo "   [media]"
echo "   archive_path = ${ARCHIVE_MOUNT}/"
echo "   playout_path = ${PLAYOUT_MOUNT}/"
echo ""
echo "2. Перезапусти gunicorn:"
echo "   sudo systemctl restart oktools.service"
echo ""
echo "3. Создай Storage Locations в Django Admin"
echo ""
echo "4. Запусти сканирование:"
echo "   cd /opt/ok-tools && python manage.py scan_video_storage"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

