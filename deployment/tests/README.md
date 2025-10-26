# OK-Tools Integration Tests

This directory contains integration tests for OK-Tools deployment and configuration.

## Test Scripts

### test_env_config.sh

Integration test script for ENV-based configuration. Tests the complete configuration flow in a Docker environment.

#### Usage

```bash
# Run from project root
./deployment/tests/test_env_config.sh

# Run from tests directory
cd deployment/tests
./test_env_config.sh
```

#### What it tests

1. **Environment file syntax** - Validates .env file format
2. **Django configuration** - Runs Django check command
3. **Database configuration** - Verifies database settings
4. **Celery configuration** - Checks Celery and Beat schedules
5. **Helper functions** - Tests custom helper functions
6. **ALLOWED_HOSTS parsing** - Validates host parsing

#### Requirements

- Bash shell
- Python with Django installed
- Project dependencies available

#### Output

The script provides detailed output for each test:
- ✓ PASSED for successful tests
- ✗ FAILED for failed tests with error details
- Summary with total, passed, and failed test counts

#### Exit codes

- `0` - All tests passed
- `1` - One or more tests failed

## Adding New Tests

To add new integration tests:

1. Create a new test function following the naming convention `test_*`
2. Add the function name to the `tests` array in the `main()` function
3. Follow the existing pattern for error handling and output

## Troubleshooting

### Common Issues

1. **Permission denied**: Make sure the script is executable:
   ```bash
   chmod +x deployment/tests/test_env_config.sh
   ```

2. **Python path issues**: Ensure you're running from the project root directory

3. **Missing dependencies**: Install project requirements:
   ```bash
   pip install -r requirements.txt
   ```

4. **Django settings not found**: Check that `DJANGO_SETTINGS_MODULE` is correctly set

### Debug Mode

For more detailed output, you can modify the script to enable debug mode by adding:
```bash
set -x  # Enable debug tracing
```

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run Integration Tests
  run: ./deployment/tests/test_env_config.sh
```

The script returns appropriate exit codes for CI/CD systems to determine success or failure.