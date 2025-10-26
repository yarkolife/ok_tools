"""
Tests for environment-based settings configuration.
"""
import os
import pytest
from django.test import TestCase, override_settings
from django.core.exceptions import ImproperlyConfigured
from unittest.mock import patch, MagicMock
import warnings


class EnvironmentSettingsTestCase(TestCase):
    """Test environment variable configuration."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing test variables
        self.test_vars = []
    
    def tearDown(self):
        """Clean up test environment variables."""
        for var in self.test_vars:
            if var in os.environ:
                del os.environ[var]
    
    def _set_env(self, key, value):
        """Helper to set env var and track for cleanup."""
        os.environ[key] = str(value)
        self.test_vars.append(key)
    
    def test_get_env_string(self):
        """Test basic string retrieval."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_STRING', 'test_value')
        result = get_env('TEST_STRING')
        self.assertEqual(result, 'test_value')
    
    def test_get_env_default(self):
        """Test default value when env var not set."""
        from ok_tools.settings import get_env
        
        result = get_env('NONEXISTENT_VAR', default='default_value')
        self.assertEqual(result, 'default_value')
    
    def test_get_env_required_missing(self):
        """Test that missing required ENV raises error."""
        from ok_tools.settings import get_env
        
        with self.assertRaises(ImproperlyConfigured) as context:
            get_env('NONEXISTENT_REQUIRED_VAR', required=True)
        
        self.assertIn('NONEXISTENT_REQUIRED_VAR', str(context.exception))
    
    def test_get_env_bool_true(self):
        """Test boolean casting - true values."""
        from ok_tools.settings import get_env
        
        for value in ['true', 'True', 'TRUE', '1', 'yes', 'Yes', 'on', 'On']:
            with self.subTest(value=value):
                self._set_env('TEST_BOOL', value)
                result = get_env('TEST_BOOL', cast=bool)
                self.assertTrue(result, f"Failed for value: {value}")
                del os.environ['TEST_BOOL']
    
    def test_get_env_bool_false(self):
        """Test boolean casting - false values."""
        from ok_tools.settings import get_env
        
        for value in ['false', 'False', 'FALSE', '0', 'no', 'No', 'off', 'Off']:
            with self.subTest(value=value):
                self._set_env('TEST_BOOL', value)
                result = get_env('TEST_BOOL', cast=bool)
                self.assertFalse(result, f"Failed for value: {value}")
                del os.environ['TEST_BOOL']
    
    def test_get_env_int(self):
        """Test integer casting."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_INT', '42')
        result = get_env('TEST_INT', cast=int)
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)
    
    def test_get_env_int_invalid(self):
        """Test integer casting with invalid value uses default."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_INT_INVALID', 'not_a_number')
        result = get_env('TEST_INT_INVALID', default=10, cast=int)
        self.assertEqual(result, 10)
    
    def test_get_env_int_invalid_no_default(self):
        """Test integer casting with invalid value and no default returns 0."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_INT_INVALID', 'not_a_number')
        result = get_env('TEST_INT_INVALID', cast=int)
        self.assertEqual(result, 0)
    
    def test_get_env_list(self):
        """Test list parsing from comma-separated string."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_LIST', 'a,b,c')
        result = get_env('TEST_LIST', cast=list)
        self.assertEqual(result, ['a', 'b', 'c'])
    
    def test_get_env_list_with_spaces(self):
        """Test list parsing with spaces around commas."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_LIST', 'a, b , c')
        result = get_env('TEST_LIST', cast=list)
        self.assertEqual(result, ['a', 'b', 'c'])
    
    def test_get_env_list_empty(self):
        """Test list parsing with empty string."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_LIST', '')
        result = get_env('TEST_LIST', cast=list, default=[])
        self.assertEqual(result, [])
    
    def test_get_env_list_with_empty_items(self):
        """Test list parsing with empty items."""
        from ok_tools.settings import get_env
        
        self._set_env('TEST_LIST', 'a,,b,')
        result = get_env('TEST_LIST', cast=list)
        self.assertEqual(result, ['a', 'b'])


