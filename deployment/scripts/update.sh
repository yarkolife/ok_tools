#!/bin/bash
set -e

# Update script for OK Tools production environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

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

print_header "OK Tools Production Update"

# Ensure a stable Docker build context path ../ok_tools
# This allows cloning the repository into arbitrary directory names (e.g. ok_tools_docker)
# while keeping docker-compose build.context fixed at ../ok_tools
PARENT_DIR="$(dirname "$PROJECT_DIR")"
if [ ! -e "$PARENT_DIR/ok_tools" ]; then
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
    print_warning "Running update as root is not recommended for security reasons."
    print_info "Best practice: Run as regular user with docker group membership"
    echo ""
    print_info "If you need to fix file permissions, run:"
    echo "  sudo chown -R \$USER:\$USER $PRODUCTION_DIR"
    echo ""
    read -p "Continue update as root anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Update cancelled. Please run as regular user."
        exit 1
    fi
    echo ""
fi

# Get current user info for file ownership
# If running with sudo, try to get the original user from SUDO_USER
if [ -n "${SUDO_USER:-}" ]; then
    CURRENT_USER="$SUDO_USER"
    CURRENT_UID=$(id -u "$SUDO_USER" 2>/dev/null || echo "$(id -u)")
    CURRENT_GID=$(id -g "$SUDO_USER" 2>/dev/null || echo "$(id -g)")
    print_info "Detected sudo usage - will use user $CURRENT_USER for file ownership"
else
    CURRENT_USER=$(id -un)
    CURRENT_UID=$(id -u)
    CURRENT_GID=$(id -g)
fi

if [ ! -d "$PRODUCTION_DIR" ]; then
    print_error "Production directory not found at $PRODUCTION_DIR"
    print_info "Please run install.sh first"
    exit 1
fi

# Logging setup - use production directory for logs
LOG_DIR="$PRODUCTION_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/update-$(date +%Y%m%d-%H%M%S).log"

# Create log file and set permissions
touch "$LOG_FILE" 2>/dev/null || {
    print_warning "Cannot create log file at $LOG_FILE, logging to console only"
    LOG_FILE=""
}

if [ -n "$LOG_FILE" ]; then
    chmod 644 "$LOG_FILE" 2>/dev/null || true
    # Redirect output to both terminal and log file
    exec > >(tee -a "$LOG_FILE") 2>&1
    print_info "Log file: $LOG_FILE"
else
    print_info "Logging to console only"
fi

echo ""

# Helper function to escape special characters for sed
escape_for_sed() {
    echo "$1" | sed -e 's/[]\/$*.^[]/\\&/g'
}

# Copy helper: keep existing file, write new version to .new unless forced
copy_as_new_if_changed() {
    local src="$1"
    local dest="$2"
    local label="$3"
    local force="${FORCE_OVERWRITE:-0}"

    if [ ! -f "$src" ]; then
        print_warning "Source file not found: $src"
        return 1
    fi

    if [ "$force" = "1" ]; then
        cp -f "$src" "$dest"
        print_info "$label overwritten (FORCE_OVERWRITE=1)"
        return 0
    fi

    if [ ! -f "$dest" ]; then
        cp "$src" "$dest"
        print_success "$label copied"
        return 0
    fi

    if cmp -s "$src" "$dest"; then
        print_info "$label unchanged"
        return 0
    fi

    local new_path="${dest}.new"
    cp "$src" "$new_path"
    print_warning "$label differs; kept existing, new saved as $(basename "$new_path")"
    return 0
}

