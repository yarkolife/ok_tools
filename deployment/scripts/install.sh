#!/bin/bash
set -e

# Interactive installation script for OK Tools production environment with hybrid logic
# Supports both template-based installation and manual configuration

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"
CONFIGS_DIR="$PROJECT_DIR/deployment/configs"

# Color functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

print_header "OK Tools Installation"

# Ensure a stable Docker build context path ../ok_tools
# This allows cloning the repository into arbitrary directory names (e.g. ok_tools_docker)
# while keeping docker-compose build.context fixed at ../ok_tools
PARENT_DIR="$(dirname "$PROJECT_DIR")"
if [ ! -e "$PARENT_DIR/ok_tools" ]; then
    # Best-effort creation; continue even if it fails
    if ln -s "$PROJECT_DIR" "$PARENT_DIR/ok_tools" 2>/dev/null; then
        print_info "Created symlink for Docker build context: $PARENT_DIR/ok_tools -> $PROJECT_DIR"
    else
        print_warning "Could not create symlink $PARENT_DIR/ok_tools (build.context ../ok_tools must exist)"
    fi
fi

# Check if running as root and warn
if [ "$(id -u)" -eq 0 ]; then
    echo ""
    print_warning "═══════════════════════════════════════════════════════════"
    print_warning "  WARNING: Running as root"
    print_warning "═══════════════════════════════════════════════════════════"
    echo ""
    print_warning "Running installation as root is not recommended for security reasons."
    print_info "Best practice: Run as regular user with docker group membership"
    echo ""
    print_info "To set up docker without sudo:"
    echo "  1. Add user to docker group: sudo usermod -aG docker \$USER"
    echo "  2. Log out and log back in (or run: newgrp docker)"
    echo "  3. Verify: docker ps (should work without sudo)"
    echo ""
    read -p "Continue installation as root anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installation cancelled. Please run as regular user."
        exit 1
    fi
    echo ""
fi

# Get current user info for file ownership
CURRENT_USER=$(id -un)
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

# Logging setup - use local directory instead of /var/log
LOG_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")/ok_tools_production/logs"
mkdir -p "$LOG_DIR" 2>/dev/null || true
LOG_FILE="$LOG_DIR/install-$(date +%Y%m%d-%H%M%S).log"

# Create log file and set permissions
if touch "$LOG_FILE" 2>/dev/null; then
    chmod 644 "$LOG_FILE" 2>/dev/null || true
    # Set ownership if not root
    if [ "$(id -u)" -ne 0 ]; then
        chown "$CURRENT_UID:$CURRENT_GID" "$LOG_FILE" 2>/dev/null || true
    fi
    # Redirect output to both terminal and log file
    exec > >(tee -a "$LOG_FILE") 2>&1
    print_info "Log file: $LOG_FILE"
else
    print_warning "Cannot create log file at $LOG_FILE, logging to console only"
    print_info "Logging to console only"
fi

# Helper function to escape special characters for sed
escape_for_sed() {
    echo "$1" | sed -e 's/[]\/$*.^[]/\\&/g'
}

# Function to automatically detect local IP address
detect_local_ip() {
    # Try to get the primary IP address using multiple methods
    LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || \
              ip route get 1.1.1.1 | awk '{print $7}' 2>/dev/null || \
              ipconfig getifaddr en0 2>/dev/null || \
              echo "127.0.0.1")
    
    # Validate that we got a reasonable IP address (not localhost)
    if [[ "$LOCAL_IP" == "127.0.0.1" ]] || [[ -z "$LOCAL_IP" ]]; then
        echo "Warning: Could not detect local IP address. Using 127.0.0.1 as fallback." >&2
        LOCAL_IP="127.0.0.1"
    fi
    
    echo "$LOCAL_IP"
}

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

