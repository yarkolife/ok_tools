#!/bin/bash
#
# Скрипт установки OK Tools Production версии на тестовый сервер
# Для локальной сети - доступ по IP, с выбором конфигурации организации
#

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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
    echo -e "${PURPLE}ℹ $1${NC}"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    print_error "Запусти скрипт с sudo: sudo bash install-production-test.sh"
    exit 1
fi

# Логирование
LOG_FILE="/var/log/ok-tools-install.log"
exec > >(tee -a "$LOG_FILE") 2>&1

print_header "Установка OK Tools Production на тестовый сервер"
print_info "Лог установки: $LOG_FILE"

# ================================
# ШАГ 1: Проверка Docker
# ================================

print_header "Шаг 1: Проверка Docker и Docker Compose"

if ! command -v docker &> /dev/null; then
    print_warning "Docker не установлен. Устанавливаю..."
    
    # Установка Docker
    apt-get update
    apt-get install -y ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      $(lsb_release -cs) stable" | \
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
# ШАГ 2: Выбор конфигурации
# ================================

print_header "Шаг 2: Выбор конфигурации организации"

# Получаем текущую директорию скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$SCRIPT_DIR/../configs"

print_info "Доступные конфигурации:"
echo ""
echo "1) OK Bayern (ok-bayern-production.cfg)"
echo "2) OK Merseburg-Querfurt (okmq-production.cfg)" 
echo "3) OK NRW (ok-nrw-production.cfg)"
echo ""

while true; do
    read -p "Выберите конфигурацию (1-3): " CONFIG_CHOICE
    case $CONFIG_CHOICE in
        1)
            CONFIG_FILE="ok-bayern-production.cfg"
            ORG_NAME="OK Bayern"
            break
            ;;
        2)
            CONFIG_FILE="okmq-production.cfg"
            ORG_NAME="OK Merseburg-Querfurt"
            break
            ;;
        3)
            CONFIG_FILE="ok-nrw-production.cfg"
            ORG_NAME="OK NRW"
            break
            ;;
        *)
            print_error "Неверный выбор. Введите 1, 2 или 3."
            ;;
    esac
done

if [ ! -f "$CONFIGS_DIR/$CONFIG_FILE" ]; then
    print_error "Файл конфигурации не найден: $CONFIGS_DIR/$CONFIG_FILE"
    exit 1
fi

print_success "Выбрана конфигурация: $ORG_NAME ($CONFIG_FILE)"

# ================================
# ШАГ 3: Ввод данных
# ================================

print_header "Шаг 3: Ввод индивидуальных данных"

# IP адрес сервера
CURRENT_IP=$(hostname -I | awk '{print $1}')
print_warning "Обнаружен IP адрес: $CURRENT_IP"
read -p "IP адрес сервера [$CURRENT_IP]: " SERVER_IP
SERVER_IP=${SERVER_IP:-$CURRENT_IP}

