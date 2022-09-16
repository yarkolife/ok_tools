"""
Django settings for ok_tools project.

Generated by 'django-admin startproject' using Django 4.0.5.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.0/ref/settings/
"""

from django.contrib.messages import constants as messages
from pathlib import Path
import configparser
import logging
import os


# Logger for settings.py
logger = logging.getLogger(__name__)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# parse configurations, set by component
config = configparser.RawConfigParser()
if 'OKTOOLS_CONFIG_FILE' in os.environ:
    config.read_file(open(
        os.environ.get('OKTOOLS_CONFIG_FILE'), encoding='utf-8'
    ))
else:
    logger.warning("No config file found for ok-tools."
                   " Switching to fallbacks.")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config.get('django', 'secret_key', fallback=None)


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config.getboolean('django', 'debug', fallback=False)

hosts = config.get('django', 'allowed_hosts', fallback=None)
ALLOWED_HOSTS = hosts.split() if hosts else ['localhost']

# Loglevel
DJANGO_LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO')

# Application definition

INSTALLED_APPS = [
    'registration',
    'licenses',
    'projects',
    'contributions',

    'admin_searchable_dropdown',
    'bootstrap_datepicker_plus',
    'crispy_forms',
    'django_extensions',
    'django_admin_listfilter_dropdown',
    'rangefilter',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ok_tools.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR/'licenses'/'templates',
            BASE_DIR/'ok_tools'/'templates',
            BASE_DIR/'registration'/'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'registration.context_processors.context',
            ],
        },
    },
]


WSGI_APPLICATION = 'ok_tools.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


use_secure_settings = config.get('django', 'use_secure_settings', fallback=False)

if use_secure_settings:
    CSRF_TRUSTED_ORIGINS = [f'https://{h}' for h in hosts]
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    CORS_ORIGIN_WHITELIST = ['https://okmq.gocept.fcio.net/']

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = config.get('django', 'language', fallback='de-de')

TIME_ZONE = config.get('django', 'timezone', fallback='Europe/Berlin')

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / 'registration/locale'
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

STATICFILES_DIR = [
    os.path.join(BASE_DIR, 'static'),
]
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_ROOT = config.get('django', 'static', fallback='static/')
STATIC_URL = 'static/'

# ManifestStaticFilesStorage is recommended in production, to prevent outdatedhttp://localhost:8000/
# JavaScript / CSS assets being served from cache (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/3.1/ref/contrib/staticfiles/#manifeststaticfilesstorage
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# authenticatable users
AUTH_USER_MODEL = 'registration.OKUser'
AUTHENTICATION_BACKENDS = ['registration.backends.EmailBackend']

# TODO config?
# Phone Number Validation
PHONENUMBER_DEFAULT_REGION = 'DE'

# Date format
DATE_INPUT_FORMATS = '%d.%m.%Y'

# Default city and zipcode for Address
CITY = 'Merseburg'
ZIPCODE = '06217'

# email
# send the mails to stdout


mail_dev_settings = config.get('django', 'mail_dev_settings', fallback=True)

if mail_dev_settings:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

EMAIL_HOST = config.get('django', 'email_host', fallback='')
EMAIL_PORT = config.get('django', 'email_port', fallback=587)
EMAIL_USE_TLS = config.get('django', 'email_use_tls', fallback=True)
EMAIL_HOST_USER = config.get('django', 'email_host_user', fallback='')
EMAIL_HOST_PASSWORD = config.get('django', 'email_host_password', fallback='')




# name of the OK
OK_NAME = 'Offener Kanal Merseburg-Querfurt e.V.'
OK_NAME_SHORT = 'OK Merseburg'

# the fixed duration of a screen board (Bildschirmtafel) in seconds
SCREEN_BOARD_DURATION = 20

# Which site should be seen after log in and log out
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# bootstrap
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# bootstrap message tags
# For warnings and errors both, the bootstrap tag (alert-*) and the django tag,
# is set to support the user side and the admin side with colorfully messages.
MESSAGE_TAGS = {
    messages.DEBUG: 'alert-secondary',
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning warning',
    messages.ERROR: 'alert-danger error',
}

# path to legacy data
LEGACY_DATA = '../legacy_data/data.xlsx'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'timestamp': {
            'format': '{asctime} {levelname} {message}',
            'style': '{',
        },
        'levelname': {
            'format': '{levelname} {message}',
            'style': '{',
        }
    },
    'handlers': {
        'file': {
            'level': DJANGO_LOG_LEVEL,
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'ok_tools-debug.log'),
            'formatter': 'timestamp',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'levelname',
        }
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': DJANGO_LOG_LEVEL,
            'propagate': True,
        },
        'console': {
            'handlers': ['console'],
            'level': 'CRITICAL',
            'propagate': True,
        }
    },
}
