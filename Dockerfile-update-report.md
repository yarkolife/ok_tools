# Отчет о корректировке конфигурации Docker Compose

## Обзор

В рамках данной задачи были исправлены ошибки в логике сборки Docker. Проблема заключалась в том, что файлы `docker-compose.production.yml` и `docker-compose.production.no-nginx.yml` ссылались на `Dockerfile` из исходного репозитория, а не на тот, который копируется в рабочую директорию при установке.

## Изменения

### 1. docker-compose.production.yml

В сервисах `web`, `celery_worker` и `celery_beat` были изменены параметры сборки:

**До:**
```yaml
build:
  context: ../ok_tools
  dockerfile: deployment/production.Dockerfile
```

**После:**
```yaml
build:
  context: .
  dockerfile: Dockerfile
```

### 2. docker-compose.production.no-nginx.yml

Аналогичные изменения были внесены в сервисы `web`, `celery_worker` и `celery_beat`:

**До:**
```yaml
build:
  context: ../ok_tools
  dockerfile: deployment/production.Dockerfile
```

**После:**
```yaml
build:
  context: .
  dockerfile: Dockerfile
```

### 3. Новый Dockerfile

Был создан новый файл `deployment/Dockerfile`, адаптированный для нового контекста сборки:

- Изменен путь к `requirements.txt` с `COPY requirements.txt .` на `COPY ../requirements.txt .`
- Изменен путь к исходному коду приложения с `COPY . .` на `COPY ../ok_tools/ .`
- Все остальные настройки остались без изменений

## Результат

Теперь конфигурации Docker Compose корректно ссылаются на Dockerfile, который будет находиться в правильной директории при установке, и пути копирования файлов соответствуют новому контексту сборки. Это устраняет ошибку в логике сборки и обеспечивает корректную работу при развёртывании.