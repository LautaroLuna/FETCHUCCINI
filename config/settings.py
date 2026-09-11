import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development keeps a harmless fallback key. Production (Render) receives
# a generated SECRET_KEY through environment variables.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

_default_debug = "False" if os.environ.get("RENDER") else "True"
DEBUG = os.environ.get("DEBUG", _default_debug).strip().lower() in {"1", "true", "yes", "on"}

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
render_host = (os.environ.get("RENDER_EXTERNAL_HOSTNAME") or "").strip()
if render_host:
    ALLOWED_HOSTS.append(render_host)
for host in (os.environ.get("ALLOWED_HOSTS") or "").split(","):
    host = host.strip()
    if host and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = []
if render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")
for origin in (os.environ.get("CSRF_TRUSTED_ORIGINS") or "").split(","):
    origin = origin.strip()
    if origin:
        CSRF_TRUSTED_ORIGINS.append(origin)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "searchapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Fetchuccini currently does not persist user-generated data. SQLite is enough
# for Django's built-in tables. On Render Free this file is ephemeral, which is
# acceptable for the current public MVP because the app does not depend on it.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Render Free has an ephemeral filesystem. /tmp is appropriate for the short
# cache used by Fetchuccini; local development keeps the cache in the project.
_default_cache = "/tmp/fetchuccini-cache" if os.environ.get("RENDER") else str(BASE_DIR / ".cache" / "fetchuccini")
CACHE_DIR = Path(os.environ.get("FETCHUCCINI_CACHE_DIR", _default_cache))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(CACHE_DIR),
        "OPTIONS": {
            "MAX_ENTRIES": 5000,
            "CULL_FREQUENCY": 3,
        },
    }
}

# Render terminates TLS before proxying requests to Gunicorn.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = "DENY"
