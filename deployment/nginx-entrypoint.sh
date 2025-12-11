#!/bin/sh
set -e

# Рендерим полный конфиг в /etc/nginx/nginx.conf (перезаписывает базовый конфиг)
envsubst '${DOMAIN_NAME}' < /etc/nginx/templates-custom/nginx.conf.template > /etc/nginx/nginx.conf

# Убираем файлы из conf.d, так как мы используем полный конфиг
rm -f /etc/nginx/conf.d/default.conf || true
rm -f /etc/nginx/conf.d/nginx.conf || true

# Ожидаем сертификаты, если домен указан
if [ -n "${DOMAIN_NAME}" ]; then
  until [ -f /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem ]; do
    echo "Waiting for Certbot to create certificates for ${DOMAIN_NAME}..."
    sleep 5
  done
  echo "Certificates found. Nginx configuration ready."
else
  echo "DOMAIN_NAME is empty; skipping cert wait."
fi