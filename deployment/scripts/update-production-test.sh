#!/bin/bash
#
# Скрипт обновления OK Tools Production на тестовом сервере
# Выполняет git pull, rebuild контейнеров, миграции и перезапуск
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
    print_error "Запусти скрипт с sudo: sudo bash update-production-test.sh"
    exit 1
fi

# Определение директории установки
INSTALL_DIR="/opt/ok-tools-test"

if [ ! -d "$INSTALL_DIR" ]; then
    print_error "OK Tools не установлен в $INSTALL_DIR"
    print_info "Сначала запусти install-production-test.sh"
    exit 1
fi

# Логирование
LOG_FILE="/var/log/ok-tools-update.log"
exec > >(tee -a "$LOG_FILE") 2>&1

print_header "Обновление OK Tools Production на тестовом сервере"
print_info "Лог обновления: $LOG_FILE"
print_info "Директория установки: $INSTALL_DIR"

cd "$INSTALL_DIR"

# ================================
# ШАГ 1: Проверка статуса
# ================================

print_header "Шаг 1: Проверка текущего статуса"

print_info "Статус контейнеров:"
docker compose ps

# Проверка git статуса
print_info "Git статус:"
git status --porcelain

if [ -n "$(git status --porcelain)" ]; then
    print_warning "Есть несохраненные изменения в git"
    read -p "Продолжить обновление? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        print_error "Обновление отменено"
        exit 1
    fi
fi

print_success "Статус проверен"

# ================================
# ШАГ 2: Создание бэкапа
# ================================

print_header "Шаг 2: Создание бэкапа"

BACKUP_DIR="/opt/ok-tools-backup-$(date +%Y%m%d-%H%M%S)"
print_info "Создание бэкапа в $BACKUP_DIR"

# Остановка контейнеров для бэкапа БД
print_info "Остановка контейнеров для бэкапа..."
docker compose stop web cron

# Бэкап базы данных
print_info "Создание бэкапа базы данных..."
mkdir -p "$BACKUP_DIR"
docker compose exec -T db pg_dump -U oktools oktools > "$BACKUP_DIR/database.sql"

# Бэкап конфигурации
print_info "Создание бэкапа конфигурации..."
cp docker-production.cfg "$BACKUP_DIR/"
cp docker-compose.yml "$BACKUP_DIR/"

# Запуск контейнеров обратно
print_info "Запуск контейнеров..."
docker compose start web cron

print_success "Бэкап создан в $BACKUP_DIR"

# ================================
# ШАГ 3: Обновление кода
# ================================

print_header "Шаг 3: Обновление кода из Git"

print_info "Получение обновлений из репозитория..."
git fetch origin

# Проверка изменений
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/main)

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    print_warning "Нет новых обновлений"
    read -p "Продолжить пересборку контейнеров? (y/n): " REBUILD
    if [ "$REBUILD" != "y" ]; then
        print_info "Обновление отменено"
        exit 0
    fi
else
    print_info "Найдены новые изменения:"
    git log --oneline "$LOCAL_COMMIT..$REMOTE_COMMIT"
    
    read -p "Применить обновления? (y/n): " APPLY_UPDATE
    if [ "$APPLY_UPDATE" != "y" ]; then
        print_error "Обновление отменено"
        exit 1
    fi
    
    # Сброс локальных изменений и применение обновлений
    git reset --hard HEAD
    git pull origin main
    print_success "Код обновлен"
fi

# ================================
# ШАГ 4: Пересборка контейнеров
# ================================

print_header "Шаг 4: Пересборка Docker контейнеров"

print_info "Остановка контейнеров..."
docker compose down

print_warning "Пересборка образов (может занять несколько минут)..."
docker compose build --no-cache

print_info "Запуск обновленных контейнеров..."
docker compose up -d

# Ожидание запуска
print_info "Ожидание запуска контейнеров..."
sleep 10

# Проверка статуса
print_info "Проверка статуса контейнеров:"
docker compose ps

print_success "Контейнеры пересобраны и запущены"

# ================================
# ШАГ 5: Применение миграций
# ================================

print_header "Шаг 5: Применение миграций базы данных"

print_info "Проверка новых миграций..."
docker compose exec web python manage.py showmigrations --plan

print_info "Применение миграций..."
docker compose exec web python manage.py migrate

print_success "Миграции применены"

# ================================
# ШАГ 6: Обновление статики
# ================================

print_header "Шаг 6: Обновление статических файлов"

print_info "Сбор статических файлов..."
docker compose exec web python manage.py collectstatic --noinput

print_success "Статические файлы обновлены"

# ================================
# ШАГ 7: Проверка работоспособности
# ================================

print_header "Шаг 7: Проверка работоспособности"

# Проверка health endpoint
print_info "Проверка доступности сервисов..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Веб-сервис доступен"
        break
    elif [ $i -eq 30 ]; then
        print_error "Веб-сервис не отвечает после обновления"
        print_warning "Проверь логи: docker compose logs web"
        exit 1
    else
        sleep 2
    fi
done

# Проверка логов на ошибки
print_info "Проверка логов на критические ошибки..."
if docker compose logs web 2>&1 | grep -i "error\|exception\|traceback" | tail -5; then
    print_warning "Обнаружены ошибки в логах, проверь: docker compose logs web"
else
    print_success "Критических ошибок в логах не обнаружено"
fi

# ================================
# ШАГ 8: Очистка
# ================================

print_header "Шаг 8: Очистка"

print_info "Удаление неиспользуемых Docker образов..."
docker image prune -f

print_info "Удаление неиспользуемых Docker volumes..."
docker volume prune -f

print_success "Очистка завершена"

# ================================
# ИТОГИ
# ================================

print_header "Обновление завершено!"

echo ""
print_success "OK Tools Production успешно обновлен!"
echo ""
echo -e "${GREEN}Статус сервисов:${NC}"
docker compose ps
echo ""
echo -e "${BLUE}Полезные команды:${NC}"
echo -e "  docker compose ps          # статус контейнеров"
echo -e "  docker compose logs -f     # логи"
echo -e "  docker compose restart     # перезапуск"
echo ""
echo -e "${YELLOW}Бэкап сохранен в:${NC} $BACKUP_DIR"
echo -e "${YELLOW}Лог обновления:${NC} $LOG_FILE"
echo ""
print_success "Готово!"

# Уведомление о необходимости перезагрузки сервера (если нужно)
if [ -f /var/run/reboot-required ]; then
    print_warning "Сервер требует перезагрузки после системных обновлений"
    print_info "Выполни: sudo reboot"
fi