class EnvListHelperTestCase(TestCase):
    """Test get_env_list helper function."""
    
    def setUp(self):
        self.test_vars = []
    
    def tearDown(self):
        for var in self.test_vars:
            if var in os.environ:
                del os.environ[var]
    
    def _set_env(self, key, value):
        os.environ[key] = str(value)
        self.test_vars.append(key)
    
    def test_get_env_list_basic(self):
        """Test basic list retrieval."""
        from ok_tools.settings import get_env_list
        
        self._set_env('TEST_LIST', 'item1,item2,item3')
        result = get_env_list('TEST_LIST')
        self.assertEqual(result, ['item1', 'item2', 'item3'])
    
    def test_get_env_list_custom_separator(self):
        """Test list with custom separator."""
        from ok_tools.settings import get_env_list
        
        self._set_env('TEST_LIST', 'item1;item2;item3')
        result = get_env_list('TEST_LIST', separator=';')
        self.assertEqual(result, ['item1', 'item2', 'item3'])
    
    def test_get_env_list_not_set(self):
        """Test default value when list not set."""
        from ok_tools.settings import get_env_list
        
        result = get_env_list('NONEXISTENT_LIST', default=['default'])
        self.assertEqual(result, ['default'])
    
    def test_get_env_list_empty_default(self):
        """Test empty default when list not set."""
        from ok_tools.settings import get_env_list
        
        result = get_env_list('NONEXISTENT_LIST')
        self.assertEqual(result, [])


class AllowedHostsParsingTestCase(TestCase):
    """Test ALLOWED_HOSTS parsing (comma and space separated)."""
    
    def test_allowed_hosts_comma_separated(self):
        """Test parsing comma-separated ALLOWED_HOSTS."""
        # This tests the actual logic from settings.py
        allowed_hosts_str = 'domain1.com,domain2.com,domain3.com'
        
        if ',' in allowed_hosts_str:
            result = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()]
        else:
            result = allowed_hosts_str.split()
        
        self.assertEqual(result, ['domain1.com', 'domain2.com', 'domain3.com'])
    
    def test_allowed_hosts_space_separated(self):
        """Test parsing space-separated ALLOWED_HOSTS."""
        allowed_hosts_str = 'domain1.com domain2.com domain3.com'
        
        if ',' in allowed_hosts_str:
            result = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()]
        else:
            result = allowed_hosts_str.split()
        
        self.assertEqual(result, ['domain1.com', 'domain2.com', 'domain3.com'])
    
    def test_allowed_hosts_single(self):
        """Test single host."""
        allowed_hosts_str = 'localhost'
        
        if ',' in allowed_hosts_str:
            result = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()]
        else:
            result = allowed_hosts_str.split()
        
        self.assertEqual(result, ['localhost'])
    
    def test_allowed_hosts_mixed_separators(self):
        """Test mixed separators with spaces."""
        allowed_hosts_str = 'domain1.com, domain2.com domain3.com'
        
        if ',' in allowed_hosts_str:
            result = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()]
        else:
            result = allowed_hosts_str.split()
        
        self.assertEqual(result, ['domain1.com', 'domain2.com domain3.com'])


