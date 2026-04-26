import os
from pathlib import Path

from django.contrib.messages import constants as messages


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'accounts',
    'properties',
    'pages',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'status.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'status/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'status.context_processors.canonical',
                'status.context_processors.base_url',
            ],
        },
    },
]

WSGI_APPLICATION = 'status.wsgi.application'


# Messages
# https://docs.djangoproject.com/en/3.0/ref/settings/#messages

MESSAGE_TAGS = {
    messages.DEBUG: "alert-info",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATICFILES_DIRS = (BASE_DIR / "status/static",)
STATIC_ROOT = BASE_DIR / "static"


# Media files (Images, Videos)
# https://docs.djangoproject.com/en/4.0/ref/settings/#media-root

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / "media"


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            # WAL lets readers run concurrently with a writer; the scheduler
            # has several worker threads, so the default rollback journal
            # yields frequent "database is locked" errors. A 30s busy timeout
            # gives contending writers a chance to serialize rather than
            # fail, which previously stranded alert state mid-transition.
            'timeout': 30,
            'transaction_mode': 'IMMEDIATE',
            # mmap_size is intentionally omitted: gunicorn workers and the
            # scheduler each open their own connection, and SQLite's mmap is
            # documented as unsafe for multi-process writers — it amplified
            # an unrelated WAL inconsistency into full database corruption
            # on 2026-04-19.
            'init_command': (
                'PRAGMA journal_mode=WAL;'
                'PRAGMA synchronous=NORMAL;'
                'PRAGMA foreign_keys=ON;'
                'PRAGMA temp_store=MEMORY;'
                'PRAGMA journal_size_limit=67108864;'
                'PRAGMA cache_size=-20000;'
            ),
        },
    }
}


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Auth
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth

AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "properties"


# Email
# https://docs.djangoproject.com/en/4.0/topics/email/#console-backend

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
