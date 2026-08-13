#!/bin/bash
# Скрипт для быстрой диагностики системы после установки

# Переменные цветов
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==========================================${NC}"
echo -e "${YELLOW} OK Tools System Diagnostics${NC}"
echo -e "${YELLOW}==========================================${NC}"

# 1. Проверка статуса контейнеров
echo -e "\n${YELLOW}1. Checking container status...${NC}"
if ! docker compose ps --format "table {{.Service}}\t{{.Status}}"; then
    echo -e "${RED}Error: Failed to get container status. Is Docker running?${NC}"
    exit 1
fi

UNHEALTHY_CONTAINERS=$(docker compose ps --format "table {{.Service}}\t{{.Status}}" | grep -i "unhealthy" | awk '{print $1}' | grep -v "SERVICE")
if [ -n "$UNHEALTHY_CONTAINERS" ]; then
    echo -e "\n${RED}Warning: The following containers are unhealthy:${NC}"
    echo "$UNHEALTHY_CONTAINERS"
    echo -e "${YELLOW}This might indicate a problem. Check logs with: docker compose logs -f <service_name>${NC}"
else
    echo -e "\n${GREEN}✓ All containers are running and healthy.${NC}"
fi

# Проверка на остановленные сервисы: `docker compose ps` без -a показывает только
# запущенные, поэтому упавший контейнер в проверке выше просто отсутствует, а не
# выглядит проблемой. Так незамеченным остался certbot, умерший в июне 2026.
STOPPED_CONTAINERS=$(docker compose ps -a --format "{{.Service}}\t{{.Status}}" | grep -i -E "exited|dead" | awk '{print $1}')
if [ -n "$STOPPED_CONTAINERS" ]; then
    echo -e "\n${RED}Warning: The following services are defined but not running:${NC}"
    docker compose ps -a --format "table {{.Service}}\t{{.Status}}" | grep -i -E "exited|dead|SERVICE"
    echo -e "${YELLOW}Start them with: docker compose up -d${NC}"
else
    echo -e "${GREEN}✓ No stopped services.${NC}"
fi

# 2. Проверка логов web-сервиса на наличие ошибок
echo -e "\n${YELLOW}2. Checking web service logs for recent errors...${NC}"
if docker compose logs --tail=50 web | grep -i -E "error|traceback"; then
    echo -e "\n${RED}Warning: Potential errors found in web service logs.${NC}"
    echo -e "${YELLOW}Please review the logs above carefully.${NC}"
else
    echo -e "${GREEN}✓ No critical errors found in recent web service logs.${NC}"
fi

# 3. Проверка срока действия TLS-сертификата
# Проверяем то, что nginx реально отдаёт по сети, а не файл на диске: после
# продления файл уже новый, но nginx держит в памяти старый сертификат до reload,
# и расходятся эти две величины именно тогда, когда это важнее всего.
echo -e "\n${YELLOW}3. Checking TLS certificate expiry...${NC}"
DOMAIN_NAME=$(grep '^DOMAIN_NAME=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [ -z "$DOMAIN_NAME" ] || [ "$DOMAIN_NAME" = "localhost" ]; then
    echo -e "${GREEN}✓ No public domain configured - skipping TLS check.${NC}"
elif ! command -v openssl >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ openssl not available - skipping TLS check.${NC}"
else
    SERVED_CERT=$(echo | openssl s_client -connect "localhost:443" -servername "$DOMAIN_NAME" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d'=' -f2)
    if [ -z "$SERVED_CERT" ]; then
        echo -e "${RED}✗ Could not read the certificate served on port 443.${NC}"
    else
        EXPIRY_EPOCH=$(date -d "$SERVED_CERT" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$SERVED_CERT" +%s 2>/dev/null)
        NOW_EPOCH=$(date +%s)
        if [ -z "$EXPIRY_EPOCH" ]; then
            echo -e "${YELLOW}⚠ Certificate expires on $SERVED_CERT (could not parse date).${NC}"
        else
            DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
            if [ "$DAYS_LEFT" -lt 0 ]; then
                echo -e "${RED}✗ Certificate for $DOMAIN_NAME EXPIRED $(( -DAYS_LEFT )) day(s) ago ($SERVED_CERT).${NC}"
                echo -e "${YELLOW}Check the certbot container: docker compose ps -a certbot${NC}"
            elif [ "$DAYS_LEFT" -lt 21 ]; then
                # Certbot продлевает за 30 дней до истечения; меньше 21 дня означает,
                # что как минимум три попытки продления уже не сработали.
                echo -e "${RED}✗ Certificate for $DOMAIN_NAME expires in $DAYS_LEFT day(s) - renewal is overdue.${NC}"
                echo -e "${YELLOW}Check the certbot container: docker compose logs --tail=50 certbot${NC}"
            else
                echo -e "${GREEN}✓ Certificate for $DOMAIN_NAME is valid for $DAYS_LEFT more day(s).${NC}"
            fi
        fi
    fi
fi

echo -e "\n${YELLOW}==========================================${NC}"
echo -e "${GREEN}Diagnostics complete.${NC}"
echo -e "${YELLOW}==========================================${NC}"