class CrontabParsingTestCase(TestCase):
    """Test crontab string parsing."""
    
    def setUp(self):
        self.test_vars = []
    
    def tearDown(self):
        for var in self.test_vars:
            if var in os.environ:
                del os.environ[var]
    
    def _set_env(self, key, value):
        os.environ[key] = str(value)
        self.test_vars.append(key)
    
    def test_parse_crontab_five_fields(self):
        """Test parsing standard 5-field crontab."""
        from ok_tools.settings import parse_crontab_env
        
        self._set_env('TEST_CRON', '*/30 * * * *')
        schedule = parse_crontab_env('TEST_CRON')
        
        self.assertEqual(str(schedule.minute), '*/30')
        self.assertEqual(str(schedule.hour), '*')
        self.assertEqual(str(schedule.day_of_month), '*')
        self.assertEqual(str(schedule.month_of_year), '*')
        self.assertEqual(str(schedule.day_of_week), '*')
    
    def test_parse_crontab_three_fields(self):
        """Test parsing 3-field crontab (should add * for missing)."""
        from ok_tools.settings import parse_crontab_env
        
        self._set_env('TEST_CRON', '*/30 * *')
        schedule = parse_crontab_env('TEST_CRON')
        
        self.assertEqual(str(schedule.minute), '*/30')
        self.assertEqual(str(schedule.hour), '*')
        self.assertEqual(str(schedule.day_of_month), '*')
        self.assertEqual(str(schedule.month_of_year), '*')  # Added
        self.assertEqual(str(schedule.day_of_week), '*')     # Added
    
    def test_parse_crontab_default(self):
        """Test default crontab value."""
        from ok_tools.settings import parse_crontab_env
        
        schedule = parse_crontab_env('NONEXISTENT_CRON', default='0 3 * * *')
        
        self.assertEqual(str(schedule.minute), '0')
        self.assertEqual(str(schedule.hour), '3')
    
    def test_parse_crontab_complex(self):
        """Test complex crontab expression."""
        from ok_tools.settings import parse_crontab_env
        
        self._set_env('TEST_CRON', '0 */2 * * 1-5')
        schedule = parse_crontab_env('TEST_CRON')
        
        self.assertEqual(str(schedule.minute), '0')
        self.assertEqual(str(schedule.hour), '*/2')
        self.assertEqual(str(schedule.day_of_week), '1-5')
    
    def test_parse_crontab_single_field(self):
        """Test parsing 1-field crontab (should add * for missing)."""
        from ok_tools.settings import parse_crontab_env
        
        self._set_env('TEST_CRON', '0')
        schedule = parse_crontab_env('TEST_CRON')
        
        self.assertEqual(str(schedule.minute), '0')
        self.assertEqual(str(schedule.hour), '*')
        self.assertEqual(str(schedule.day_of_month), '*')
        self.assertEqual(str(schedule.month_of_year), '*')
        self.assertEqual(str(schedule.day_of_week), '*')


class BackwardCompatibilityTestCase(TestCase):
    """Test backward compatibility with .cfg files."""
    
    def setUp(self):
        self.test_vars = []
    
    def tearDown(self):
        for var in self.test_vars:
            if var in os.environ:
                del os.environ[var]
    
    def _set_env(self, key, value):
        os.environ[key] = str(value)
        self.test_vars.append(key)
    
    @patch('ok_tools.settings.config')
    def test_get_config_env_priority(self, mock_config):
        """Test that ENV variables take priority over .cfg."""
        from ok_tools.settings import get_config
        
        # Set up mock config
        mock_config.get.return_value = 'cfg_value'
        
        # Set env var
        self._set_env('TEST_SECTION_KEY', 'env_value')
        
        # Test that env value is returned
        result = get_config('test', 'key', fallback='fallback')
        self.assertEqual(result, 'env_value')
        
        # Verify config.get was not called
        mock_config.get.assert_not_called()
    
    @patch('ok_tools.settings.config')
    @patch('ok_tools.settings.CONFIG_FILE_USED', True)
    def test_get_config_fallback_to_cfg(self, mock_config):
        """Test fallback to .cfg when ENV not set."""
        from ok_tools.settings import get_config
        
        # Set up mock config
        mock_config.get.return_value = 'cfg_value'
        
        # Test that cfg value is returned when env not set
        result = get_config('test', 'key', fallback='fallback')
        self.assertEqual(result, 'cfg_value')
        
        # Verify config.get was called
        mock_config.get.assert_called_once_with('test', 'key', fallback='fallback')
    
    @patch('ok_tools.settings.config')
    @patch('ok_tools.settings.CONFIG_FILE_USED', True)
    def test_get_config_fallback_to_default(self, mock_config):
        """Test fallback to default when both ENV and .cfg fail."""
        from ok_tools.settings import get_config
        
        # Set up mock config to raise exception
        mock_config.get.side_effect = Exception("Config error")
        
        # Test that fallback is returned
        result = get_config('test', 'key', fallback='fallback')
        self.assertEqual(result, 'fallback')
    
    def test_deprecation_warning_shown(self):
        """Test that deprecation warning is logged when .cfg used."""
        with patch.dict(os.environ, {'OKTOOLS_CONFIG_FILE': '/path/to/config.cfg'}):
            with patch('ok_tools.settings.config') as mock_config:
                with patch('builtins.open', create=True) as mock_open:
                    with patch('ok_tools.settings.logger') as mock_logger:
                        # Set up mock file
                        mock_file = MagicMock()
                        mock_file.__enter__.return_value = mock_file
                        mock_open.return_value = mock_file
                        mock_config.read_file.return_value = None
                        
                        # Re-import settings to trigger warning
                        import importlib
                        import ok_tools.settings
                        importlib.reload(ok_tools.settings)
                        
                        # Verify warning was logged
                        mock_logger.warning.assert_called_with("Using deprecated .cfg file. Please migrate to .env")


