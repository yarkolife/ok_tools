# Анализ конфигурационных файлов OK-Tools Bayern

> Источники: [deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template), [deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg), [ok_tools/settings.py](ok_tools/settings.py)
>
> Ключевые ссылки на конструкции кода: [configparser.RawConfigParser()](ok_tools/settings.py:29), [config.get()](ok_tools/settings.py:36), [config.getboolean()](ok_tools/settings.py:40), [os.getenv()](ok_tools/settings.py:46), [os.environ.get()](ok_tools/settings.py:283)

## 1. Сравнение ok-bayern.env.template vs ok-bayern-production.cfg

Ниже приводится сравнение с учетом смыслового соответствия ключей (нормализуем имена: приводим к нижнему регистру и сопоставляем поля одного домена, например `ORG_NAME` ↔ `organization.name`, `DEBUG` ↔ `django.debug`). Дополнительно указываются типы данных, примеры значений и примечания.

### 1.1 Переменные только в .cfg

| Секция/Ключ (.cfg) | Тип | Пример значения | Примечание/Источник |
|---|---|---|---|
| organization.organization_owner | string | OK Bayern | Владелец организации ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:20)) |
| organization.broadcast_start | time HH:MM | 18:00 | Время начала блока вещания ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:23)) |
| organization.broadcast_end | time HH:MM | 19:45 | Время окончания ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:24)) |
| peertube_channel | string | (пусто) | Идентификатор канала PeerTube ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:29)) |
| nas_storage.archive_unc_path | path (UNC) | \\\\192.168.1.100\\Archive | UNC путь для архивов (Windows) ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:35)) |
| nas_storage.playout_unc_path | path (UNC) | \\\\192.168.1.101\\Playout | UNC путь для плейаута ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:36)) |
| django.language | string | de-de | Язык интерфейса ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:47)) |
| django.timezone | string | Europe/Berlin | Часовой пояс ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:48)) |
| django.static | path | /opt/ok-tools/staticfiles/ | STATIC_ROOT ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:49)) и [config.get()](ok_tools/settings.py:189) |
| django.media | path | /opt/ok-tools/media/ | MEDIA_ROOT ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:50)) и [config.get()](ok_tools/settings.py:192) |
| django.email_host | string | smtp.your-provider.de | SMTP хост ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:51)) |
| django.email_port | int | 587 | SMTP порт ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:52)) |
| django.email_use_tls | bool | True | TLS для SMTP ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:53)) |
| django.email_host_user | string | noreply@ok-bayern.de | SMTP пользователь ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:54)) |
| django.email_host_password | string | YOUR-SMTP-PASSWORD | SMTP пароль ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:55)) |
| django.default_from_email | string | noreply@ok-bayern.de | Отправитель по умолчанию ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:56)) |
| django.mail_dev_settings | bool | False | Переключатель dev-почты ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:57)) и [config.getboolean()](ok_tools/settings.py:234) |
| django.use_secure_settings | bool | True | Включает secure-настройки ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:58)) и блок use_secure_settings ([config.getboolean()](ok_tools/settings.py:156)) |
| media.archive_path | path | /mnt/nas/archive/ | Путь архива ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:67)) |
| media.playout_path | path | /mnt/nas/playout/ | Путь плейаута ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:71)) |
| media.auto_scan | bool | False | Автосканирование медиа ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:74)) |
| media.auto_copy_on_schedule | bool | True | Копировать на плейаут при сохранении сетки ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:77)) |
| logging.level | enum | INFO | Уровень логирования ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:80)) |
| logging.file | path | /app/logs/oktools.log | Файл логов ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:81)) |
| bootstrap.version | string | 5.3.3 | Версия Bootstrap ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:85)) и [config.get()](ok_tools/settings.py:367) |
| bootstrap.icons_version | string | 1.11.0 | Версия Bootstrap Icons ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:88)) и [config.get()](ok_tools/settings.py:369) |
| api.page_size | int | 20 | Пагинация API ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:92)) и [REST_FRAMEWORK](ok_tools/settings.py:216) |
| api.anon_rate_limit | string | 100/hour | Рейтлимит анонимов ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:95)) |
| api.user_rate_limit | string | 1000/hour | Рейтлимит авторизованных ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:98)) |
| security.session_timeout | int (sec) | 1200 | Таймаут сессии ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:102)) |
| security.password_min_length | int | 8 | Минимальная длина пароля ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:105)) |
| security.csrf_cookie_age | int (sec) | 31449600 | Срок жизни CSRF ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:108)) |
| video.supported_formats | csv | mp4,mov,mpeg,mpg | Допустимые форматы ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:112)) |
| video.screen_board_duration | int (sec) | 20 | Длительность экранной заставки ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:115)) и [config.getint()](ok_tools/settings.py:259) |
| i18n.default_language | string | de | Базовый язык ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:119)) |
| i18n.supported_languages | csv | de,en | Список языков ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:122)) |
| i18n.locale_paths | path | ok_tools/locale | Пути локалей ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:125)) |
| i18n.phone_region | string | DE | Регион телефонов ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:127)) и [config.get()](ok_tools/settings.py:225) |
| i18n.date_format | strftime | %d.%m.%Y | Формат даты ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:129)) и [config.get()](ok_tools/settings.py:228) |
| static.storage_backend | dotted path | whitenoise.storage.CompressedManifestStaticFilesStorage | Бэкенд статики ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:132)) |
| static.static_url | path segment | static/ | Префикс URL статики ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:135)) |
| cache.backend | dotted path | django.core.cache.backends.locmem.LocMemCache | Бэкенд кеша ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:139)) |
| cache.timeout | int (sec) | 300 | Таймаут кеша ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:142)) |
| celery.broker_url | url | redis://localhost:6379/0 | Брокер Celery ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:146)) и [config.get()](ok_tools/settings.py:373) |
| celery.result_backend | url | redis://localhost:6379/0 | Результаты Celery ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:149)) и [config.get()](ok_tools/settings.py:374) |
| celery_beat.expire_rentals_schedule | cron | */30 * * | План задач (истечение аренды) ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:154)) и [parse_crontab()](ok_tools/settings.py:385) |
| celery_beat.cleanup_old_backups_schedule | cron | 0 2 * * * | Уборка бэкапов ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:158)) |
| celery_beat.run_backup_db_schedule | cron | 0 3 * * * | Бэкап БД ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:162)) |
| celery_beat.auto_scan_schedule | cron | 0 */2 * * * | Автоскан медиа ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:166)) |
| celery_beat.link_orphan_licenses_schedule | cron | 0 4 * * * | Связка сиротских лицензий ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:168)) |
| celery_beat.sync_licenses_videos_schedule | cron | 0 5 * * * | Синхронизация лицензий/видео ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:170)) |
| celery_Beat.update_video_metadata_schedule | cron | 0 1 1 * * | Метаданные видео ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:172)) |

