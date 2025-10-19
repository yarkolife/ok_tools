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

# Обновление кода из репозитория
print_info "Обновление кода из репозитория..."
if ! git pull origin main; then
    print_error "Ошибка при обновлении кода из репозитория"
    exit 1
fi
print_success "Код успешно обновлен"

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

# Проверка изменений в Dockerfile.production
if echo "$CHANGED_FILES" | grep -E "deployment/docker/Dockerfile\.production" >/dev/null; then
    NEED_FULL_REBUILD=true
    print_info "🐳 Обнаружены изменения в Dockerfile.production - требуется полная пересборка"
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

# Ротация бэкапов - оставляем только последние 5
print_info "Ротация бэкапов..."
BACKUP_PATTERN="/opt/ok_tools_backup-*"
BACKUP_COUNT=$(ls -1d $BACKUP_PATTERN 2>/dev/null | wc -l)
KEEP_BACKUPS=5

if [ "$BACKUP_COUNT" -gt "$KEEP_BACKUPS" ]; then
    print_info "Найдено $BACKUP_COUNT бэкапов, оставляем только последние $KEEP_BACKUPS"
    
    # Получаем список бэкапов, отсортированных по дате создания (старые первыми)
    OLD_BACKUPS=$(ls -1td $BACKUP_PATTERN | tail -n +$((KEEP_BACKUPS + 1)))
    
    for old_backup in $OLD_BACKUPS; do
        if [ -d "$old_backup" ]; then
            print_info "Удаляем старый бэкап: $(basename "$old_backup")"
            rm -rf "$old_backup"
        fi
    done
    
    print_success "Ротация бэкапов завершена. Оставлено $KEEP_BACKUPS последних бэкапов"
else
    print_info "Количество бэкапов ($BACKUP_COUNT) не превышает лимит ($KEEP_BACKUPS), ротация не требуется"
fi

# ================================
# ШАГ 3: Пропущен - код уже обновлен в начале скрипта
# ================================

print_info "Код уже обновлен в начале скрипта, пропускаем дублирование"

# ================================
# ШАГ 3: Пересборка контейнеров (условная)
# ================================

if [ "$UPDATE_STRATEGY" = "FULL_REBUILD" ]; then
    print_header "Шаг 3: Полная пересборка Docker контейнеров"
    
    # Копируем обновленный Dockerfile
    print_info "Копирование обновленного Dockerfile..."
    if [ -f "deployment/docker/Dockerfile.production" ]; then
        cp deployment/docker/Dockerfile.production Dockerfile
        print_success "Dockerfile обновлен"
    else
        print_warning "Dockerfile.production не найден, использую существующий"
    fi

print_info "Остановка контейнеров..."
docker compose down

    print_warning "Полная пересборка образов (может занять несколько минут)..."
docker compose build --no-cache

print_info "Запуск обновленных контейнеров..."
docker compose up -d
    
elif [ "$UPDATE_STRATEGY" = "CODE_UPDATE" ]; then
    print_header "Шаг 3: Инкрементальная пересборка Docker контейнеров"
    
    # Копируем обновленный Dockerfile если он изменился
    print_info "Проверка изменений в Dockerfile..."
    if [ -f "deployment/docker/Dockerfile.production" ]; then
        if ! cmp -s "deployment/docker/Dockerfile.production" "Dockerfile"; then
            print_info "Dockerfile изменился, копирую обновленную версию..."
            cp deployment/docker/Dockerfile.production Dockerfile
            print_success "Dockerfile обновлен"
        else
            print_info "Dockerfile не изменился"
        fi
    fi
    
    print_info "Инкрементальная пересборка web образа..."
    docker compose build web
    
else
    print_header "Шаг 3: Только перезапуск контейнеров"
    
    print_info "Подготовка к перезапуску контейнеров..."
fi

# Ожидание завершения сборки
print_info "Ожидание завершения сборки..."
sleep 5

# ================================
# ШАГ 4: Исправление конфигурации (условное)
# ================================

