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
# En Vercel el build lee estos settings (detección de WSGI, collectstatic) sin garantía de recibir las
# variables del proyecto; config/wsgi.py vuelve a exigir SECRET_KEY antes de atender peticiones.
SECRET_KEY_MISSING = not SECRET_KEY
if not SECRET_KEY:
    if DEBUG or "test" in sys.argv:
        SECRET_KEY = "insecure-dev-only-key-change-me"
    elif ON_VERCEL:
        SECRET_KEY = "vercel-build-only-placeholder"
    else:
        raise ImproperlyConfigured("SECRET_KEY es obligatorio cuando DEBUG=False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,backend")
if ON_VERCEL:
    # Dominios *.vercel.app del despliegue; los dominios propios se agregan en ALLOWED_HOSTS.
    ALLOWED_HOSTS += [".vercel.app"] + [
        host for host in (env("VERCEL_URL"), env("VERCEL_BRANCH_URL"), env("VERCEL_PROJECT_PRODUCTION_URL")) if host
    ]

# --- Machine Learning ----------------------------------------------------------
# El paquete sipd_ml y los artefactos entrenados viven dentro de backend/.
ML_MODELS_DIR = Path(env("ML_MODELS_DIR", BASE_DIR / "ml_models"))

# --- Reentrenamiento desde la interfaz web ---------------------------------------
# thread: hilo en segundo plano del propio proceso web (Docker/local).
# worker: la API sólo encola; `python manage.py process_training_runs` ejecuta.
# sync:   en la misma petición (sólo pruebas automatizadas).
# github: la API encola y lanza el flujo .github/workflows/train-models.yml, que entrena en GitHub Actions,
#         registra las versiones en esta misma BD y publica los artefactos con un commit (Vercel redespliega).
# disabled: valor por defecto en Vercel (disco efímero y tiempo máximo de función).
ML_TRAINING_EXECUTOR = env("ML_TRAINING_EXECUTOR", "disabled" if ON_VERCEL else "thread").strip().lower()
# Sin latido durante este tiempo, una ejecución se considera interrumpida (p. ej. reinicio del servidor).
# Con GitHub Actions se espera más: el ejecutor tarda unos minutos en arrancar e instalar dependencias.
ML_TRAINING_STALE_MINUTES = int(env("ML_TRAINING_STALE_MINUTES", "30" if ML_TRAINING_EXECUTOR == "github" else "10"))
# Lanzamiento automático del flujo (executor github). Sin token, el flujo se ejecuta a mano desde GitHub.
GITHUB_TRAINING_REPOSITORY = env("GITHUB_TRAINING_REPOSITORY", "")  # p. ej. "usuario/SIPD-UDES"
GITHUB_TRAINING_TOKEN = env("GITHUB_TRAINING_TOKEN", "")  # token de grano fino con permiso "Actions: write"
GITHUB_TRAINING_WORKFLOW = env("GITHUB_TRAINING_WORKFLOW", "train-models.yml")
GITHUB_TRAINING_REF = env("GITHUB_TRAINING_REF", "main")
# Mínimos técnicos para poder hacer la partición estratificada 75/25 y calcular métricas.
ML_TRAINING_MIN_ROWS = int(env("ML_TRAINING_MIN_ROWS", "100"))
ML_TRAINING_MIN_CLASS_ROWS = int(env("ML_TRAINING_MIN_CLASS_ROWS", "10"))


def _optional_float(name: str):
    value = env(name, "")
    return float(value) if str(value).strip() else None


# Criterios de aceptación opcionales (métricas sobre el conjunto de prueba). Vacíos = sin mínimo:
# el proyecto no define umbrales de rendimiento aprobados; cada institución debe fijarlos.
ML_ACCEPTANCE_MIN_METRICS = {
    metric: value for metric, value in {
        "f1": _optional_float("ML_ACCEPTANCE_MIN_F1"),
        "recall": _optional_float("ML_ACCEPTANCE_MIN_RECALL"),
        "precision": _optional_float("ML_ACCEPTANCE_MIN_PRECISION"),
        "roc_auc": _optional_float("ML_ACCEPTANCE_MIN_ROC_AUC"),
    }.items() if value is not None
}

