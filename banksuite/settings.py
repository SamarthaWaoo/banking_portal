"""
Django settings for banksuite project (SpendSmart Bank).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Auto-load .env if python-dotenv is installed (local development)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass  # dotenv not installed — env vars must be set another way (production)


# Auto-load .env if python-dotenv is installed (local development)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass  # dotenv not installed

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Auto-load .env if python-dotenv is installed (local development)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass  # dotenv not installed — env vars must be set another way (production)


# ---------------------------------------------------------------------------
# SECURITY
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-CHANGE_THIS_IN_PRODUCTION')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS = [f'https://{RENDER_EXTERNAL_HOSTNAME}']

# ---------------------------------------------------------------------------
# INSTALLED APPS
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'accounts',
    'upi',
    'loans',
    'admin_dashboard',
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

ROOT_URLCONF = 'banksuite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'banksuite.wsgi.application'

# ---------------------------------------------------------------------------
# DATABASE — MySQL (with SQLite fallback when DB_ENGINE is not set)
# ---------------------------------------------------------------------------
# DB_ENGINE choices: mysql (default) | postgres | sqlite3
_db_engine = os.environ.get('DB_ENGINE', 'mysql').lower()

# PostgreSQL via DATABASE_URL (Render / Railway / Heroku)
_database_url = os.environ.get('DATABASE_URL', '')

if _database_url and _database_url.startswith('postgres'):
    import dj_database_url
    DATABASES = {'default': dj_database_url.config(default=_database_url, conn_max_age=600)}

elif _db_engine == 'sqlite3':
    # ⚠ WARNING: SQLite is NOT persistent on Render/Railway — data is lost on restart.
    # Use MySQL or PostgreSQL for any deployed environment.
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

elif _db_engine == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     os.environ.get('DB_NAME',     'banksuite'),
            'USER':     os.environ.get('DB_USER',     'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST':     os.environ.get('DB_HOST',     '127.0.0.1'),
            'PORT':     os.environ.get('DB_PORT',     '5432'),
            'OPTIONS':  {'sslmode': os.environ.get('DB_SSLMODE', 'prefer')},
        }
    }

else:  # mysql (default)
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.mysql',
            'NAME':     os.environ.get('DB_NAME',     'banksuite'),
            'USER':     os.environ.get('DB_USER',     'root'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST':     os.environ.get('DB_HOST',     '127.0.0.1'),
            'PORT':     os.environ.get('DB_PORT',     '3306'),
            'OPTIONS':  {
                'sql_mode':     'STRICT_TRANS_TABLES',
                'charset':      'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL           = 'accounts:login'
LOGIN_REDIRECT_URL  = 'upi:dashboard'
LOGOUT_REDIRECT_URL = 'landing'

# ---------------------------------------------------------------------------
# INTERNATIONALISATION
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N      = True
USE_TZ        = True

# ---------------------------------------------------------------------------
# STATIC FILES
# ---------------------------------------------------------------------------
STATIC_URL       = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT      = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
            if not DEBUG
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# SESSION / SECURITY
# ---------------------------------------------------------------------------
# ── Admin registration protection ──────────────────────────────────────
# Set this in .env — anyone creating an admin account must supply this key.
ADMIN_REGISTRATION_SECRET = os.environ.get('ADMIN_REGISTRATION_SECRET', '')

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY    = False
X_FRAME_OPTIONS         = 'DENY'
