#!/bin/bash
set -e

# Integration Test Script for ENV-based Configuration
# Tests the complete configuration flow in a Docker environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")/.."
TEST_ENV_FILE="/tmp/oktools_test.env"

echo "=========================================="
echo "OK-Tools ENV Configuration Integration Tests"
echo "=========================================="
echo ""

# Function to create minimal test .env file
create_test_env() {
    echo "Creating test environment file..."
    
    cat > "$TEST_ENV_FILE" << 'EOF'
# Minimal test configuration
DJANGO_SECRET_KEY=test-secret-key-for-integration-testing-only-do-not-use-in-production
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,testserver
POSTGRES_DB=oktools_test
POSTGRES_USER=oktools_test
POSTGRES_PASSWORD=test_password_12345
DB_HOST=db
DB_PORT=5432
DJANGO_LOG_LEVEL=DEBUG

# Organization
ORG_NAME=Test Organization
ORG_SHORT_NAME=Test Org
ORG_WEBSITE=https://test.example.com
ORG_EMAIL=test@example.com
ORG_PHONE=+49 123 456789
ORG_ADDRESS=Test Street 1\\nTest City
ORG_ORGANIZATION_OWNER=TEST_ORG
STATE_MEDIA_INSTITUTION=MSA

# Email (dev mode)
EMAIL_HOST=smtp.test.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=test@example.com
EMAIL_HOST_PASSWORD=test_password
DEFAULT_FROM_EMAIL=noreply@test.com
MAIL_DEV_SETTINGS=True

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Celery Beat Schedules
CELERY_BEAT_EXPIRE_RENTALS=*/30 * * * *
CELERY_BEAT_CLEANUP_BACKUPS=0 2 * * *
CELERY_BEAT_BACKUP_DB=0 3 * * *
CELERY_BEAT_AUTO_SCAN=0 */2 * * *
CELERY_BEAT_LINK_LICENSES=0 4 * * *
CELERY_BEAT_SYNC_VIDEOS=0 5 * * *
CELERY_BEAT_UPDATE_METADATA=0 1 1 * *

# Media & NAS
NAS_PLAYOUT_PATH=/tmp/test/playout
NAS_ARCHIVE_PATH=/tmp/test/archive
MEDIA_AUTO_SCAN=False

# Bootstrap
BOOTSTRAP_VERSION=5.3.3
BOOTSTRAP_ICONS_VERSION=1.11.0

# Logging
LOGGING_FILE=/tmp/oktools_test.log
BACKUP_DIR=/tmp/test/backups

# Application
PYTHONPATH=/app
PYTHONUNBUFFERED=1
GUNICORN_WORKERS=2
GUNICORN_THREADS=1
GUNICORN_TIMEOUT=60
LOG_LEVEL=debug
EOF
    
    chmod 600 "$TEST_ENV_FILE"
    echo "✓ Test environment file created: $TEST_ENV_FILE"
}

# Function to cleanup
cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ -f "$TEST_ENV_FILE" ]; then
        rm -f "$TEST_ENV_FILE"
        echo "✓ Removed test environment file"
    fi
}

# Trap cleanup on exit
trap cleanup EXIT

# Test 1: Validate .env file syntax
test_env_syntax() {
    echo ""
    echo "Test 1: Validating .env file syntax"
    echo "======================================"
    
    if [ ! -f "$TEST_ENV_FILE" ]; then
        echo "✗ FAILED: Test env file not found"
        return 1
    fi
    
    # Check for basic syntax issues
    local errors=0
    
    # Check for lines without = (except comments and empty lines)
    if grep -vE '^#|^$' "$TEST_ENV_FILE" | grep -vE '=' > /dev/null; then
        echo "✗ FAILED: Found lines without '='"
        errors=$((errors + 1))
    fi
    
    # Check for duplicate keys
    local dupes=$(grep -vE '^#|^$' "$TEST_ENV_FILE" | cut -d'=' -f1 | sort | uniq -d)
    if [ -n "$dupes" ]; then
        echo "✗ FAILED: Found duplicate keys: $dupes"
        errors=$((errors + 1))
    fi
    
    if [ $errors -eq 0 ]; then
        echo "✓ PASSED: .env syntax is valid"
        return 0
    else
        return 1
    fi
}

# Test 2: Load environment and check Django settings
test_django_check() {
    echo ""
    echo "Test 2: Django Configuration Check"
    echo "===================================="
    
    # Export test environment variables
    set -a
    source "$TEST_ENV_FILE"
    set +a
    
    cd "$PROJECT_DIR"
    
    # Run Django check command
    echo "Running: python manage.py check --deploy"
    if python manage.py check --deploy 2>&1 | tee /tmp/django_check.log; then
        echo "✓ PASSED: Django check succeeded"
        return 0
    else
        echo "✗ FAILED: Django check found issues"
        cat /tmp/django_check.log
        return 1
    fi
}

# Test 3: Test database connection
test_database_connection() {
    echo ""
    echo "Test 3: Database Connection Test"
    echo "=================================="
    
    set -a
    source "$TEST_ENV_FILE"
    set +a
    
    cd "$PROJECT_DIR"
    
    # This is a dry-run test without actual DB
    echo "Checking database configuration..."
    
    python << 'PYEOF'
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ok_tools.settings')

try:
    from django.conf import settings
    db_config = settings.DATABASES['default']
    
    required_keys = ['ENGINE', 'NAME', 'USER', 'PASSWORD', 'HOST', 'PORT']
    missing = [k for k in required_keys if k not in db_config or not db_config[k]]
    
    if missing:
        print(f"✗ FAILED: Missing database config: {missing}")
        sys.exit(1)
    
    print("✓ PASSED: Database configuration is complete")
    print(f"  - Engine: {db_config['ENGINE']}")
    print(f"  - Database: {db_config['NAME']}")
    print(f"  - Host: {db_config['HOST']}:{db_config['PORT']}")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ FAILED: {str(e)}")
    sys.exit(1)
PYEOF
    
    return $?
}

