# Server Configurations

**⚠️ Note:** This directory is optional and contains example server-specific configuration files. The main configuration templates are located in `deployment/configs/` directory.

If you don't need server-specific configurations, you can ignore this directory. The installation script uses templates from `deployment/configs/` directory.

## Files

- `env.example` - Example template file (similar to files in `deployment/configs/`)
- `README.md` - This file

## Usage (Optional)

If you want to maintain server-specific configurations separately:

1. **Copy the example file:**
   ```bash
   cp deployment/servers/env.example deployment/servers/.env
   ```

2. **Edit `.env` and replace all `__REPLACE_ME__` placeholders:**
   - `POSTGRES_PASSWORD` - Database password
   - `DJANGO_SECRET_KEY` - Django secret key
   - `ALLOWED_HOSTS` - Your domain/IP addresses
   - `SUPERUSER_PASSWORD` - Admin password
   - `EMAIL_HOST_PASSWORD` - Email SMTP password
   - Other organization-specific values

3. **Use during installation:**
   The installation script can use templates from `deployment/configs/` or you can manually copy this file to the production directory.

## Notes

- This directory is excluded from git (in `.gitignore`) if it contains sensitive `.env` files
- For most installations, use templates from `deployment/configs/` directory instead
- See [ENV_TEMPLATE.md](../docs/ENV_TEMPLATE.md) for detailed variable descriptions
