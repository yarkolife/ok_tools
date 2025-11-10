# Server Configurations

This directory contains server-specific environment configuration files.

## ⚠️ Important Security Notice

**This directory is excluded from git** (in `.gitignore`) because it contains sensitive information like passwords and secret keys.

## Files

- `.env.example` - Template file with placeholders (safe to commit)
- `.env` - Your actual server configuration (NOT tracked in git, contains real passwords)

## Usage

1. **Copy the example file:**
   ```bash
   cp deployment/servers/env.example deployment/servers/.env
   ```

2. **Edit `.env` and replace all `__REPLACE_ME__` placeholders:**
   - `POSTGRES_PASSWORD` - Database password
   - `DJANGO_SECRET_KEY` - Django secret key (generate with: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`)
   - `ALLOWED_HOSTS` - Your domain/IP addresses
   - `SUPERUSER_PASSWORD` - Admin password
   - `EMAIL_HOST_PASSWORD` - Email SMTP password
   - Other organization-specific values

3. **Copy to production directory:**
   ```bash
   cp deployment/servers/.env /path/to/production/.env
   ```

## Pre-configured Settings

The `.env.example` file is pre-configured with:
- ✅ NAS mount path: `/mnt/nas` (read-only)
- ✅ Organization: OKMQ defaults
- ✅ Celery result backend: `django-db` (results visible in admin)
- ✅ All required variables with sensible defaults

## Notes

- Never commit `.env` files to git
- Keep backups of your `.env` file in a secure location
- Use different `.env` files for different environments (dev, staging, production)
- See [ENV_TEMPLATE.md](../docs/ENV_TEMPLATE.md) for detailed variable descriptions

