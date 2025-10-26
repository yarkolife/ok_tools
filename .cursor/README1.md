# Скрипты установки OK Tools Production на тестовый сервер

Набор скриптов для автоматической установки, обновления и удаления OK Tools Production версии на тестовый сервер в локальной сети.

## 📋 Требования

- **ОС**: Debian/Ubuntu Linux
- **Права**: root/sudo доступ
- **Сеть**: доступ к интернету для скачивания Docker образов
- **NAS**: настроенное SMB/CIFS хранилище для видеофайлов
- **Порты**: 8000 (веб-интерфейс), 5432 (PostgreSQL)

## 🚀 Быстрый старт

### Установка
```bash
sudo bash deployment/scripts/install-production-test.sh
```

### Пост-установочная настройка
```bash
sudo bash deployment/scripts/configure-production-test.sh
```

### Обновление
```bash
sudo bash deployment/scripts/update-production-test.sh
```

### Остановка и удаление
```bash
sudo bash deployment/scripts/stop-production-test.sh
```

## 📁 Структура скриптов

```
deployment/scripts/
├── install-production-test.sh    # Основной скрипт установки
├── configure-production-test.sh  # Скрипт пост-установочной настройки
├── update-production-test.sh     # Скрипт обновления
├── stop-production-test.sh       # Скрипт остановки и удаления
└── README.md                     # Данная документация
```

## 🔧 Детальное описание

### install-production-test.sh

**Назначение**: Полная установка OK Tools Production на тестовый сервер

**Исправления в версии 2.0:**
- Автоматическое исправление путей в конфигурации (`STATIC_ROOT`, `MEDIA_ROOT`)
- Исправление `db_host` с `localhost` на `db` для Docker
- Исправление `db_name` с `oktools_okmq` на `oktools`
- Автоматическое создание директории `static/`
- Исправление прав доступа на файлы
- Удаление проблемной миграции `0004_add_unc_path_to_storage.py`

**Функции**:
1. **Проверка Docker** - установка Docker и Docker Compose если отсутствуют
2. **Выбор конфигурации** - выбор из доступных конфигураций организаций:
   - OK Bayern (`ok-bayern-production.cfg`)
   - OK Merseburg-Querfurt (`okmq-production.cfg`)
   - OK NRW (`ok-nrw-production.cfg`)
3. **Ввод данных** - настройка индивидуальных параметров:
   - IP адрес сервера
   - PostgreSQL пароль
   - Django SECRET_KEY (автогенерация или ввод)
   - NAS настройки (IP, share, credentials)
4. **Подготовка окружения** - создание `/opt/ok-tools-test/`
5. **Создание конфигурации** - копирование и настройка выбранного cfg файла
6. **Настройка NAS** - монтирование с оптимизированными параметрами
7. **Настройка Docker** - адаптация docker-compose для тестового сервера
8. **Запуск контейнеров** - сборка и запуск всех сервисов
9. **Инициализация Django** - миграции, статика, создание суперпользователя
10. **Итоговая информация** - URL доступа и следующие шаги

**Результат**: Полностью работающий OK Tools на `http://IP:8001`

### configure-production-test.sh

**Назначение**: Пост-установочная настройка и диагностика OK Tools

**Функции**:
1. **Проверка статуса контейнеров** - диагностика состояния Docker сервисов
2. **Проверка конфигурации** - валидация настроек Django
3. **Исправление проблем** - автоматическое исправление найденных ошибок
4. **Проверка миграций** - диагностика и исправление проблем с БД
5. **Проверка статических файлов** - сбор и валидация статики
6. **Проверка суперпользователя** - проверка наличия админов
7. **Проверка NAS** - диагностика подключения к хранилищу
8. **Финальная проверка** - health check и доступность приложения

**Использование**:
```bash
sudo bash deployment/scripts/configure-production-test.sh
```

**Результат**: Диагностированный и исправленный OK Tools

### update-production-test.sh

**Назначение**: Обновление установленного OK Tools

**Функции**:
1. **Проверка статуса** - текущее состояние контейнеров и git
2. **Создание бэкапа** - сохранение БД и конфигурации
3. **Обновление кода** - git pull из репозитория
4. **Пересборка контейнеров** - rebuild Docker образов
5. **Применение миграций** - обновление схемы БД
6. **Обновление статики** - сбор новых статических файлов
7. **Проверка работоспособности** - health check и логи
8. **Очистка** - удаление неиспользуемых Docker ресурсов

**Результат**: Обновленный OK Tools с сохранением данных

### stop-production-test.sh

**Назначение**: Полная остановка и удаление OK Tools

**Функции**:
1. **Финальный бэкап** - сохранение всех данных и логов
2. **Остановка контейнеров** - graceful shutdown
3. **Удаление Docker ресурсов** - volumes и образы (опционально)
4. **Размонтирование NAS** - отключение сетевых хранилищ (опционально)
5. **Удаление файлов** - директория приложения (опционально)
6. **Очистка системы** - неиспользуемые Docker ресурсы

**Результат**: Полная очистка системы от OK Tools

## ⚙️ Конфигурации организаций

Скрипты поддерживают следующие предустановленные конфигурации:

### OK Bayern
- **Файл**: `ok-bayern-production.cfg`
- **Организация**: Offener Kanal Bayern e.V.
- **Регион**: Bayern, BLM
- **Домен**: ok-bayern.de

### OK Merseburg-Querfurt
- **Файл**: `okmq-production.cfg`
- **Организация**: Offener Kanal Merseburg-Querfurt e.V.
- **Регион**: Sachsen-Anhalt, MSA
- **Домен**: okmq.de

