#!/bin/bash

# ================================
# OK Tools Production - Post-Install Configuration Script
# ================================
# Скрипт для настройки после установки
# Использование: sudo bash configure-production-test.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# ================================
# Проверка окружения
# ================================

print_header "OK Tools Production - Post-Install Configuration"

# Проверка прав
if [ "$EUID" -ne 0 ]; then
    print_error "Запусти скрипт с sudo: sudo bash configure-production-test.sh"
    exit 1
fi

INSTALL_DIR="/opt/ok_tools_test"

# Проверка существования установки
if [ ! -d "$INSTALL_DIR" ]; then
    print_error "Установка не найдена в $INSTALL_DIR"
    print_info "Сначала запусти install-production-test.sh"
    exit 1
fi

if [ ! -f "$INSTALL_DIR/docker-production.cfg" ]; then
    print_error "Конфигурация не найдена"
    print_info "Сначала запусти install-production-test.sh"
    exit 1
fi

print_success "Установка найдена в $INSTALL_DIR"

cd "$INSTALL_DIR"

# ================================
# ШАГ 1: Проверка статуса контейнеров
# ================================

print_header "Шаг 1: Проверка статуса контейнеров"

print_info "Проверка статуса Docker контейнеров..."
docker compose ps

# Проверка доступности сервисов
print_info "Проверка доступности веб-сервиса..."
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    print_success "Веб-сервис доступен"
else
    print_warning "Веб-сервис не отвечает, проверяю логи..."
    docker compose logs web --tail=20
fi

# ================================
# ШАГ 2: Проверка и исправление конфигурации
# ================================

print_header "Шаг 2: Проверка конфигурации"

print_info "Проверка настроек Django..."
docker compose exec web python manage.py diffsettings | grep -E "(STATIC_ROOT|DATABASES)" || true

# Проверка и исправление STATIC_ROOT
STATIC_ROOT=$(docker compose exec web python manage.py shell -c "from django.conf import settings; print(settings.STATIC_ROOT)" 2>/dev/null || echo "")
if [[ "$STATIC_ROOT" == *"/opt/ok-tools/static/"* ]]; then
    print_warning "Неправильный STATIC_ROOT: $STATIC_ROOT"
    print_info "Исправляю конфигурацию..."
    sed -i 's|static = /opt/ok-tools/static/|static = /app/static/|g' docker-production.cfg
    docker compose restart web
    sleep 10
    print_success "STATIC_ROOT исправлен"
fi

# Проверка DATABASE_HOST
DB_HOST=$(docker compose exec web python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['HOST'])" 2>/dev/null || echo "")
if [[ "$DB_HOST" == "localhost" ]]; then
    print_warning "Неправильный DATABASE_HOST: $DB_HOST"
    print_info "Исправляю конфигурацию..."
    sed -i 's/db_host = localhost/db_host = db/g' docker-production.cfg
    docker compose restart web
    sleep 10
    print_success "DATABASE_HOST исправлен"
fi

# ================================
# ШАГ 3: Проверка миграций
# ================================

print_header "Шаг 3: Проверка миграций"

print_info "Проверка статуса миграций..."
docker compose exec web python manage.py showmigrations --plan | tail -20

# Проверка на проблемные миграции
if [ -f "media_files/migrations/0004_add_unc_path_to_storage.py" ]; then
    print_warning "Обнаружена проблемная миграция 0004_add_unc_path_to_storage.py"
    print_info "Удаляю проблемную миграцию..."
    rm -f media_files/migrations/0004_add_unc_path_to_storage.py
    docker compose restart web
    sleep 10
    print_success "Проблемная миграция удалена"
fi

# Попытка применения миграций
print_info "Проверка и применение миграций..."
if docker compose exec web python manage.py migrate --check; then
    print_success "Все миграции применены"
else
    print_info "Применяю миграции..."
    docker compose exec web python manage.py migrate
    print_success "Миграции применены"
fi

# ================================
# ШАГ 4: Проверка статических файлов
# ================================

print_header "Шаг 4: Проверка статических файлов"

# Создание директории static если не существует
if [ ! -d "static" ]; then
    print_info "Создаю директорию static..."
    mkdir -p static
    chmod 755 static
    chown pavlo:pavlo static
fi

