FROM python:3.12-slim

# Installing system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
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
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

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

# Opening the port
EXPOSE 8000

# Command to run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--max-requests", "1000", "--max-requests-jitter", "100", "ok_tools.wsgi:application"]
