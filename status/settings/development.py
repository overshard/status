from . import *  # noqa


# Custom settings

BASE_URL = "http://localhost:8000"


# Core settings
# https://docs.djangoproject.com/en/4.0/ref/settings/#core-settings

SECRET_KEY = 'django-insecure-kbp9@ye$bf)$^l5-6q_4&2*ghbh29s*u)s2fy05xzj6gorvv!t'


# Debuggging
# https://docs.djangoproject.com/en/4.0/ref/settings/#debugging

DEBUG = True


# Security
# https://docs.djangoproject.com/en/4.0/ref/settings/#security

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8000',
]


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Media files (Images, Videos)
# https://docs.djangoproject.com/en/4.0/ref/settings/#media-root

MEDIA_URL = BASE_URL + '/media/'