if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
    print_header "Шаг 4: Обновление конфигурации"

    print_info "Проверка изменений в конфигурационных файлах..."
    
    # Определяем, какая конфигурация используется
    CONFIG_SOURCE=""
    if grep -q "organization_owner = OKMQ" docker-production.cfg 2>/dev/null; then
        CONFIG_SOURCE="deployment/configs/okmq-production.cfg"
    elif grep -q "organization_owner = OK Bayern" docker-production.cfg 2>/dev/null; then
        CONFIG_SOURCE="deployment/configs/ok-bayern-production.cfg"
    elif grep -q "organization_owner = OK NRW" docker-production.cfg 2>/dev/null; then
        CONFIG_SOURCE="deployment/configs/ok-nrw-production.cfg"
    fi

    if [ -n "$CONFIG_SOURCE" ] && [ -f "$CONFIG_SOURCE" ]; then
        print_info "Найдена исходная конфигурация: $CONFIG_SOURCE"
        
        # Создаем бэкап текущей конфигурации
        cp docker-production.cfg docker-production.cfg.backup
        
        # Копируем обновленную конфигурацию
        print_info "Копирование обновленной конфигурации..."
        cp "$CONFIG_SOURCE" docker-production.cfg
        
        # Восстанавливаем пользовательские настройки из бэкапа
        print_info "Восстановление пользовательских настроек..."
        
        # Извлекаем пользовательские значения из бэкапа
        SECRET_KEY=$(grep "secret_key = " docker-production.cfg.backup | cut -d'=' -f2 | tr -d ' ')
        DB_PASSWORD=$(grep "db_pw = " docker-production.cfg.backup | cut -d'=' -f2 | tr -d ' ')
        ALLOWED_HOSTS=$(grep "allowed_hosts = " docker-production.cfg.backup | cut -d'=' -f2 | sed 's/^ *//' | sed 's/ *$//')
        
        # Применяем пользовательские настройки
        if [ -n "$SECRET_KEY" ]; then
            sed -i "s/secret_key = .*/secret_key = $SECRET_KEY/g" docker-production.cfg
        fi
        
        if [ -n "$DB_PASSWORD" ]; then
            sed -i "s/db_pw = .*/db_pw = $DB_PASSWORD/g" docker-production.cfg
        fi
        
        # Восстанавливаем ALLOWED_HOSTS из бэкапа для сохранения IP адреса сервера
        if [ -n "$ALLOWED_HOSTS" ]; then
            # Проверяем и исправляем формат ALLOWED_HOSTS перед восстановлением
            # Проверяем, есть ли пробелы между хостами (правильный формат)
            if [[ "$ALLOWED_HOSTS" != *" "* ]]; then
                print_warning "Исправляю формат ALLOWED_HOSTS из бэкапа (добавляю пробелы между хостами)..."
                # Исправляем формат: добавляем пробелы между доменами/IP адресами
                # Ищем паттерны доменов и IP адресов и добавляем пробелы между ними
                ALLOWED_HOSTS=$(echo "$ALLOWED_HOSTS" | sed 's/\([a-zA-Z0-9.-]\+\.[a-zA-Z0-9.-]\+\)\([a-zA-Z0-9.-]\+\.[a-zA-Z0-9.-]\+\)/\1 \2/g' | sed 's/\([0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+\)\([a-zA-Z0-9.-]\+\.[a-zA-Z0-9.-]\+\)/\1 \2/g' | sed 's/  */ /g')
                print_info "ALLOWED_HOSTS исправлен: $ALLOWED_HOSTS"
            fi
            
            sed -i "s/allowed_hosts = .*/allowed_hosts = $ALLOWED_HOSTS/g" docker-production.cfg
            print_info "ALLOWED_HOSTS восстановлен из бэкапа: $ALLOWED_HOSTS"
        fi
        
        # Применяем Docker-специфичные исправления
        print_info "Применение Docker-специфичных исправлений..."
        sed -i 's|static = /opt/ok-tools/static/|static = /app/static/|g' docker-production.cfg
        sed -i 's|media = /opt/ok-tools/media/|media = /app/media/|g' docker-production.cfg
        sed -i 's/db_host = localhost/db_host = db/g' docker-production.cfg
        sed -i 's/db_name = oktools_okmq/db_name = oktools/g' docker-production.cfg
        
        # Удаляем временный бэкап
        rm docker-production.cfg.backup
        
        print_success "Конфигурация обновлена из $CONFIG_SOURCE"
    else
        print_warning "Исходная конфигурация не найдена, применяю только исправления..."
        
        # Применяем только исправления для существующей конфигурации
        if grep -q "static = /opt/ok-tools/static/" docker-production.cfg 2>/dev/null; then
            print_warning "Исправляю STATIC_ROOT..."
            sed -i 's|static = /opt/ok-tools/static/|static = /app/static/|g' docker-production.cfg
            print_success "STATIC_ROOT исправлен"
        fi

        if grep -q "media = /opt/ok-tools/media/" docker-production.cfg 2>/dev/null; then
            print_warning "Исправляю MEDIA_ROOT..."
            sed -i 's|media = /opt/ok-tools/media/|media = /app/media/|g' docker-production.cfg
            print_success "MEDIA_ROOT исправлен"
        fi

        if grep -q "db_host = localhost" docker-production.cfg 2>/dev/null; then
            print_warning "Исправляю db_host..."
            sed -i 's/db_host = localhost/db_host = db/g' docker-production.cfg
            print_success "db_host исправлен"
        fi

        if grep -q "db_name = oktools_okmq" docker-production.cfg 2>/dev/null; then
            print_warning "Исправляю db_name..."
            sed -i 's/db_name = oktools_okmq/db_name = oktools/g' docker-production.cfg
            print_success "db_name исправлен"
        fi

        # Проверяем и исправляем формат ALLOWED_HOSTS
        CURRENT_ALLOWED_HOSTS_LINE=$(grep "allowed_hosts = " docker-production.cfg)
        CURRENT_ALLOWED_HOSTS_VALUE=$(echo "$CURRENT_ALLOWED_HOSTS_LINE" | cut -d'=' -f2 | sed 's/^ *//' | sed 's/ *$//')
        
        # Проверяем, есть ли пробелы между хостами (правильный формат)
        if [[ "$CURRENT_ALLOWED_HOSTS_VALUE" != *" "* ]]; then
            print_warning "Обнаружен неправильный формат ALLOWED_HOSTS (отсутствуют пробелы между хостами)..."
            
            # Исправляем формат ALLOWED_HOSTS - добавляем пробелы между хостами
            # Ищем паттерны доменов и IP адресов и добавляем пробелы между ними
            FIXED_ALLOWED_HOSTS=$(echo "$CURRENT_ALLOWED_HOSTS_VALUE" | sed 's/\([a-zA-Z0-9.-]\+\.[a-zA-Z0-9.-]\+\)\([a-zA-Z0-9.-]\+\.[a-zA-Z0-9.-]\+\)/\1 \2/g' | sed 's/\([0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+\)\([a-zA-Z0-9.-]\+\.[a-zA-Z0-9.-]\+\)/\1 \2/g' | sed 's/  */ /g')
            
            # Заменяем в файле
            sed -i "s|allowed_hosts = .*|allowed_hosts = $FIXED_ALLOWED_HOSTS|g" docker-production.cfg
            print_success "ALLOWED_HOSTS исправлен: $FIXED_ALLOWED_HOSTS"
        else
            print_info "Формат ALLOWED_HOSTS корректный: $CURRENT_ALLOWED_HOSTS_VALUE"
        fi
        
        # Проверяем, есть ли IP адрес сервера в ALLOWED_HOSTS
        CURRENT_ALLOWED_HOSTS_VALUE=$(grep "allowed_hosts = " docker-production.cfg | cut -d'=' -f2 | sed 's/^ *//' | sed 's/ *$//')
        
        if [[ "$CURRENT_ALLOWED_HOSTS_VALUE" != *"192.168.88.213"* ]]; then
            print_info "Добавляю IP адрес сервера в ALLOWED_HOSTS..."
            if [[ "$CURRENT_ALLOWED_HOSTS_VALUE" == *"localhost"* ]]; then
                # Заменяем localhost на IP адрес + localhost
                sed -i 's/allowed_hosts = .*/allowed_hosts = 192.168.88.213 localhost 127.0.0.1 */g' docker-production.cfg
            else
                # Добавляем IP адрес к существующим хостам
                sed -i 's/allowed_hosts = .*/allowed_hosts = 192.168.88.213 */g' docker-production.cfg
            fi
            print_success "IP адрес сервера добавлен в ALLOWED_HOSTS"
        else
            print_info "IP адрес сервера уже присутствует в ALLOWED_HOSTS"
        fi
    fi

    print_success "Конфигурация обновлена и исправлена"
    
    print_info "Конфигурация подготовлена для применения при перезапуске контейнеров"
