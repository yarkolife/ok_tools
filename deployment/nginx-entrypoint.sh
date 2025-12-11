#!/bin/sh
set -e

# Определяем, является ли домен localhost или локальным IP
IS_LOCAL=false
if [ -n "${DOMAIN_NAME}" ]; then
  if [ "${DOMAIN_NAME}" = "localhost" ] || [ "${DOMAIN_NAME}" = "127.0.0.1" ] || echo "${DOMAIN_NAME}" | grep -qE '^192\.168\.|^10\.|^172\.(1[6-9]|2[0-9]|3[01])\.'; then
    IS_LOCAL=true
  fi
fi

# Рендерим базовый конфиг
envsubst '${DOMAIN_NAME}' < /etc/nginx/templates-custom/nginx.conf.template > /etc/nginx/nginx.conf.tmp

# Если это localhost/локальный IP и нет сертификатов, модифицируем конфиг для работы без SSL
if [ "$IS_LOCAL" = "true" ] && [ ! -f "/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem" ]; then
  echo "DOMAIN_NAME is localhost or local IP (${DOMAIN_NAME}) - configuring HTTP without SSL"
  
  # Создаем конфиг без HTTPS блока и без редиректа на HTTPS
  # Удаляем редирект на HTTPS и блокируем HTTPS блок
  sed -i '/# Redirect all HTTP traffic to HTTPS/,/^}/d' /etc/nginx/nginx.conf.tmp
  sed -i '/# HTTPS server/,/^}$/d' /etc/nginx/nginx.conf.tmp
  
  # Добавляем проксирование на Django в HTTP блок
  cat >> /etc/nginx/nginx.conf.tmp << 'EOF'

# HTTP server (no SSL for localhost)
server {
    listen 80;
    server_name ${DOMAIN_NAME};
    
    # Health check endpoint
    location /health {
        return 200 "OK";
        add_header Content-Type text/plain;
    }
    
    # Static files
    location /static/ {
        alias /var/www/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /var/www/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Video streaming with range support
    location ~ ^/admin/media_files/videofile/\d+/stream/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_buffering off;
        proxy_request_buffering off;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        proxy_http_version 1.1;
    }

    # Rate limiting for sensitive endpoints
    location ~ ^/(admin|api)/ {
        limit_req zone=api burst=10 nodelay;
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Login rate limiting
    location /profile/login/ {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # All other requests
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF
  
  # Заменяем DOMAIN_NAME в новом блоке
  envsubst '${DOMAIN_NAME}' < /etc/nginx/nginx.conf.tmp > /etc/nginx/nginx.conf
  rm -f /etc/nginx/nginx.conf.tmp
else
  # Для реальных доменов используем стандартный конфиг
  mv /etc/nginx/nginx.conf.tmp /etc/nginx/nginx.conf
  
  # Ожидаем сертификаты для реальных доменов
  if [ -n "${DOMAIN_NAME}" ] && [ "$IS_LOCAL" = "false" ]; then
    until [ -f /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem ]; do
      echo "Waiting for Certbot to create certificates for ${DOMAIN_NAME}..."
      sleep 5
    done
    echo "Certificates found. Nginx configuration ready."
  fi
fi

# Убираем файлы из conf.d, так как мы используем полный конфиг
rm -f /etc/nginx/conf.d/default.conf || true
rm -f /etc/nginx/conf.d/nginx.conf || true