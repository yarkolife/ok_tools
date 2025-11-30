# Настройка Nextcloud для загрузки видео

## Быстрая настройка

### 1. Создайте сервисный аккаунт в Nextcloud

1. Войдите в Nextcloud как администратор
2. Перейдите в **Настройки** → **Пользователи**
3. Создайте нового пользователя:
   - **Имя пользователя**: `ok_tools_service` (или другое)
   - **Пароль**: создайте надежный пароль

### 2. Создайте App Password (пароль приложения)

1. Войдите как созданный пользователь (`ok_tools_service`)
2. Перейдите в **Настройки** → **Безопасность** → **Устройства и сессии**
3. Прокрутите до раздела **Пароли приложений**
4. Нажмите **Создать новый пароль приложения**
5. Введите имя: `OK Tools Video Upload`
6. **Скопируйте созданный пароль** - он показывается только один раз!
   - Формат: `xxxx-xxxx-xxxx-xxxx`

### 3. Создайте папку для загрузок

1. Войдите как `ok_tools_service`
2. Создайте папку: `Freistellungen`
3. Внутри создайте папку: `Videos`
4. Итоговый путь: `Freistellungen/Videos/`

### 4. Настройте переменные окружения

Добавьте в `.env` файл или в Docker environment:

```bash
# Включить интеграцию Nextcloud
NEXTCLOUD_ENABLED=true

# URL вашего Nextcloud (без слеша в конце)
NEXTCLOUD_URL=https://ваш-nextcloud.example.com

# Имя пользователя сервисного аккаунта
NEXTCLOUD_USERNAME=ok_tools_service

# Пароль приложения (из шага 2)
NEXTCLOUD_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Путь к папке загрузок
NEXTCLOUD_UPLOAD_FOLDER=Freistellungen/Videos
```

### 5. Выполните миграцию базы данных

В Docker контейнере:

```bash
docker compose exec web python manage.py migrate licenses
```

### 6. Перезапустите приложение

```bash
docker compose restart web
```

## Проверка работы

1. Войдите в OK Tools
2. Перейдите к созданию Freistellung (License)
3. Должна появиться секция **Video Upload**
4. Загрузите тестовое видео
5. Проверьте в Nextcloud, что файл появился в `Freistellungen/Videos/`

## Решение проблем

### Ошибка: "Nextcloud integration is disabled"
- Проверьте, что `NEXTCLOUD_ENABLED=true` в переменных окружения

### Ошибка: "401 Unauthorized"
- Проверьте правильность `NEXTCLOUD_USERNAME`
- Убедитесь, что используете App Password, а не основной пароль
- Проверьте, что пароль приложения не был отозван

### Ошибка: "404 Not Found"
- Проверьте правильность `NEXTCLOUD_URL` (без слеша в конце)
- Убедитесь, что WebDAV включен в Nextcloud
- Проверьте формат URL: `https://ваш-nextcloud.com/remote.php/dav/files/USERNAME/`

### Ошибка: "403 Forbidden"
- Проверьте права доступа к папке в Nextcloud
- Убедитесь, что сервисный аккаунт имеет права на запись

## Тестирование WebDAV вручную

Проверить доступ можно через curl:

```bash
curl -u ok_tools_service:APP_PASSWORD \
  https://ваш-nextcloud.com/remote.php/dav/files/ok_tools_service/
```

Должен вернуться XML со списком файлов.

## Отключение функции

Чтобы отключить загрузку видео:

1. Установите `NEXTCLOUD_ENABLED=false`
2. Перезапустите приложение
3. Формы загрузки видео исчезнут из интерфейса

## Безопасность

- ✅ Используйте App Password, а не основной пароль
- ✅ Ограничьте права доступа сервисного аккаунта только нужной папкой
- ✅ Используйте HTTPS для Nextcloud
- ✅ Не храните пароли в коде, только в переменных окружения

## Автоматическая очистка удаленных видео

Система автоматически проверяет и помечает удаленные из Nextcloud файлы.

Запуск вручную:
```bash
docker compose exec web python manage.py cleanup_deleted_nextcloud_videos
```

Подробная документация: `deployment/docs/NEXTCLOUD_SETUP.md`

