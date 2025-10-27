# OK Tools Installation Guide

This guide describes the interactive installation process for OK Tools using the new environment-based configuration system. This method provides a guided setup for deploying OK Tools in production environments using Docker containers.

## Migration to ENV-based Configuration

OK Tools has migrated from hybrid .cfg/.env configuration to pure environment variables (.env) for better security, maintainability, and 12-factor app compliance.

**Key Benefits:**
- Single source of truth for configuration
- Better integration with Docker/Kubernetes
- Improved secret management
- Type-safe configuration with validation
- Zero-downtime migration path

**For existing deployments with .cfg files:** See [Migration Guide](#migration-guide-for-existing-deployments) section.

**Complete migration documentation:** See [Migration Summary Report](reports/migration-summary-final.md:1)

## Getting Started

The installation script automates the setup process and guides you through configuration choices. To start the installation:

```bash
./deployment/scripts/install.sh
```

The script will guide you through the installation process with interactive prompts.

## Installation Process

### 1. Choose Installation Type

The script offers three installation types:

- **Production**: Public server with domain name, Nginx web server, and SSL certificates
- **Local Network**: LAN access without domain or SSL (for internal networks)
- **Localhost**: Development on a single machine

### 2. Choose Configuration Mode

After selecting the installation type, you can choose between:

- **Use existing template**: Select from available configuration templates in `deployment/configs/`
- **Manual configuration**: Answer prompts to configure the application step-by-step

#### Using Templates

If you choose template-based installation, the script will:

- Display available templates from `deployment/configs/`
- Prompt you to select a template
- Ask for required values to replace `__REPLACE_ME__` placeholders in the template
- Create a `.env` file with your configured values

#### Manual Configuration

If you choose manual configuration, you'll be prompted for:

- Organization details (name, website, contact information)
- Database password (auto-generated if left empty)
- Superuser credentials (username, email, password)
- Django settings including allowed hosts based on installation type
- SSL configuration (for Production mode only)

### 3. File Creation and Configuration

The installation script performs the following actions:

- Creates a production directory at `../ok_tools_production`
- Creates necessary subdirectories: `data/postgres`, `data/static`, `data/media`, `logs`, `backups`
- Generates a `.env` configuration file with your settings
- Copies the appropriate Docker Compose file based on installation type:
  - Production: Uses `docker-compose.production.yml` with Nginx
  - Local Network/Localhost: Uses `docker-compose.production.no-nginx.yml`
- Copies necessary files: `Dockerfile`, `entrypoint.sh`, and Nginx configuration files (for Production)

## New Configuration Structure

### Environment Variables Organization

The new configuration system uses environment variables organized into logical groups:

#### Core Django Settings
- `DJANGO_SECRET_KEY` - Secret key for Django (required)
- `DEBUG` - Enable/disable debug mode
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts
- `DJANGO_LOG_LEVEL` - Logging level (INFO, DEBUG, etc.)

#### Database Configuration
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password (required)
- `DB_HOST` - Database host
- `DB_PORT` - Database port

#### Email Configuration
- `EMAIL_HOST` - SMTP server hostname
- `EMAIL_PORT` - SMTP server port
- `EMAIL_USE_TLS` - Use TLS encryption
- `EMAIL_HOST_USER` - SMTP username
- `EMAIL_HOST_PASSWORD` - SMTP password
- `DEFAULT_FROM_EMAIL` - Default from email address

#### Organization Settings
- `ORG_NAME` - Organization full name
- `ORG_SHORT_NAME` - Organization short name
- `ORG_WEBSITE` - Organization website
- `ORG_EMAIL` - Organization email
- `ORG_PHONE` - Organization phone
- `ORG_ADDRESS` - Organization address

#### Celery Configuration
- `CELERY_BROKER_URL` - Redis broker URL
- `CELERY_RESULT_BACKEND` - Redis result backend
- `CELERY_BEAT_*` - Scheduled task configurations

**For complete reference:** See [Environment Variables Reference](docs/ENV_VARIABLES.md:1)

## Starting the Application

After configuration is complete, the script automatically starts Docker containers using:

```bash
docker compose up -d
```

This command runs all required services in the background.

## Next Steps

After installation, you should:

1. **Check container status:**
   ```bash
   docker compose ps
   ```

2. **View application logs:**
   ```bash
   docker compose logs -f web
   ```

3. **Access the admin panel:**
   - Production with SSL: `https://your-domain.com/admin`
   - Production without SSL: `http://your-domain.com/admin`
   - Local Network: `http://server-ip:8000/admin`
   - Localhost: `http://localhost:8000/admin`
   
   Use the superuser credentials you configured during installation.

4. **Update the application:**
   ```bash
   ./deployment/scripts/update.sh
   ```

5. **Configure post-deployment settings:**
   ```bash
   ./deployment/scripts/configure.sh
   ```

## Migration Guide for Existing Deployments

### Automated Migration

For existing deployments using .cfg files:

1. **Run the migration script:**
   ```bash
   ./deployment/scripts/migrate-config-to-env.sh
   ```

2. **Review the generated .env file:**
   ```bash
   nano deployment/configs/your-env-file.env
   # Update any __REPLACE_ME__ placeholders
   # Verify all values are correct
   ```

3. **Deploy with new configuration:**
   ```bash
   docker compose -f deployment/docker-compose.production.yml --env-file deployment/configs/your-env-file.env up -d
   ```

### Manual Migration

1. **Copy the appropriate template:**
   ```bash
   cp deployment/configs/ok-bayern.env.template .env
   ```

2. **Edit the configuration:**
   ```bash
   nano .env
   # Set all required variables
   # Replace __REPLACE_ME__ placeholders
   ```

3. **Test the configuration:**
   ```bash
   docker compose --env-file .env config
   ```

### Emergency Rollback

If issues occur after migration:

1. **Run the rollback script:**
   ```bash
   ./deployment/scripts/rollback.sh
   ```

2. **Follow the prompts** to restore the previous configuration

3. **Verify services** are running correctly after rollback

**For detailed rollback procedures:** See [Rollback Script Report](reports/rollback-script-report.md:1)

## Quick Start with New .env Files

### For New Deployments

1. **Copy and customize template:**
   ```bash
   cp deployment/configs/ok-bayern.env.template .env
   nano .env  # Replace __REPLACE_ME__ values
   ```

2. **Start services:**
   ```bash
   docker compose -f deployment/docker-compose.production.yml up -d
   ```

### For Development

1. **Create development .env:**
   ```bash
   cp deployment/configs/ok-bayern.env.template .env
   # Set DEBUG=True and development values
   ```

2. **Run with development configuration:**
   ```bash
   docker compose -f deployment/docker-compose.production.yml --env-file .env up -d
   ```

## Post-Installation

- Check that all containers are running properly
- Verify you can access the application through your chosen URL
- Log into the admin panel to configure additional settings
- Set up any required integrations or additional configuration
- Review and customize the application settings as needed

## Testing Configuration

### Validate .env File
```bash
docker compose --env-file .env config
```

### Run Django Checks
```bash
docker compose exec web python manage.py check --deploy
```

### Run Integration Tests
```bash
./deployment/tests/test_env_config.sh
```
## Проверка конфигурации

Чтобы убедиться, что Django правильно читает переменные из `.env` файла, выполните скрипт:

```bash
./deployment/scripts/check_env.sh
```

Этот скрипт выведет значения `DATABASE_URL`, `DEBUG` и `ALLOWED_HOSTS` так, как их видит Django.


## Troubleshooting

### Common Issues

1. **Permission denied on .env file:**
   ```bash
   chmod 600 .env
   ```

2. **Configuration not loading:**
   - Verify .env file is in the correct location
   - Check variable names match exactly
   - Ensure no syntax errors in .env file

3. **Database connection issues:**
   - Verify database container is running
   - Check DB_HOST, DB_PORT, and credentials
   - Ensure network connectivity between containers

4. **Emergency rollback needed:**
   ```bash
   ./deployment/scripts/rollback.sh
   ```

### Getting Help

1. Check container status: `docker compose ps`
2. Review logs: `docker compose logs -f web`
3. Verify configuration in the generated `.env` file
4. Ensure all required ports are available
5. Run integration tests: `./deployment/tests/test_env_config.sh`
6. Create an issue in the repository with a detailed description

## Documentation

- [Migration Summary Report](reports/migration-summary-final.md:1) - Complete migration documentation
- [Environment Variables Reference](docs/ENV_VARIABLES.md:1) - Full variable documentation
- [Architecture Decision](reports/config-architecture-decision.md:1) - Technical decision documentation
- [Individual Reports](reports/) - Detailed reports for each migration component

## Support

If you encounter problems during installation:

1. Check container status: `docker compose ps`
2. Review logs: `docker compose logs -f web`
3. Verify configuration in the generated `.env` file
4. Ensure all required ports are available
5. Run integration tests: `./deployment/tests/test_env_config.sh`
6. Create an issue in the repository with a detailed description
