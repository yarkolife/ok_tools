#!/bin/bash
set -e

# Interactive installation script for OK Tools production environment with hybrid logic
# Supports both template-based installation and manual configuration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"
CONFIGS_DIR="$PROJECT_DIR/deployment/configs"

echo "=========================================="
echo "OK Tools Installation (Hybrid)"
echo "=========================================="
echo ""

echo "Choose installation type:"
echo "1. Production (Public server with Domain, Nginx, and SSL)"
echo "2. Local Network (LAN access, no domain or SSL)"
echo "3. Localhost (Development on a single machine)"
read -p "Enter your choice (1, 2, or 3): " INSTALL_TYPE
echo ""

# Function to display available templates
show_templates() {
    echo "Available configuration templates:"
    local templates=($(ls "$CONFIGS_DIR"/*.env.template 2>/dev/null))
    if [ ${#templates[@]} -eq 0 ]; then
        echo "  No templates found in $CONFIGS_DIR"
        return 1
    fi
    
    local i=1
    for template in "${templates[@]}"; do
        template_name=$(basename "$template" .env.template)
        echo " $i. $template_name"
        i=$((i+1))
    done
    return 0
}

# Function to prompt for secrets based on template
prompt_secrets() {
    local template="$1"
    local temp_config="/tmp/oktools_config.tmp"
    
    # Copy template to temporary file
    cp "$template" "$temp_config"
    
    # Extract all __REPLACE_ME__ values and prompt for them
    while IFS= read -r line; do
        if [[ $line =~ ^[^#].*=.*__REPLACE_ME__.*$ ]]; then
            key=$(echo "$line" | cut -d'=' -f1)
            echo -n "Enter value for $key: " >&2
            read -r value
            sed -i.bak "s|$key=__REPLACE_ME__|$key=$value|g" "$temp_config"
            sed -i.bak "s|$key:__REPLACE_ME__|$key:$value|g" "$temp_config"  # For colon-separated values
        fi
    done < "$template"
    
    echo "$temp_config"
}

# Check if production directory already exists
if [ -d "$PRODUCTION_DIR" ]; then
    echo "Production directory already exists at: $PRODUCTION_DIR"
    read -p "Do you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create production directory
mkdir -p "$PRODUCTION_DIR"/{data/postgres,data/static,data/media,logs,backups}

# Ask user for installation mode
echo "Choose installation mode:"
echo "1. Use existing template"
echo "2. Manual configuration"
echo ""
read -p "Enter your choice (1 or 2): " INSTALL_MODE

# Process installation based on type
case $INSTALL_TYPE in
    1)
        echo "Selected: Production (Public server with Domain, Nginx, and SSL)"
        ;;
    2)
        echo "Selected: Local Network (LAN access, no domain or SSL)"
        ;;
    3)
        echo "Selected: Localhost (Development on a single machine)"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

if [ "$INSTALL_MODE" = "1" ]; then
    # Template-based installation
    if ! show_templates; then
        echo "No templates available. Switching to manual configuration."
        INSTALL_MODE="2"
    else
        echo ""
        read -p "Enter template number (or name): " TEMPLATE_CHOICE
        
        # Check if user entered a number or name
        if [[ $TEMPLATE_CHOICE =~ ^[0-9]+$ ]]; then
            # User entered a number
            templates=($(ls "$CONFIGS_DIR"/*.env.template))
            if [ $TEMPLATE_CHOICE -ge 1 ] && [ $TEMPLATE_CHOICE -le ${#templates[@]} ]; then
                TEMPLATE_FILE="${templates[$((TEMPLATE_CHOICE-1))]}"
            else
                echo "Invalid template number."
                exit 1
            fi
        else
            # User entered a name
            TEMPLATE_FILE="$CONFIGS_DIR/$TEMPLATE_CHOICE.env.template"
            if [ ! -f "$TEMPLATE_FILE" ]; then
                echo "Template $TEMPLATE_CHOICE not found."
                exit 1
            fi
        fi
        
        echo "Using template: $TEMPLATE_FILE"
        
        # Prompt for secrets based on the selected template
        CONFIG_FILE=$(prompt_secrets "$TEMPLATE_FILE")
        
        # Copy the completed config to production directory
        cp "$CONFIG_FILE" "$PRODUCTION_DIR/.env"
        chmod 600 "$PRODUCTION_DIR/.env"
        echo "✓ Created .env file at: $PRODUCTION_DIR/.env"
        
        # Copy necessary files based on installation type
        echo ""
        echo "Copying deployment files..."
        if [ "$INSTALL_TYPE" = "1" ]; then
            # Production: use nginx-enabled compose file and copy nginx files
            cp "$PROJECT_DIR/deployment/docker-compose.production.yml" "$PRODUCTION_DIR/docker-compose.yml"
            cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template"
            cp "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/nginx-entrypoint.sh"
            chmod +x "$PRODUCTION_DIR/nginx-entrypoint.sh"
        else
            # Local Network or Localhost: use compose file without nginx
            cp "$PROJECT_DIR/deployment/docker-compose.production.no-nginx.yml" "$PRODUCTION_DIR/docker-compose.yml"
        fi
        cp "$PROJECT_DIR/deployment/production.Dockerfile" "$PRODUCTION_DIR/Dockerfile"
        cp "$PROJECT_DIR/deployment/entrypoint.production.sh" "$PRODUCTION_DIR/entrypoint.sh"
        chmod +x "$PRODUCTION_DIR/entrypoint.sh"
        
        if [ "$INSTALL_TYPE" = "1" ]; then
            echo "✓ Copied docker-compose.yml (with nginx)"
            echo "✓ Copied nginx.conf.template"
            echo "✓ Copied nginx-entrypoint.sh"
        else
            echo "✓ Copied docker-compose.yml (without nginx)"
        fi
        echo "✓ Copied Dockerfile"
        echo "✓ Copied entrypoint.sh"
        
    fi
elif [ "$INSTALL_MODE" = "2" ]; then
    # Manual configuration
    echo "Step 1: Organization Configuration"
    echo "===================================="
    read -p "Organization name (e.g., 'Your Community Media Organization e.V.'): " ORG_NAME
    read -p "Organization short name (e.g., 'Your CMO'): " ORG_SHORT_NAME
    read -p "Organization website (e.g., 'https://your-domain.com'): " ORG_WEBSITE
    read -p "Organization email: " ORG_EMAIL
    read -p "Organization phone: " ORG_PHONE
    read -p "Organization address (use \\n for line breaks): " ORG_ADDRESS
    read -p "State media institution (MSA/LFK/BLM/etc.): " STATE_MEDIA_INSTITUTION

    echo ""
    echo "Step 2: Database Configuration"
    echo "=============================="
    read -p "Database password (leave empty for auto-generated): " DB_PASSWORD
    if [ -z "$DB_PASSWORD" ]; then
        DB_PASSWORD=$(openssl rand -base64 32)
        echo "Generated database password: $DB_PASSWORD"
    fi

    echo ""
    echo "Step 3: Superuser Configuration"
    echo "==============================="
    read -p "Superuser username (default: admin): " SUPERUSER_USERNAME
    SUPERUSER_USERNAME=${SUPERUSER_USERNAME:-admin}
    read -p "Superuser email: " SUPERUSER_EMAIL
    read -p "Superuser password (leave empty for auto-generated): " SUPERUSER_PASSWORD
    if [ -z "$SUPERUSER_PASSWORD" ]; then
        SUPERUSER_PASSWORD=$(openssl rand -base64 32)
        echo "Generated superuser password: $SUPERUSER_PASSWORD"
    fi

    echo ""
    echo "Step 4: Django Configuration"
    echo "============================"
    DJANGO_SECRET_KEY=$(openssl rand -base64 50)
    
    # Set ALLOWED_HOSTS based on installation type
    if [ "$INSTALL_TYPE" = "1" ]; then
        # Production: use domain name
        read -p "Allowed hosts (comma-separated, e.g., 'localhost,your-domain.com'): " ALLOWED_HOSTS
    elif [ "$INSTALL_TYPE" = "2" ]; then
        # Local Network: ask for IP address
        read -p "Server IP address in local network (e.g., 192.168.1.100): " SERVER_IP
        ALLOWED_HOSTS="$SERVER_IP"
    else
        # Localhost: automatically set
        ALLOWED_HOSTS="localhost,127.0.1"
    fi
    
    # Additional configuration for backup directory
    BACKUP_DIR="/app/backups"
    echo "Using default backup directory: $BACKUP_DIR"

    echo ""
    # SSL Configuration - only for Production mode
    if [ "$INSTALL_TYPE" = "1" ]; then
        echo "Step 5: SSL Configuration"
        echo "========================="
        read -p "Enable SSL with Certbot (Let's Encrypt)? (y/n): " ENABLE_SSL
        if [[ $ENABLE_SSL =~ ^[Yy]$ ]]; then
            read -p "Enter your domain name (e.g., your-domain.com): " DOMAIN_NAME
            read -p "Enter your email for Let's Encrypt registration: " SSL_EMAIL
            SSL_ENABLED=true
        else
            SSL_ENABLED=false
            DOMAIN_NAME=""
            SSL_EMAIL=""
        fi
    else
        # For Local Network or Localhost, skip SSL configuration
        SSL_ENABLED=false
        DOMAIN_NAME=""
        SSL_EMAIL=""
    fi

    # Generate .env file
    ENV_FILE="$PRODUCTION_DIR/.env"
    cat > "$ENV_FILE" << EOF
    # OK Tools Environment Configuration
    # Generated: $(date)

    # Database Configuration
    POSTGRES_DB=oktools
    POSTGRES_USER=oktools
    POSTGRES_PASSWORD=$DB_PASSWORD
    DATABASE_URL=postgresql://oktools:$DB_PASSWORD@db:5432/oktools

    # Django Configuration
    DJANGO_SETTINGS_MODULE=ok_tools.settings
    DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
    DEBUG=False
    ALLOWED_HOSTS=$ALLOWED_HOSTS

    # Organization Configuration
    ORG_NAME=$ORG_NAME
    ORG_SHORT_NAME=$ORG_SHORT_NAME
    ORG_WEBSITE=$ORG_WEBSITE
    ORG_EMAIL=$ORG_EMAIL
    ORG_PHONE=$ORG_PHONE
    ORG_ADDRESS=$ORG_ADDRESS
    STATE_MEDIA_INSTITUTION=$STATE_MEDIA_INSTITUTION

    # Superuser Configuration
    SUPERUSER_USERNAME=$SUPERUSER_USERNAME
    SUPERUSER_EMAIL=$SUPERUSER_EMAIL
    SUPERUSER_PASSWORD=$SUPERUSER_PASSWORD

    # Application Configuration
    PYTHONPATH=/app
    PYTHONUNBUFFERED=1

    # Gunicorn Configuration
    GUNICORN_WORKERS=4
    GUNICORN_THREADS=2
    GUNICORN_TIMEOUT=120
    GUNICORN_MAX_REQUESTS=1000
    GUNICORN_MAX_REQUESTS_JITTER=100

    # Redis Configuration
    REDIS_URL=redis://redis:6379/0

    # NAS/Network Storage Configuration (optional)
    NAS_PLAYOUT_PATH=/mnt/nas/playout
    NAS_ARCHIVE_PATH=/mnt/nas/archive
    NAS_MOUNT_ENABLED=false

EOF

    # Add SSL configuration only for Production mode
    if [ "$INSTALL_TYPE" = "1" ]; then
        cat >> "$ENV_FILE" << EOF
    # SSL/HTTPS Configuration
    SSL_ENABLED=$SSL_ENABLED
    SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
    SSL_KEY_PATH=/etc/nginx/ssl/key.pem
    DOMAIN_NAME=$DOMAIN_NAME

EOF
    fi

    cat >> "$ENV_FILE" << EOF
    # Logging Configuration
    LOG_LEVEL=info

    # Backup Configuration
    BACKUP_DIR=$BACKUP_DIR
    EOF

EOF

    chmod 600 "$ENV_FILE"
    echo "✓ Created .env file at: $ENV_FILE"

    # Copy necessary files based on installation type
    echo ""
    echo "Copying deployment files..."
    if [ "$INSTALL_TYPE" = "1" ]; then
        # Production: use nginx-enabled compose file and copy nginx files
        cp "$PROJECT_DIR/deployment/docker-compose.production.yml" "$PRODUCTION_DIR/docker-compose.yml"
        cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template"
        cp "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/nginx-entrypoint.sh"
        chmod +x "$PRODUCTION_DIR/nginx-entrypoint.sh"
    else
        # Local Network or Localhost: use compose file without nginx
        cp "$PROJECT_DIR/deployment/docker-compose.production.no-nginx.yml" "$PRODUCTION_DIR/docker-compose.yml"
    fi
    cp "$PROJECT_DIR/deployment/production.Dockerfile" "$PRODUCTION_DIR/Dockerfile"
    cp "$PROJECT_DIR/deployment/entrypoint.production.sh" "$PRODUCTION_DIR/entrypoint.sh"
    chmod +x "$PRODUCTION_DIR/entrypoint.sh"

    if [ "$INSTALL_TYPE" = "1" ]; then
        echo "✓ Copied docker-compose.yml (with nginx)"
        echo "✓ Copied nginx.conf.template"
        echo "✓ Copied nginx-entrypoint.sh"
    else
        echo "✓ Copied docker-compose.yml (without nginx)"
    fi
    echo "✓ Copied Dockerfile"
    echo "✓ Copied entrypoint.sh"
else
    echo "Invalid choice. Exiting."
    exit 1
fi

# Request SSL certificate if enabled (only for Production)
if [ "$INSTALL_TYPE" = "1" ] && [ "$SSL_ENABLED" = true ]; then
    echo ""
    echo "Requesting SSL certificate for $DOMAIN_NAME..."
    docker compose run --rm --entrypoint "\
      certbot certonly --webroot -w /var/www/certbot \
        --email $SSL_EMAIL --agree-tos --no-eff-email \
        -d $DOMAIN_NAME" certbot
    echo "✓ SSL certificate obtained successfully."
fi

# Start containers
echo ""
echo "Starting Docker containers..."
cd "$PRODUCTION_DIR"
docker compose up -d

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo "Production directory: $PRODUCTION_DIR"
echo "Configuration file: $PRODUCTION_DIR/.env"
echo ""
echo "Next steps:"
echo "1. Check container status: docker compose ps"
echo "2. View logs: docker compose logs -f web"
if [ "$INSTALL_TYPE" = "1" ] && [ "$SSL_ENABLED" = true ]; then
    echo "3. Access admin panel: https://$DOMAIN_NAME/admin"
elif [ "$INSTALL_TYPE" = "2" ]; then
    echo "3. Access admin panel: http://$SERVER_IP:8000/admin"
else
    echo "3. Access admin panel: http://localhost:8000/admin"
fi
echo "   Username: $SUPERUSER_USERNAME (or as configured)"
echo "   Password: As configured during setup"
echo ""
echo "To update the application, run: $SCRIPT_DIR/update.sh"
echo "To configure post-deployment settings, run: $SCRIPT_DIR/configure.sh"