### OK NRW
- **Файл**: `ok-nrw-production.cfg`
- **Организация**: OK NRW
- **Регион**: Nordrhein-Westfalen, LfM NRW
- **Домен**: ok-nrw.de

## 🗂️ Структура установки

После установки структура файлов:

```
/opt/ok-tools-test/
├── docker-compose.yml           # Адаптированный для тестового сервера
├── docker-production.cfg        # Конфигурация приложения
├── Dockerfile                   # Production Dockerfile
├── nginx.conf                   # Конфигурация nginx
├── update.sh                    # Локальный скрипт обновления
├── stop.sh                      # Локальный скрипт остановки
├── media_files/                 # Модуль работы с видео
├── licenses/                    # Модуль лицензий
├── registration/                # Модуль регистрации
└── ...                         # Остальные файлы приложения
```

## 🌐 NAS хранилище

### Требования
- **Протокол**: SMB/CIFS
- **Доступ**: Аутентификация по логину/паролю
- **Структура**:
  ```
  NAS_ROOT/
  ├── playout/          # Видео для трансляции
  │   ├── week01/
  │   ├── week02/
  │   └── trailers/
  └── archive/          # Архив видео
      ├── 12345_title1.mp4
      └── 67890_title2.mov
  ```

### Монтирование
Скрипты автоматически:
- Устанавливают `cifs-utils`
- Создают точки монтирования `/mnt/nas/playout` и `/mnt/nas/archive`
- Настраивают credentials файлы
- Добавляют записи в `/etc/fstab` с оптимизированными параметрами:
  ```
  rsize=1048576,wsize=1048576,vers=3.0
  ```

## 🔍 Troubleshooting

### Проблемы с Docker

**Docker не запускается**:
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

**Проблемы с правами**:
```bash
sudo usermod -aG docker $USER
# Перелогиниться
```

### Проблемы с NAS

**NAS не монтируется**:
```bash
# Проверить доступность
ping NAS_IP
smbutil view //NAS_IP

# Проверить credentials
cat /root/.smbcredentials_playout

# Монтировать вручную
mount -t cifs //NAS_IP/SHARE /mnt/nas/playout -o credentials=/root/.smbcredentials_playout
```

**Медленная работа с NAS**:
```bash
# Проверить параметры в fstab
grep nas /etc/fstab

# Должны быть: rsize=1048576,wsize=1048576,vers=3.0
```

### Проблемы с приложением

**Контейнеры не запускаются**:
```bash
cd /opt/ok-tools-test
docker compose logs web
docker compose logs db
```

**База данных недоступна**:
```bash
docker compose exec db psql -U oktools -d oktools -c "SELECT version();"
```

**Статические файлы не загружаются**:
```bash
docker compose exec web python manage.py collectstatic --noinput
```

### Проблемы с сетью

**Приложение недоступно по IP**:
```bash
# Проверить порты
netstat -tlnp | grep 8000

# Проверить firewall
ufw status
iptables -L
```

**Health check не проходит**:
```bash
curl -v http://localhost:8000/health
curl -v http://SERVER_IP:8000/health
```

## 📊 Мониторинг

### Проверка статуса
```bash
cd /opt/ok-tools-test
docker compose ps                    # Статус контейнеров
docker compose logs -f web          # Логи веб-сервиса
docker compose logs -f db           # Логи базы данных
```

### Проверка ресурсов
```bash
docker stats                        # Использование ресурсов
df -h /mnt/nas/                     # Использование NAS
free -h                             # Использование памяти
```

### Проверка логов
```bash
tail -f /var/log/ok-tools-install.log    # Лог установки
tail -f /var/log/ok-tools-update.log     # Лог обновления
```

## 🔄 Обновления

### Автоматическое обновление
```bash
sudo bash deployment/scripts/update-production-test.sh
```

### Ручное обновление
```bash
cd /opt/ok-tools-test
git pull origin main
docker compose down
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

## 🗑️ Полное удаление

### С сохранением бэкапа
```bash
sudo bash deployment/scripts/stop-production-test.sh
# Выбрать "n" для сохранения данных
```

### Полное удаление
```bash
sudo bash deployment/scripts/stop-production-test.sh
# Выбрать "y" для удаления всех компонентов
```

### Ручная очистка
```bash
cd /opt/ok-tools-test
docker compose down -v --rmi all
sudo rm -rf /opt/ok-tools-test
sudo umount /mnt/nas/*
sudo sed -i '/OK Tools NAS Mounts/d' /etc/fstab
```

## 📞 Поддержка

При возникновении проблем:

1. **Проверь логи**: `/var/log/ok-tools-*.log`
2. **Проверь статус контейнеров**: `docker compose ps`
3. **Проверь доступность сервисов**: `curl http://SERVER_IP:8000/health`
4. **Создай бэкап**: Скрипты автоматически создают бэкапы
5. **Обратись к документации**: Проверь настройки NAS и сети

## 📝 Примеры использования

### Установка для OK Bayern
```bash
sudo bash deployment/scripts/install-production-test.sh
# Выбрать: 1 (OK Bayern)
# IP сервера: 192.168.1.100
# NAS IP: 192.168.1.50
# Share: sendedaten
```

### Обновление с бэкапом
```bash
sudo bash deployment/scripts/update-production-test.sh
# Автоматически создаст бэкап перед обновлением
```

### Остановка с сохранением данных
```bash
sudo bash deployment/scripts/stop-production-test.sh
# Выбрать "n" для сохранения volumes и директории
```

---

**Версия**: 1.0  
**Дата**: 2025-01-12  
**Автор**: OK Tools Development Team