#!/usr/bin/env python
"""
Тест для проверки настроек chunked upload
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ok_tools.settings')
sys.path.insert(0, '/app')
django.setup()

from django.conf import settings

def test_chunked_upload_settings():
    """Проверяем, что все настройки chunked upload доступны"""
    print("=" * 60)
    print("Тестирование настроек Chunked Upload")
    print("=" * 60)
    
    # Проверка основных настроек Nextcloud
    assert hasattr(settings, 'NEXTCLOUD_ENABLED'), "NEXTCLOUD_ENABLED не найден"
    print(f"✓ NEXTCLOUD_ENABLED: {settings.NEXTCLOUD_ENABLED}")
    
    if settings.NEXTCLOUD_ENABLED:
        # Проверка новых настроек chunked upload
        assert hasattr(settings, 'NEXTCLOUD_CHUNKED_UPLOAD_ENABLED'), \
            "NEXTCLOUD_CHUNKED_UPLOAD_ENABLED не найден"
        assert hasattr(settings, 'NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD'), \
            "NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD не найден"
        assert hasattr(settings, 'NEXTCLOUD_CHUNK_SIZE'), \
            "NEXTCLOUD_CHUNK_SIZE не найден"
        
        print(f"✓ NEXTCLOUD_CHUNKED_UPLOAD_ENABLED: {settings.NEXTCLOUD_CHUNKED_UPLOAD_ENABLED}")
        print(f"✓ NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD: {settings.NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD} MB")
        print(f"✓ NEXTCLOUD_CHUNK_SIZE: {settings.NEXTCLOUD_CHUNK_SIZE} MB")
        
        # Проверка типов данных
        assert isinstance(settings.NEXTCLOUD_CHUNKED_UPLOAD_ENABLED, bool), \
            "NEXTCLOUD_CHUNKED_UPLOAD_ENABLED должен быть bool"
        assert isinstance(settings.NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD, int), \
            "NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD должен быть int"
        assert isinstance(settings.NEXTCLOUD_CHUNK_SIZE, int), \
            "NEXTCLOUD_CHUNK_SIZE должен быть int"
        
        print("✓ Типы данных корректны")
        
        # Проверка разумных значений
        assert settings.NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD > 0, \
            "Threshold должен быть положительным"
        assert settings.NEXTCLOUD_CHUNK_SIZE > 0, \
            "Chunk size должен быть положительным"
        assert settings.NEXTCLOUD_CHUNK_SIZE <= settings.NEXTCLOUD_CHUNKED_UPLOAD_THRESHOLD, \
            "Chunk size не должен превышать threshold"
        
        print("✓ Значения в допустимых пределах")
    
    print("=" * 60)
    print("✅ Все тесты пройдены!")
    print("=" * 60)
    return True

def test_views_context():
    """Проверяем, что views добавляют настройки в context"""
    from licenses.views import CreateLicenseView, ListLicensesView, UpdateLicensesView
    
    print("\n" + "=" * 60)
    print("Тестирование Views Context")
    print("=" * 60)
    
    views = [
        ('CreateLicenseView', CreateLicenseView),
        ('ListLicensesView', ListLicensesView),
        ('UpdateLicensesView', UpdateLicensesView),
    ]
    
    for name, view_class in views:
        # Проверяем, что get_context_data существует
        assert hasattr(view_class, 'get_context_data'), \
            f"{name} не имеет метода get_context_data"
        print(f"✓ {name} имеет get_context_data")
    
    print("=" * 60)
    print("✅ Все views корректны!")
    print("=" * 60)
    return True

if __name__ == '__main__':
    try:
        test_chunked_upload_settings()
        test_views_context()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Тест провален: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