else
    print_header "Шаг 5: Пропуск исправления конфигурации (только перезапуск)"
    print_info "Стратегия RESTART_ONLY - исправление конфигурации не требуется"
fi

# ================================
# ШАГ 5: Применение миграций (условное)
# ================================

if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
print_header "Шаг 5: Применение миграций базы данных"

    # Проверка миграций (проблемная миграция 0004 уже исправлена)
    print_info "Проверка миграций..."

print_info "Проверка новых миграций..."
    if ! docker compose exec web python manage.py showmigrations --plan; then
        print_error "Ошибка при проверке миграций"
        exit 1
    fi

print_info "Применение миграций..."
    if ! docker compose exec web python manage.py migrate; then
        print_error "Ошибка при применении миграций"
        print_info "Попытка исправления проблемных миграций..."
        
        # Попытка исправить проблемную миграцию 0005
        if docker compose exec web python manage.py migrate media_files 0005 --fake 2>/dev/null; then
            print_success "Миграция 0005 успешно помечена как примененная"
            print_info "Повторное применение миграций..."
docker compose exec web python manage.py migrate
        else
            print_error "Не удалось исправить миграции автоматически"
            exit 1
        fi
    fi

print_success "Миграции применены"
else
    print_header "Шаг 5: Пропуск применения миграций (только перезапуск)"
    print_info "Стратегия RESTART_ONLY - применение миграций не требуется"
