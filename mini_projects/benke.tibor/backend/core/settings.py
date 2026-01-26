"""
Django settings for KnowledgeRouter project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Structured logging setup (import early to configure before Django)
from infrastructure.structured_logging import setup_structured_logging  # noqa: E402

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-test-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Feature flags
USE_SIMPLE_PIPELINE = os.getenv('USE_SIMPLE_PIPELINE', 'False') == 'True'  # True = old fast pipeline, False = new LangGraph workflow

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'corsheaders',
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]

CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'hu-hu'
TIME_ZONE = 'Europe/Budapest'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# LLM Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Timeout and Retry Configuration
OPENAI_TIMEOUT = int(os.getenv('OPENAI_TIMEOUT', 30))  # seconds
OPENAI_MAX_RETRIES = int(os.getenv('OPENAI_MAX_RETRIES', 3))
RAG_TIMEOUT = int(os.getenv('RAG_TIMEOUT', 10))  # seconds

# Vector DB Configuration
QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', 6334))
QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

# Multi-domain collection with domain filtering (NEW approach)
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION', 'multi_domain_kb')

# Legacy: Individual collections per domain (backward compatibility)
# Not used with multi_domain_kb approach - all domains in one collection with filters
QDRANT_COLLECTIONS = {
    'hr': os.getenv('QDRANT_COLLECTION_HR', 'multi_domain_kb'),
    'it': os.getenv('QDRANT_COLLECTION_IT', 'multi_domain_kb'),
    'finance': os.getenv('QDRANT_COLLECTION_FINANCE', 'multi_domain_kb'),
    'legal': 'multi_domain_kb',
    'marketing': 'multi_domain_kb',  # All domains use same collection with domain filter
    'general': 'multi_domain_kb',
}

# Embedding model
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')

# LLM settings
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.7))
MAX_TOKENS = int(os.getenv('MAX_TOKENS', 2048))

# Data directories
DATA_DIR = BASE_DIR / 'data'
USERS_DIR = DATA_DIR / 'users'
SESSIONS_DIR = DATA_DIR / 'sessions'
FILES_DIR = DATA_DIR / 'files'

# Create directories if they don't exist
for directory in [USERS_DIR, SESSIONS_DIR, FILES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# STRUCTURED LOGGING SETUP (Loki Integration)
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
JSON_LOGGING = os.getenv("JSON_LOGGING", "true").lower() == "true"

# Setup structured logging (replaces Django's default logging)
setup_structured_logging(
    log_level=LOG_LEVEL,
    log_file=None,  # stdout only for Docker
    json_format=JSON_LOGGING
)

print(f"✅ Loki structured logging enabled: level={LOG_LEVEL}, json={JSON_LOGGING}")

# Django LOGGING config (kept for compatibility, but overridden by structured_logging)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,  # Keep this False so our setup works
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,  # Use environment variable
    },
}
