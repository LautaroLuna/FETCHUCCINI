import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

FETCHUCCINI_VERSION = "0.36"
FETCHUCCINI_STORE_CONCURRENCY = max(1, int(os.environ.get("FETCHUCCINI_STORE_CONCURRENCY", "4")))
FETCHUCCINI_GLOBAL_STORE_CONCURRENCY = max(1, int(os.environ.get("FETCHUCCINI_GLOBAL_STORE_CONCURRENCY", "6")))
FETCHUCCINI_STORE_GATE_WAIT_SECONDS = max(1.0, float(os.environ.get("FETCHUCCINI_STORE_GATE_WAIT_SECONDS", "20")))
FETCHUCCINI_REFRESH_LOCK_SECONDS = max(10, int(os.environ.get("FETCHUCCINI_REFRESH_LOCK_SECONDS", "60")))
FETCHUCCINI_REFRESH_WAIT_SECONDS = max(0.2, float(os.environ.get("FETCHUCCINI_REFRESH_WAIT_SECONDS", "2.5")))

# Local development keeps a harmless fallback key. Production (Render) receives
# a generated SECRET_KEY through environment variables.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

is_render = bool(os.environ.get("RENDER"))
is_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_SERVICE_ID"))

_default_debug = "False" if (is_render or is_railway) else "True"
DEBUG = os.environ.get("DEBUG", _default_debug).strip().lower() in {"1", "true", "yes", "on"}

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

render_host = (os.environ.get("RENDER_EXTERNAL_HOSTNAME") or "").strip()
if render_host:
    ALLOWED_HOSTS.append(render_host)

railway_host = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip()
if railway_host:
    ALLOWED_HOSTS.append(railway_host)

# Railway health checks use this hostname when probing the service.
if is_railway and "healthcheck.railway.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("healthcheck.railway.app")

for host in (os.environ.get("ALLOWED_HOSTS") or "").split(","):
    host = host.strip()
    if host and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = []
if render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")
if railway_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_host}")
for origin in (os.environ.get("CSRF_TRUSTED_ORIGINS") or "").split(","):
    origin = origin.strip()
    if origin:
        CSRF_TRUSTED_ORIGINS.append(origin)

# v0.23: Pirulo and Mercadia now use public storefront API fallbacks instead of
# relying only on HTML/search hosts that reject some datacenter IPs. Keep every
# store enabled by default; FETCHUCCINI_DISABLED_STORES can still disable any
# adapter immediately from the hosting environment if a store changes again.
_default_disabled_stores = ""
FETCHUCCINI_DISABLED_STORES = tuple(
    store.strip()
    for store in os.environ.get("FETCHUCCINI_DISABLED_STORES", _default_disabled_stores).split(",")
    if store.strip()
)


# v0.26: Mercadia Bridge. Railway cannot currently query Mercadia directly
# (HTTP 403 from the storefront). A trusted local Fetchuccini installation can
# sync requested Mercadia searches into Railway over HTTPS using this secret.
MERCADIA_BRIDGE_KEY = (os.environ.get("MERCADIA_BRIDGE_KEY") or "").strip()
MERCADIA_BRIDGE_ENABLED = bool(MERCADIA_BRIDGE_KEY) and (
    is_render or is_railway or
    (os.environ.get("MERCADIA_BRIDGE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}
)

# v0.29: persistent Mercadia catalog uploaded by the Windows bridge.
# If a Railway Volume is mounted at /data, the catalog survives deploys and
# restarts. Without a volume Railway falls back to /tmp; the bridge can rebuild
# it on the next scheduled sync.
_catalog_dir_env = (os.environ.get("MERCADIA_CATALOG_DIR") or "").strip()
if _catalog_dir_env:
    MERCADIA_CATALOG_DIR = Path(_catalog_dir_env)
elif is_railway and Path("/data").exists():
    MERCADIA_CATALOG_DIR = Path("/data/fetchuccini")
elif is_render and Path("/data").exists():
    MERCADIA_CATALOG_DIR = Path("/data/fetchuccini")
elif is_railway or is_render:
    MERCADIA_CATALOG_DIR = Path("/tmp/fetchuccini-data")
else:
    MERCADIA_CATALOG_DIR = BASE_DIR / ".data" / "fetchuccini"
MERCADIA_CATALOG_DIR.mkdir(parents=True, exist_ok=True)

# v0.35: catalog freshness / publish safety. The Windows sync normally runs
# every 6 hours, so 12h is a warning and 36h is treated as stale. A suspicious
# full-catalog shrink is rejected server-side and the last good snapshot stays.
MERCADIA_CATALOG_WARN_AGE_SECONDS = int(os.environ.get("MERCADIA_CATALOG_WARN_AGE_SECONDS", 12 * 60 * 60))
MERCADIA_CATALOG_STALE_AGE_SECONDS = int(os.environ.get("MERCADIA_CATALOG_STALE_AGE_SECONDS", 36 * 60 * 60))
MERCADIA_CATALOG_MIN_PUBLISH_COUNT = int(os.environ.get("MERCADIA_CATALOG_MIN_PUBLISH_COUNT", 15000))
MERCADIA_CATALOG_MIN_PUBLISH_RATIO = float(os.environ.get("MERCADIA_CATALOG_MIN_PUBLISH_RATIO", "0.65"))
MERCADIA_STAGING_MAX_AGE_SECONDS = int(os.environ.get("MERCADIA_STAGING_MAX_AGE_SECONDS", 24 * 60 * 60))

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
    "searchapp.middleware.RequestObservabilityMiddleware",
    "searchapp.middleware.ResponseSecurityHeadersMiddleware",
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

# v0.36: Redis is optional but preferred in production. With REDIS_URL set,
# cache/rate-limits/circuit-breakers are shared across Gunicorn workers and
# future Railway replicas. Without Redis the app keeps the proven file cache.
REDIS_URL = (os.environ.get("REDIS_URL") or "").strip()
if REDIS_URL:
    FETCHUCCINI_CACHE_BACKEND = "redis"
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "fetchuccini",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,
                "SOCKET_CONNECT_TIMEOUT": 2,
                "SOCKET_TIMEOUT": 2,
            },
        }
    }
else:
    FETCHUCCINI_CACHE_BACKEND = "file"
    _default_cache = "/tmp/fetchuccini-cache" if (is_render or is_railway) else str(BASE_DIR / ".cache" / "fetchuccini")
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
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
# Start HSTS conservatively; Railway/Render terminate HTTPS before Django.
SECURE_HSTS_SECONDS = 3600 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# v0.36: compact production observability. Keep Django/Gunicorn defaults and
# raise only Fetchuccini's operational loggers to INFO.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "fetchuccini.requests": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "searchapp.services.aggregator": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "searchapp.services.resilience": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
