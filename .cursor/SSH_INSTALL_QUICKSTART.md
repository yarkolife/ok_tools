# Быстрая установка на Debian SSH сервер

## 🎯 Для OK Merseburg Test Server

---

## Вариант 1: Автоматическая установка (Рекомендуется)

### На локальной машине:

```bash
# Скопируй скрипт на сервер
scp deployment/scripts/setup-ok-merseburg-test.sh user@YOUR_SERVER_IP:/tmp/
```

### На сервере через SSH:

```bash
# Подключись к серверу
ssh user@YOUR_SERVER_IP

# Запусти скрипт
sudo bash /tmp/setup-ok-merseburg-test.sh
```

Скрипт спросит:
- Пароль PostgreSQL
- Домен (например: `test.ok-merseburg.de`)
- IP и credentials для NAS
- Email настройки
- Credentials суперпользователя Django

Установка займет ~10-15 минут.

---

## Вариант 2: Ручная установка (клонирование с GitHub)

### На сервере:

```bash
# 1. Обнови систему
sudo apt update && sudo apt upgrade -y

# 2. Установи git
sudo apt install -y git

# 3. Клонируй репозиторий
cd /opt
sudo git clone https://github.com/yarkolife/ok_tools.git ok-tools
cd ok-tools

# 4. Запусти установочный скрипт
sudo bash deployment/scripts/setup-ok-merseburg-test.sh
```

---

## Вариант 3: Полностью ручная установка

Следуй [подробной инструкции](OK_MERSEBURG_TEST_SETUP.md):

```bash
# Открой инструкцию
cat deployment/OK_MERSEBURG_TEST_SETUP.md
```

---

## После установки

### 1. Импорт дампа базы данных

Скопируй дамп на сервер:
```bash
# С локальной машины
scp /path/to/dump.sql user@SERVER_IP:/tmp/
```

На сервере импортируй:
```bash
# SQL дамп
sudo -u postgres psql oktools_test < /tmp/dump.sql

# Или pg_dump format
sudo -u postgres pg_restore -d oktools_test /tmp/dump.dump

# Или определенную таблицу (например, только лицензии)
sudo -u postgres pg_restore -d oktools_test -t licenses_license /tmp/dump.dump
```

### 2. Создай Storage Locations

Открой админку: `http://test.ok-merseburg.de/admin/`

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

### 3. Первое сканирование видео

```bash
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg

python manage.py scan_video_storage
```

### 4. Настрой SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d test.ok-merseburg.de
```

---

## 🔧 Полезные команды на сервере

### Проверка статуса

```bash
# Статус приложения
sudo systemctl status oktools

# Статус nginx
sudo systemctl status nginx

# Проверка NAS
mount | grep cifs
sudo -u oktools ls -la /mnt/nas/playout
```

### Логи

```bash
# Логи приложения (real-time)
sudo journalctl -u oktools -f

# Логи nginx
sudo tail -f /var/log/nginx/oktools-error.log
sudo tail -f /var/log/nginx/oktools-access.log

# Логи Django
tail -f /opt/ok-tools/logs/oktools.log
```

### Перезапуск сервисов

```bash
# Перезапуск приложения
sudo systemctl restart oktools

# Перезапуск nginx
sudo systemctl restart nginx

# Перезапуск обоих
sudo systemctl restart oktools nginx
```

### Django команды

```bash
# Переключись на пользователя oktools
sudo su - oktools
cd /opt/ok-tools/app
source /opt/ok-tools/venv/bin/activate
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg

# Миграции
python manage.py migrate

# Создать суперпользователя
python manage.py createsuperuser

# Сканирование видео
python manage.py scan_video_storage

# Синхронизация лицензий и видео
python manage.py sync_licenses_videos

# Django shell
python manage.py shell
```

### Обновление приложения

```bash
# Как oktools пользователь
sudo su - oktools
cd /opt/ok-tools/app

# Получи обновления с GitHub
git pull origin main

# Обнови зависимости
source /opt/ok-tools/venv/bin/activate
pip install -r requirements.txt

# Миграции
export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg
python manage.py migrate

# Собери статику
python manage.py collectstatic --noinput

# Выйди и перезапусти
exit
sudo systemctl restart oktools
```

### Бэкапы

```bash
# Бэкап базы данных
sudo -u postgres pg_dump oktools_test > /backup/oktools_$(date +%Y%m%d_%H%M%S).sql

# Бэкап конфигурации
sudo cp /opt/ok-tools/config/production.cfg /backup/production_$(date +%Y%m%d).cfg
```

### Ремонтирование NAS

```bash
# Проверь статус
mount | grep cifs

# Ремонтируй
sudo umount /mnt/nas/playout
sudo umount /mnt/nas/archive
sudo mount -a

# Проверь доступ
sudo -u oktools ls -la /mnt/nas/playout
```

---

## 🐛 Troubleshooting

### Проблема: Приложение не запускается

```bash
# Проверь логи
sudo journalctl -u oktools -n 50 --no-pager

# Проверь конфигурацию
sudo -u oktools cat /opt/ok-tools/config/production.cfg

# Проверь права
ls -la /opt/ok-tools/
```

### Проблема: 502 Bad Gateway

```bash
# Проверь что gunicorn работает
sudo systemctl status oktools
curl http://127.0.0.1:8000

# Проверь nginx
sudo nginx -t
sudo systemctl status nginx
```

### Проблема: NAS не монтируется

```bash
# Проверь доступность
ping 192.168.188.1

# Проверь credentials
sudo cat /root/.smbcredentials_playout

# Тестовое монтирование
sudo mount -t cifs //192.168.188.1/sendedaten /mnt/nas/playout \
  -o credentials=/root/.smbcredentials_playout,uid=1000,gid=1000

# Проверь что смонтировано
mount | grep cifs
```

### Проблема: База данных не подключается

```bash
# Проверь PostgreSQL
sudo systemctl status postgresql

# Проверь подключение
sudo -u postgres psql oktools_test

# В psql:
\l                    # список баз
\du                   # список пользователей
\dt                   # список таблиц
SELECT count(*) FROM licenses_license;  # проверь данные
```

---

## 📋 Checklist после установки

- [ ] Приложение доступно через браузер
- [ ] Вход в админку работает
- [ ] NAS хранилища смонтированы
- [ ] Storage Locations созданы
- [ ] Дамп базы импортирован
- [ ] Первое сканирование видео выполнено
- [ ] SSL сертификат установлен
- [ ] Email отправка работает (тестовое письмо)
- [ ] Cron задачи настроены
- [ ] Бэкап базы данных настроен

---

## 🔗 Полезные ссылки

- [Полная инструкция установки](OK_MERSEBURG_TEST_SETUP.md)
- [Настройка NAS на Debian](NAS_DEBIAN_SETUP.md)
- [Media Files руководство](../media_files/ADMIN_GUIDE.md)
- [Media Files краткое руководство](../media_files/ADMIN_QUICKSTART.txt)
- [Общая информация о deployment](README.md)

---

## 💡 Совет

После установки рекомендуется:
1. Сделать snapshot/бэкап виртуальной машины
2. Настроить автоматические бэкапы базы данных
3. Настроить мониторинг (например, через systemd email notifications)
4. Протестировать все функции перед использованием в production

---

**Готово! Тестовый сервер OK Merseburg готов к работе.**