# Function to validate .env file
validate_env_file() {
    local env_file="$1"
    local errors=0
    local warnings=0
    
    echo ""
    echo "Validating .env file..."
    echo "======================"
    
    # Critical variables that must exist and have values
    local critical_vars=(
        "POSTGRES_PASSWORD"
        "POSTGRES_DB"
        "POSTGRES_USER"
        "DATABASE_URL"
        "DJANGO_SECRET_KEY"
        "ALLOWED_HOSTS"
    )
    
    # Check if file exists
    if [ ! -f "$env_file" ]; then
        echo "❌ ERROR: .env file not found at $env_file"
        return 1
    fi
    
    # Check each critical variable
    for var in "${critical_vars[@]}"; do
        # Extract the value for this variable
        local value=$(grep "^${var}=" "$env_file" | head -1 | cut -d'=' -f2-)
        
        # Check if variable exists
        if [ -z "$value" ]; then
            echo "❌ ERROR: $var is missing or empty"
            errors=$((errors+1))
            continue
        fi
        
        # Check if value is a placeholder
        if [[ "$value" == *"__REPLACE_ME__"* ]]; then
            echo "❌ ERROR: $var still contains __REPLACE_ME__ placeholder"
            errors=$((errors+1))
            continue
        fi
        
        # Check if value contains inline comments
        if [[ "$value" =~ [[:space:]]+# ]]; then
            echo "⚠️  WARNING: $var contains inline comment - value may be malformed"
            warnings=$((warnings+1))
        fi
        
        # Special validation for specific variables
        case "$var" in
            "DATABASE_URL")
                if [[ ! "$value" =~ ^postgresql:// ]]; then
                    echo "❌ ERROR: DATABASE_URL must start with postgresql://"
                    errors=$((errors+1))
                fi
                ;;
            "ALLOWED_HOSTS")
                if [[ -z "$value" ]] || [[ "$value" == "localhost" ]]; then
                    echo "⚠️  WARNING: ALLOWED_HOSTS should include your domain/IP"
                    warnings=$((warnings+1))
                fi
                ;;
        esac
        
        echo "✓ $var: OK"
    done
    
    # Check for concatenated lines (common issue)
    local concatenated=$(grep -E '^[A-Z_]+=.*[A-Z_]+=' "$env_file" | wc -l | tr -d ' ')
    if [ "$concatenated" -gt 0 ]; then
        echo "❌ ERROR: Found $concatenated line(s) with concatenated variables"
        echo "   This usually means line breaks are missing in the .env file"
        errors=$((errors+1))
        
        # Show problematic lines
        echo "   Problematic lines:"
        grep -E '^[A-Z_]+=.*[A-Z_]+=' "$env_file" | head -5 | sed 's/^/   /'
    fi
    
    # Summary
    echo ""
    echo "Validation Summary:"
    echo "==================="
    echo "Errors: $errors"
    echo "Warnings: $warnings"
    
    if [ $errors -gt 0 ]; then
        echo ""
        echo "❌ Validation FAILED - please fix errors before proceeding"
        return 1
    elif [ $warnings -gt 0 ]; then
        echo ""
        echo "⚠️  Validation passed with warnings - review before production use"
        return 0
    else
        echo ""
        echo "✅ Validation PASSED - .env file is properly configured"
        return 0
    fi
}

# Function to prompt for secrets based on template
prompt_secrets() {
    local template="$1"
    local output_file="$2"
    local secrets_file="${output_file%.env}_secrets.txt"
    
    echo "" >&2
    echo "Processing template: $(basename "$template")" >&2
    echo "Please enter values (press Enter to auto-generate):" >&2
    echo "====================================================" >&2
    
    # Copy template to output file
    cp "$template" "$output_file"
    
    # Create secrets file
    echo "# Generated Secrets - $(date)" > "$secrets_file"
    echo "# KEEP THIS FILE SECURE!" >> "$secrets_file"
    echo "" >> "$secrets_file"
    
    # POSTGRES_PASSWORD
    echo "" >&2
    echo -n "POSTGRES_PASSWORD (or press Enter to generate): " >&2
    read -s postgres_pass
    echo "" >&2
    if [ -z "$postgres_pass" ]; then
        postgres_pass=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
        echo "Generated POSTGRES_PASSWORD: $postgres_pass" >&2
        echo "POSTGRES_PASSWORD=$postgres_pass" >> "$secrets_file"
    fi
    # POSTGRES_PASSWORD
    escaped_postgres_pass=$(escape_for_sed "$postgres_pass")
    sed -i.bak -E "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$escaped_postgres_pass|" "$output_file"

    # DATABASE_URL (единый формат)
    sed -i.bak -E "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://oktools:$escaped_postgres_pass@db:5432/oktools|" "$output_file"
    
    # DJANGO_SECRET_KEY
    echo -n "DJANGO_SECRET_KEY (or press Enter to generate): " >&2
    read -s django_key
    echo "" >&2
    if [ -z "$django_key" ]; then
        django_key=$(openssl rand -base64 50 | tr -d '=+/\n' | cut -c1-50)
        echo "Generated DJANGO_SECRET_KEY: $django_key" >&2
        echo "DJANGO_SECRET_KEY=$django_key" >> "$secrets_file"
    fi
    # DJANGO_SECRET_KEY
    escaped_django_key=$(escape_for_sed "$django_key")
    sed -i.bak -E "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$escaped_django_key|" "$output_file"
    
    # ALLOWED_HOSTS - keep template value if it already contains a domain,
    # otherwise fall back to local network defaults
    if [ "$INSTALL_TYPE" = "2" ]; then
        # Local Network: detect IP and merge with existing template value (if any)
        existing_hosts=$(grep '^ALLOWED_HOSTS=' "$output_file" | head -1 | cut -d'=' -f2-)
        LOCAL_IP=$(detect_local_ip)
        echo "Detected local IP: $LOCAL_IP" >&2

        if [ -z "$existing_hosts" ] || [[ "$existing_hosts" == *"__REPLACE_ME__"* ]]; then
            # No meaningful value in template → use default local network pattern
        allowed_hosts="localhost,127.0.0.1,$LOCAL_IP"
        echo "Using ALLOWED_HOSTS: $allowed_hosts" >&2
    else
            # Keep template value (e.g. portal.okmq.de) and only append local IP if missing
            if [[ "$existing_hosts" == *"$LOCAL_IP"* ]]; then
                allowed_hosts="$existing_hosts"
            else
                allowed_hosts="$existing_hosts,$LOCAL_IP"
            fi
            echo "Keeping template ALLOWED_HOSTS and adding local IP: $allowed_hosts" >&2
        fi
    else
        # Production / Localhost: prompt as before, template is just a default
        echo -n "ALLOWED_HOSTS (comma-separated, or press Enter for localhost): " >&2
        read allowed_hosts
        if [ -z "$allowed_hosts" ]; then
            allowed_hosts="localhost,127.0.0.1"
            echo "Using default: $allowed_hosts" >&2
        fi
    fi
    sed -i.bak -E "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$allowed_hosts|" "$output_file"
    
    # SUPERUSER_PASSWORD
    echo -n "SUPERUSER_PASSWORD (or press Enter to generate): " >&2
    read -s superuser_pass
    echo "" >&2
    if [ -z "$superuser_pass" ]; then
        superuser_pass=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
        echo "Generated SUPERUSER_PASSWORD: $superuser_pass" >&2
        echo "SUPERUSER_PASSWORD=$superuser_pass" >> "$secrets_file"
    fi
    # SUPERUSER_PASSWORD
    escaped_superuser_pass=$(escape_for_sed "$superuser_pass")
    sed -i.bak -E "s|^SUPERUSER_PASSWORD=.*|SUPERUSER_PASSWORD=$escaped_superuser_pass|" "$output_file"
    
    # EMAIL_HOST_PASSWORD
    echo -n "EMAIL_HOST_PASSWORD (or press Enter to generate): " >&2
    read -s email_pass
    echo "" >&2
    if [ -z "$email_pass" ]; then
        email_pass=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
        echo "Generated EMAIL_HOST_PASSWORD: $email_pass" >&2
        echo "EMAIL_HOST_PASSWORD=$email_pass" >> "$secrets_file"
    fi
    # EMAIL_HOST_PASSWORD
    escaped_email_pass=$(escape_for_sed "$email_pass")
    sed -i.bak -E "s|^EMAIL_HOST_PASSWORD=.*|EMAIL_HOST_PASSWORD=$escaped_email_pass|" "$output_file"
    
    # Remove backup files
    rm -f "$output_file.bak"
    
    chmod 600 "$secrets_file"
    echo "" >&2
    echo "✓ Configuration completed" >&2
    echo "✓ Secrets saved to: $secrets_file" >&2
    echo "" >&2
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

# Set ownership of production directory to current user (if not root)
if [ "$(id -u)" -ne 0 ]; then
    chown -R "$CURRENT_UID:$CURRENT_GID" "$PRODUCTION_DIR" 2>/dev/null || true
    print_info "Set ownership of $PRODUCTION_DIR to $CURRENT_USER"
fi

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
        # Auto-detect IP for Local Network setup
        LOCAL_IP=$(detect_local_ip)
        echo "Detected local IP: $LOCAL_IP"
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
        
        # Prompt for secrets and create .env file directly
        ENV_FILE="$PRODUCTION_DIR/.env"
        prompt_secrets "$TEMPLATE_FILE" "$ENV_FILE"
        if [ "$INSTALL_TYPE" = "1" ] && ! grep -q "^DOMAIN_NAME=" "$ENV_FILE"; then
            ALLOWED_VAL=$(grep '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d'=' -f2-)
            DOMAIN_CANDIDATE=$(echo "$ALLOWED_VAL" | tr ',' '\n' | grep -v -E '^(localhost|127\\.0\\.0\\.1)$' | head -1)
            DOMAIN_CANDIDATE=${DOMAIN_CANDIDATE:-localhost}
            echo "DOMAIN_NAME=$DOMAIN_CANDIDATE" >> "$ENV_FILE"
            echo "✓ Added DOMAIN_NAME=$DOMAIN_CANDIDATE to .env"
        fi
        chmod 600 "$ENV_FILE"
        # Set ownership if not root
        if [ "$(id -u)" -ne 0 ]; then
            chown "$CURRENT_UID:$CURRENT_GID" "$ENV_FILE" 2>/dev/null || true
        fi
        
        echo "✓ Created .env file at: $ENV_FILE"
        
        # Validate the generated .env file
        if ! validate_env_file "$PRODUCTION_DIR/.env"; then
            echo ""
            echo "⚠️  .env file validation failed. Please review and fix errors."
            read -p "Do you want to continue anyway? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Installation cancelled."
                exit 1
            fi
        fi
        
        # Copy logo and favicon to project static directory
        echo ""
        echo "Copying logo and favicon files..."
        if [ -d "$PROJECT_DIR/deployment/img" ]; then
            mkdir -p "$PROJECT_DIR/ok_tools/static/img"
            if [ -f "$PROJECT_DIR/deployment/img/logo.png" ]; then
                cp "$PROJECT_DIR/deployment/img/logo.png" "$PROJECT_DIR/ok_tools/static/img/logo.png"
                echo "✓ Copied logo.png"
            else
                echo "⚠️  Warning: logo.png not found in deployment/img/"
            fi
            if [ -f "$PROJECT_DIR/deployment/img/favicon.ico" ]; then
                cp "$PROJECT_DIR/deployment/img/favicon.ico" "$PROJECT_DIR/ok_tools/static/img/favicon.ico"
                echo "✓ Copied favicon.ico"
            else
                echo "⚠️  Warning: favicon.ico not found in deployment/img/"
            fi
        else
            echo "⚠️  Warning: deployment/img/ directory not found. Please copy logo.png and favicon.ico to ok_tools/static/img/ manually."
        fi
        
        # Copy necessary files based on installation type
        echo ""
        echo "Copying deployment files..."
        if [ "$INSTALL_TYPE" = "1" ]; then
            # Production: use nginx-enabled compose file and copy nginx files
            cp "$PROJECT_DIR/deployment/docker-compose.production.yml" "$PRODUCTION_DIR/docker-compose.yml"
            if [ -f "$PRODUCTION_DIR/nginx.conf.template" ]; then
                TS=$(date +%Y%m%d-%H%M%S)
                cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template.new.$TS"
                echo "⚠️  Existing nginx.conf.template kept, new version saved as nginx.conf.template.new.$TS"
            else
                cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template"
                echo "✓ Copied nginx.conf.template"
            fi
            mkdir -p "$PRODUCTION_DIR/deployment"
            cp "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh"
            chmod +x "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh"
        else
            # Local Network or Localhost: use compose file without nginx
            cp "$PROJECT_DIR/deployment/docker-compose.production.no-nginx.yml" "$PRODUCTION_DIR/docker-compose.yml"
        fi
        
        if [ "$INSTALL_TYPE" = "1" ]; then
            echo "✓ Copied docker-compose.yml (with nginx)"
            echo "✓ Copied nginx entrypoint script"
        else
            echo "✓ Copied docker-compose.yml (without nginx)"
        fi
        
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
        # Local Network: auto-detect IP and create comprehensive ALLOWED_HOSTS
        LOCAL_IP=$(detect_local_ip)
        echo "Detected local IP: $LOCAL_IP"
        ALLOWED_HOSTS="localhost,127.0.0.1,$LOCAL_IP"
        echo "Using ALLOWED_HOSTS: $ALLOWED_HOSTS"
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

    echo ""
    echo "Step 5: Extended Configuration"
    echo "==============================="
    read -p "Django log level (INFO/DEBUG/WARNING/ERROR) [INFO]: " DJANGO_LOG_LEVEL
    DJANGO_LOG_LEVEL=${DJANGO_LOG_LEVEL:-INFO}

    read -p "Email host (SMTP server) [smtp.your-provider.de]: " EMAIL_HOST
    EMAIL_HOST=${EMAIL_HOST:-smtp.your-provider.de}

    read -p "Email port [587]: " EMAIL_PORT
    EMAIL_PORT=${EMAIL_PORT:-587}

    read -p "Organization owner name: " ORG_ORGANIZATION_OWNER

    read -p "Broadcast start time (HH:MM) [18:00]: " ORG_BROADCAST_START
    ORG_BROADCAST_START=${ORG_BROADCAST_START:-18:00}

    read -p "Broadcast end time (HH:MM) [19:45]: " ORG_BROADCAST_END
    ORG_BROADCAST_END=${ORG_BROADCAST_END:-19:45}

    # Generate .env file using echo commands to avoid heredoc issues
    ENV_FILE="$PRODUCTION_DIR/.env"
    
    # Create header
    echo "# OK Tools Environment Configuration" > "$ENV_FILE"
    echo "# Generated: $(date)" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Database Configuration
    echo "# Database Configuration" >> "$ENV_FILE"
    echo "POSTGRES_DB=oktools" >> "$ENV_FILE"
    echo "POSTGRES_USER=oktools" >> "$ENV_FILE"
    echo "POSTGRES_PASSWORD=$DB_PASSWORD" >> "$ENV_FILE"
    echo "DATABASE_URL=postgresql://oktools:$DB_PASSWORD@db:5432/oktools" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Django Configuration
    echo "# Django Configuration" >> "$ENV_FILE"
    echo "DJANGO_SETTINGS_MODULE=ok_tools.settings" >> "$ENV_FILE"
    echo "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" >> "$ENV_FILE"
    echo "DEBUG=False" >> "$ENV_FILE"
    echo "ALLOWED_HOSTS=$ALLOWED_HOSTS" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Organization Configuration
    echo "# Organization Configuration" >> "$ENV_FILE"
    echo "ORG_NAME=$ORG_NAME" >> "$ENV_FILE"
    echo "ORG_SHORT_NAME=$ORG_SHORT_NAME" >> "$ENV_FILE"
    echo "ORG_WEBSITE=$ORG_WEBSITE" >> "$ENV_FILE"
    echo "ORG_EMAIL=$ORG_EMAIL" >> "$ENV_FILE"
    echo "ORG_PHONE=$ORG_PHONE" >> "$ENV_FILE"
    # Handle ORG_ADDRESS with proper escaping
    echo "ORG_ADDRESS=$ORG_ADDRESS" | sed 's/\\n/\n/g' >> "$ENV_FILE"
    echo "STATE_MEDIA_INSTITUTION=$STATE_MEDIA_INSTITUTION" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Superuser Configuration
    echo "# Superuser Configuration" >> "$ENV_FILE"
    echo "SUPERUSER_USERNAME=$SUPERUSER_USERNAME" >> "$ENV_FILE"
    echo "SUPERUSER_EMAIL=$SUPERUSER_EMAIL" >> "$ENV_FILE"
    echo "SUPERUSER_PASSWORD=$SUPERUSER_PASSWORD" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Application Configuration
    echo "# Application Configuration" >> "$ENV_FILE"
    echo "PYTHONPATH=/app" >> "$ENV_FILE"
    echo "PYTHONUNBUFFERED=1" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Gunicorn Configuration
    echo "# Gunicorn Configuration" >> "$ENV_FILE"
    echo "GUNICORN_WORKERS=4" >> "$ENV_FILE"
    echo "GUNICORN_THREADS=2" >> "$ENV_FILE"
    echo "GUNICORN_TIMEOUT=120" >> "$ENV_FILE"
    echo "GUNICORN_MAX_REQUESTS=1000" >> "$ENV_FILE"
    echo "GUNICORN_MAX_REQUESTS_JITTER=100" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Redis Configuration
    echo "# Redis Configuration" >> "$ENV_FILE"
    echo "REDIS_URL=redis://redis:6379/0" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # NAS/Network Storage Configuration
    echo "# NAS/Network Storage Configuration (optional)" >> "$ENV_FILE"
    echo "NAS_PLAYOUT_PATH=/mnt/nas/playout" >> "$ENV_FILE"
    echo "NAS_ARCHIVE_PATH=/mnt/nas/archive" >> "$ENV_FILE"
    echo "NAS_MOUNT_ENABLED=false" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Add SSL configuration only for Production mode
    if [ "$INSTALL_TYPE" = "1" ]; then
        echo "# SSL/HTTPS Configuration" >> "$ENV_FILE"
        echo "SSL_ENABLED=$SSL_ENABLED" >> "$ENV_FILE"
        echo "SSL_CERT_PATH=/etc/nginx/ssl/cert.pem" >> "$ENV_FILE"
        echo "SSL_KEY_PATH=/etc/nginx/ssl/key.pem" >> "$ENV_FILE"
        echo "DOMAIN_NAME=$DOMAIN_NAME" >> "$ENV_FILE"
        echo "" >> "$ENV_FILE"
    fi

    # Logging and Backup Configuration
    echo "# Logging Configuration" >> "$ENV_FILE"
    echo "LOG_LEVEL=info" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    echo "# Backup Configuration" >> "$ENV_FILE"
    echo "BACKUP_DIR=$BACKUP_DIR" >> "$ENV_FILE"
    echo "# Set Docker Compose project name" >> "$ENV_FILE"
    echo "COMPOSE_PROJECT_NAME=oktools" >> "$ENV_FILE"
    
    # Django Extended Configuration
    echo "# Django Extended Configuration" >> "$ENV_FILE"
    echo "DJANGO_LOG_LEVEL=$DJANGO_LOG_LEVEL" >> "$ENV_FILE"
    echo "DJANGO_LANGUAGE=de-de" >> "$ENV_FILE"
    echo "DJANGO_TIMEZONE=Europe/Berlin" >> "$ENV_FILE"
    echo "DJANGO_STATIC_ROOT=/app/staticfiles/" >> "$ENV_FILE"
    echo "DJANGO_MEDIA_ROOT=/app/media/" >> "$ENV_FILE"
    echo "DJANGO_USE_SECURE_SETTINGS=True" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Email Configuration
    echo "# Email Configuration" >> "$ENV_FILE"
    echo "EMAIL_HOST=$EMAIL_HOST" >> "$ENV_FILE"
    echo "EMAIL_PORT=$EMAIL_PORT" >> "$ENV_FILE"
    echo "EMAIL_USE_TLS=True" >> "$ENV_FILE"
    echo "EMAIL_HOST_USER=noreply@your-domain.com" >> "$ENV_FILE"
    echo "EMAIL_HOST_PASSWORD=__REPLACE_ME__" >> "$ENV_FILE"
    echo "DEFAULT_FROM_EMAIL=noreply@your-domain.com" >> "$ENV_FILE"
    echo "MAIL_DEV_SETTINGS=False" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Organization Extended
    echo "# Organization Extended" >> "$ENV_FILE"
    echo "ORG_ORGANIZATION_OWNER=$ORG_ORGANIZATION_OWNER" >> "$ENV_FILE"
    echo "ORG_BROADCAST_START=$ORG_BROADCAST_START" >> "$ENV_FILE"
    echo "ORG_BROADCAST_END=$ORG_BROADCAST_END" >> "$ENV_FILE"
    echo "ORG_PEERTUBE_CHANNEL=" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # NAS Storage Extended
    echo "# NAS Storage Extended" >> "$ENV_FILE"
    echo "NAS_ARCHIVE_UNC_PATH=" >> "$ENV_FILE"
    echo "NAS_PLAYOUT_UNC_PATH=" >> "$ENV_FILE"
    echo "MEDIA_AUTO_SCAN=False" >> "$ENV_FILE"
    echo "MEDIA_AUTO_COPY_ON_SCHEDULE=True" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Logging
    echo "# Logging" >> "$ENV_FILE"
    echo "LOGGING_FILE=/app/logs/oktools.log" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Bootstrap
    echo "# Bootstrap" >> "$ENV_FILE"
    echo "BOOTSTRAP_VERSION=5.3.3" >> "$ENV_FILE"
    echo "BOOTSTRAP_ICONS_VERSION=1.11.0" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # API Configuration
    echo "# API Configuration" >> "$ENV_FILE"
    echo "API_PAGE_SIZE=20" >> "$ENV_FILE"
    echo "API_ANON_RATE_LIMIT=100/hour" >> "$ENV_FILE"
    echo "API_USER_RATE_LIMIT=1000/hour" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Security
    echo "# Security" >> "$ENV_FILE"
    echo "SECURITY_SESSION_TIMEOUT=1200" >> "$ENV_FILE"
    echo "SECURITY_PASSWORD_MIN_LENGTH=8" >> "$ENV_FILE"
    echo "SECURITY_CSRF_COOKIE_AGE=31449600" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Video
    echo "# Video" >> "$ENV_FILE"
    echo "VIDEO_SUPPORTED_FORMATS=mp4,mov,mpeg,mpg" >> "$ENV_FILE"
    echo "VIDEO_SCREEN_BOARD_DURATION=20" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # I18n
    echo "# I18n" >> "$ENV_FILE"
    echo "I18N_DEFAULT_LANGUAGE=de" >> "$ENV_FILE"
    echo "I18N_SUPPORTED_LANGUAGES=de,en" >> "$ENV_FILE"
    echo "I18N_LOCALE_PATHS=ok_tools/locale" >> "$ENV_FILE"
    echo "I18N_PHONE_REGION=DE" >> "$ENV_FILE"
    echo "I18N_DATE_FORMAT=%d.%m.%Y" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Static Files
    echo "# Static Files" >> "$ENV_FILE"
    echo "STATIC_STORAGE_BACKEND=whitenoise.storage.CompressedManifestStaticFilesStorage" >> "$ENV_FILE"
    echo "STATIC_URL_PREFIX=static/" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Cache
    echo "# Cache" >> "$ENV_FILE"
    echo "CACHE_BACKEND=django.core.cache.backends.locmem.LocMemCache" >> "$ENV_FILE"
    echo "CACHE_TIMEOUT=300" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Celery Extended
    echo "# Celery Extended" >> "$ENV_FILE"
    echo "CELERY_BROKER_URL=redis://redis:6379/0" >> "$ENV_FILE"
    echo "CELERY_RESULT_BACKEND=redis://redis:6379/0" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Celery Beat Schedules
    echo "# Celery Beat Schedules" >> "$ENV_FILE"
    echo "CELERY_BEAT_EXPIRE_RENTALS=*/30 * * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_CLEANUP_BACKUPS=0 2 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_BACKUP_DB=0 3 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_AUTO_SCAN=0 */2 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_LINK_LICENSES=0 4 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_SYNC_VIDEOS=0 5 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_UPDATE_METADATA=0 1 1 * *" >> "$ENV_FILE"

        if [ "$INSTALL_TYPE" = "1" ] && ! grep -q "^DOMAIN_NAME=" "$ENV_FILE"; then
            ALLOWED_VAL=$(grep '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d'=' -f2-)
            DOMAIN_CANDIDATE=$(echo "$ALLOWED_VAL" | tr ',' '\n' | grep -v -E '^(localhost|127\\.0\\.0\\.1)$' | head -1)
            DOMAIN_CANDIDATE=${DOMAIN_CANDIDATE:-localhost}
            echo "DOMAIN_NAME=$DOMAIN_CANDIDATE" >> "$ENV_FILE"
            echo "✓ Added DOMAIN_NAME=$DOMAIN_CANDIDATE to .env"
        fi
        chmod 600 "$ENV_FILE"
        # Set ownership if not root
        if [ "$(id -u)" -ne 0 ]; then
            chown "$CURRENT_UID:$CURRENT_GID" "$ENV_FILE" 2>/dev/null || true
        fi
        echo "✓ Created .env file at: $ENV_FILE"

    # Validate the generated .env file
    if ! validate_env_file "$ENV_FILE"; then
        echo ""
        echo "⚠️  .env file validation failed. Please review and fix errors."
        read -p "Do you want to continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            exit 1
        fi
    fi

    # Copy logo and favicon to project static directory
    echo ""
    echo "Copying logo and favicon files..."
    if [ -d "$PROJECT_DIR/deployment/img" ]; then
        mkdir -p "$PROJECT_DIR/ok_tools/static/img"
        if [ -f "$PROJECT_DIR/deployment/img/logo.png" ]; then
            cp "$PROJECT_DIR/deployment/img/logo.png" "$PROJECT_DIR/ok_tools/static/img/logo.png"
            echo "✓ Copied logo.png"
        else
            echo "⚠️  Warning: logo.png not found in deployment/img/"
        fi
        if [ -f "$PROJECT_DIR/deployment/img/favicon.ico" ]; then
            cp "$PROJECT_DIR/deployment/img/favicon.ico" "$PROJECT_DIR/ok_tools/static/img/favicon.ico"
            echo "✓ Copied favicon.ico"
        else
            echo "⚠️  Warning: favicon.ico not found in deployment/img/"
        fi
    else
        echo "⚠️  Warning: deployment/img/ directory not found. Please copy logo.png and favicon.ico to ok_tools/static/img/ manually."
    fi
    
    # Copy necessary files based on installation type
    echo ""
    echo "Copying deployment files..."
    if [ "$INSTALL_TYPE" = "1" ]; then
        # Production: use nginx-enabled compose file and copy nginx files
        cp "$PROJECT_DIR/deployment/docker-compose.production.yml" "$PRODUCTION_DIR/docker-compose.yml"
        if [ -f "$PRODUCTION_DIR/nginx.conf.template" ]; then
            TS=$(date +%Y%m%d-%H%M%S)
            cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template.new.$TS"
            echo "⚠️  Existing nginx.conf.template kept, new version saved as nginx.conf.template.new.$TS"
        else
            cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template"
            echo "✓ Copied nginx.conf.template"
        fi
        cp "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/nginx-entrypoint.sh"
        chmod +x "$PRODUCTION_DIR/nginx-entrypoint.sh"
        echo "✓ Copied docker-compose.yml (with nginx)"
        echo "✓ Copied nginx-entrypoint.sh"
    else
        # Local Network or Localhost: use compose file without nginx
        cp "$PROJECT_DIR/deployment/docker-compose.production.no-nginx.yml" "$PRODUCTION_DIR/docker-compose.yml"
        echo "✓ Copied docker-compose.yml (without nginx)"
    fi
    
    # Generate docker-compose.override.yml from .env variables
    print_info "Generating docker-compose.override.yml from .env..."
    if [ -f "$PROJECT_DIR/deployment/scripts/generate-override.sh" ]; then
        cd "$PRODUCTION_DIR"
        if bash "$PROJECT_DIR/deployment/scripts/generate-override.sh"; then
            print_success "docker-compose.override.yml generated successfully"
        else
            print_warning "Failed to generate docker-compose.override.yml (this is optional)"
        fi
        cd "$PROJECT_DIR"
    else
        print_warning "generate-override.sh not found - skipping override generation"
    fi
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

# Ensure all required directories exist with proper permissions
echo ""
echo "Creating required directories..."
mkdir -p "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
chmod 755 "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media"
chmod 755 "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"

# Set ownership of all production files to current user (if not root)
if [ "$(id -u)" -ne 0 ]; then
    chown -R "$CURRENT_UID:$CURRENT_GID" "$PRODUCTION_DIR" 2>/dev/null || true
    print_info "Set ownership of production files to $CURRENT_USER"
fi

echo "✓ Directories created and permissions set"

# Start containers
echo ""
echo "Starting Docker containers..."
cd "$PRODUCTION_DIR" || { echo "Failed to change directory to $PRODUCTION_DIR"; exit 1; }
echo "Current directory: $(pwd)"
echo "Checking files..."
ls -la docker-compose.yml
echo ""
docker compose --project-directory . up -d --build

# Wait for containers to be ready
echo "Waiting for containers to be ready..."
sleep 10

# Run migrations
echo "Running database migrations..."
docker compose exec -T web python manage.py migrate --noinput

# Compile translation messages
echo "Compiling translation messages..."
if ! docker compose exec -T web python manage.py compilemessages; then
    echo "Warning: Failed to compile translation messages, continuing..."
else
    echo "Translation messages compiled successfully"
fi

# Collect static files
print_info "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput
print_success "Static files collected"

# Health check
print_info "Checking web service availability on port 8010..."
for i in {1..30}; do
    if curl -s http://localhost:8010/health > /dev/null 2>&1; then
        print_success "Web service is available"
        break
    elif [ $i -eq 30 ]; then
        print_warning "Web service health check timeout (may still be starting)"
    else
        sleep 2
    fi
done

# Cleanup unused Docker images
print_info "Cleaning up unused Docker images..."
docker image prune -f > /dev/null 2>&1
print_success "Cleanup completed"

# Create helper scripts
print_info "Creating management scripts..."
cat > "$PRODUCTION_DIR/stop.sh" <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
docker compose down
echo "✓ Services stopped"
EOF

cat > "$PRODUCTION_DIR/restart.sh" <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
docker compose restart
echo "✓ Services restarted"
EOF

cat > "$PRODUCTION_DIR/logs.sh" <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
docker compose logs -f "${1:-web}"
EOF

cat > "$PRODUCTION_DIR/status.sh" <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
docker compose ps
EOF

# Create local update.sh script that pulls from git and calls main update script
# Use the actual PROJECT_DIR path that was computed during installation
cat > "$PRODUCTION_DIR/update.sh" <<EOF
#!/bin/bash
# Local update wrapper script for OK Tools production environment
# This script updates the code from git and then calls the main update script

set -e

# Get script directory and project directory
PRODUCTION_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
PROJECT_DIR="$PROJECT_DIR"

# Try to find project directory if default path doesn't exist
if [ ! -d "\$PROJECT_DIR" ] || [ ! -f "\$PROJECT_DIR/deployment/scripts/update.sh" ]; then
    # Try to find project directory by looking for deployment/scripts/update.sh
    # Search in parent directory and common locations
    PARENT_DIR="\$(dirname "\$PRODUCTION_DIR")"
    for possible_dir in "\$PARENT_DIR"/*; do
        if [ -d "\$possible_dir" ] && [ -f "\$possible_dir/deployment/scripts/update.sh" ]; then
            PROJECT_DIR="\$possible_dir"
            break
        fi
    done
fi

# Check if project directory exists
if [ ! -d "\$PROJECT_DIR" ]; then
    echo "Error: Project directory not found. Expected at: $PROJECT_DIR"
    echo "Please check your installation or set PROJECT_DIR environment variable."
    exit 1
fi

# Check if main update script exists
MAIN_UPDATE_SCRIPT="\$PROJECT_DIR/deployment/scripts/update.sh"
if [ ! -f "\$MAIN_UPDATE_SCRIPT" ]; then
    echo "Error: Main update script not found at \$MAIN_UPDATE_SCRIPT"
    exit 1
fi

# Create backup archive of PROJECT_DIR before updating
echo "Creating backup archive of project directory before update..."
BACKUP_ARCHIVE_DIR="\$PRODUCTION_DIR/backups/code_backups"
mkdir -p "\$BACKUP_ARCHIVE_DIR"
TIMESTAMP=\$(date +%Y%m%d-%H%M%S)
ARCHIVE_NAME="code_backup_\$TIMESTAMP.tar.gz"
ARCHIVE_PATH="\$BACKUP_ARCHIVE_DIR/\$ARCHIVE_NAME"

# Create archive excluding unnecessary files
cd "\$(dirname "\$PROJECT_DIR")"
PROJECT_BASENAME=\$(basename "\$PROJECT_DIR")
tar -czf "\$ARCHIVE_PATH" \\
    --exclude="\$PROJECT_BASENAME/venv" \\
    --exclude="\$PROJECT_BASENAME/__pycache__" \\
    --exclude="\$PROJECT_BASENAME/**/__pycache__" \\
    --exclude="\$PROJECT_BASENAME/.git" \\
    --exclude="\$PROJECT_BASENAME/node_modules" \\
    --exclude="\$PROJECT_BASENAME/.pytest_cache" \\
    --exclude="\$PROJECT_BASENAME/.mypy_cache" \\
    --exclude="\$PROJECT_BASENAME/*.pyc" \\
    --exclude="\$PROJECT_BASENAME/**/*.pyc" \\
    --exclude="\$PROJECT_BASENAME/staticfiles" \\
    --exclude="\$PROJECT_BASENAME/media" \\
    --exclude="\$PROJECT_BASENAME/logs" \\
    "\$PROJECT_BASENAME" 2>/dev/null || {
    echo "Warning: Failed to create backup archive, continuing anyway..."
}

if [ -f "\$ARCHIVE_PATH" ]; then
    ARCHIVE_SIZE=\$(du -h "\$ARCHIVE_PATH" | cut -f1)
    echo "✓ Backup archive created: \$ARCHIVE_NAME (\$ARCHIVE_SIZE)"
    
    # Rotate old backups - keep only last 5
    OLD_BACKUPS=\$(ls -1t "\$BACKUP_ARCHIVE_DIR"/code_backup_*.tar.gz 2>/dev/null | tail -n +6)
    if [ -n "\$OLD_BACKUPS" ]; then
        echo "\$OLD_BACKUPS" | xargs rm -f 2>/dev/null || true
        echo "✓ Removed old backup archives (kept 5 most recent)"
    fi
else
    echo "⚠ Warning: Backup archive was not created"
fi

# Change to project directory and pull latest code
echo "Updating code from git repository..."
cd "\$PROJECT_DIR"

# Check if this is a git repository and handle errors
if [ ! -d ".git" ]; then
    echo "⚠ Warning: Not a git repository - skipping git pull"
    echo "To enable updates from git, initialize repository: git init && git remote add origin <url>"
elif ! git pull 2>&1; then
    GIT_PULL_EXIT=\$?
    echo "⚠ Warning: git pull failed (exit code: \$GIT_PULL_EXIT)"
    echo "Possible reasons:"
    echo "  - No internet connection"
    echo "  - Git remote not configured"
    echo "  - Merge conflicts (resolve manually)"
    echo "  - Authentication required"
    echo ""
    echo "Continuing update without git pull - using current code"
else
    echo "✓ Code updated from repository"
fi

# Call the main update script with flag indicating it was called from local script
echo "Running update script..."
export LOCAL_UPDATE_CALLED=1
exec "\$MAIN_UPDATE_SCRIPT"
EOF

chmod +x "$PRODUCTION_DIR"/*.sh 2>/dev/null
print_success "Management scripts created"

echo ""
print_header "Installation Complete!"
echo "Production directory: $PRODUCTION_DIR"
echo "Configuration file: $PRODUCTION_DIR/.env"
echo ""
echo "Next steps:"
echo "1. Check container status: docker compose ps"
echo "2. View logs: docker compose logs -f web"
if [ "$INSTALL_TYPE" = "1" ] && [ "$SSL_ENABLED" = true ]; then
    echo "3. Access admin panel: https://$DOMAIN_NAME/admin"
elif [ "$INSTALL_TYPE" = "2" ]; then
    # For Local Network, use the detected IP and external port 8010
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP=$(detect_local_ip)
    fi
    echo "3. Access admin panel: http://$LOCAL_IP:8010/admin"
else
    echo "3. Access admin panel: http://localhost:8010/admin"
fi
echo "   Username: $SUPERUSER_USERNAME (or as configured)"
echo "   Password: As configured during setup"
echo ""
echo "To update application, run: $PRODUCTION_DIR/update.sh"
echo "To configure post-deployment settings, run: $SCRIPT_DIR/configure.sh"
# Run post-installation diagnostics
print_header "Running Post-Installation Diagnostics"

# 1. Check container status
print_info "1. Checking container status..."
if ! docker compose ps --format "table {{.Service}}\t{{.Status}}"; then
    print_error "Failed to get container status. Is Docker running?"
    exit 1
fi

UNHEALTHY_CONTAINERS=$(docker compose ps --format "table {{.Service}}\t{{.Status}}" | grep -i "unhealthy" | awk '{print $1}' | grep -v "SERVICE")
if [ -n "$UNHEALTHY_CONTAINERS" ]; then
    print_warning "The following containers are unhealthy:"
    echo "$UNHEALTHY_CONTAINERS"
    print_info "Check logs with: docker compose logs -f <service_name>"
else
    print_success "All containers are running and healthy"
fi

# 2. Check web service logs for errors
print_info "2. Checking web service logs for recent errors..."
ERROR_LINES=$(docker compose logs --tail=50 web 2>&1 | grep -iE "(error|exception|traceback)" | grep -vE "(ERROR|WARNING|INFO|DEBUG)\s*\:" | grep -vE "No valid legacy config|Validation|migration|Your models.*have changes")
if [ -n "$ERROR_LINES" ]; then
    print_warning "Potential errors found in web service logs:"
    echo "$ERROR_LINES" | head -5 | sed 's/^/  /'
    print_info "Please review the logs above carefully"
else
    print_success "No critical errors found in recent web service logs"
fi

print_header "Diagnostics Complete"