class SettingsIntegrationTestCase(TestCase):
    """Integration tests for actual Django settings."""
    
    def test_debug_setting(self):
        """Test DEBUG setting can be read."""
        from django.conf import settings
        # DEBUG should be boolean
        self.assertIsInstance(settings.DEBUG, bool)
    
    def test_allowed_hosts_setting(self):
        """Test ALLOWED_HOSTS is a list."""
        from django.conf import settings
        self.assertIsInstance(settings.ALLOWED_HOSTS, list)
    
    def test_database_settings(self):
        """Test database configuration exists."""
        from django.conf import settings
        self.assertIn('default', settings.DATABASES)
        self.assertIn('NAME', settings.DATABASES['default'])
    
    def test_celery_settings(self):
        """Test Celery configuration exists."""
        from django.conf import settings
        self.assertIsNotNone(settings.CELERY_BROKER_URL)
        self.assertIsNotNone(settings.CELERY_RESULT_BACKEND)
    
    def test_celery_beat_schedule(self):
        """Test Celery Beat schedules are configured."""
        from django.conf import settings
        self.assertIsInstance(settings.CELERY_BEAT_SCHEDULE, dict)
        self.assertIn('expire_rentals', settings.CELERY_BEAT_SCHEDULE)
    
    def test_celery_beat_schedule_structure(self):
        """Test Celery Beat schedule has correct structure."""
        from django.conf import settings
        
        for task_name, task_config in settings.CELERY_BEAT_SCHEDULE.items():
            self.assertIn('task', task_config)
            self.assertIn('schedule', task_config)
            self.assertTrue(hasattr(task_config['schedule'], '__class__'))
    
    @override_settings(DEBUG=True)
    def test_debug_override(self):
        """Test that DEBUG can be overridden."""
        from django.conf import settings
        self.assertTrue(settings.DEBUG)
    
    @override_settings(ALLOWED_HOSTS=['example.com'])
    def test_allowed_hosts_override(self):
        """Test that ALLOWED_HOSTS can be overridden."""
        from django.conf import settings
        self.assertIn('example.com', settings.ALLOWED_HOSTS)


class EnvConfigFileTestCase(TestCase):
    """Test configuration file handling."""
    
    def setUp(self):
        self.test_vars = []
    
    def tearDown(self):
        for var in self.test_vars:
            if var in os.environ:
                del os.environ[var]
    
    def _set_env(self, key, value):
        os.environ[key] = str(value)
        self.test_vars.append(key)
    
    @patch('ok_tools.settings.config')
    def test_config_file_used_flag(self, mock_config):
        """Test CONFIG_FILE_USED flag is set when config file is used."""
        with patch.dict(os.environ, {'OKTOOLS_CONFIG_FILE': '/path/to/config.cfg'}):
            with patch('builtins.open', create=True) as mock_open:
                # Set up mock file
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_open.return_value = mock_file
                mock_config.read_file.return_value = None
                
                # Re-import settings to trigger config file loading
                import importlib
                import ok_tools.settings
                importlib.reload(ok_tools.settings)
                
                # Check that CONFIG_FILE_USED is True
                self.assertTrue(ok_tools.settings.CONFIG_FILE_USED)
    
    def test_no_config_file_warning(self):
        """Test warning when no config file is found."""
        with patch('ok_tools.settings.logger') as mock_logger:
            # Re-import settings without config file
            import importlib
            import ok_tools.settings
            importlib.reload(ok_tools.settings)
            
            # Verify warning was logged
            mock_logger.warning.assert_called_with(
                "No config file found for ok-tools." " Switching to fallbacks."
            )