#!/bin/bash
set -e

# Update script for OK Tools production environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

if [ ! -d "$PRODUCTION_DIR" ]; then
    echo "Error: Production directory not found at $PRODUCTION_DIR"
    echo "Please run install.sh first"
    exit 1
fi

echo "=========================================="
echo "OK Tools Production Update"
echo "=========================================="
echo ""

# Function to detect and repair corrupted .env files
repair_env_file() {
    local env_file="$PRODUCTION_DIR/.env"
    
    if [ ! -f "$env_file" ]; then
        echo "Warning: .env file not found at $env_file"
        return 1
    fi
    
    # Check for corruption pattern: concatenated variables (pattern: KEY=VALUE=VALUE)
    local corrupted_lines=$(grep -E '^[^#].*=.*=.*' "$env_file" | wc -l)
    
    if [ "$corrupted_lines" -gt 0 ]; then
        echo "Detected corruption in .env file ($corrupted_lines corrupted lines)"
        echo "Creating backup..."
        cp "$env_file" "$env_file.backup.$(date +%Y%m%d_%H%M%S)"
        
        echo "Repairing .env file..."
        
        # Create temporary file for repaired content
        local temp_file="/tmp/repaired_env.tmp"
        
        # Process each line to fix concatenated variables
        while IFS= read -r line; do
            # Skip comments and empty lines
            if [[ $line =~ ^# ]] || [[ -z "$line" ]]; then
                echo "$line" >> "$temp_file"
                continue
            fi
            
            # Check if line contains concatenated variables
            if [[ $line =~ ^([^=]+)=(.*)=(.*)$ ]]; then
                # Extract the first key-value pair
                local key="${BASH_REMATCH[1]}"
                local value="${BASH_REMATCH[2]}"
                
                # Write the first key-value pair
                echo "$key=$value" >> "$temp_file"
                
                # Try to extract the second key-value pair
                local remaining="${BASH_REMATCH[3]}"
                if [[ $remaining =~ ^([^=]+)=(.*)$ ]]; then
                    local second_key="${BASH_REMATCH[1]}"
                    local second_value="${BASH_REMATCH[2]}"
                    echo "$second_key=$second_value" >> "$temp_file"
                fi
            else
                # Line is not corrupted, write as-is
                echo "$line" >> "$temp_file"
            fi
        done < "$env_file"
        
        # Replace original file with repaired version
        mv "$temp_file" "$env_file"
        chmod 600 "$env_file"
        
        echo "✓ .env file repaired successfully"
        return 0
    else
        echo "✓ .env file appears to be valid"
        return 1
    fi
}

# Check and repair .env file if needed
repair_env_file

# Pull latest code
echo "Pulling latest code from repository..."
cd "$PROJECT_DIR"
git pull

# Update docker-compose files and configs in production directory
echo "Updating docker-compose files and configs..."
cd "$PROJECT_DIR"

# Determine which docker-compose file to use based on existing installation
if grep -q "^DOMAIN_NAME=" "$PRODUCTION_DIR/.env" && [ ! -z "$(grep '^DOMAIN_NAME=' "$PRODUCTION_DIR/.env" | cut -d'=' -f2)" ]; then
    echo "Detected: Production with Nginx and SSL"
    cp -f deployment/docker-compose.production.yml "$PRODUCTION_DIR/docker-compose.yml"
else
    echo "Detected: Local Network or Localhost (without Nginx)"
    cp -f deployment/docker-compose.production.no-nginx.yml "$PRODUCTION_DIR/docker-compose.yml"
fi

cp -f deployment/production.Dockerfile "$PRODUCTION_DIR/"
cp -f deployment/nginx.conf.template "$PRODUCTION_DIR/"
cp -f deployment/nginx-entrypoint.sh "$PRODUCTION_DIR/"
cp -f deployment/entrypoint.production.sh "$PRODUCTION_DIR/"

# Create configs directory if it doesn't exist and copy config files
mkdir -p "$PRODUCTION_DIR/configs"
cp -f deployment/configs/* "$PRODUCTION_DIR/configs/"

# Rebuild Docker images
echo "Rebuilding Docker images..."
cd "$PRODUCTION_DIR"
docker compose build --no-cache

# Restart containers
echo "Restarting containers..."
docker compose down
docker compose up -d

# Run migrations
echo "Running database migrations..."
docker compose exec -T web python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput

echo ""
echo "=========================================="
echo "Update Complete!"
echo "=========================================="
echo "Check logs: docker compose logs -f web"