FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    libart-2.0-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    pdftk \
    gettext \
    cron \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    ffmpeg \
    libmediainfo-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for ffprobe and ffmpeg tools
RUN ln -sf /usr/bin/ffprobe /usr/local/bin/ffprobe
RUN ln -sf /usr/bin/ffmpeg /usr/local/bin/ffmpeg

# Fix libmediainfo library path
RUN ldconfig

# Set up the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copy the application code
COPY . .

# Create directories for static files and media
RUN mkdir -p /app/staticfiles /app/media

# Build arguments for user UID/GID (default to 1000 if not provided)
ARG USER_UID=1000
ARG USER_GID=1000

# Create a non-root user for security with configurable UID/GID
# This allows matching the host user's UID/GID for proper file permissions
# Remove existing user/group if they exist with different UID/GID
RUN if getent group app > /dev/null 2>&1; then \
        groupdel app || true; \
    fi && \
    if getent passwd app > /dev/null 2>&1; then \
        userdel app || true; \
    fi && \
    groupadd --gid ${USER_GID} app && \
    useradd --create-home --shell /bin/bash --uid ${USER_UID} --gid ${USER_GID} app && \
    chown -R app:app /app

# Make entrypoints executable
RUN chmod +x /app/deployment/entrypoint.production.sh
RUN chmod +x /app/deployment/entrypoint.celery.sh

# Drop root for every container built from this image (CIS Docker 4.1).
# The entrypoints only need write access to /app, which is chowned above, and
# gunicorn binds 8000, so no privileged port is involved. The celery services
# already ran as this user via `user: app` in compose.
USER app

# Expose the correct port
EXPOSE 8000



# Command to run with production entrypoint
CMD ["/app/deployment/entrypoint.production.sh"]