"""
Configuración de Django para SIPD.

Todos los valores sensibles se leen de variables de entorno (.env).
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")


def env(name: str, default=None):
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return str(env(name, str(default))).strip().lower() in {"1", "true", "yes", "si", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in str(env(name, default)).split(",") if item.strip()]


# Vercel define VERCEL=1 en el entorno de sus funciones.
ON_VERCEL = env_bool("VERCEL", False)

DEBUG = env_bool("DEBUG", False)
SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or "test" in sys.argv:
        SECRET_KEY = "insecure-dev-only-key-change-me"
    else:
        raise ImproperlyConfigured("SECRET_KEY es obligatorio cuando DEBUG=False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,backend")
if ON_VERCEL:
    # Dominios *.vercel.app del despliegue; los dominios propios se agregan en ALLOWED_HOSTS.
    ALLOWED_HOSTS += [".vercel.app"] + [
        host for host in (env("VERCEL_URL"), env("VERCEL_BRANCH_URL"), env("VERCEL_PROJECT_PRODUCTION_URL")) if host
    ]

# --- Paquete de Machine Learning (carpeta ml/ del proyecto) -------------------
ML_DIR = Path(env("ML_DIR", PROJECT_ROOT / "ml"))
ML_MODELS_DIR = Path(env("ML_MODELS_DIR", ML_DIR / "models"))
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "users",
    "academic",
    "students",
    "ml",
    "predictions",
    "followups",
    "uploads",
    "audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# --- Base de datos: PostgreSQL ------------------------------------------------
# En Vercel, la integración de Neon/Postgres define DATABASE_URL (o POSTGRES_URL).
DATABASE_URL = env("DATABASE_URL") or env("POSTGRES_URL")
if DATABASE_URL:
    # Funciones serverless: sin conexiones persistentes y compatibles con poolers (PgBouncer).
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=0 if ON_VERCEL else 60)}
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = ON_VERCEL
elif ON_VERCEL:
    raise ImproperlyConfigured("Defina DATABASE_URL (PostgreSQL) en las variables de entorno de Vercel.")
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "sipd"),
            "USER": env("DB_USER", "sipd"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = env("TIME_ZONE", "America/Bogota")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", "/tmp/sipd-media" if ON_VERCEL else BASE_DIR / "media"))
if ON_VERCEL:
    # Sistema de archivos de sólo lectura: WhiteNoise sirve los estáticos sin collectstatic.
    WHITENOISE_USE_FINDERS = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API REST -----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    "COERCE_DECIMAL_TO_STRING": False,
    "DEFAULT_THROTTLE_RATES": {"login": env("LOGIN_THROTTLE_RATE", "10/min")},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_TOKEN_LIFETIME", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_REFRESH_TOKEN_LIFETIME", "1440"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))

# --- Umbrales de riesgo (ÚNICA fuente de verdad) ------------------------------
RISK_LOW_THRESHOLD = float(env("RISK_LOW_THRESHOLD", "0.30"))
RISK_MEDIUM_THRESHOLD = float(env("RISK_MEDIUM_THRESHOLD", "0.60"))

# --- Reglas académicas institucionales ----------------------------------------
GPA_MIN = float(env("GPA_MIN", "0.0"))
GPA_MAX = float(env("GPA_MAX", "5.0"))

# --- Carga de archivos --------------------------------------------------------
# Vercel limita el cuerpo de las peticiones a 4,5 MB.
UPLOAD_MAX_BYTES = int(env("UPLOAD_MAX_BYTES", str((4 if ON_VERCEL else 5) * 1024 * 1024)))
UPLOAD_MAX_ROWS = int(env("UPLOAD_MAX_ROWS", "50000"))
FILE_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_BYTES + 1024 * 1024

# --- Seguridad en producción --------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
if ON_VERCEL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