### 1.2 Переменные только в .env.template

| Переменная (.env) | Тип | Пример значения | Примечание/Источник |
|---|---|---|---|
| POSTGRES_DB | string | oktools | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:9)) |
| POSTGRES_USER | string | oktools | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:10)) |
| POSTGRES_PASSWORD | string | __REPLACE_ME__ | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:11)) |
| DATABASE_URL | url | postgresql://oktools:...@db:5432/oktools | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:12)) |
| DJANGO_SETTINGS_MODULE | string | ok_tools.settings | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:17)) |
| DJANGO_SECRET_KEY | string | __REPLACE_ME__ | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:18)) |
| DEBUG | bool | False | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:19)) |
| ALLOWED_HOSTS | csv | localhost,127.0.1,__REPLACE_ME__ | Комма-сепаратор (в .cfg — пробел) ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:20)) |
| ORG_NAME | string | Bayern Community Media Organization e.V. | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:25)) |
| ORG_SHORT_NAME | string | Bayern CMO | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:26)) |
| ORG_WEBSITE | url | https://bayern-your-domain.com | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:27)) |
| ORG_EMAIL | email | info@bayern-your-domain.com | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:28)) |
| ORG_ADDRESS | multiline | Bayern Street 123\nBayern City, Postal Code | Экранированные переводы строк ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:29)) |
| ORG_PHONE | string | +49 123 456789 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:30)) |
| ORG_FAX | string | +49 123 456790 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:31)) |
| ORG_DESCRIPTION | string | Welcome to our Bayern Community Media Organization! | Текст приветствия ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:32)) |
| ORG_OPENING_HOURS | multiline | Mon: 13:00 – 16:00\nTue – Thu: 10:00 – 18:00\nFri: 10:00 – 16:00 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:33)) |
| STATE_MEDIA_INSTITUTION | string | MSA | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:34)) |
| SUPERUSER_USERNAME | string | admin | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:39)) |
| SUPERUSER_EMAIL | email | admin@bayern-your-domain.com | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:40)) |
| SUPERUSER_PASSWORD | string | __REPLACE_ME__ | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:41)) |
| PYTHONPATH | path | /app | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:46)) |
| PYTHONUNBUFFERED | int/bool | 1 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:47)) |
| GUNICORN_WORKERS | int | 4 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:52)) |
| GUNICORN_THREADS | int | 2 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:53)) |
| GUNICORN_TIMEOUT | int (sec) | 120 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:54)) |
| GUNICORN_MAX_REQUESTS | int | 1000 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:55)) |
| GUNICORN_MAX_REQUESTS_JITTER | int | 100 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:56)) |
| REDIS_URL | url | redis://redis:6379/0 | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:61)) |
| NAS_PLAYOUT_PATH | path | /mnt/nas/playout | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:67)) |
| NAS_ARCHIVE_PATH | path | /mnt/nas/archive | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:66)) |
| NAS_MOUNT_ENABLED | bool | false | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:68)) |
| SSL_ENABLED | bool | false | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:73)) |
| SSL_CERT_PATH | path | /etc/nginx/ssl/cert.pem | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:74)) |
| SSL_KEY_PATH | path | /etc/nginx/ssl/key.pem | ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:75)) |
| LOG_LEVEL | enum | info | Уровень логов для внешних сервисов ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:80)) |
| BACKUP_DIR | path | /app/backups | Используется в settings через `os.environ.get()` ([deployment/configs/ok-bayern.env.template](deployment/configs/ok-bayern.env.template:85), [os.environ.get()](ok_tools/settings.py:283)) |

