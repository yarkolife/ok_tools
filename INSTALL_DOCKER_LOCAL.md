# Установка OK Tools через Docker (локальная сеть)

## 🐳 Для OK Merseburg - Docker без nginx

**Что установится:**
- PostgreSQL 15 (в контейнере)
- Django + Gunicorn (в контейнере)
- Cron задачи (в контейнере)
- **БЕЗ** nginx (прямой доступ к Gunicorn)
- **БЕЗ** SSL (HTTP only)

**Доступ:** `http://IP:8000` из локальной сети

---

## ✅ Преимущества Docker установки

✓ Не нужно устанавливать Python, PostgreSQL, Gunicorn на сервере  
✓ Все зависимости изолированы в контейнерах  
✓ Легко обновлять и откатывать  
✓ Быстрая установка (~5-10 минут)  
✓ Работает одинаково на разных системах  

---

## 🚀 Автоматическая установка (один скрипт)

### На сервере через SSH:

```bash
ssh user@YOUR_SERVER_IP

# Установи git
sudo apt update && sudo apt install -y git

# Клонируй репозиторий
cd /opt
sudo git clone https://github.com/yarkolife/ok_tools.git
cd ok_tools

# Запусти установку
sudo bash deployment/docker/setup-docker-local.sh
```

### Скрипт спросит:

- **IP адрес сервера** (автоопределится, можно подтвердить)
- **NAS Playout**: IP, share, логин/пароль
- **NAS Archive**: отдельный или тот же
- **Суперпользователь Django**: username, email, password

### Что делает скрипт:

1. Устанавливает Docker (если нет)
2. Устанавливает cifs-utils для NAS
3. Монтирует NAS хранилища на хост
4. Клонирует код приложения
5. Создает конфигурацию
6. Собирает Docker образ
7. Запускает контейнеры (db + web + cron)
8. Применяет миграции Django
9. Создает суперпользователя

**Время установки:** ~5-10 минут (зависит от скорости интернета)

---

## 📦 Что будет установлено

### Структура:

```
/opt/ok-tools/                    # Код приложения
├── deployment/
│   └── docker/
│       ├── docker-compose.local.yml   # Docker конфигурация
│       ├── config/
│       │   └── production.cfg         # Конфигурация приложения
│       └── setup-docker-local.sh      # Скрипт установки
├── Dockerfile                         # Docker образ
└── ...

/mnt/nas/
├── playout/                      # NAS Playout (смонтирован на хосте)
└── archive/                      # NAS Archive (смонтирован на хосте)
```

### Docker контейнеры:

```bash
oktools_db    # PostgreSQL 15
oktools_web   # Django + Gunicorn (порт 8000)
oktools_cron  # Cron задачи (expire_rentals)
```

### Docker volumes:

```
postgres_data  # База данных PostgreSQL
static_data    # Статические файлы Django
media_data     # Загружаемые файлы
```

---

## 🔧 Управление Docker контейнерами

Все команды выполняются из `/opt/ok-tools`:

```bash
cd /opt/ok-tools
```

### Статус контейнеров:

```bash
docker compose -f deployment/docker/docker-compose.local.yml ps
```

### Логи (real-time):

```bash
# Все контейнеры
docker compose -f deployment/docker/docker-compose.local.yml logs -f

# Только web
docker compose -f deployment/docker/docker-compose.local.yml logs -f web

# Только db
docker compose -f deployment/docker/docker-compose.local.yml logs -f db
```

### Перезапуск:

```bash
# Перезапустить все
docker compose -f deployment/docker/docker-compose.local.yml restart

# Перезапустить только web
docker compose -f deployment/docker/docker-compose.local.yml restart web
```

### Остановка:

```bash
docker compose -f deployment/docker/docker-compose.local.yml down
```

### Запуск:

```bash
docker compose -f deployment/docker/docker-compose.local.yml up -d
```

### Пересборка (после обновления кода):

