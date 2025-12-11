#!/bin/sh
set -e

# Рендерим полный конфиг в /etc/nginx/nginx.conf (перезаписывает базовый конфиг)
envsubst '${DOMAIN_NAME}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/nginx.conf

# Убираем дефолтный сервер из conf.d, если он есть
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