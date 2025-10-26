FROM python:3.12-slim

# Installing system dependencies
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
    libmediainfo0v5 \
    libmediainfo-dev \
    libzen0v5 \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for ffprobe and ffmpeg tools
RUN ln -sf /usr/bin/ffprobe /usr/local/bin/ffprobe
RUN ln -sf /usr/bin/ffmpeg /usr/local/bin/ffmpeg

# Fix libmediainfo library path
RUN ldconfig

# Setting up the working directory
WORKDIR /app

# Copying the requirements file
COPY requirements.txt .

# Installing Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copying the application code
COPY . .

# Creating directories for static files and logs
RUN mkdir -p /app/static /app/media /app/logs

# Creating a user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app

# Make entrypoint executable
RUN chmod +x /app/deployment/entrypoint.production.sh

# Collecting static files (optional, will be done at runtime)
RUN python manage.py collectstatic --noinput --settings=ok_tools.settings || true

# Opening the port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

# Command to run with production entrypoint
CMD ["/app/deployment/entrypoint.production.sh"]