```bash
git pull origin main
docker compose -f deployment/docker/docker-compose.local.yml build
docker compose -f deployment/docker/docker-compose.local.yml up -d
```

---

## 📋 После установки

### 1. Проверь что работает

```bash
# Статус контейнеров
docker compose -f deployment/docker/docker-compose.local.yml ps

# Все должны быть Up
# oktools_db    Up
# oktools_web   Up
# oktools_cron  Up

# Проверь доступ
curl http://192.168.1.100:8000  # твой IP

# Или открой в браузере
http://192.168.1.100:8000
```

### 2. Импорт дампа базы данных

```bash
cd /opt/ok-tools

# Скопируй дамп на сервер (с локальной машины)
scp /path/to/dump.sql user@SERVER_IP:/tmp/

# На сервере импортируй
docker compose -f deployment/docker/docker-compose.local.yml exec -T db \
  psql -U oktools oktools < /tmp/dump.sql

# Или войди в psql интерактивно
docker compose -f deployment/docker/docker-compose.local.yml exec db \
  psql -U oktools oktools
```

### 3. Создай Storage Locations

Открой: `http://192.168.1.100:8000/admin/`

**Media Files → Storage locations → Add:**

**Playout:**
- Name: `OK Merseburg Playout`
- Type: `PLAYOUT`
- Path: `/mnt/nas/playout/`
- Is active: ✓

**Archive:**
- Name: `OK Merseburg Archive`
- Type: `ARCHIVE`
- Path: `/mnt/nas/archive/`
- Is active: ✓

### 4. Первое сканирование видео

```bash
cd /opt/ok-tools

docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py scan_video_storage
```

---

## 🛠️ Django команды в Docker

Все Django команды выполняются через `docker compose exec web`:

```bash
cd /opt/ok-tools

# Миграции
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py migrate

# Создать суперпользователя
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py createsuperuser

# Сканирование видео
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py scan_video_storage

# Синхронизация лицензий и видео
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py sync_licenses_videos

# Django shell
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py shell

# Собрать статику
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py collectstatic --noinput
```

---

## 🔄 Обновление приложения

```bash
cd /opt/ok-tools

# 1. Получи обновления с GitHub
git pull origin main

# 2. Пересобери образ
docker compose -f deployment/docker/docker-compose.local.yml build

# 3. Перезапусти контейнеры
docker compose -f deployment/docker/docker-compose.local.yml down
docker compose -f deployment/docker/docker-compose.local.yml up -d

# 4. Применить миграции (если есть)
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py migrate
```

---

## 💾 Бэкапы

### Бэкап базы данных:

```bash
cd /opt/ok-tools

# Создать бэкап
docker compose -f deployment/docker/docker-compose.local.yml exec -T db \
  pg_dump -U oktools oktools > backup_$(date +%Y%m%d_%H%M%S).sql

# Или с gzip
docker compose -f deployment/docker/docker-compose.local.yml exec -T db \
  pg_dump -U oktools oktools | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Восстановление:

```bash
# Из SQL файла
docker compose -f deployment/docker/docker-compose.local.yml exec -T db \
  psql -U oktools oktools < backup_20241012.sql

# Из gzip
gunzip < backup_20241012.sql.gz | \
  docker compose -f deployment/docker/docker-compose.local.yml exec -T db \
  psql -U oktools oktools
```

---

## 🔍 Мониторинг

### Проверка здоровья контейнеров:

```bash
cd /opt/ok-tools

# Статус всех контейнеров
docker compose -f deployment/docker/docker-compose.local.yml ps

# Использование ресурсов
docker stats oktools_web oktools_db oktools_cron

# Логи ошибок
docker compose -f deployment/docker/docker-compose.local.yml logs --tail=50 web
```

### Проверка NAS:

```bash
# На хосте
mount | grep cifs
ls -la /mnt/nas/playout
ls -la /mnt/nas/archive

# Внутри контейнера
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  ls -la /mnt/nas/playout
```

---

## 🐛 Troubleshooting

### Контейнеры не запускаются

```bash
cd /opt/ok-tools

