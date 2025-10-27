# Architecture Refactoring Report: Source Code and Production Directory Separation

## Date
2025-10-27

## Overview
Successfully completed a fundamental architectural refactoring of the deployment system to separate source code from the production working directory. This change eliminates code duplication and ensures that Docker builds from the repository root.

## Changes Made

### 1. Docker Compose Files Refactoring

#### `deployment/docker-compose.production.yml`
- **Changed**: All service build contexts from `.` to `../../`
- **Changed**: `dockerfile` path to `deployment/production.Dockerfile`
- **Removed**: Incorrect volume mounts (`../ok_tools:/app`)
- **Services affected**: `web`, `celery_worker`, `celery_beat`

#### `deployment/docker-compose.production.no-nginx.yml`
- **Changed**: All service build contexts from `.` to `../../`
- **Changed**: `dockerfile` path to `deployment/production.Dockerfile`
- **Removed**: Incorrect volume mounts (`../ok_tools:/app`)
- **Services affected**: `web`, `celery_worker`, `celery_beat`

### 2. Dockerfile Refactoring

#### `deployment/production.Dockerfile`
- **Removed**: All `../` prefixes from `COPY` commands
- **Changed**: Direct paths from repository root (e.g., `COPY requirements.txt .`)
- **Changed**: Entrypoint path to `/app/deployment/entrypoint.production.sh`
- **Reason**: Build context is now repository root, so paths are direct

### 3. Installation Script Refactoring

#### `deployment/scripts/install.sh`
- **Removed**: All source code copying commands:
  - `requirements.txt`
  - `manage.py`
  - `ok_tools/` directory
  - Application directories (`inventory`, `dashboard`, `licenses`, etc.)
- **Removed**: Redundant deployment file copying
- **Kept**: 
  - Production directory creation
  - `docker-compose.yml` copying to working directory
  - `.env` file generation
  - Data directories creation (`data/`, `logs/`, `backups/`, `media/`)
  - Nginx configuration files (for production mode)

### 4. .dockerignore Creation

Created `.dockerignore` in repository root with exclusions:
```
# Git files
.git/, .gitignore

# Production data directories
ok_tools_production/, data/, logs/, backups/, media/

# Python cache
__pycache__/, *.pyc

# IDE/OS files
.idea/, .vscode/, .DS_Store

# Environment files
.env, _secrets.txt

# Documentation
deployment/reports/
```

## Architecture Benefits

### Before
```
Repository Root
└── deployment/
    └── scripts/install.sh
        ├── Copies source code → ok_tools_production/
        ├── Copies deployment files → ok_tools_production/
        └── Docker builds from ok_tools_production/
```

### After
```
Repository Root (Build Context)
├── Source Code (ok_tools/, inventory/, etc.)
├── deployment/
│   ├── docker-compose.production.yml
│   └── production.Dockerfile
└── ok_tools_production/ (Working Directory Only)
    ├── docker-compose.yml (copied)
    ├── .env (generated)
    └── data/ (runtime volumes)
```

## Key Improvements

1. **No Code Duplication**: Source code stays in repository, not copied to production directory
2. **Single Source of Truth**: Docker builds directly from repository
3. **Faster Deployments**: No need to copy large directories during installation
4. **Cleaner Separation**: Working directory contains only configuration and data
5. **Better Version Control**: Changes in repository immediately reflected in builds
6. **Reduced Disk Usage**: Source code not duplicated on production server

## Technical Details

### Build Context Path
When `install.sh` runs from `deployment/scripts/`, the context `../../` correctly points to repository root:
```
deployment/scripts/install.sh (current location)
↓
../../ (context path in docker-compose.yml)
↓
/Users/pavlo/coding/ok_tools_dev (repository root)
```

### Docker Compose Workflow
1. Script copies `docker-compose.yml` to working directory
2. User runs `docker compose up` from working directory
3. Docker Compose uses `context: ../../` to find repository root
4. Dockerfile builds using files from repository root
5. Runtime volumes mount from working directory

## Git Commit

**Commit Hash**: 3167243  
**Branch**: version_3  
**Message**: "Refactor: Separate source code from production directory"  
**Files Changed**: 5 files, +71 insertions, -77 deletions

## Testing Recommendations

1. **Clean Installation Test**:
   ```bash
   cd deployment/scripts
   ./install.sh
   ```

2. **Verify Build Context**:
   ```bash
   cd ok_tools_production
   docker compose build --no-cache
   ```

3. **Check Running Containers**:
   ```bash
   docker compose ps
   docker compose logs web
   ```

4. **Verify No Source Code in Working Directory**:
   ```bash
   ls ok_tools_production/
   # Should only contain: docker-compose.yml, .env, data/, logs/, etc.
   # Should NOT contain: ok_tools/, inventory/, manage.py, requirements.txt
   ```

## Migration Path for Existing Installations

For existing installations that have duplicated source code:

1. **Backup current installation**
2. **Pull latest changes** from version_3 branch
3. **Remove old source code** from production directory:
   ```bash
   cd ok_tools_production
   rm -rf ok_tools/ inventory/ dashboard/ licenses/ media_files/ planung/ projects/ registration/ rental/ manage.py requirements.txt
   ```
4. **Rebuild containers**:
   ```bash
   docker compose down
   docker compose up -d --build
   ```

## Conclusion

This architectural refactoring establishes a cleaner, more maintainable deployment structure that follows Docker best practices. The separation of concerns between source code (repository) and runtime data (working directory) improves deployment efficiency and reduces complexity.

## Next Steps

- Monitor first production deployment with new architecture
- Update deployment documentation
- Create rollback procedure if needed
- Consider adding deployment validation script