# PostgreSQL пароль
while true; do
    read -sp "Пароль для PostgreSQL (минимум 8 символов): " DB_PASSWORD
    echo
    if [ ${#DB_PASSWORD} -ge 8 ]; then
        break
    else
        print_error "Пароль должен содержать минимум 8 символов"
    fi
done

# Django SECRET_KEY
print_info "Django SECRET_KEY:"
echo "1) Автогенерация (рекомендуется)"
echo "2) Ввести вручную"
echo ""
read -p "Выберите опцию (1-2): " SECRET_KEY_CHOICE

if [ "$SECRET_KEY_CHOICE" = "1" ]; then
    SECRET_KEY=$(python3 -c "from secrets import token_urlsafe; print(token_urlsafe(50))" 2>/dev/null || openssl rand -base64 50)
    print_success "SECRET_KEY сгенерирован автоматически"
else
    read -sp "Введите Django SECRET_KEY (минимум 50 символов): " SECRET_KEY
    echo
    if [ ${#SECRET_KEY} -lt 50 ]; then
        print_warning "SECRET_KEY слишком короткий, генерирую автоматически"
        SECRET_KEY=$(python3 -c "from secrets import token_urlsafe; print(token_urlsafe(50))" 2>/dev/null || openssl rand -base64 50)
    fi
fi

# NAS настройки
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

print_success "Данные введены"

# ================================
# ШАГ 4: Подготовка окружения
# ================================

print_header "Шаг 4: Подготовка окружения"

INSTALL_DIR="/opt/ok_tools_test"

# Проверка рабочей директории
if [ ! -d "$INSTALL_DIR" ]; then
    print_error "Директория $INSTALL_DIR не существует"
    print_info "Сначала клонируй репозиторий:"
    print_info "  sudo mkdir -p $INSTALL_DIR"
    print_info "  cd $INSTALL_DIR"
    print_info "  sudo git clone https://github.com/yarkolife/ok_tools_dev.git ."
    print_info "  sudo chown -R pavlo:pavlo $INSTALL_DIR"
    exit 1
fi

# Проверка git репозитория
if [ ! -d "$INSTALL_DIR/.git" ]; then
    print_error "Git репозиторий не найден в $INSTALL_DIR"
    print_info "Убедись, что клонировал репозиторий правильно"
    exit 1
fi

print_success "Найдена рабочая директория с git репозиторием: $INSTALL_DIR"

# Копирование файлов из deployment/docker/
print_info "Копирование Docker файлов..."
cp "$INSTALL_DIR/deployment/docker/Dockerfile.production" "$INSTALL_DIR/Dockerfile"
cp "$INSTALL_DIR/deployment/docker/docker-compose.production.yml" "$INSTALL_DIR/docker-compose.yml"
cp "$INSTALL_DIR/deployment/docker/nginx.conf" "$INSTALL_DIR/nginx.conf"
print_success "Docker файлы скопированы"

# Код приложения уже есть в директории
print_success "Код приложения уже присутствует в директории"

cd "$INSTALL_DIR"

# ================================
# ШАГ 5: Создание конфигурации
# ================================

print_header "Шаг 5: Создание конфигурации"

# Копирование выбранной конфигурации
cp "$CONFIGS_DIR/$CONFIG_FILE" "$INSTALL_DIR/docker-production.cfg"

# Замена плейсхолдеров
print_info "Замена плейсхолдеров в конфигурации..."

# SECRET_KEY
sed -i "s/YOUR-PRODUCTION-SECRET-KEY-HERE/$SECRET_KEY/g" "$INSTALL_DIR/docker-production.cfg"

# Database password
sed -i "s/YOUR-DATABASE-PASSWORD/$DB_PASSWORD/g" "$INSTALL_DIR/docker-production.cfg"

# Allowed hosts - добавляем IP сервера
sed -i "s/allowed_hosts = .*/allowed_hosts = $SERVER_IP localhost 127.0.0.1 */g" "$INSTALL_DIR/docker-production.cfg"

# NAS пути (если они изменились)
if [ -n "$NAS_PLAYOUT_IP" ] && [ -n "$NAS_PLAYOUT_SHARE" ]; then
    sed -i "s|archive_unc_path = .*|archive_unc_path = \\\\\\\\$NAS_ARCHIVE_IP\\\\\\\\$NAS_ARCHIVE_SHARE|g" "$INSTALL_DIR/docker-production.cfg"
    sed -i "s|playout_unc_path = .*|playout_unc_path = \\\\\\\\$NAS_PLAYOUT_IP\\\\\\\\$NAS_PLAYOUT_SHARE|g" "$INSTALL_DIR/docker-production.cfg"
fi

chmod 644 "$INSTALL_DIR/docker-production.cfg"
print_success "Конфигурация создана: $INSTALL_DIR/docker-production.cfg"

# ================================
# ШАГ 6: Настройка NAS монтирования
# ================================

print_header "Шаг 6: Настройка NAS монтирования"

# Установка cifs-utils
if ! command -v mount.cifs &> /dev/null; then
    print_info "Установка cifs-utils..."
    apt-get update
    apt-get install -y cifs-utils
    print_success "cifs-utils установлен"
else
    print_success "cifs-utils уже установлен"
fi

# Создание точек монтирования
mkdir -p /mnt/nas/playout
mkdir -p /mnt/nas/archive
chmod 755 /mnt/nas
print_success "Точки монтирования созданы"

# Создание credentials файлов
print_info "Создание credentials файлов..."
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

# Добавление в fstab с оптимизированными параметрами
print_info "Добавление в /etc/fstab..."
if ! grep -q "/mnt/nas/playout" /etc/fstab; then
    cat >> /etc/fstab <<EOF

# OK Tools NAS Mounts (Production Test)
//$NAS_PLAYOUT_IP/$NAS_PLAYOUT_SHARE  /mnt/nas/playout  cifs  credentials=/root/.smbcredentials_playout,uid=0,gid=0,file_mode=0755,dir_mode=0755,rsize=1048576,wsize=1048576,vers=3.0,_netdev,nofail  0  0
//$NAS_ARCHIVE_IP/$NAS_ARCHIVE_SHARE  /mnt/nas/archive  cifs  credentials=/root/.smbcredentials_archive,uid=0,gid=0,file_mode=0755,dir_mode=0755,rsize=1048576,wsize=1048576,vers=3.0,_netdev,nofail  0  0
EOF
fi

# Монтирование
print_info "Монтирование NAS..."
mount -a || true
sleep 3

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
# ШАГ 7: Настройка docker-compose
# ================================

print_header "Шаг 7: Настройка docker-compose"

# Обновление docker-compose.yml для тестового сервера
print_info "Настройка docker-compose.yml для тестового сервера..."

# Удаляем nginx сервис и меняем порты
cat > "$INSTALL_DIR/docker-compose.yml" <<EOF
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: oktools
      POSTGRES_USER: oktools
      POSTGRES_PASSWORD: $DB_PASSWORD
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - oktools-network

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    networks:
      - oktools-network

  web:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8001:8000"
    environment:
      - OKTOOLS_CONFIG_FILE=/app/docker-production.cfg
      - DJANGO_SETTINGS_MODULE=ok_tools.settings
      - POSTGRES_PASSWORD=$DB_PASSWORD
    depends_on:
      - db
      - redis
    volumes:
      - ./docker-production.cfg:/app/docker-production.cfg:ro
      - static_files:/app/static
      - media_files:/app/media
      - logs:/app/logs
      - /mnt/nas/playout:/mnt/nas/playout:ro
      - /mnt/nas/archive:/mnt/nas/archive:ro
    restart: unless-stopped
    networks:
      - oktools-network

  cron:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - OKTOOLS_CONFIG_FILE=/app/docker-production.cfg
      - DJANGO_SETTINGS_MODULE=ok_tools.settings
      - POSTGRES_PASSWORD=$DB_PASSWORD
    depends_on:
      - db
      - web
    volumes:
      - ./docker-production.cfg:/app/docker-production.cfg:ro
      - logs:/app/logs
      - /mnt/nas/playout:/mnt/nas/playout:ro
      - /mnt/nas/archive:/mnt/nas/archive:ro
    command: |
      sh -c "
        touch /app/logs/expire_rentals.log &&
        echo '*/30 * * * * cd /app && python scripts/run_expire_rentals.py >> /app/logs/expire_rentals.log 2>&1' | crontab - &&
        service cron start &&
        tail -f /app/logs/expire_rentals.log
      "
    restart: unless-stopped
    networks:
      - oktools-network

volumes:
  postgres_data:
  static_files:
  media_files:
  logs:

networks:
  oktools-network:
    driver: bridge
EOF

print_success "docker-compose.yml настроен для тестового сервера"

# ================================
# ШАГ 8: Запуск контейнеров
# ================================

print_header "Шаг 8: Запуск Docker контейнеров"

cd "$INSTALL_DIR"

# Остановка старых контейнеров если есть
print_info "Остановка старых контейнеров..."
docker compose down 2>/dev/null || true

# Сборка образов
print_warning "Сборка Docker образов (может занять несколько минут)..."
docker compose build

# Запуск контейнеров
print_warning "Запуск контейнеров..."
docker compose up -d

# Ожидание запуска
print_info "Ожидание запуска контейнеров..."
sleep 10

# Проверка статуса
print_info "Проверка статуса контейнеров:"
docker compose ps

# Проверка health
print_info "Проверка доступности сервисов..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Веб-сервис доступен"
        break
    elif [ $i -eq 30 ]; then
        print_warning "Веб-сервис не отвечает, но продолжаю установку"
        break
    else
        sleep 2
    fi
done

print_success "Docker контейнеры запущены"

# ================================
# ШАГ 9: Инициализация Django
# ================================

print_header "Шаг 9: Инициализация Django"

# Применение миграций
print_info "Применение миграций базы данных..."
docker compose exec web python manage.py migrate

# Сбор статики
print_info "Сбор статических файлов..."
docker compose exec web python manage.py collectstatic --noinput

# Создание суперпользователя
print_header "Создание суперпользователя Django"
print_warning "Создайте суперпользователя для доступа к админке:"
docker compose exec web python manage.py createsuperuser

print_success "Django инициализирован"

# ================================
# ШАГ 10: Итоговая информация
# ================================

print_header "Установка завершена!"

echo ""
print_success "OK Tools Production успешно установлен на тестовый сервер!"
echo ""
echo -e "${GREEN}Доступ к приложению:${NC}"
echo -e "  URL: http://$SERVER_IP:8001"
echo -e "  Админка: http://$SERVER_IP:8001/admin/"
echo -e "  Health check: http://$SERVER_IP:8001/health"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo -e "  1. Открой http://$SERVER_IP:8001/admin/ в браузере"
echo -e "  2. Создай Storage Locations (Media Files → Storage locations):"
echo -e "     - Name: $ORG_NAME Playout, Type: PLAYOUT, Path: /mnt/nas/playout/"
echo -e "     - Name: $ORG_NAME Archive, Type: ARCHIVE, Path: /mnt/nas/archive/"
echo -e "  3. Импортируй дамп базы данных (если нужно):"
echo -e "     cd $INSTALL_DIR && docker compose exec -T db psql -U oktools oktools < dump.sql"
echo -e "  4. Запусти первое сканирование видео:"
echo -e "     cd $INSTALL_DIR && docker compose exec web python manage.py scan_video_storage"
echo ""
echo -e "${BLUE}Полезные команды:${NC}"
echo -e "  cd $INSTALL_DIR"
echo -e "  docker compose ps          # статус контейнеров"
echo -e "  docker compose logs -f     # логи"
echo -e "  docker compose restart     # перезапуск"
echo -e "  docker compose down        # остановка"
echo -e "  docker compose up -d       # запуск"
echo ""
echo -e "${PURPLE}Файлы конфигурации:${NC}"
echo -e "  Конфигурация: $INSTALL_DIR/docker-production.cfg"
echo -e "  Docker compose: $INSTALL_DIR/docker-compose.yml"
echo -e "  Лог установки: $LOG_FILE"
echo ""
echo -e "${YELLOW}Примечание:${NC} Установка выполнена в директории $INSTALL_DIR"
echo -e "  Для обновления используй скрипт update-production-test.sh"
echo ""
print_success "Готово!"

# Создание скриптов управления
print_info "Создание скриптов управления..."

cat > "$INSTALL_DIR/update.sh" <<'EOF'
#!/bin/bash
# Скрипт обновления OK Tools Production Test
cd "$(dirname "$0")"
docker compose down
git pull origin main
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
echo "Обновление завершено!"
EOF
chmod +x "$INSTALL_DIR/update.sh"

cat > "$INSTALL_DIR/stop.sh" <<'EOF'
#!/bin/bash
# Скрипт остановки OK Tools Production Test
cd "$(dirname "$0")"
docker compose down
echo "Сервисы остановлены"
EOF
chmod +x "$INSTALL_DIR/stop.sh"

print_success "Скрипты управления созданы в $INSTALL_DIR/"