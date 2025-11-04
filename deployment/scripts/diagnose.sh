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

# 2. Проверка логов web-сервиса на наличие ошибок
echo -e "\n${YELLOW}2. Checking web service logs for recent errors...${NC}"
if docker compose logs --tail=50 web | grep -i -E "error|traceback"; then
    echo -e "\n${RED}Warning: Potential errors found in web service logs.${NC}"
    echo -e "${YELLOW}Please review the logs above carefully.${NC}"
else
    echo -e "${GREEN}✓ No critical errors found in recent web service logs.${NC}"
fi

echo -e "\n${YELLOW}==========================================${NC}"
echo -e "${GREEN}Diagnostics complete.${NC}"
echo -e "${YELLOW}==========================================${NC}"