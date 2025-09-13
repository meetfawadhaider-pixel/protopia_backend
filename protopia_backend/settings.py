# protopia_backend/protopia_backend/settings.py
import os
from pathlib import Path

# ─── .env support ──────────────────────────────────────────────────────────────
# pip install python-dotenv
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent

if load_dotenv:
    # Load variables from <project root>/.env
    load_dotenv(BASE_DIR / ".env")

# ─── Django core ───────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.getenv("DEBUG", "1") == "1"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# Frontend URL (used by Stripe success/cancel URLs too)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

INSTALLED_APPS = [
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "assessments",
    "stripe_integration",  # ← added
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

ROOT_URLCONF = "protopia_backend.urls"

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

WSGI_APPLICATION = "protopia_backend.wsgi.application"

# ─── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "protopia_db"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

# ─── Passwords ─────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── I18N / TZ ─────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─── Static ────────────────────────────────────────────────────────────────────
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Auth ──────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"  # custom email-based user

# ─── DRF / JWT ─────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# ─── CORS / CSRF (dev-friendly) ────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "1") == "1"
# (optional tighter setting for later)
CORS_ALLOWED_ORIGINS = [
    FRONTEND_URL,
]
CSRF_TRUSTED_ORIGINS = [
    FRONTEND_URL.replace("http://", "http://").replace("https://", "https://"),
]

# ─── Stripe config (read from .env) ────────────────────────────────────────────
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Price IDs (from your Stripe dashboard)
STRIPE_PRICE_WEEKLY = os.getenv("STRIPE_PRICE_WEEKLY", "")
STRIPE_PRICE_MONTHLY = os.getenv("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_YEARLY = os.getenv("STRIPE_PRICE_YEARLY", "")

# Helpful sanity check logs (dev only)
if DEBUG:
    missing = []
    for k in [
        "STRIPE_SECRET_KEY",
        "STRIPE_PRICE_WEEKLY",
        "STRIPE_PRICE_MONTHLY",
        "STRIPE_PRICE_YEARLY",
    ]:
        if not globals().get(k):
            missing.append(k)
    if missing:
        print("[Stripe] Missing env vars:", ", ".join(missing))

# ─── Email (SMTP) ──────────────────────────────────────────────────────────────
# Use Gmail SMTP with an App Password, or set your own SMTP via env
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# ─── Cache (stores 6-digit codes) ──────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "protopia-email-cache",
    }
}
