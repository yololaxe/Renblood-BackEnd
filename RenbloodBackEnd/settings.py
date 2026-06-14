from pathlib import Path
import logging
import os

from corsheaders.defaults import default_headers
from RenbloodBackEnd.environment import load_environment


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DJANGO_ENV, ENV_FILE = load_environment(BASE_DIR)

logger = logging.getLogger("renblood.startup")


def _parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value, default=None):
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def _require_env(name):
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


DEBUG = _parse_bool(os.getenv("DEBUG"), default=(DJANGO_ENV == "local"))

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DJANGO_ENV == "local":
        SECRET_KEY = "local-development-only"
    else:
        raise RuntimeError("Missing required environment variable: SECRET_KEY")

MONGO_URI = _require_env("MONGO_URI")
MONGO_DB_NAME = os.getenv(
    "MONGO_DB_NAME",
    {
        "production": "renblood_mongo",
        "staging": "renblood_mongo_staging",
        "local": "renblood_mongo_staging",
    }[DJANGO_ENV],
).strip()

if DJANGO_ENV == "staging" and MONGO_DB_NAME == "renblood_mongo":
    raise RuntimeError(
        "Unsafe configuration refused: staging cannot use the production MongoDB database renblood_mongo."
    )
if DJANGO_ENV == "production" and MONGO_DB_NAME == "renblood_mongo_staging":
    raise RuntimeError(
        "Unsafe configuration refused: production cannot use the staging MongoDB database renblood_mongo_staging."
    )

DEFAULT_ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "renblood-backend-production.up.railway.app",
    "renblood-backend-staging.up.railway.app",
    "renblood-backend.onrender.com",
]
ALLOWED_HOSTS = _parse_csv(os.getenv("ALLOWED_HOSTS"), default=DEFAULT_ALLOWED_HOSTS)

DEFAULT_CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "https://renblood-frontend.onrender.com",
    "https://renblood-backend-production.up.railway.app",
    "https://renblood-website.web.app",
    "https://renblood-staging.web.app",
]
CORS_ALLOWED_ORIGINS = _parse_csv(
    os.getenv("CORS_ALLOWED_ORIGINS"),
    default=DEFAULT_CORS_ALLOWED_ORIGINS,
)

API_KEY_RENBLOOD = os.getenv("API_KEY_RENBLOOD")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DISCORD_ROLE_ID = os.getenv("DISCORD_ROLE_ID")
FRONTEND_URL = os.getenv("FRONTEND_URL")

print(f"Renblood backend startup: environment={DJANGO_ENV} database={MONGO_DB_NAME}")
logger.info(
    "Renblood backend startup environment=%s database=%s",
    DJANGO_ENV,
    MONGO_DB_NAME,
)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "players",
    "jobs",
    "game_sessions",
    "rest_framework",
    "channels",
    "quests",
    "npcs",
    "markets",
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-firebase-uid",
    "x-api-key",
]

ASGI_APPLICATION = "RenbloodBackEnd.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
]

ROOT_URLCONF = "RenbloodBackEnd.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "RenbloodBackEnd.wsgi.application"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.AllowAllUsersModelBackend",
]

DATABASES = {
    "default": {
        "ENGINE": "djongo",
        "NAME": MONGO_DB_NAME,
        "ENFORCE_SCHEMA": False,
        "CLIENT": {
            "host": MONGO_URI,
            "tls": True,
            "tlsAllowInvalidCertificates": True,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"
