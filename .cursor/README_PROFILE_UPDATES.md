# 📋 Profile Model Updates

## Описание

Обновления модели `Profile` для добавления поля номера документа и чекбоксов разрешения передачи данных третьим лицам.

## ✨ Новые поля

### 1. **Ausweisnummer (ID Document Number)**
- **Тип**: `CharField`
- **Максимальная длина**: 50 символов
- **Обязательность**: Опциональное (`blank=True, null=True`)
- **Описание**: "ID document number (passport, ID card, etc.)"
- **Доступ**: Только в админке

### 2. **Phone Data Sharing Permission**
- **Поле**: `phone_data_sharing_allowed`
- **Тип**: `BooleanField`
- **По умолчанию**: `False`
- **Описание**: "Permission to share phone number with third parties"
- **Доступ**: Только в админке

### 3. **Email Data Sharing Permission**
- **Поле**: `email_data_sharing_allowed`
- **Тип**: `BooleanField`
- **По умолчанию**: `False`
- **Описание**: "Permission to share email address with third parties"
- **Доступ**: Только в админке

## 🔧 Технические детали

### Модель (`registration/models.py`)
```python
# ID document number
ausweisnummer = models.CharField(
    _('ID document number'), blank=True, null=True, max_length=50,
    help_text=_('ID document number (passport, ID card, etc.)')
)

# Data sharing permissions
phone_data_sharing_allowed = models.BooleanField(
    _('Phone data sharing allowed'),
    default=False,
    help_text=_('Permission to share phone number with third parties')
)

email_data_sharing_allowed = models.BooleanField(
    _('Email data sharing allowed'),
    default=False,
    help_text=_('Permission to share email address with third parties')
)
```

### Миграция
- **Файл**: `registration/migrations/0004_profile_ausweisnummer_and_more.py`
- **Статус**: ✅ Применена
- **Операции**:
  - Добавлено поле `ausweisnummer`
  - Добавлено поле `phone_data_sharing_allowed`
  - Добавлено поле `email_data_sharing_allowed`

## 🎛️ Админка

### Fieldsets Organization
```python
fieldsets = (
    (_('Basic Information'), {
        'fields': ('okuser', 'first_name', 'last_name', 'gender', 'birthday')
    }),
    (_('Contact Information'), {
        'fields': ('phone_number', 'mobile_number', 'street', 'house_number', 'zipcode', 'city')
    }),
    (_('ID Document'), {
        'fields': ('ausweisnummer',),
        'classes': ('collapse',)
    }),
    (_('Organization'), {
        'fields': ('media_authority', 'member', 'verified')
    }),
    (_('Data Sharing Permissions'), {
        'fields': ('phone_data_sharing_allowed', 'email_data_sharing_allowed'),
        'classes': ('collapse',),
        'description': _('Admin-only: Permissions for sharing data with third parties')
    }),
    (_('Additional Information'), {
        'fields': ('comment', 'created_at'),
        'classes': ('collapse',)
    }),
)
```

### Секции админки:
1. **Basic Information** - основная информация о пользователе
2. **Contact Information** - контактные данные
3. **ID Document** - документ удостоверения личности (свернуто)
4. **Organization** - организационная принадлежность
5. **Data Sharing Permissions** - разрешения на передачу данных (свернуто, только админы)
6. **Additional Information** - дополнительная информация (свернуто)

## 🚫 Исключения из пользовательских форм

### UserDataForm
```python
exclude = (
    'verified',
    'okuser',
    'media_authority',
    'created_at',
    'member',
    'comment',
    'ausweisnummer',  # Admin-only field
    'phone_data_sharing_allowed',  # Admin-only field
    'email_data_sharing_allowed',  # Admin-only field
)
```

### ProfileForm
- Использует `fields` вместо `exclude`
- Автоматически исключает все не указанные поля
- Админские поля не включены в список полей

## 🔒 Безопасность

### Принципы доступа:
- **Админские поля**: Видны только администраторам в Django Admin
- **Пользовательские формы**: Обычные пользователи не могут изменять админские поля
- **Регистрация**: Новые поля не отображаются при самостоятельной регистрации

### Поля только для админов:
- `ausweisnummer` - номер документа
- `phone_data_sharing_allowed` - разрешение передачи телефона
- `email_data_sharing_allowed` - разрешение передачи email

## 📊 Экспорт данных

### ProfileResource обновлен:
```python
ausweisnummer = _f('ausweisnummer', _('ID document number'))
```

Новое поле включено в экспорт профилей через Django Admin.

## ✅ Тестирование

### Проведенные тесты:
1. **Поля в модели**: Проверено наличие новых полей в базе данных
2. **Исключение из форм**: Проверено, что админские поля не показываются в пользовательских формах
3. **Админка**: Проверено, что поля корректно отображаются в админке
4. **Миграция**: Успешно применена без ошибок

### Результаты тестов:
- ✅ Все тесты прошли успешно
- ✅ Веб-сайт работает корректно
- ✅ Админка функционирует без ошибок

## 🎯 Использование

### Для администраторов:
1. Перейти в Django Admin → Profiles
2. Открыть профиль пользователя
3. В секции "Data Sharing Permissions" установить разрешения
4. В секции "ID Document" указать номер документа

### Для пользователей:
- При регистрации новые поля не отображаются
- При редактировании профиля новые поля недоступны
- Обычная функциональность не изменена

## 📁 Измененные файлы

1. **`registration/models.py`** - добавлены новые поля в модель Profile
2. **`registration/admin.py`** - обновлены fieldsets и ProfileResource
3. **`registration/forms.py`** - исключены админские поля из пользовательских форм
4. **`registration/migrations/0004_profile_ausweisnummer_and_more.py`** - миграция

## 🔄 Совместимость

- ✅ Обратная совместимость сохранена
- ✅ Существующие профили не затронуты
- ✅ API не изменен
- ✅ Пользовательский интерфейс не изменен

---

**Дата создания**: 10 октября 2025  
**Статус**: ✅ Завершено  
**Тестирование**: ✅ Пройдено