# Function to validate .env file (from install.sh)
validate_env_file() {
    local env_file="$1"
    local errors=0
    local warnings=0
    
    echo ""
    echo "Validating .env file..."
    echo "======================"
    
    # Check if file exists
    if [ ! -f "$env_file" ]; then
        echo "❌ ERROR: .env file not found at $env_file"
        return 1
    fi
    
    # Check file permissions
    if [ ! -r "$env_file" ]; then
        echo "❌ ERROR: Cannot read .env file at $env_file (permission denied)"
        echo "   File owner: $(ls -ld "$env_file" | awk '{print $3":"$4}')"
        echo "   Current user: $(whoami)"
        echo "   Try: sudo chmod 644 $env_file"
        echo "   Or: sudo chown $(whoami):$(whoami) $env_file"
        return 1
    fi
    
    # Critical variables that must exist and have values
    local critical_vars=(
        "POSTGRES_PASSWORD"
        "POSTGRES_DB"
        "POSTGRES_USER"
        "DATABASE_URL"
        "DJANGO_SECRET_KEY"
        "ALLOWED_HOSTS"
    )
    
    # Check each critical variable
    for var in "${critical_vars[@]}"; do
        # Extract the value for this variable - try with current user first, then sudo if needed
        local value=$(grep "^${var}=" "$env_file" 2>/dev/null | head -1 | cut -d'=' -f2-)
        
        # If grep failed, try with sudo (if available)
        if [ $? -ne 0 ] || [ -z "$value" ]; then
            if command -v sudo >/dev/null 2>&1; then
                value=$(sudo grep "^${var}=" "$env_file" 2>/dev/null | head -1 | cut -d'=' -f2-)
            fi
        fi
        
        # Check if variable exists
        if [ -z "$value" ]; then
            echo "❌ ERROR: $var is missing or empty (or cannot read file)"
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
    
    # Check for concatenated lines (common issue) - IMPROVED DETECTION
    # Only flag as error if it's clearly a concatenation of separate variables
    local concatenated=$(grep -E '^[A-Z_][A-Z0-9_]*=[^=]*[A-Z_][A-Z0-9_]*=' "$env_file" | wc -l | tr -d ' ')
    if [ "$concatenated" -gt 0 ]; then
        echo "❌ ERROR: Found $concatenated line(s) with concatenated variables"
        echo "   This usually means line breaks are missing in .env file"
        errors=$((errors+1))
        
        # Show problematic lines
        echo "   Problematic lines:"
        grep -E '^[A-Z_][A-Z0-9_]*=[^=]*[A-Z_][A-Z0-9_]*=' "$env_file" | head -5 | sed 's/^/   /'
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

# IMPROVED Function to detect and repair corrupted .env files
# Only repairs actual corruption, not legitimate values with '='
repair_env_file() {
    local env_file="$PRODUCTION_DIR/.env"
    
    if [ ! -f "$env_file" ]; then
        echo "Warning: .env file not found at $env_file"
        return 1
    fi
    
    # Check file permissions
    if [ ! -r "$env_file" ]; then
        echo "Warning: Cannot read .env file at $env_file (permission denied)"
        echo "   File owner: $(ls -ld "$env_file" 2>/dev/null | awk '{print $3":"$4}' || echo 'unknown')"
        echo "   Current user: $(whoami)"
        return 1
    fi
    
    # Check for corruption pattern: ONLY flag clear concatenations of separate variables
    # Pattern: KEY1=VALUE1KEY2=VALUE2 (no space between VALUE1 and KEY2)
    local corrupted_lines=$(grep -E '^[A-Z_][A-Z0-9_]*=[^=]*[A-Z_][A-Z0-9_]*=' "$env_file" 2>/dev/null | wc -l || echo "0")
    
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
            
            # Check if line contains ACTUAL concatenated variables (not just = in values)
            if [[ $line =~ ^([^=]+)=(.*) ]]; then
                local key="${BASH_REMATCH[1]}"
                local value="${BASH_REMATCH[2]}"
                
                # Check if this is actually a concatenation by looking for pattern: VALUEKEY2=
                # where KEY2 starts with uppercase letter and is followed by =
                if [[ $value =~ ([^=]*[A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
                    # This is a concatenation, split it
                    local first_value="${BASH_REMATCH[1]}"
                    local remaining="${BASH_REMATCH[2]}"
                    
                    # Write the first key-value pair
                    echo "$key=$first_value" >> "$temp_file"
                    
                    # Try to extract the second key-value pair
                    if [[ $remaining =~ ^([^=]+)=(.*)$ ]]; then
                        local second_key="${BASH_REMATCH[1]}"
                        local second_value="${BASH_REMATCH[2]}"
                        echo "$second_key=$second_value" >> "$temp_file"
                    fi
                else
                    # Line is not corrupted, write as-is
                    echo "$line" >> "$temp_file"
                fi
            else
                # Line is not corrupted, write as-is
                echo "$line" >> "$temp_file"
            fi
        done < "$env_file"
        
        # Replace original file with repaired version
        mv "$temp_file" "$env_file"
        chmod 600 "$env_file"
        
        # Set ownership if not root and we know the current user
        if [ "$(id -u)" -ne 0 ] && [ -n "${CURRENT_UID:-}" ]; then
            chown "$CURRENT_UID:$CURRENT_GID" "$env_file" 2>/dev/null || true
        fi
        
        echo "✓ .env file repaired successfully"
        return 0
    else
        echo "✓ .env file appears to be valid"
        return 0
    fi
}

# Function to fix file permissions if needed
fix_permissions() {
    local target_dir="$1"
    
    if [ ! -d "$target_dir" ]; then
        return 1
    fi
    
    # Check if running as root - if so, try to fix ownership
    if [ "$(id -u)" -eq 0 ]; then
        print_info "Running as root - cannot automatically fix ownership"
        return 1
    fi
    
    # Check if files are owned by different user
    local dir_owner=$(stat -c '%U' "$target_dir" 2>/dev/null || stat -f '%Su' "$target_dir" 2>/dev/null || echo "")
    if [ -n "$dir_owner" ] && [ "$dir_owner" != "$CURRENT_USER" ] && [ "$dir_owner" != "root" ]; then
        print_warning "Production directory is owned by $dir_owner, but running as $CURRENT_USER"
        print_info "Attempting to fix ownership..."
        
        # Try to fix with sudo if available
        if command -v sudo >/dev/null 2>&1; then
            if sudo chown -R "$CURRENT_UID:$CURRENT_GID" "$target_dir" 2>/dev/null; then
                print_success "Fixed ownership of $target_dir to $CURRENT_USER"
                return 0
            else
                print_warning "Could not fix ownership - may need manual intervention"
                return 1
            fi
        else
            print_warning "sudo not available - cannot fix ownership automatically"
            return 1
        fi
    fi
    
    return 0
}

# Try to fix permissions if needed (but don't fail if we can't)
fix_permissions "$PRODUCTION_DIR" || true

# Check and repair .env file if needed
if ! repair_env_file; then
    print_info "Note: .env file check completed (or skipped due to permissions)"
fi

# Validate .env file before proceeding
ENV_FILE="$PRODUCTION_DIR/.env"
if [ ! -r "$ENV_FILE" ]; then
    echo ""
    print_error "Cannot read .env file at $ENV_FILE"
    echo ""
    print_info "File information:"
    ls -ld "$ENV_FILE" 2>/dev/null || echo "   File not found or cannot access"
    echo "   Current user: $CURRENT_USER"
    echo ""
    
    # Try to fix permissions automatically
    if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        print_info "Attempting to fix .env file permissions..."
        if sudo chmod 644 "$ENV_FILE" 2>/dev/null && sudo chown "$CURRENT_UID:$CURRENT_GID" "$ENV_FILE" 2>/dev/null; then
            chmod 600 "$ENV_FILE" 2>/dev/null || true
            print_success "Fixed .env file permissions"
        else
            print_warning "Could not automatically fix permissions"
        fi
    fi
    
    # Check again after attempt to fix
    if [ ! -r "$ENV_FILE" ]; then
        print_warning "To fix permissions manually, run one of these commands:"
        echo "   sudo chmod 644 $ENV_FILE && sudo chown $CURRENT_USER:$CURRENT_USER $ENV_FILE"
        echo "   sudo chown $CURRENT_USER:$CURRENT_USER $ENV_FILE"
        echo ""
        read -p "Do you want to continue without .env validation? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Update cancelled. Please fix .env file permissions first."
            exit 1
        fi
        print_warning "Continuing without .env validation - this may cause issues later"
    fi
elif ! validate_env_file "$ENV_FILE"; then
    echo ""
    print_warning ".env file validation failed. Please review and fix errors"
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Update cancelled"
        exit 1
    fi
fi

# Create backup before update
print_header "Creating Backup Before Update"
BACKUP_DIR="$PRODUCTION_DIR/backups/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

print_info "Backing up database..."
cd "$PRODUCTION_DIR"

# Check if database container is running
if ! docker compose ps db | grep -q "Up"; then
    print_warning "Database container is not running, skipping database backup"
else
    # Wait for database to be ready (up to 30 seconds)
    print_info "Waiting for database to be ready..."
    DB_READY=false
    for i in {1..30}; do
        if docker compose exec -T db pg_isready -U oktools > /dev/null 2>&1; then
            DB_READY=true
            break
        fi
        if [ $i -lt 30 ]; then
            sleep 1
        fi
    done
    
    if [ "$DB_READY" = false ]; then
        print_warning "Database is not ready after 30 seconds, skipping backup"
        print_info "Database may still be starting up. Backup will be skipped for safety."
    else
        # Attempt to create database backup
        print_info "Creating database backup..."
        # Create backup and capture both stdout and stderr
        if docker compose exec -T db pg_dump -U oktools oktools > "$BACKUP_DIR/database.sql" 2>"$BACKUP_DIR/database_backup_error.log"; then
            BACKUP_EXIT_CODE=0
        else
            BACKUP_EXIT_CODE=$?
        fi
        
        # Check if backup was successful
        if [ $BACKUP_EXIT_CODE -eq 0 ] && [ -f "$BACKUP_DIR/database.sql" ] && [ -s "$BACKUP_DIR/database.sql" ]; then
            BACKUP_SIZE=$(du -h "$BACKUP_DIR/database.sql" | cut -f1)
            print_success "Database backup created successfully (size: $BACKUP_SIZE)"
            # Remove error log if backup was successful
            rm -f "$BACKUP_DIR/database_backup_error.log" 2>/dev/null || true
        else
            print_warning "Database backup failed"
            # Show error details if error log exists and has content
            if [ -f "$BACKUP_DIR/database_backup_error.log" ] && [ -s "$BACKUP_DIR/database_backup_error.log" ]; then
                print_info "  Error details:"
                head -5 "$BACKUP_DIR/database_backup_error.log" | sed 's/^/    /'
            fi
            # Remove empty backup file
            if [ -f "$BACKUP_DIR/database.sql" ] && [ ! -s "$BACKUP_DIR/database.sql" ]; then
                rm -f "$BACKUP_DIR/database.sql"
                print_info "  Removed empty backup file"
            fi
            print_info "  You may want to create a manual backup:"
            print_info "    docker compose exec -T db pg_dump -U oktools oktools > backup.sql"
        fi
    fi
fi

print_info "Backing up configuration..."
cp "$PRODUCTION_DIR/.env" "$BACKUP_DIR/.env.backup" 2>/dev/null || true
cp "$PRODUCTION_DIR/docker-compose.yml" "$BACKUP_DIR/docker-compose.yml.backup" 2>/dev/null || true
print_success "Configuration backup created"

# Backup rotation - keep only last 5
print_info "Rotating backups (keeping last 5)..."
BACKUP_COUNT=$(ls -1d "$PRODUCTION_DIR/backups/backup-"* 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt 5 ]; then
    OLD_BACKUPS=$(ls -1td "$PRODUCTION_DIR/backups/backup-"* | tail -n +6)
    for old_backup in $OLD_BACKUPS; do
        rm -rf "$old_backup"
        print_info "Removed old backup: $(basename "$old_backup")"
    done
fi
print_success "Backup rotation completed (kept 5 most recent)"

# Function to create local update.sh script in production directory
create_local_update_script() {
    local local_update_script="$PRODUCTION_DIR/update.sh"
    
    # Check if script already exists
    if [ -f "$local_update_script" ]; then
        print_info "Local update script already exists at $local_update_script"
        # Verify it's executable
        if [ ! -x "$local_update_script" ]; then
            print_info "Making local update script executable..."
            chmod +x "$local_update_script" 2>/dev/null || sudo chmod +x "$local_update_script" 2>/dev/null || true
        fi
        return 0
    fi
    
    print_info "Creating local update.sh script in production directory..."
    print_info "Target: $local_update_script"
    
    # Ensure production directory exists and is writable
    if [ ! -d "$PRODUCTION_DIR" ]; then
        print_error "Production directory does not exist: $PRODUCTION_DIR"
        return 1
    fi
    
    # Determine project directory for the script
    local project_dir_for_script="$PROJECT_DIR"
    print_info "Project directory: $project_dir_for_script"
    
    # Check write permissions and determine creation method
    local need_sudo=false
    local current_uid_check=$(id -u)
    print_info "Current UID: $current_uid_check, Current user: $(whoami)"
    
    if [ "$current_uid_check" -eq 0 ]; then
        # Running as root - can write directly
        need_sudo=false
        print_info "Running as root - will create file directly"
    elif [ -w "$PRODUCTION_DIR" ]; then
        # Have write permission - can write directly
        need_sudo=false
        print_info "Have write permission - will create file directly"
    else
        # No write permission - need sudo
        need_sudo=true
        print_info "No write permission - will use sudo to create file"
        if ! command -v sudo >/dev/null 2>&1; then
            print_error "Cannot create local update script - no write permission and sudo not available"
            print_info "Production directory: $PRODUCTION_DIR"
            print_info "Current user: $(whoami)"
            print_info "Directory owner: $(stat -c '%U' "$PRODUCTION_DIR" 2>/dev/null || stat -f '%Su' "$PRODUCTION_DIR" 2>/dev/null || echo 'unknown')"
            return 1
        fi
    fi
    
    # Create the script content
    local script_content=$(cat <<'SCRIPT_EOF'
#!/bin/bash
# Local update wrapper script for OK Tools production environment
# This script updates the code from git and then calls the main update script

set -e

# Get script directory and project directory
PRODUCTION_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="PROJECT_DIR_PLACEHOLDER"

# Try to find project directory if default path doesn't exist
if [ ! -d "$PROJECT_DIR" ] || [ ! -f "$PROJECT_DIR/deployment/scripts/update.sh" ]; then
    # Try to find project directory by looking for deployment/scripts/update.sh
    # Search in parent directory and common locations
    PARENT_DIR="$(dirname "$PRODUCTION_DIR")"
    for possible_dir in "$PARENT_DIR"/*; do
        if [ -d "$possible_dir" ] && [ -f "$possible_dir/deployment/scripts/update.sh" ]; then
            PROJECT_DIR="$possible_dir"
            break
        fi
    done
fi

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project directory not found. Expected at: PROJECT_DIR_PLACEHOLDER"
    echo "Please check your installation or set PROJECT_DIR environment variable."
    exit 1
fi

# Check if main update script exists
MAIN_UPDATE_SCRIPT="$PROJECT_DIR/deployment/scripts/update.sh"
if [ ! -f "$MAIN_UPDATE_SCRIPT" ]; then
    echo "Error: Main update script not found at $MAIN_UPDATE_SCRIPT"
    exit 1
fi

# Create backup archive of PROJECT_DIR before updating
echo "Creating backup archive of project directory before update..."
BACKUP_ARCHIVE_DIR="$PRODUCTION_DIR/backups/code_backups"
mkdir -p "$BACKUP_ARCHIVE_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE_NAME="code_backup_$TIMESTAMP.tar.gz"
ARCHIVE_PATH="$BACKUP_ARCHIVE_DIR/$ARCHIVE_NAME"

# Create archive excluding unnecessary files
cd "$(dirname "$PROJECT_DIR")"
PROJECT_BASENAME=$(basename "$PROJECT_DIR")
tar -czf "$ARCHIVE_PATH" \\
    --exclude="$PROJECT_BASENAME/venv" \\
    --exclude="$PROJECT_BASENAME/__pycache__" \\
    --exclude="$PROJECT_BASENAME/**/__pycache__" \\
    --exclude="$PROJECT_BASENAME/.git" \\
    --exclude="$PROJECT_BASENAME/node_modules" \\
    --exclude="$PROJECT_BASENAME/.pytest_cache" \\
    --exclude="$PROJECT_BASENAME/.mypy_cache" \\
    --exclude="$PROJECT_BASENAME/*.pyc" \\
    --exclude="$PROJECT_BASENAME/**/*.pyc" \\
    --exclude="$PROJECT_BASENAME/staticfiles" \\
    --exclude="$PROJECT_BASENAME/media" \\
    --exclude="$PROJECT_BASENAME/logs" \\
    "$PROJECT_BASENAME" 2>/dev/null || {
    echo "Warning: Failed to create backup archive, continuing anyway..."
}

if [ -f "$ARCHIVE_PATH" ]; then
    ARCHIVE_SIZE=$(du -h "$ARCHIVE_PATH" | cut -f1)
    echo "✓ Backup archive created: $ARCHIVE_NAME ($ARCHIVE_SIZE)"
    
    # Rotate old backups - keep only last 5
    OLD_BACKUPS=$(ls -1t "$BACKUP_ARCHIVE_DIR"/code_backup_*.tar.gz 2>/dev/null | tail -n +6)
    if [ -n "$OLD_BACKUPS" ]; then
        echo "$OLD_BACKUPS" | xargs rm -f 2>/dev/null || true
        echo "✓ Removed old backup archives (kept 5 most recent)"
    fi
else
    echo "⚠ Warning: Backup archive was not created"
fi

# Change to project directory and pull latest code
echo "Updating code from git repository..."
cd "$PROJECT_DIR"
git pull

# Call the main update script with flag indicating it was called from local script
echo "Running update script..."
export LOCAL_UPDATE_CALLED=1
exec "$MAIN_UPDATE_SCRIPT"
SCRIPT_EOF
)
    
    # Replace placeholder with actual project directory
    script_content="${script_content//PROJECT_DIR_PLACEHOLDER/$project_dir_for_script}"
    
    # Create the script file
    if [ "$need_sudo" = true ]; then
        print_info "Creating local update script with sudo (permission required)..."
        echo "$script_content" | sudo tee "$local_update_script" > /dev/null
        if [ $? -ne 0 ] || [ ! -f "$local_update_script" ]; then
            print_error "Failed to create local update script with sudo"
            return 1
        fi
        sudo chmod +x "$local_update_script" 2>/dev/null || true
    else
        print_info "Creating local update script..."
        echo "$script_content" > "$local_update_script"
        if [ $? -ne 0 ] || [ ! -f "$local_update_script" ]; then
            print_error "Failed to create local update script"
            return 1
        fi
        chmod +x "$local_update_script" 2>/dev/null || true
    fi
    
    # Set ownership if we know the intended user (even if running as root via sudo)
    if [ -n "${CURRENT_UID:-}" ] && [ "$CURRENT_UID" != "0" ]; then
        if [ "$need_sudo" = true ] || [ "$(id -u)" -eq 0 ]; then
            sudo chown "$CURRENT_UID:$CURRENT_GID" "$local_update_script" 2>/dev/null || true
        else
            chown "$CURRENT_UID:$CURRENT_GID" "$local_update_script" 2>/dev/null || true
        fi
        print_info "Set ownership of local update script to user $CURRENT_USER (UID: $CURRENT_UID)"
    fi
    
    # Verify file was created successfully
    if [ -f "$local_update_script" ] && [ -x "$local_update_script" ]; then
        print_success "Local update script created at $local_update_script"
        print_info "You can now use: $local_update_script"
        return 0
    else
        print_error "Failed to create or verify local update script at $local_update_script"
        if [ -f "$local_update_script" ]; then
            print_warning "File exists but is not executable, attempting to fix..."
            chmod +x "$local_update_script" 2>/dev/null || sudo chmod +x "$local_update_script" 2>/dev/null || true
        fi
        return 1
    fi
}

# Pull latest code FIRST (only if called directly, not from local script)
# Check if we're being called from local script by checking caller
if [ -z "${LOCAL_UPDATE_CALLED:-}" ]; then
    print_info "Pulling latest code from repository..."
    cd "$PROJECT_DIR"
    
    # Check if this is a git repository
    if [ ! -d ".git" ]; then
        print_warning "Not a git repository - skipping git pull"
        print_info "To enable updates from git, initialize repository: git init && git remote add origin <url>"
    elif ! git pull 2>&1; then
        GIT_PULL_EXIT=$?
        print_warning "git pull failed (exit code: $GIT_PULL_EXIT)"
        print_info "Possible reasons:"
        print_info "  - No internet connection"
        print_info "  - Git remote not configured (run: git remote add origin <url>)"
        print_info "  - Merge conflicts (resolve manually and retry)"
        print_info "  - Authentication required (configure git credentials)"
        echo ""
        read -p "Continue update anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Update cancelled. Please fix git issues and retry."
            exit 1
        fi
        print_warning "Continuing update without git pull - using current code"
    else
        print_success "Code updated from repository"
    fi
fi

# Check and create local update script AFTER git pull (so we have latest version)
if ! create_local_update_script; then
    print_warning "Failed to create local update script, but continuing with update..."
    print_info "You can create it manually later or run update script directly from project directory"
fi

# Verify that template files exist after git pull
print_info "Verifying template files..."
TEMPLATE_INDEX="$PROJECT_DIR/ok_tools/templates/admin/index.html"
TEMPLATE_NAV="$PROJECT_DIR/ok_tools/templates/admin/nav_sidebar.html"
TEMPLATE_BASE="$PROJECT_DIR/ok_tools/templates/admin/base_site.html"

if [ ! -f "$TEMPLATE_INDEX" ]; then
    print_warning "Template file not found: $TEMPLATE_INDEX"
    print_info "Checking git status..."
    cd "$PROJECT_DIR"
    git status ok_tools/templates/admin/ || true
    print_info "Attempting to restore from git..."
    git checkout HEAD -- ok_tools/templates/admin/index.html 2>/dev/null || print_warning "Could not restore index.html from git"
fi

if [ ! -f "$TEMPLATE_NAV" ]; then
    print_warning "Template file not found: $TEMPLATE_NAV"
    print_info "Attempting to restore from git..."
    cd "$PROJECT_DIR"
    git checkout HEAD -- ok_tools/templates/admin/nav_sidebar.html 2>/dev/null || print_warning "Could not restore nav_sidebar.html from git"
fi

# Verify files exist now
if [ -f "$TEMPLATE_INDEX" ] && [ -f "$TEMPLATE_NAV" ]; then
    print_success "Template files verified: index.html and nav_sidebar.html exist"
else
    print_error "Template files are missing - Docker build may fail or use old templates"
    print_info "Files should be at:"
    print_info "  - $TEMPLATE_INDEX"
    print_info "  - $TEMPLATE_NAV"
    ls -la "$PROJECT_DIR/ok_tools/templates/admin/" 2>/dev/null || print_warning "Template directory not found"
fi

# Update docker-compose files and configs in production directory
print_info "Updating docker-compose files and configs..."
cd "$PROJECT_DIR"

# Determine which docker-compose file to use based on existing installation
# Enhanced detection logic from install.sh
INSTALL_TYPE=""
if grep -q "^DOMAIN_NAME=" "$PRODUCTION_DIR/.env" && [ ! -z "$(grep '^DOMAIN_NAME=' "$PRODUCTION_DIR/.env" | cut -d'=' -f2)" ]; then
    print_info "Detected: Production with Nginx and SSL"
    INSTALL_TYPE="1"
    copy_as_new_if_changed "deployment/docker-compose.production.yml" "$PRODUCTION_DIR/docker-compose.yml" "docker-compose.yml"
    copy_as_new_if_changed "deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template" "nginx.conf.template"
    # Ensure deployment directory exists
    mkdir -p "$PRODUCTION_DIR/deployment" 2>/dev/null || sudo mkdir -p "$PRODUCTION_DIR/deployment" 2>/dev/null || true
    # Remove directory if it exists instead of file (fix for incorrect previous installations)
    if [ -d "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh" ]; then
        print_warning "Removing directory that should be a file: $PRODUCTION_DIR/deployment/99-custom-nginx-config.sh"
        rm -rf "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh" 2>/dev/null || {
            if command -v sudo >/dev/null 2>&1; then
                sudo rm -rf "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh" 2>/dev/null || {
                    print_error "Cannot remove directory - insufficient permissions even with sudo"
                    print_info "Please manually remove: sudo rm -rf $PRODUCTION_DIR/deployment/99-custom-nginx-config.sh"
                }
            else
                print_error "Cannot remove directory - insufficient permissions and sudo not available"
                print_info "Please manually remove: rm -rf $PRODUCTION_DIR/deployment/99-custom-nginx-config.sh (as root)"
            fi
        }
    fi
    # Copy file with sudo if needed
    if cp -f "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh" 2>/dev/null; then
        chmod +x "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh" 2>/dev/null || sudo chmod +x "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh" 2>/dev/null || true
    else
        if command -v sudo >/dev/null 2>&1; then
            sudo cp -f "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh"
            sudo chmod +x "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh"
        else
            print_error "Cannot copy nginx entrypoint script - insufficient permissions and sudo not available"
            exit 1
        fi
    fi
else
    # Check if it's Local Network or Localhost
    if grep -q "127.0.0.1" "$PRODUCTION_DIR/.env" && grep -q "localhost" "$PRODUCTION_DIR/.env"; then
        print_info "Detected: Localhost (Development on a single machine)"
        INSTALL_TYPE="3"
    else
        print_info "Detected: Local Network (LAN access, no domain or SSL)"
        INSTALL_TYPE="2"
    fi
    copy_as_new_if_changed "deployment/docker-compose.production.no-nginx.yml" "$PRODUCTION_DIR/docker-compose.yml" "docker-compose.yml"
fi

cp -f deployment/production.Dockerfile "$PRODUCTION_DIR/"
cp -f deployment/entrypoint.production.sh "$PRODUCTION_DIR/"

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

# Set ownership of copied files if not root
if [ "$(id -u)" -ne 0 ] && [ -n "${CURRENT_UID:-}" ]; then
    chown "$CURRENT_UID:$CURRENT_GID" "$PRODUCTION_DIR/docker-compose.yml" \
          "$PRODUCTION_DIR/production.Dockerfile" \
          "$PRODUCTION_DIR/entrypoint.production.sh" 2>/dev/null || true
    if [ "$INSTALL_TYPE" = "1" ]; then
        chown "$CURRENT_UID:$CURRENT_GID" "$PRODUCTION_DIR/nginx.conf.template" \
              "$PRODUCTION_DIR/deployment/99-custom-nginx-config.sh" 2>/dev/null || true
    fi
fi

# Copy logo and favicon to project static directory
print_info "Copying logo and favicon files..."
if [ -d "$PROJECT_DIR/deployment/img" ]; then
    mkdir -p "$PROJECT_DIR/ok_tools/static/img"
    if [ -f "$PROJECT_DIR/deployment/img/logo.png" ]; then
        cp -f "$PROJECT_DIR/deployment/img/logo.png" "$PROJECT_DIR/ok_tools/static/img/logo.png"
        print_success "Copied logo.png"
    else
        print_warning "logo.png not found in deployment/img/ - keeping existing file if present"
    fi
    if [ -f "$PROJECT_DIR/deployment/img/favicon.ico" ]; then
        cp -f "$PROJECT_DIR/deployment/img/favicon.ico" "$PROJECT_DIR/ok_tools/static/img/favicon.ico"
        print_success "Copied favicon.ico"
    else
        print_warning "favicon.ico not found in deployment/img/ - keeping existing file if present"
    fi
else
    print_warning "deployment/img/ directory not found - keeping existing logo and favicon files"
fi

# Create configs directory if it doesn't exist and copy config files
# BUT DON'T COPY .env TEMPLATES to avoid overwriting existing .env
mkdir -p "$PRODUCTION_DIR/configs"
# Copy only non-.env template files to avoid overwriting existing .env
find deployment/configs -type f ! -name "*.env.template" -exec cp -f {} "$PRODUCTION_DIR/configs/" \;

# Update .env file with new variables if they don't exist
echo "Checking for missing environment variables..."
ENV_FILE="$PRODUCTION_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    # Backup current .env
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✓ Backed up .env file"
    
    # Function to add variable if not exists
    add_env_var_if_missing() {
        local key="$1"
        local value="$2"
        
        if ! grep -q "^${key}=" "$ENV_FILE"; then
            echo "$key=$value" >> "$ENV_FILE"
            echo "  + Added $key"
        else
            echo "  ✓ $key already exists, keeping current value"
        fi
    }
    
    # Add new ENV variables with defaults
    add_env_var_if_missing "DJANGO_LOG_LEVEL" "INFO"
    add_env_var_if_missing "DJANGO_LANGUAGE" "de-de"
    add_env_var_if_missing "DJANGO_TIMEZONE" "Europe/Berlin"
    add_env_var_if_missing "DJANGO_STATIC_ROOT" "/app/staticfiles/"
    add_env_var_if_missing "DJANGO_MEDIA_ROOT" "/app/media/"
    add_env_var_if_missing "DJANGO_USE_SECURE_SETTINGS" "True"
    add_env_var_if_missing "MAIL_DEV_SETTINGS" "False"
    add_env_var_if_missing "MEDIA_AUTO_SCAN" "False"
    add_env_var_if_missing "MEDIA_AUTO_COPY_ON_SCHEDULE" "True"
    add_env_var_if_missing "BOOTSTRAP_VERSION" "5.3.3"
    add_env_var_if_missing "BOOTSTRAP_ICONS_VERSION" "1.11.0"
    add_env_var_if_missing "API_PAGE_SIZE" "20"
    add_env_var_if_missing "VIDEO_SCREEN_BOARD_DURATION" "20"
    add_env_var_if_missing "I18N_PHONE_REGION" "DE"
    add_env_var_if_missing "I18N_DATE_FORMAT" "%d.%m.%Y"
    add_env_var_if_missing "CELERY_BROKER_URL" "redis://redis:6379/0"
    add_env_var_if_missing "CELERY_RESULT_BACKEND" "redis://redis:6379/0"
    add_env_var_if_missing "CELERY_BEAT_EXPIRE_RENTALS" "*/30 * * * *"
    add_env_var_if_missing "CELERY_BEAT_CLEANUP_BACKUPS" "0 2 * * *"
    add_env_var_if_missing "CELERY_BEAT_BACKUP_DB" "0 3 * * *"
    add_env_var_if_missing "CELERY_BEAT_AUTO_SCAN" "0 */2 * * *"
    add_env_var_if_missing "CELERY_BEAT_LINK_LICENSES" "0 4 * * *"
    add_env_var_if_missing "CELERY_BEAT_SYNC_VIDEOS" "0 5 * * *"
    add_env_var_if_missing "CELERY_BEAT_UPDATE_METADATA" "0 1 1 * *"
    add_env_var_if_missing "LOGGING_FILE" "/app/logs/oktools.log"
    
    echo "✓ Environment variables updated"
else
    echo "Warning: .env file not found at $ENV_FILE"
fi

# Check if migration from volumes to bind mounts is needed
print_info "Checking for volume migration..."
MIGRATION_NEEDED=false
cd "$PRODUCTION_DIR"

# Check if old docker-compose.yml uses named volumes
if [ -f "docker-compose.yml" ]; then
    if grep -q "static_volume:\|media_volume:" "docker-compose.yml"; then
        MIGRATION_NEEDED=true
        print_warning "Detected old volume-based configuration - migration required"
    fi
fi

# Migrate from volumes to bind mounts if needed
if [ "$MIGRATION_NEEDED" = true ]; then
    print_header "Migrating from Volumes to Bind Mounts"
    
    # Stop containers first
    print_info "Stopping containers..."
    docker compose down || true
    
    # Create directories
    print_info "Creating bind mount directories..."
    mkdir -p "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
    chmod 755 "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media"
    chmod 755 "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
    
    # Set ownership if not root
    if [ "$(id -u)" -ne 0 ] && [ -n "${CURRENT_UID:-}" ]; then
        chown -R "$CURRENT_UID:$CURRENT_GID" "$PRODUCTION_DIR/data" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups" 2>/dev/null || true
    fi
    
    # Create temporary container to copy data from volumes
    print_info "Copying data from volumes to bind mounts..."
    
    # Get project name
    PROJECT_NAME=$(grep -m1 "^COMPOSE_PROJECT_NAME=" "$PRODUCTION_DIR/.env" 2>/dev/null | cut -d'=' -f2 || echo "oktools")
    PROJECT_NAME=${PROJECT_NAME:-oktools}
    
    # Copy static files if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_static_volume\|static_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_static_volume|static_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying static files from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/data/static:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Static files migrated"
        fi
    fi
    
    # Copy media files if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_media_volume\|media_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_media_volume|media_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying media files from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/data/media:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Media files migrated"
        fi
    fi
    
    # Copy logs if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_logs_volume\|logs_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_logs_volume|logs_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying logs from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/logs:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Logs migrated"
        fi
    fi
    
    # Copy backups if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_backups_volume\|backups_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_backups_volume|backups_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying backups from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/backups:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Backups migrated"
        fi
    fi
    
    print_success "Migration completed"
    print_warning "Old volumes will be removed after successful startup"
    print_info "You can manually remove them later with: docker volume prune"
    echo ""
fi

# Ensure all required directories exist with proper permissions
print_info "Ensuring required directories exist..."
mkdir -p "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
chmod 755 "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media"
chmod 755 "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"

# Set ownership if not root
if [ "$(id -u)" -ne 0 ] && [ -n "${CURRENT_UID:-}" ]; then
    chown -R "$CURRENT_UID:$CURRENT_GID" "$PRODUCTION_DIR/data" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups" 2>/dev/null || true
fi

# Check if static directory is empty (bind mount will hide container files if host dir is empty)
if [ -z "$(ls -A "$PRODUCTION_DIR/data/static" 2>/dev/null)" ]; then
    print_warning "Static directory is empty on host"
    print_info "Files will be created after container starts and collectstatic runs"
fi

print_success "Directories checked and permissions set"

# Stop containers before rebuilding (if not already stopped)
if [ "$MIGRATION_NEEDED" != true ]; then
    print_info "Stopping containers..."
    cd "$PRODUCTION_DIR"
    docker compose down
fi

# Rebuild Docker images
# Interactive choice: use cache (faster) or rebuild without cache (clean)
echo ""
print_info "Docker image build options:"
echo "  1) Build with cache (faster, recommended for regular updates)"
echo "  2) Build without cache (full rebuild, use when dependencies changed)"
echo ""
read -p "Choose build option (1 or 2, default: 1): " -t 10 BUILD_OPTION
echo ""

# Normalize BUILD_OPTION - default to 1 if empty or invalid
BUILD_OPTION=${BUILD_OPTION:-1}
BUILD_OPTION=$(echo "$BUILD_OPTION" | tr -d '[:space:]' | head -c 1)

if [ "$BUILD_OPTION" = "2" ]; then
    print_info "Rebuilding Docker images (without cache - full rebuild)..."
    docker compose build --no-cache
    # Clean up build cache after full rebuild to free disk space
    print_info "Cleaning up Docker build cache after full rebuild..."
    docker builder prune -f > /dev/null 2>&1
    print_success "Build cache cleaned"
else
    print_info "Rebuilding Docker images (using cache for faster builds)..."
    # Docker will use local base images if available (no need for --pull flag)
    # Keep build cache for faster subsequent builds
    docker compose build
fi

# Start containers
print_info "Starting containers..."
docker compose up -d

# Wait for containers to be ready
print_info "Waiting for containers to be ready..."
sleep 10

# Run migrations
print_info "Running database migrations..."
docker compose exec -T web python manage.py migrate --noinput

# Compile translation messages
print_info "Compiling translation messages..."
if ! docker compose exec -T web python manage.py compilemessages; then
    print_warning "Failed to compile translation messages, continuing..."
else
    print_success "Translation messages compiled successfully"
    
    # Verify compiled translation files exist
    print_info "Verifying compiled translation files..."
    MO_FILES=$(docker compose exec -T web find /app -name "*.mo" -type f 2>/dev/null | wc -l | tr -d ' ' || echo "0")
    if [ "$MO_FILES" -gt 0 ]; then
        print_success "Found $MO_FILES compiled translation files (.mo)"
        
        # Check for German translations specifically
        DE_MO_FILES=$(docker compose exec -T web find /app -path "*/locale/de/LC_MESSAGES/*.mo" -type f 2>/dev/null | wc -l | tr -d ' ' || echo "0")
        if [ "$DE_MO_FILES" -gt 0 ]; then
            print_success "Found $DE_MO_FILES German translation files"
        else
            print_warning "No German translation files found - translations may not work"
        fi
    else
        print_warning "No compiled translation files found - translations will not work"
    fi
fi

# Collect static files
print_info "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput

# Verify static files are present and accessible
print_info "Verifying static files..."
STATIC_COUNT=$(docker compose exec -T web sh -c "find /app/staticfiles -type f 2>/dev/null | wc -l" | tr -d ' ' || echo "0")
if [ "$STATIC_COUNT" -gt 0 ]; then
    print_success "Found $STATIC_COUNT static files in container"
    
    # Wait a moment for filesystem sync
    sleep 2
    
    # Check if files are visible on host
    HOST_STATIC_COUNT=$(find "$PRODUCTION_DIR/data/static" -type f 2>/dev/null | wc -l || echo "0")
    if [ "$HOST_STATIC_COUNT" -gt 0 ]; then
        print_success "Static files are accessible on host: $HOST_STATIC_COUNT files found"
    else
        print_warning "Static files not visible on host"
        print_info "This may be a permissions issue. Checking..."
        echo "   Container files: $STATIC_COUNT"
        echo "   Host files: $HOST_STATIC_COUNT"
        print_info "Trying to fix permissions..."
        
        # Try to fix permissions - run as root in container to ensure access
        docker compose exec -T --user root web sh -c "chown -R app:app /app/staticfiles && chmod -R 755 /app/staticfiles" || true
        
        # Check again after permission fix
        sleep 1
        HOST_STATIC_COUNT_AFTER=$(find "$PRODUCTION_DIR/data/static" -type f 2>/dev/null | wc -l || echo "0")
        if [ "$HOST_STATIC_COUNT_AFTER" -gt 0 ]; then
            print_success "Permission fix successful: $HOST_STATIC_COUNT_AFTER files now visible"
        else
            print_warning "Files still not visible. This may be normal if running in a restricted environment"
            print_info "Static files are available inside the container and will be served by Django/WhiteNoise"
        fi
    fi
else
    print_warning "No static files found in container after collectstatic"
    print_info "This may indicate a problem with static files configuration"
fi

# Cleanup Docker resources
print_info "Cleaning up unused Docker resources..."
docker image prune -f > /dev/null 2>&1
docker volume prune -f > /dev/null 2>&1
print_success "Docker cleanup completed"

# Health check
print_info "Checking web service availability on port 8010..."
for i in {1..30}; do
    if curl -s http://localhost:8010/health > /dev/null 2>&1; then
        print_success "Web service is available"
        break
    elif [ $i -eq 30 ]; then
        print_warning "Web service health check timeout"
    else
        sleep 2
    fi
done

# Check logs for errors
print_info "Checking logs for errors..."
ERROR_LINES=$(docker compose logs web 2>&1 | grep -iE "(error|exception|traceback)" | grep -vE "(ERROR|WARNING|INFO|DEBUG)\s*\:" | grep -vE "No valid legacy config|Validation|migration" | tail -10)
if [ -n "$ERROR_LINES" ]; then
    print_warning "Potential errors found in logs:"
    echo "$ERROR_LINES" | head -5 | sed 's/^/  /'
    print_info "Full logs: docker compose logs web"
else
    print_success "No critical errors in logs"
fi

# Clean up old volumes after successful update (if migration was performed)
if [ "$MIGRATION_NEEDED" = true ]; then
    echo ""
    print_info "Cleaning up old volumes..."
    # Remove old named volumes (non-destructive - only removes if not in use)
    docker volume ls | grep -E "${PROJECT_NAME}_static_volume|static_volume|${PROJECT_NAME}_media_volume|media_volume|${PROJECT_NAME}_logs_volume|logs_volume|${PROJECT_NAME}_backups_volume|backups_volume" | awk '{print $2}' | while read vol; do
        if docker volume inspect "$vol" >/dev/null 2>&1; then
            print_info "  Removing old volume: $vol"
            docker volume rm "$vol" 2>/dev/null || print_info "    (Volume may still be in use, will be cleaned up later)"
        fi
    done
    print_success "Volume cleanup completed"
fi

# Run post-update diagnostics
print_header "Running Post-Update Diagnostics"

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
    print_info "Please review logs above carefully"
else
    print_success "No critical errors found in recent web service logs"
fi

print_header "Update Complete!"
echo "Production directory: $PRODUCTION_DIR"
echo ""

# Display access information based on installation type
case $INSTALL_TYPE in
    1)
        # Production with SSL
        DOMAIN_NAME=$(grep "^DOMAIN_NAME=" "$PRODUCTION_DIR/.env" | cut -d'=' -f2)
        print_info "Access admin panel: https://$DOMAIN_NAME/admin"
        ;;
    2)
        # Local Network - detect IP
        LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || \
                  ip route get 1.1.1.1 | awk '{print $7}' 2>/dev/null || \
                  ipconfig getifaddr en0 2>/dev/null || \
                  echo "127.0.0.1")
        print_info "Access admin panel: http://$LOCAL_IP:8010/admin"
        ;;
    3)
        # Localhost
        print_info "Access admin panel: http://localhost:8010/admin"
        ;;
    *)
        print_info "Access admin panel: http://localhost:8010/admin"
        ;;
esac

echo ""
print_info "Next steps:"
echo "1. Check container status: cd $PRODUCTION_DIR && docker compose ps"
echo "2. View logs: cd $PRODUCTION_DIR && docker compose logs -f web"
if [ -f "$PRODUCTION_DIR/update.sh" ]; then
    echo "3. For future updates, use: $PRODUCTION_DIR/update.sh"
    echo "   (This script automatically updates from git and uses the latest version)"
else
    echo "3. For future updates, use: $SCRIPT_DIR/update.sh"
fi
echo "4. If issues occur, check logs or contact support"

print_header "Diagnostics Complete"