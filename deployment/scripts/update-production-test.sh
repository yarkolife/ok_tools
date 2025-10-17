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
INSTALL_DIR="/opt/ok_tools_test"

# Проверка существования директории
if [ ! -d "$INSTALL_DIR" ]; then
    print_error "OK Tools не установлен в $INSTALL_DIR"
    print_info "Сначала запусти install-production-test.sh"
    exit 1
fi

# Переход в директорию установки
cd "$INSTALL_DIR" || {
    print_error "Не удается перейти в $INSTALL_DIR"
    exit 1
}

# Логирование
LOG_FILE="/var/log/ok-tools-update.log"
exec > >(tee -a "$LOG_FILE") 2>&1

print_header "Обновление OK Tools Production на тестовом сервере"
print_info "Лог обновления: $LOG_FILE"
print_info "Директория установки: $INSTALL_DIR"

cd "$INSTALL_DIR"

# ================================
# ШАГ 1: Проверка статуса и определение типа изменений
# ================================

print_header "Шаг 1: Проверка текущего статуса и анализ изменений"

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

# Анализ изменений для определения стратегии обновления
print_info "Анализ изменений..."

# Получаем список измененных файлов
CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")

# Инициализация флагов
NEED_FULL_REBUILD=false
NEED_CODE_UPDATE=false
NEED_CONFIG_UPDATE=false
NEED_RESTART_ONLY=false

# Проверка критических изменений
if echo "$CHANGED_FILES" | grep -E "(requirements\.txt|Dockerfile|docker-compose\.yml)" >/dev/null; then
    NEED_FULL_REBUILD=true
    print_info "🔧 Обнаружены изменения в зависимостях или Docker конфигурации - требуется полная пересборка"
fi

if echo "$CHANGED_FILES" | grep -E "\.(py|html|css|js)$" >/dev/null; then
    NEED_CODE_UPDATE=true
    print_info "📝 Обнаружены изменения в коде - требуется обновление кода"
fi

if echo "$CHANGED_FILES" | grep -E "(nginx\.conf|\.cfg|\.conf)$" >/dev/null; then
    NEED_CONFIG_UPDATE=true
    print_info "⚙️ Обнаружены изменения в конфигурации - требуется обновление настроек"
fi

# Проверка миграций
if echo "$CHANGED_FILES" | grep -E "migrations/.*\.py$" >/dev/null; then
    NEED_CODE_UPDATE=true
    print_info "🗄️ Обнаружены изменения в миграциях - требуется применение миграций"
fi

# Если нет критических изменений, проверяем только git pull
if [ -z "$CHANGED_FILES" ] && ! $NEED_FULL_REBUILD && ! $NEED_CODE_UPDATE && ! $NEED_CONFIG_UPDATE; then
    print_info "📋 Нет критических изменений - проверяем обновления из репозитория"
    NEED_RESTART_ONLY=true
fi

# Определение стратегии обновления
if $NEED_FULL_REBUILD; then
    UPDATE_STRATEGY="FULL_REBUILD"
    print_info "🎯 Стратегия: ПОЛНАЯ ПЕРЕСБОРКА"
elif $NEED_CODE_UPDATE || $NEED_CONFIG_UPDATE; then
    UPDATE_STRATEGY="CODE_UPDATE"
    print_info "🎯 Стратегия: ОБНОВЛЕНИЕ КОДА И НАСТРОЕК"
else
    UPDATE_STRATEGY="RESTART_ONLY"
    print_info "🎯 Стратегия: ТОЛЬКО ПЕРЕЗАПУСК"
fi

print_success "Анализ завершен"

# ================================
# ШАГ 2: Создание бэкапа
# ================================

print_header "Шаг 2: Создание бэкапа"

BACKUP_DIR="/opt/ok_tools_backup-$(date +%Y%m%d-%H%M%S)"
print_info "Создание бэкапа в $BACKUP_DIR"

# Остановка контейнеров для бэкапа БД
print_info "Остановка контейнеров для бэкапа..."
docker compose stop web

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
docker compose start web

print_success "Бэкап создан в $BACKUP_DIR"

# ================================
# ШАГ 3: Обновление кода (условное)
# ================================

if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
    print_header "Шаг 3: Обновление кода из Git"
    
    print_info "Получение обновлений из репозитория..."
    git fetch origin
    
    # Проверка изменений
    LOCAL_COMMIT=$(git rev-parse HEAD)
    REMOTE_COMMIT=$(git rev-parse origin/main)
    
    if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
        print_warning "Нет новых обновлений"
        read -p "Продолжить обновление? (y/n): " CONTINUE_UPDATE
        if [ "$CONTINUE_UPDATE" != "y" ]; then
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
else
    print_header "Шаг 3: Пропуск обновления кода (только перезапуск)"
    print_info "Стратегия RESTART_ONLY - обновление кода не требуется"
fi

# ================================
# ШАГ 4: Пересборка контейнеров (условная)
# ================================