# Проверь логи
docker compose -f deployment/docker/docker-compose.local.yml logs

# Проверь что Docker работает
sudo systemctl status docker

# Проверь что порт 8000 свободен
sudo netstat -tulpn | grep :8000

# Перезапусти Docker
sudo systemctl restart docker
```

### Приложение не открывается

```bash
# Проверь что web контейнер работает
docker compose -f deployment/docker/docker-compose.local.yml ps web

# Проверь логи
docker compose -f deployment/docker/docker-compose.local.yml logs web

# Проверь доступ с сервера
curl http://localhost:8000
curl http://192.168.1.100:8000

# Проверь firewall (если настроен)
sudo ufw status
```

### NAS не монтируется

```bash
# На хосте (НЕ в контейнере)
ping 192.168.188.1

# Проверь credentials
sudo cat /root/.smbcredentials_playout

# Ремонтируй
sudo umount /mnt/nas/playout
sudo umount /mnt/nas/archive
sudo mount -a

# Проверь
mount | grep cifs
```

### База данных не подключается

```bash
cd /opt/ok-tools

# Проверь что db контейнер работает
docker compose -f deployment/docker/docker-compose.local.yml ps db

# Войди в PostgreSQL
docker compose -f deployment/docker/docker-compose.local.yml exec db \
  psql -U oktools oktools

# В psql:
\l      # список баз
\dt     # список таблиц
\q      # выход
```

### Пересоздать все контейнеры с нуля

```bash
cd /opt/ok-tools

# Останови и удали контейнеры + volumes
docker compose -f deployment/docker/docker-compose.local.yml down -v

# Пересобери и запусти
docker compose -f deployment/docker/docker-compose.local.yml build
docker compose -f deployment/docker/docker-compose.local.yml up -d

# Заново создай суперпользователя
docker compose -f deployment/docker/docker-compose.local.yml exec web \
  python manage.py createsuperuser
```

---

## 📊 Сравнение установок

| Параметр | Docker | Gunicorn (native) |
|----------|--------|-------------------|
| Установка | ⭐⭐⭐⭐⭐ Очень просто | ⭐⭐⭐ Средне |
| Не нужен Python на хосте | ✅ Да | ❌ Нет |
| Не нужен PostgreSQL на хосте | ✅ Да | ❌ Нет |
| Изоляция | ⭐⭐⭐⭐⭐ Полная | ⭐⭐ Частичная |
| Обновление | ⭐⭐⭐⭐⭐ git pull + rebuild | ⭐⭐⭐ git pull + restart |
| Откат | ⭐⭐⭐⭐⭐ Легко | ⭐⭐ Сложнее |
| Ресурсы | ⭐⭐⭐⭐ Немного больше | ⭐⭐⭐⭐⭐ Меньше |

---

## ✅ Checklist установки

- [ ] Docker установлен
- [ ] Репозиторий клонирован в /opt/ok-tools
- [ ] NAS хранилища смонтированы на хосте
- [ ] Конфигурация создана
- [ ] Контейнеры запущены (docker compose ps)
- [ ] Приложение доступно по http://IP:8000
- [ ] Вход в админку работает
- [ ] Storage Locations созданы
- [ ] Дамп импортирован (если нужно)
- [ ] Первое сканирование выполнено

---

## 🎯 Быстрая шпаргалка

```bash
cd /opt/ok-tools
alias dcp='docker compose -f deployment/docker/docker-compose.local.yml'

# Статус
dcp ps

# Логи
dcp logs -f

# Перезапуск
dcp restart

# Django команды
dcp exec web python manage.py [команда]

# Бэкап БД
dcp exec -T db pg_dump -U oktools oktools > backup.sql

# Обновление
git pull && dcp build && dcp up -d
```

---

**Готово! OK Tools работает в Docker в локальной сети.**

**Доступ:** `http://YOUR_IP:8000`  
**Админка:** `http://YOUR_IP:8000/admin/`