# Test 4: Verify Celery configuration
test_celery_config() {
    echo ""
    echo "Test 4: Celery Configuration Test"
    echo "==================================="
    
    set -a
    source "$TEST_ENV_FILE"
    set +a
    
    cd "$PROJECT_DIR"
    
    python << 'PYEOF'
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ok_tools.settings')

try:
    from django.conf import settings
    
    # Check broker URL
    if not settings.CELERY_BROKER_URL:
        print("✗ FAILED: CELERY_BROKER_URL not set")
        sys.exit(1)
    
    # Check result backend
    if not settings.CELERY_RESULT_BACKEND:
        print("✗ FAILED: CELERY_RESULT_BACKEND not set")
        sys.exit(1)
    
    # Check beat schedule
    if not isinstance(settings.CELERY_BEAT_SCHEDULE, dict):
        print("✗ FAILED: CELERY_BEAT_SCHEDULE is not a dict")
        sys.exit(1)
    
    required_tasks = [
        'expire_rentals',
        'cleanup_old_backups',
        'run_backup_db',
        'auto_scan',
        'link_orphan_licenses',
        'sync_licenses_videos',
        'update_video_metadata'
    ]
    
    missing_tasks = [t for t in required_tasks if t not in settings.CELERY_BEAT_SCHEDULE]
    if missing_tasks:
        print(f"✗ FAILED: Missing Celery Beat tasks: {missing_tasks}")
        sys.exit(1)
    
    print("✓ PASSED: Celery configuration is valid")
    print(f"  - Broker: {settings.CELERY_BROKER_URL}")
    print(f"  - Backend: {settings.CELERY_RESULT_BACKEND}")
    print(f"  - Scheduled tasks: {len(settings.CELERY_BEAT_SCHEDULE)}")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ FAILED: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF
    
    return $?
}

# Test 5: Verify helper functions
test_helper_functions() {
    echo ""
    echo "Test 5: Helper Functions Test"
    echo "==============================="
    
    set -a
    source "$TEST_ENV_FILE"
    set +a
    
    cd "$PROJECT_DIR"
    
    python << 'PYEOF'
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ok_tools.settings')

try:
    from ok_tools.settings import get_env, get_env_list, parse_crontab_env
    
    # Test get_env
    os.environ['TEST_VAR'] = 'test_value'
    result = get_env('TEST_VAR')
    if result != 'test_value':
        print(f"✗ FAILED: get_env returned '{result}' instead of 'test_value'")
        sys.exit(1)
    
    # Test get_env with bool
    os.environ['TEST_BOOL'] = 'true'
    result = get_env('TEST_BOOL', cast=bool)
    if result != True:
        print(f"✗ FAILED: get_env bool cast failed")
        sys.exit(1)
    
    # Test get_env_list
    os.environ['TEST_LIST'] = 'a,b,c'
    result = get_env_list('TEST_LIST')
    if result != ['a', 'b', 'c']:
        print(f"✗ FAILED: get_env_list returned {result}")
        sys.exit(1)
    
    # Test parse_crontab_env
    os.environ['TEST_CRON'] = '*/30 * * * *'
    schedule = parse_crontab_env('TEST_CRON')
    if str(schedule.minute) != '*/30':
        print(f"✗ FAILED: parse_crontab_env failed")
        sys.exit(1)
    
    print("✓ PASSED: All helper functions work correctly")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ FAILED: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF
    
    return $?
}

# Test 6: Test ALLOWED_HOSTS parsing
test_allowed_hosts() {
    echo ""
    echo "Test 6: ALLOWED_HOSTS Parsing Test"
    echo "===================================="
    
    set -a
    source "$TEST_ENV_FILE"
    set +a
    
    cd "$PROJECT_DIR"
    
    python << 'PYEOF'
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ok_tools.settings')

try:
    from django.conf import settings
    
    if not isinstance(settings.ALLOWED_HOSTS, list):
        print(f"✗ FAILED: ALLOWED_HOSTS is not a list: {type(settings.ALLOWED_HOSTS)}")
        sys.exit(1)
    
    if len(settings.ALLOWED_HOSTS) == 0:
        print("✗ FAILED: ALLOWED_HOSTS is empty")
        sys.exit(1)
    
    print("✓ PASSED: ALLOWED_HOSTS parsed correctly")
    print(f"  - Hosts: {settings.ALLOWED_HOSTS}")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ FAILED: {str(e)}")
    sys.exit(1)
PYEOF
    
    return $?
}

# Main test runner
main() {
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    
    # Create test environment
    create_test_env
    
    # Run all tests
    tests=(
        "test_env_syntax"
        "test_django_check"
        "test_database_connection"
        "test_celery_config"
        "test_helper_functions"
        "test_allowed_hosts"
    )
    
    for test in "${tests[@]}"; do
        total_tests=$((total_tests + 1))
        if $test; then
            passed_tests=$((passed_tests + 1))
        else
            failed_tests=$((failed_tests + 1))
        fi
    done
    
    # Summary
    echo ""
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo "Total tests:  $total_tests"
    echo "Passed:       $passed_tests"
    echo "Failed:       $failed_tests"
    echo ""
    
    if [ $failed_tests -eq 0 ]; then
        echo "✓ ALL TESTS PASSED"
        return 0
    else
        echo "✗ SOME TESTS FAILED"
        return 1
    fi
}

# Run main
main
exit $?