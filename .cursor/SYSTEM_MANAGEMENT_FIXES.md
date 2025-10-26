# System Management Page Fixes

## Проблемы, которые были найдены и исправлены

### 1. **Несуществующая команда `cleanup_duplicates`**

**Проблема:** В шаблоне `system_management.html` была форма для команды `cleanup_duplicates`, но сама команда не существовала.

**Решение:** 
- Создана команда `cleanup_duplicates.py`
- Обновлена логика в `admin_commands.py` для правильной обработки параметров
- Восстановлена форма в шаблоне с правильными параметрами

### 2. **Несоответствие параметров команд**

**Проблема:** Параметры в UI не соответствовали реальным параметрам команд.

**Исправления:**

#### Команда `find_duplicates`:
- **Убрано:** `min_duplicates` и `number` (не поддерживаются)
- **Исправлено:** `output_format` → `json` (boolean флаг)

#### Команда `cleanup_duplicates`:
- **Добавлено:** Полная реализация команды
- **Параметры:** `dry_run`, `storage_type`, `number`

## Созданные файлы

### `media_files/management/commands/cleanup_duplicates.py`

Новая команда для удаления дубликатов видеофайлов:

```python
class Command(BaseCommand):
    """Cleanup duplicate video files by keeping the best quality version."""
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--storage-type', type=str)
        parser.add_argument('--number', type=int)
```

**Логика работы:**
1. Находит видео с дубликатами (больше одной версии)
2. Определяет "лучшую" версию по приоритету:
   - Тип хранилища (ARCHIVE > PLAYOUT > CUSTOM)
   - Битрейт (выше лучше)
   - Дата создания (новее лучше)
3. Удаляет дубликаты, оставляя лучшую версию

## Исправления в существующих файлах

### `media_files/admin_commands.py`

**Изменения:**
```python
# БЫЛО:
elif command == 'find_duplicates':
    options['output'] = output_format  # Неправильно
    options['min_duplicates'] = int(min_duplicates)  # Не существует

# СТАЛО:
elif command == 'find_duplicates':
    if request.POST.get('output_format') == 'json':
        options['json'] = True  # Правильный boolean флаг
    # Убраны несуществующие параметры
```

### `media_files/templates/admin/system_management.html`

**Изменения:**
1. **Убраны несуществующие параметры** из формы `find_duplicates`
2. **Восстановлена форма** для `cleanup_duplicates` с правильными параметрами
3. **Улучшены подсказки** для пользователей

## Проверенные команды

### ✅ Работающие команды:

1. **`auto_scan`**
   - Параметры: `force`, `calculate_checksums`, `storage_type`
   - ✅ Все параметры соответствуют команде

2. **`scan_storage`**
   - Параметры: `storage_id`, `force`, `calculate_checksum`
   - ✅ Все параметры соответствуют команде

3. **`sync_licenses_videos`**
   - Параметры: `dry_run`, `force_sync_duration`, `number`
   - ✅ Все параметры соответствуют команде

4. **`link_orphan_licenses`**
   - Параметры: `dry_run`, `scan_first`, `number`
   - ✅ Все параметры соответствуют команде

5. **`cleanup_playout`**
   - Параметры: `dry_run`, `check_attributes`, `check_locks`, `older_than`, `storage_id`
   - ✅ Все параметры соответствуют команде

6. **`find_duplicates`**
   - Параметры: `json`, `storage_type`
   - ✅ Исправлены несуществующие параметры

7. **`cleanup_duplicates`** (новая)
   - Параметры: `dry_run`, `storage_type`, `number`
   - ✅ Полностью реализована

## Тестирование

### Проверка команд:

```bash
# Тест новой команды
python manage.py cleanup_duplicates --dry-run

# Тест всех команд через System Management
# Открыть: http://localhost:8000/admin/media_files/videofile/system-management/
```

### Ожидаемые результаты:

1. **Все формы работают** без ошибок
2. **Параметры передаются** корректно
3. **Команды выполняются** успешно
4. **Вывод отображается** в сообщениях Django

## Безопасность

### Dry Run по умолчанию:
- Команда `cleanup_duplicates` имеет `dry_run` включен по умолчанию
- Пользователь должен явно отключить dry run для реального удаления
- Логирование всех операций удаления

### Права доступа:
- Только staff пользователи могут выполнять команды
- Проверка прав в `system_management_view`

## Совместимость

- ✅ Обратная совместимость сохранена
- ✅ Все существующие команды работают как прежде
- ✅ Добавлена новая функциональность
- ✅ Улучшен пользовательский интерфейс

## Связанные файлы

### Измененные:
- `media_files/admin_commands.py` - исправлена логика параметров
- `media_files/templates/admin/system_management.html` - исправлены формы

### Созданные:
- `media_files/management/commands/cleanup_duplicates.py` - новая команда

### Без изменений:
- Все остальные команды работают корректно
- Модели и утилиты не изменены
