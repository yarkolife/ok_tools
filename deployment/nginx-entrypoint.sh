#!/bin/sh
set -e

# Рендерим конфиг сразу в /etc/nginx/conf.d (обходит default.conf из образа)
envsubst '${DOMAIN_NAME}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/nginx.conf

# Убираем дефолтный сервер, чтобы не перекрывал наш
rm -f /etc/nginx/conf.d/default.conf || true

# Ожидаем сертификаты, если домен указан
if [ -n "${DOMAIN_NAME}" ]; then
  until [ -f /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem ]; do
    echo "Waiting for Certbot to create certificates for ${DOMAIN_NAME}..."
    sleep 5
  done
  echo "Certificates found. Starting Nginx..."
else
  echo "DOMAIN_NAME is empty; skipping cert wait, starting Nginx..."
fi

nginx -g 'daemon off;'