# Проверка сбора статических файлов
print_info "Проверка статических файлов..."
if docker compose exec web python manage.py collectstatic --dry-run --noinput | grep -q "0 static files"; then
    print_success "Статические файлы уже собраны"
else
    print_info "Собираю статические файлы..."
    docker compose exec web python manage.py collectstatic --noinput
    print_success "Статические файлы собраны"
fi

# ================================
# ШАГ 5: Проверка суперпользователя
# ================================

print_header "Шаг 5: Проверка суперпользователя"

print_info "Проверка наличия суперпользователей..."
SUPERUSER_COUNT=$(docker compose exec web python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).count())" 2>/dev/null || echo "0")

if [ "$SUPERUSER_COUNT" -gt 0 ]; then
    print_success "Суперпользователи найдены ($SUPERUSER_COUNT)"
else
    print_warning "Суперпользователи не найдены"
    echo ""
    print_info "Создай суперпользователя:"
    echo "  docker compose exec web python manage.py createsuperuser"
    echo ""
fi

# ================================
# ШАГ 6: Проверка NAS подключения
# ================================

print_header "Шаг 6: Проверка NAS подключения"

# Проверка точек монтирования
if mountpoint -q /mnt/nas/playout 2>/dev/null; then
    print_success "NAS Playout подключен"
    ls -la /mnt/nas/playout/ | head -5
else
    print_warning "NAS Playout не подключен"
fi

if mountpoint -q /mnt/nas/archive 2>/dev/null; then
    print_success "NAS Archive подключен"
    ls -la /mnt/nas/archive/ | head -5
else
    print_warning "NAS Archive не подключен"
fi

# ================================
# ШАГ 7: Проверка логов
# ================================

print_header "Шаг 7: Проверка логов"

print_info "Проверка логов веб-сервиса..."
docker compose logs web --tail=10

print_info "Проверка логов базы данных..."
docker compose logs db --tail=5

# ================================
# ШАГ 8: Финальная проверка
# ================================

print_header "Шаг 8: Финальная проверка"

# Проверка доступности
SERVER_IP=$(hostname -I | awk '{print $1}')
print_info "Проверка доступности приложения..."

if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    print_success "✅ Приложение доступно"
    echo ""
    echo -e "${GREEN}🎉 OK Tools Production готов к работе!${NC}"
    echo ""
    echo -e "${BLUE}Доступ к приложению:${NC}"
    echo -e "  🌐 URL: http://$SERVER_IP:8001"
    echo -e "  🔧 Админка: http://$SERVER_IP:8001/admin/"
    echo -e "  ❤️  Health: http://$SERVER_IP:8001/health"
    echo ""
    echo -e "${YELLOW}Следующие шаги:${NC}"
    echo -e "  1. Открой http://$SERVER_IP:8001/admin/ в браузере"
    echo -e "  2. Создай Storage Locations в админке"
    echo -e "  3. Настрой пользователей и права доступа"
    echo ""
else
    print_error "❌ Приложение недоступно"
    print_info "Проверь логи: docker compose logs web"
    echo ""
    echo -e "${YELLOW}Команды для диагностики:${NC}"
    echo -e "  docker compose ps"
    echo -e "  docker compose logs web"
    echo -e "  docker compose logs db"
    echo ""
fi

# ================================
# Дополнительные команды
# ================================

print_header "Полезные команды"

echo -e "${BLUE}Управление контейнерами:${NC}"
echo -e "  docker compose ps                    # Статус контейнеров"
echo -e "  docker compose logs web              # Логи веб-сервиса"
echo -e "  docker compose restart web           # Перезапуск веб-сервиса"
echo -e "  docker compose down                  # Остановка всех контейнеров"
echo -e "  docker compose up -d                 # Запуск всех контейнеров"
echo ""

echo -e "${BLUE}Управление Django:${NC}"
echo -e "  docker compose exec web python manage.py createsuperuser"
echo -e "  docker compose exec web python manage.py migrate"
echo -e "  docker compose exec web python manage.py collectstatic --noinput"
echo -e "  docker compose exec web python manage.py shell"
echo ""

echo -e "${BLUE}Обновление:${NC}"
echo -e "  git pull origin main                 # Обновление кода"
echo -e "  docker compose build --no-cache     # Пересборка образов"
echo -e "  bash configure-production-test.sh   # Повторная настройка"
echo ""

print_success "Конфигурация завершена!"
