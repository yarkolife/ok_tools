#!/bin/sh
set -e

# Заменяем переменную в шаблоне и создаем конечный конфиг
envsubst '${DOMAIN_NAME}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/nginx.conf

# Ожидаем, пока Certbot создаст сертификаты
until [ -f /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem ]; do
  echo "Waiting for Certbot to create certificates for ${DOMAIN_NAME}..."
  sleep 5
done

echo "Certificates found. Starting Nginx..."
# Запускаем Nginx в фоновом режиме
nginx -g 'daemon off;'