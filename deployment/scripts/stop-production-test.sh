#!/bin/bash
#
# Скрипт остановки и удаления OK Tools Production с тестового сервера
# Останавливает контейнеры, опционально удаляет volumes и размонтирует NAS
#

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Функции для красивого вывода
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

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    print_error "Запусти скрипт с sudo: sudo bash stop-production-test.sh"
    exit 1
fi

# Определение директории установки
INSTALL_DIR="/opt/ok-tools-test"

if [ ! -d "$INSTALL_DIR" ]; then
    print_error "OK Tools не установлен в $INSTALL_DIR"
    print_info "Нечего удалять"
    exit 1
fi

print_header "Остановка и удаление OK Tools Production с тестового сервера"
print_info "Директория установки: $INSTALL_DIR"

cd "$INSTALL_DIR"

# ================================
# ШАГ 1: Создание финального бэкапа
# ================================

print_header "Шаг 1: Создание финального бэкапа"

BACKUP_DIR="/opt/ok-tools-final-backup-$(date +%Y%m%d-%H%M%S)"
print_info "Создание финального бэкапа в $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"

# Бэкап базы данных
if docker compose ps | grep -q "Up"; then
    print_info "Создание бэкапа базы данных..."
    docker compose exec -T db pg_dump -U oktools oktools > "$BACKUP_DIR/database.sql" 2>/dev/null || true
    
    # Бэкап медиа файлов
    print_info "Создание бэкапа медиа файлов..."
    docker compose exec web tar -czf - /app/media 2>/dev/null | cat > "$BACKUP_DIR/media.tar.gz" || true
else
    print_warning "Контейнеры не запущены, пропускаю бэкап данных"
fi

# Бэкап конфигурации
print_info "Создание бэкапа конфигурации..."
cp docker-production.cfg "$BACKUP_DIR/" 2>/dev/null || true
cp docker-compose.yml "$BACKUP_DIR/" 2>/dev/null || true

# Бэкап логов
print_info "Создание бэкапа логов..."
docker compose logs > "$BACKUP_DIR/logs.txt" 2>/dev/null || true

print_success "Финальный бэкап создан в $BACKUP_DIR"

# ================================
# ШАГ 2: Остановка контейнеров
# ================================

print_header "Шаг 2: Остановка Docker контейнеров"

if docker compose ps | grep -q "Up"; then
    print_info "Остановка контейнеров..."
    docker compose down
    print_success "Контейнеры остановлены"
else
    print_info "Контейнеры уже остановлены"
fi

# ================================
# ШАГ 3: Удаление Docker ресурсов
# ================================

print_header "Шаг 3: Удаление Docker ресурсов"

# Вопрос об удалении volumes
echo ""
print_warning "Удаление Docker volumes приведет к потере всех данных!"
echo "Включает:"
echo "  - База данных PostgreSQL"
echo "  - Статические файлы"
echo "  - Медиа файлы"
echo "  - Логи приложения"
echo ""
read -p "Удалить Docker volumes? (y/n): " DELETE_VOLUMES

if [ "$DELETE_VOLUMES" = "y" ]; then
    print_warning "Удаление Docker volumes..."
    docker compose down -v
    docker volume prune -f
    print_success "Docker volumes удалены"
else
    print_info "Docker volumes сохранены"
fi

# Удаление образов
print_info "Удаление Docker образов..."
docker compose down --rmi all 2>/dev/null || true
docker image prune -f
print_success "Docker образы удалены"

# ================================
# ШАГ 4: Размонтирование NAS
# ================================

print_header "Шаг 4: Размонтирование NAS"

# Вопрос о размонтировании
echo ""
print_warning "Размонтирование NAS хранилищ"
echo "Это отключит доступ к сетевым хранилищам видеофайлов"
echo ""
read -p "Размонтировать NAS? (y/n): " UNMOUNT_NAS