if [ "$UPDATE_STRATEGY" = "FULL_REBUILD" ]; then
    print_header "Шаг 4: Полная пересборка Docker контейнеров"
    
    print_info "Остановка контейнеров..."
    docker compose down
    
    print_warning "Полная пересборка образов (может занять несколько минут)..."
    docker compose build --no-cache
    
    print_info "Запуск обновленных контейнеров..."
    docker compose up -d
    
elif [ "$UPDATE_STRATEGY" = "CODE_UPDATE" ]; then
    print_header "Шаг 4: Инкрементальная пересборка Docker контейнеров"
    
    print_info "Остановка web контейнера..."
    docker compose stop web
    
    print_info "Инкрементальная пересборка web образа..."
    docker compose build web
    
    print_info "Запуск обновленного web контейнера..."
    docker compose start web
    
else
    print_header "Шаг 4: Только перезапуск контейнеров"
    
    print_info "Перезапуск контейнеров..."
    docker compose restart
fi

# Ожидание запуска
print_info "Ожидание запуска контейнеров..."
sleep 10

# Проверка статуса
print_info "Проверка статуса контейнеров:"
docker compose ps

print_success "Контейнеры пересобраны и запущены"

# ================================
# ШАГ 5: Исправление конфигурации (условное)
# ================================

if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
    print_header "Шаг 5: Исправление конфигурации"

print_info "Проверка и исправление конфигурации..."

# Проверка и исправление STATIC_ROOT
if grep -q "static = /opt/ok-tools/static/" docker-production.cfg 2>/dev/null; then
    print_warning "Исправляю STATIC_ROOT..."
    sed -i 's|static = /opt/ok-tools/static/|static = /app/static/|g' docker-production.cfg
    print_success "STATIC_ROOT исправлен"
fi

# Проверка и исправление MEDIA_ROOT
if grep -q "media = /opt/ok-tools/media/" docker-production.cfg 2>/dev/null; then
    print_warning "Исправляю MEDIA_ROOT..."
    sed -i 's|media = /opt/ok-tools/media/|media = /app/media/|g' docker-production.cfg
    print_success "MEDIA_ROOT исправлен"
fi

# Проверка и исправление db_host
if grep -q "db_host = localhost" docker-production.cfg 2>/dev/null; then
    print_warning "Исправляю db_host..."
    sed -i 's/db_host = localhost/db_host = db/g' docker-production.cfg
    print_success "db_host исправлен"
fi

# Проверка и исправление db_name
if grep -q "db_name = oktools_okmq" docker-production.cfg 2>/dev/null; then
    print_warning "Исправляю db_name..."
    sed -i 's/db_name = oktools_okmq/db_name = oktools/g' docker-production.cfg
    print_success "db_name исправлен"
fi

# Перезапуск web контейнера если были изменения
if [ -f docker-production.cfg.orig ] || [ -f docker-production.cfg.bak ]; then
    print_info "Перезапуск web контейнера для применения изменений..."
    docker compose restart web
    sleep 10
fi

    print_success "Конфигурация проверена и исправлена"
else
    print_header "Шаг 5: Пропуск исправления конфигурации (только перезапуск)"
    print_info "Стратегия RESTART_ONLY - исправление конфигурации не требуется"
fi

# ================================
# ШАГ 6: Применение миграций (условное)
# ================================

if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
    print_header "Шаг 6: Применение миграций базы данных"

# Проверка миграций (проблемная миграция 0004 уже исправлена)
print_info "Проверка миграций..."

print_info "Проверка новых миграций..."
docker compose exec web python manage.py showmigrations --plan

print_info "Применение миграций..."
docker compose exec web python manage.py migrate

    print_success "Миграции применены"
else
    print_header "Шаг 6: Пропуск применения миграций (только перезапуск)"
    print_info "Стратегия RESTART_ONLY - применение миграций не требуется"
fi

# ================================
# ШАГ 7: Обновление статики (условное)
# ================================

if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
    print_header "Шаг 7: Обновление статических файлов"

# Создание директории static если не существует
if [ ! -d "static" ]; then
    print_info "Создаю директорию static..."
    mkdir -p static
    chmod 755 static
    chown pavlo:pavlo static 2>/dev/null || true
fi

print_info "Сбор статических файлов..."
docker compose exec web python manage.py collectstatic --noinput

    print_success "Статические файлы обновлены"
else
    print_header "Шаг 7: Пропуск обновления статических файлов (только перезапуск)"
    print_info "Стратегия RESTART_ONLY - обновление статических файлов не требуется"
fi

# ================================
# ШАГ 8: Проверка работоспособности
# ================================

print_header "Шаг 8: Проверка работоспособности"

# Проверка health endpoint
print_info "Проверка доступности сервисов..."
for i in {1..30}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
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
# ШАГ 9: Очистка
# ================================

print_header "Шаг 9: Очистка"

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