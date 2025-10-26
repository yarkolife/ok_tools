# OK Tools Installation Guide

This guide describes the interactive installation process for OK Tools using the new installation script. This method provides a guided setup for deploying OK Tools in production environments using Docker containers.

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
- Create the `.env` file with your configured values

#### Manual Configuration

If you choose manual configuration, you'll be prompted for:

- Organization details (name, website, contact information)
- Database password (auto-generated if left empty)
- Superuser credentials (username, email, password)
- Django settings including allowed hosts based on installation type
- SSL configuration (for Production mode only)

### 3. File Creation and Configuration

The installation script performs the following actions:

- Creates the production directory at `../ok_tools_production`
- Creates necessary subdirectories: `data/postgres`, `data/static`, `data/media`, `logs`, `backups`
- Generates the `.env` configuration file with your settings
- Copies the appropriate Docker Compose file based on installation type:
 - Production: Uses `docker-compose.production.yml` with Nginx
  - Local Network/Localhost: Uses `docker-compose.production.no-nginx.yml`
- Copies necessary files: `Dockerfile`, `entrypoint.sh`, and Nginx configuration files (for Production)

## Starting the Application

After configuration is complete, the script automatically starts the Docker containers using:

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

## Post-Installation

- Check that all containers are running properly
- Verify you can access the application through your chosen URL
- Log into the admin panel to configure additional settings
- Set up any required integrations or additional configuration
- Review and customize the application settings as needed

## Support

If you encounter problems during installation:

1. Check container status: `docker compose ps`
2. Review logs: `docker compose logs -f web`
3. Verify configuration in the generated `.env` file
4. Ensure all required ports are available
5. Create an issue in the repository with a detailed description
