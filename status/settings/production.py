import os

from . import *  # noqa


# Custom settings

BASE_URL = os.environ.get("DJANGO_BASE_URL")


# Core settings
# https://docs.djangoproject.com/en/4.0/ref/settings/#core-settings

ALLOWED_HOSTS = [os.environ.get("DJANGO_BASE_URL").split("//")[1]]


# Debuggging
# https://docs.djangoproject.com/en/4.0/ref/settings/#debugging

DEBUG = False


# HTTP
# https://docs.djangoproject.com/en/4.0/ref/settings/#http

SECURE_BROWSER_XSS_FILTER = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
USE_X_FORWARDED_HOST = True


# Security
# https://docs.djangoproject.com/en/4.0/ref/settings/#security

CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [os.environ.get("DJANGO_BASE_URL")]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
SESSION_COOKIE_SECURE = True


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/data/db/db.sqlite3",
    }
}


# Media files (Images, Videos)
# https://docs.djangoproject.com/en/4.0/ref/settings/#media-root

MEDIA_URL = BASE_URL + "/media/"
MEDIA_ROOT = "/data/media"


# Logging
# https://docs.djangoproject.com/en/4.0/topics/logging/

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}