### 1.3 Общие переменные (семантическое совпадение)

| Домены | .env имя | .cfg секция/ключ | Тип | Пример (.env / .cfg) | Примечание |
|---|---|---|---|---|---|
| Django: режим и доступ | DEBUG | django.debug | bool | False / False | [config.getboolean()](ok_tools/settings.py:40) |
| Django: хосты | ALLOWED_HOSTS | django.allowed_hosts | list (csv / space) | `localhost,127.0.1,example.com` / `ok-bayern.de www.ok-bayern.de` | Разный разделитель |
| Django: секрет | DJANGO_SECRET_KEY | django.secret_key | string | `__REPLACE_ME__` / `YOUR-PRODUCTION-SECRET-KEY-HERE` | [config.get()](ok_tools/settings.py:36) |
| База данных: имя | POSTGRES_DB | django.db_name | string | oktools / oktools_bayern | |
| База данных: пользователь | POSTGRES_USER | django.db_user | string | oktools / oktools | |
| База данных: пароль | POSTGRES_PASSWORD | django.db_pw | string | `__REPLACE_ME__` / `YOUR-DATABASE-PASSWORD` | |
| Организация: имя | ORG_NAME | organization.name | string | ... / Offener Kanal Bayern e.V. | |
| Организация: кратко | ORG_SHORT_NAME | organization.short_name | string | ... / OK Bayern | |
| Организация: сайт | ORG_WEBSITE | organization.website | url | ... / https://ok-bayern.de | |
| Организация: email | ORG_EMAIL | organization.email | email | ... / info@ok-bayern.de | |
| Организация: адрес | ORG_ADDRESS | organization.address | multiline | ... / многострочно | |
| Организация: телефон | ORG_PHONE | organization.phone | string | ... / +49 89 123456 | |
| Организация: факс | ORG_FAX | organization.fax | string | ... / +49 89 123457 | |
| Организация: описание | ORG_DESCRIPTION | organization.description | string | ... / Willkommen... | |
| Организация: часы | ORG_OPENING_HOURS | organization.opening_hours | multiline | ... / многострочно | |
| Организация: СМИ | STATE_MEDIA_INSTITUTION | organization.state_media_institution | string | MSA / BLM | |
| Медиа: архив | NAS_ARCHIVE_PATH | media.archive_path | path | /mnt/nas/archive / /mnt/nas/archive/ | Тот же смысл |
| Медиа: плейаут | NAS_PLAYOUT_PATH | media.playout_path | path | /mnt/nas/playout / /mnt/nas/playout/ | Тот же смысл |
| Логи: уровень | LOG_LEVEL | logging.level | enum | info / INFO | Разный регистр; в Django используется [DJANGO_LOG_LEVEL](ok_tools/settings.py:46) |

