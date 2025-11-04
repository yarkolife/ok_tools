#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "Stopping OK Tools Production"
echo "=========================================="

if [ ! -d "$PRODUCTION_DIR" ]; then
    echo -e "${RED}Error: Production directory not found at $PRODUCTION_DIR${NC}"
    exit 1
fi

cd "$PRODUCTION_DIR"

echo "Stopping containers..."
docker compose down

echo -e "${GREEN}✓ All services stopped${NC}"
echo ""
echo "To start services again, run:"
echo "  cd $PRODUCTION_DIR && docker compose up -d"