# --- Correo (recuperación de contraseña) -------------------------------------
# Con EMAIL_HOST_USER definido se envía por SMTP (Gmail: smtp.gmail.com, 587, TLS y una "contraseña de
# aplicación"); si no, los correos se escriben en la consola del backend (útil en desarrollo).
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "15"))
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST_USER
                    else "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", f"SIPD <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "SIPD <no-reply@localhost>")
# Dirección pública del frontend: se usa en el enlace del correo de recuperación.
# En Vercel, sin FRONTEND_URL, se usa el dominio de producción del proyecto (el frontend se sirve ahí mismo).
_VERCEL_PRODUCTION_HOST = env("VERCEL_PROJECT_PRODUCTION_URL") if ON_VERCEL else None
FRONTEND_URL = env("FRONTEND_URL", f"https://{_VERCEL_PRODUCTION_HOST}" if _VERCEL_PRODUCTION_HOST
                   else "http://localhost:5173").rstrip("/")
# Vigencia del enlace de recuperación (segundos).
PASSWORD_RESET_TIMEOUT = int(env("PASSWORD_RESET_TIMEOUT", "1800"))

# Nombre institucional usado en los reportes PDF.
INSTITUTION_NAME = env("INSTITUTION_NAME", "Institución de Educación Superior")
# Máximo de filas por exportación CSV (evita exportaciones sin límite).
REPORT_EXPORT_MAX_ROWS = int(env("REPORT_EXPORT_MAX_ROWS", "50000"))

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
    "notifications",
    "reports",
    "alerts",
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
# En Vercel, la integración de Neon/Postgres define DATABASE_URL (o POSTGRES_URL), que pasa por
# el pooler, y DATABASE_URL_UNPOOLED (conexión directa). Se prefiere la directa: el arranque usa un
# candado de sesión de PostgreSQL que no funciona de forma fiable a través del pooler.
DATABASE_URL = (env("DATABASE_URL_UNPOOLED") if ON_VERCEL else None) or env("DATABASE_URL") or env("POSTGRES_URL")
if DATABASE_URL:
    # Funciones serverless: sin conexiones persistentes y compatibles con poolers (PgBouncer).
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=0 if ON_VERCEL else 60)}
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = ON_VERCEL
    if ON_VERCEL:
        # Que un fallo de conexión se reporte rápido y no agote el tiempo máximo de la función.
        DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 10
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
    "DEFAULT_AUTHENTICATION_CLASSES": ["users.tokens.SipdJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    "COERCE_DECIMAL_TO_STRING": False,
    "DEFAULT_THROTTLE_RATES": {
        "login": env("LOGIN_THROTTLE_RATE", "10/min"),
        "password_reset": env("PASSWORD_RESET_THROTTLE_RATE", "5/hour"),
    },
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

# Cookie HttpOnly del refresh token (Secure salvo en desarrollo o en Docker local por http).
AUTH_COOKIE_SECURE = env_bool("SECURE_COOKIES", not DEBUG)

# Número de proxies inversos de confianza delante de Django (Nginx en Docker, Vercel). Con 0 se usa
# REMOTE_ADDR y se ignora X-Forwarded-For, que un cliente podría falsificar.
TRUSTED_PROXY_COUNT = int(env("TRUSTED_PROXY_COUNT", "1" if ON_VERCEL else "0"))
REST_FRAMEWORK["NUM_PROXIES"] = TRUSTED_PROXY_COUNT or 0

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))

# --- Umbrales de riesgo (ÚNICA fuente de verdad) ------------------------------
RISK_LOW_THRESHOLD = float(env("RISK_LOW_THRESHOLD", "0.30"))
RISK_MEDIUM_THRESHOLD = float(env("RISK_MEDIUM_THRESHOLD", "0.60"))
# Alerta temprana por aumento de la probabilidad entre la predicción anterior y la actual (0.15 = 15 puntos).
# Es un parámetro de diseño, no un valor validado con datos institucionales.
ALERT_RISE_THRESHOLD = float(env("ALERT_RISE_THRESHOLD", "0.15"))

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
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    # Producción: HTTPS obligatorio y HSTS (1 año por defecto). Docker local por http los desactiva.
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True) and "test" not in sys.argv
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
if ON_VERCEL or TRUSTED_PROXY_COUNT:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