Примечание: `DATABASE_URL` в `.env` агрегирует хост/порт/пользователь/пароль, но в `.cfg` эти параметры разделены (`db_host`, `db_port`, `db_user`, `db_pw`).

## 2. Переменные окружения в ok_tools/settings.py

### 2.1 Полный список ENV переменных

| Переменная | Где читается | Тип | Значение по умолчанию | Пример | Примечание |
|---|---|---|---|---|---|
| OKTOOLS_CONFIG_FILE | [os.environ](ok_tools/settings.py:30) | path | отсутствует (если не задано) | `/opt/ok-tools/ok-bayern-production.cfg` | Определяет путь к .cfg; при отсутствии — включается режим fallback ([configparser.RawConfigParser()](ok_tools/settings.py:29)) |
| DJANGO_LOG_LEVEL | [os.getenv()](ok_tools/settings.py:46) | enum | `INFO` | `DEBUG` / `WARNING` | Используется в настройке логирования (форматтеры/handlers) |
| BACKUP_DIR | [os.environ.get()](ok_tools/settings.py:283) | path | `config['django']['backup_dir']` или `backups/` | `/app/backups` | Приоритет: ENV → .cfg → fallback |

### 2.2 Переменные с значениями по умолчанию

- DJANGO_LOG_LEVEL: `INFO` ([os.getenv()](ok_tools/settings.py:46)).
- BACKUP_DIR: если нет в ENV и .cfg, то `backups/` ([os.environ.get()](ok_tools/settings.py:283), [config.get()](ok_tools/settings.py:283)).
- OKTOOLS_CONFIG_FILE: отсутствует — будет предупреждение и применены встроенные значения/фолбэки ([logger.warning()](ok_tools/settings.py:33)).

### 2.3 Обязательные переменные

- В текущей реализации обязательных ENV-переменных нет: все три читаемые переменные имеют безопасные фолбэки или отключаемы (путь к .cfg не обязателен, но крайне рекомендуется для production).

## 3. Перекрестный анализ и рекомендации

### 3.1 Отсутствующие переменные в .env.template (из settings.py)

| Переменная | Статус в .env.template | Рекомендация |
|---|---|---|
| OKTOOLS_CONFIG_FILE | отсутствует | Добавить ключ с абсолютным путем на образце (например, `/opt/ok-tools/deployment/configs/ok-bayern-production.cfg`). Это упростит загрузку настроек через [config.get()](ok_tools/settings.py:36). |
| DJANGO_LOG_LEVEL | отсутствует (есть `LOG_LEVEL`) | Добавить `DJANGO_LOG_LEVEL` для согласованности с Django-логгером. Либо привести `LOG_LEVEL` к использованию в Django через маппинг. |
| BACKUP_DIR | присутствует | Соответствует использованию в [os.environ.get()](ok_tools/settings.py:283). |

### 3.2 Отсутствующие переменные в .cfg (из settings.py)

| Ключ .cfg (ожидается) | Статус в .cfg | Где используется | Рекомендация |
|---|---|---|---|
| django.backup_dir | отсутствует | [os.environ.get() → config.get()](ok_tools/settings.py:283) | Добавить `backup_dir`, например `/opt/ok-tools/backups/`, чтобы не полагаться на ENV и fallback. |