if [ "$UNMOUNT_NAS" = "y" ]; then
    print_info "Размонтирование NAS..."
    
    # Размонтирование
    umount /mnt/nas/playout 2>/dev/null || true
    umount /mnt/nas/archive 2>/dev/null || true
    
    # Удаление из fstab
    print_info "Удаление записей из /etc/fstab..."
    sed -i '/# OK Tools NAS Mounts (Production Test)/,/^$/d' /etc/fstab
    
    # Удаление credentials файлов
    print_info "Удаление credentials файлов..."
    rm -f /root/.smbcredentials_playout
    rm -f /root/.smbcredentials_archive
    
    # Удаление точек монтирования
    print_info "Удаление точек монтирования..."
    rmdir /mnt/nas/playout 2>/dev/null || true
    rmdir /mnt/nas/archive 2>/dev/null || true
    rmdir /mnt/nas 2>/dev/null || true
    
    print_success "NAS размонтирован и настроенная конфигурация удалена"
else
    print_info "NAS остался смонтированным"
fi

# ================================
# ШАГ 5: Удаление файлов приложения
# ================================

print_header "Шаг 5: Удаление файлов приложения"

# Вопрос об удалении директории
echo ""
print_warning "Удаление директории приложения: $INSTALL_DIR"
echo "Это удалит:"
echo "  - Весь код приложения"
echo "  - Конфигурационные файлы"
echo "  - Docker файлы"
echo "  - Локальные скрипты управления"
echo ""
read -p "Удалить директорию приложения? (y/n): " DELETE_DIR

if [ "$DELETE_DIR" = "y" ]; then
    print_info "Удаление директории приложения..."
    cd /
    rm -rf "$INSTALL_DIR"
    print_success "Директория приложения удалена"
else
    print_info "Директория приложения сохранена: $INSTALL_DIR"
    print_info "Можешь запустить установку заново или удалить вручную"
fi

# ================================
# ШАГ 6: Очистка системы
# ================================

print_header "Шаг 6: Очистка системы"

# Удаление неиспользуемых Docker ресурсов
print_info "Очистка неиспользуемых Docker ресурсов..."
docker system prune -f

# Удаление логов установки
print_info "Очистка логов установки..."
rm -f /var/log/ok-tools-install.log
rm -f /var/log/ok-tools-update.log

print_success "Система очищена"

# ================================
# ИТОГИ
# ================================

print_header "Удаление завершено!"

echo ""
print_success "OK Tools Production удален с тестового сервера"
echo ""
echo -e "${GREEN}Выполненные действия:${NC}"
echo -e "  ✓ Создан финальный бэкап: $BACKUP_DIR"

if [ "$DELETE_VOLUMES" = "y" ]; then
    echo -e "  ✓ Docker volumes удалены"
else
    echo -e "  ○ Docker volumes сохранены"
fi

echo -e "  ✓ Docker образы удалены"

if [ "$UNMOUNT_NAS" = "y" ]; then
    echo -e "  ✓ NAS размонтирован"
    echo -e "  ✓ NAS конфигурация удалена"
else
    echo -e "  ○ NAS остался смонтированным"
fi

if [ "$DELETE_DIR" = "y" ]; then
    echo -e "  ✓ Директория приложения удалена"
else
    echo -e "  ○ Директория приложения сохранена: $INSTALL_DIR"
fi

echo -e "  ✓ Система очищена"
echo ""
echo -e "${YELLOW}Финальный бэкап:${NC} $BACKUP_DIR"
echo ""
echo -e "${BLUE}Для полной очистки Docker:${NC}"
echo -e "  docker system prune -a -f  # удалит ВСЕ неиспользуемые ресурсы"
echo ""
echo -e "${BLUE}Для повторной установки:${NC}"
echo -e "  sudo bash /path/to/install-production-test.sh"
echo ""
print_success "Готово!"

# Предупреждение о сохранении данных
if [ "$DELETE_VOLUMES" != "y" ] || [ "$DELETE_DIR" != "y" ]; then
    echo ""
    print_warning "Некоторые данные сохранены:"
    if [ "$DELETE_VOLUMES" != "y" ]; then
        echo -e "  - Docker volumes с базой данных и файлами"
    fi
    if [ "$DELETE_DIR" != "y" ]; then
        echo -e "  - Директория приложения: $INSTALL_DIR"
    fi
    echo ""
    print_info "Для полного удаления запусти скрипт повторно и выбери удаление всех компонентов"
fi