fi

# ================================
# ШАГ 6: Обновление статики (условное)
# ================================

if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
print_header "Шаг 6: Обновление статических файлов"

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
    print_header "Шаг 6: Пропуск обновления статических файлов (только перезапуск)"
    print_info "Стратегия RESTART_ONLY - обновление статических файлов не требуется"
fi

# ================================
# ШАГ 7: Полный перезапуск всех контейнеров
# ================================

print_header "Шаг 7: Полный перезапуск всех контейнеров"

print_info "Остановка всех контейнеров..."
docker compose down

print_info "Запуск всех контейнеров..."
docker compose up -d --remove-orphans

# Ожидание запуска
print_info "Ожидание запуска контейнеров..."
sleep 15

# Проверка статуса
print_info "Проверка статуса контейнеров:"
docker compose ps

print_success "Все контейнеры успешно перезапущены"

# Проверяем, что конфигурация применилась в контейнере
if [ "$UPDATE_STRATEGY" != "RESTART_ONLY" ]; then
    print_info "Проверка применения конфигурации в контейнере..."
    if docker compose exec web cat /app/docker-production.cfg | grep -q "db_host = db"; then
        print_success "Конфигурация успешно применена в контейнере"
    else
        print_warning "Конфигурация не применилась автоматически, исправляю в контейнере..."
        docker compose exec web sed -i 's/db_host = localhost/db_host = db/g' /app/docker-production.cfg
        print_success "Конфигурация исправлена в контейнере"
    fi
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

# Дополнительная ротация бэкапов (на случай, если основная не сработала)
print_info "Проверка ротации бэкапов..."
BACKUP_PATTERN="/opt/ok_tools_backup-*"
BACKUP_COUNT=$(ls -1d $BACKUP_PATTERN 2>/dev/null | wc -l)
KEEP_BACKUPS=5

if [ "$BACKUP_COUNT" -gt "$KEEP_BACKUPS" ]; then
    print_info "Дополнительная ротация: найдено $BACKUP_COUNT бэкапов, оставляем $KEEP_BACKUPS"
    OLD_BACKUPS=$(ls -1td $BACKUP_PATTERN | tail -n +$((KEEP_BACKUPS + 1)))
    
    for old_backup in $OLD_BACKUPS; do
        if [ -d "$old_backup" ]; then
            print_info "Удаляем старый бэкап: $(basename "$old_backup")"
            rm -rf "$old_backup"
        fi
    done
    print_success "Дополнительная ротация бэкапов завершена"
fi

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
echo -e "${YELLOW}Ротация бэкапов:${NC} Оставляем последние 5 бэкапов"
echo ""
print_success "Готово!"

# Уведомление о необходимости перезагрузки сервера (если нужно)
if [ -f /var/run/reboot-required ]; then
    print_warning "Сервер требует перезагрузки после системных обновлений"
    print_info "Выполни: sudo reboot"
fi