Дополнительно: синхронизация значений

- Разделители ALLOWED_HOSTS: в `.env` — запятая, в `.cfg` — пробел. Рекомендуется унифицировать формат и реализацию парсинга (либо всегда пробел в .cfg, а `.env` парсить через замену запятой на пробел перед разбором).

- Redis/Celery: в `.env` присутствует единый `REDIS_URL`, а в `.cfg` — раздельные `celery.broker_url` и `celery.result_backend`. Рекомендуется: если `REDIS_URL` задан, а `.cfg` пуст — генерировать значения для Celery из ENV либо добавить два отдельных ключа в `.env` для симметрии.

- NAS пути: в `.env` используются POSIX пути (`NAS_ARCHIVE_PATH`/`NAS_PLAYOUT_PATH`), в `.cfg` есть UNC-подсказки (`nas_storage.*`) и POSIX (`media.*`). Рекомендуется зафиксировать источник истины (POSIX в контейнере) и описать это в README, UNC — как подсказку для клиентских систем.

- Баг формата: секция `[bootstrap]` в .cfg записана как `bootstrap]` ([deployment/configs/ok-bayern-production.cfg](deployment/configs/ok-bayern-production.cfg:83)). Исправить на `[bootstrap]`.

- Cron-формат: `expire_rentals_schedule` содержит 3 поля (`*/30 * *`). [parse_crontab()](ok_tools/settings.py:385) допускает разное число полей, но для единообразия лучше 5-польный формат: `*/30 * * * *`.

### 3.3 Рекомендации по синхронизации

1. Добавить в `.env.template` переменные `OKTOOLS_CONFIG_FILE` и `DJANGO_LOG_LEVEL` (значение по умолчанию `INFO`).
2. В `.cfg` добавить ключ `django.backup_dir` для согласования с [BACKUP_DIR](ok_tools/settings.py:283).
3. Унифицировать ALLOWED_HOSTS: хранить в `.cfg` как пробел-разделённый список, а в `.env` — либо также пробелами, либо обеспечить преобразование.
4. Ввести соответствие между `REDIS_URL` и `celery.broker_url/result_backend`; документировать приоритет.
5. Исправить секцию `[bootstrap]`, сверить версии Bootstrap/CDN с [BOOTSTRAP_CDN_URL](ok_tools/settings.py:368) и [BOOTSTRAP_ICONS_URL](ok_tools/settings.py:370).
6. Проверить email-настройки при `mail_dev_settings=False` ([EMAIL_BACKEND](ok_tools/settings.py:238), [EMAIL_*](ok_tools/settings.py:240-247)).

## Приложение: Краткая схема источников конфигурации

```mermaid
flowchart TD
    A[Environment (.env)] -->|OKTOOLS_CONFIG_FILE| B[settings.py]
    B -->|configparser| C[Production .cfg]
    A -->|DJANGO_LOG_LEVEL, BACKUP_DIR| B
    C -->|django.*, organization.*, media.*, celery.*| B
    B --> D[Django App]
```

— Конструкции: [configparser.RawConfigParser()](ok_tools/settings.py:29), [os.getenv()](ok_tools/settings.py:46), [os.environ.get()](ok_tools/settings.py:283).

---

# Резюме

- `.cfg` содержит обширный набор параметров, которых нет в `.env`, включая email, i18n, security, celery beat, cache, static.
- `.env` содержит параметры для Docker/Gunicorn/SSL/Superuser/Redis, которых нет в `.cfg`.
- Пересечения по смыслу: Django (debug/allowed_hosts/secret_key), БД, Организация, Медиа пути, Уровень логов.
- В [settings.py](ok_tools/settings.py) из ENV реально используются только три переменные: `OKTOOLS_CONFIG_FILE`, `DJANGO_LOG_LEVEL`, `BACKUP_DIR`. Добавить недостающие в `.env.template` и ключ `django.backup_dir` в `.cfg`.
- Исправить `bootstrap]` → `[bootstrap]`, нормализовать формат cron и ALLOWED_HOSTS.
