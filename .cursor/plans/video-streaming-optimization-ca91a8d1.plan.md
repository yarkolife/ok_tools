<!-- ca91a8d1-e9ec-4cd9-a001-b451a1352603 c3606ae7-060d-42ba-98cd-2bbfb06acc7c -->
# Скрипт установки production версии на тестовый сервер

## 1. Создать скрипт `deployment/scripts/install-production-test.sh`

Интерактивный Bash скрипт со следующими функциями:

### Структура скрипта:

**Шаг 1:** Проверка Docker и Docker Compose

- Установка если отсутствуют

**Шаг 2:** Выбор конфигурации организации

- Показать доступные конфигурации из `deployment/configs/`:
  - `ok-bayern-production.cfg` (OK Bayern)
  - `okmq-production.cfg` (OK Merseburg-Querfurt)
  - `ok-nrw-production.cfg` (OK NRW)
- Интерактивный выбор (1/2/3)

**Шаг 3:** Ввод индивидуальных данных

- IP адрес сервера (автоопределение текущего)
- PostgreSQL пароль
- Django SECRET_KEY (автогенерация или ввод)
- NAS настройки:
  - IP адрес NAS
  - Share name
  - Username/password для монтирования
  - Опционально: отдельный archive NAS

**Шаг 4:** Подготовка окружения

- Создание рабочей директории `/opt/ok-tools-test/`
- Копирование файлов из `deployment/docker/`:
  - `Dockerfile.production`
  - `docker-compose.production.yml`
  - `nginx.conf`
- Копирование всего кода приложения

**Шаг 5:** Создание конфигурации

- Копировать выбранный cfg из `deployment/configs/`
- Заменить плейсхолдеры:
  - `YOUR-PRODUCTION-SECRET-KEY-HERE` → сгенерированный/введённый SECRET_KEY
  - `YOUR-DATABASE-PASSWORD` → введённый пароль БД
  - `allowed_hosts` → добавить IP адрес сервера
  - NAS пути если изменились
- Сохранить как `/opt/ok-tools-test/docker-production.cfg`

**Шаг 6:** Настройка NAS монтирования

- Установка `cifs-utils` если нужно
- Создание точек монтирования `/mnt/nas/playout`, `/mnt/nas/archive`
- Создание credentials файлов
- Добавление в `/etc/fstab` с параметрами оптимизации:
  ```
  rsize=1048576,wsize=1048576,vers=3.0
  ```

- Монтирование

**Шаг 7:** Настройка docker-compose

- Обновить `docker-compose.production.yml`:
  - Изменить порт на `8000:8000` (без nginx для теста)
  - Добавить volumes для NAS: `/mnt/nas/playout`, `/mnt/nas/archive`
  - Установить `POSTGRES_PASSWORD` из env
  - Указать правильный путь к конфигурации

**Шаг 8:** Запуск контейнеров

- `docker compose build`
- `docker compose up -d`
- Ожидание запуска (проверка health)

**Шаг 9:** Инициализация Django

- Применение миграций: `docker compose exec web python manage.py migrate`
- Создание суперпользователя: `docker compose exec web python manage.py createsuperuser`
- Сбор статики: `docker compose exec web python manage.py collectstatic --noinput`

**Шаг 10:** Вывод итоговой информации

- URL доступа: `http://{IP}:8000`
- Админка: `http://{IP}:8000/admin/`
- Команды для управления
- Следующие шаги (настройка Storage Locations)

## 2. Дополнительные файлы

### `deployment/scripts/update-production-test.sh`

Скрипт обновления:

- Git pull
- Rebuild контейнеров
- Миграции
- Перезапуск

### `deployment/scripts/stop-production-test.sh`

Скрипт остановки и удаления:

- `docker compose down`
- Опционально: удаление volumes
- Размонтирование NAS

## 3. README для скриптов

`deployment/scripts/README.md` с инструкциями:

- Требования
- Использование скриптов
- Troubleshooting
- Примеры

## Технические детали:

- Скрипт должен быть идемпотентным (можно запускать повторно)
- Проверки на каждом шаге с rollback при ошибках
- Цветной вывод для удобства
- Логирование в файл
- Поддержка Debian/Ubuntu

### To-dos

- [ ] Создать deployment/scripts/install-production-test.sh с интерактивной установкой
- [ ] Создать deployment/scripts/update-production-test.sh для обновления
- [ ] Создать deployment/scripts/stop-production-test.sh для остановки
- [ ] Создать deployment/scripts/README.md с документацией