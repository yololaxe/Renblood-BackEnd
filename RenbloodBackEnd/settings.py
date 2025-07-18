from pathlib import Path
import os
from dotenv import load_dotenv
from corsheaders.defaults import default_headers

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '7i$q*aq)$3solh4xc_)8z$m2wqfmm&6+=!-kg5o$j9%v+c3ikp'
API_KEY_RENBLOOD = os.getenv("API_KEY_RENBLOOD")
DISCORD_CLIENT_ID       = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET   = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI    = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_BOT_TOKEN       = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID        = os.getenv("DISCORD_GUILD_ID")
DISCORD_ROLE_ID         = os.getenv("DISCORD_ROLE_ID")
FRONTEND_URL            = os.getenv("FRONTEND_URL")
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "corsheaders",
    'players',  # Ajout de l'application
    'jobs',
    'game_sessions',
    'rest_framework',
    'channels'
]


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Ajout du middleware CORS
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "https://renblood-frontend.onrender.com",
    "https://renblood-backend-production.up.railway.app",
    "https://renblood-website.web.app"
]
# CORS_ALLOW_ALL_ORIGINS = True  # ⚠️ à ne pas laisser en prod

CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-firebase-uid",
    "x-api-key",
]

ASGI_APPLICATION = 'RenbloodBackEnd.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS"
]

ROOT_URLCONF = 'RenbloodBackEnd.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'RenbloodBackEnd.wsgi.application'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.AllowAllUsersModelBackend',
]

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

# Charger les variables d'environnement depuis un fichier .env
load_dotenv()



DATABASES = {
    'default': {
        'ENGINE': 'djongo',
        'NAME': os.getenv('MONGO_DB_NAME', 'renblood_mongo'),
        'ENFORCE_SCHEMA': False,
        'CLIENT': {
            'host': os.getenv('MONGO_DB_URI'),
            'tls': True,
            'tlsAllowInvalidCertificates': True
        }
    }
}

ALLOWED_HOSTS = [
    "renblood-backend.onrender.com", 
    "127.0.0.1", 
    "localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "renblood-backend-production.up.railway.app",
    "renblood-website.web.app"
]


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-fr'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'
