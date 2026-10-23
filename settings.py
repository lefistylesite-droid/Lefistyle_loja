"""LEFI | Moda autoral: configurações seguras para desenvolvimento e Render."""
import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DEBUG', '0') == '1'
SECRET_KEY = os.environ.get('SECRET_KEY', 'local-dev-only-change-before-production')
if not DEBUG and SECRET_KEY == 'local-dev-only-change-before-production':
    raise RuntimeError('Configure SECRET_KEY seguro na produção.')
ALLOWED_HOSTS = [x.strip() for x in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if x.strip()]
render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_host and render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_host)

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'store.apps.StoreConfig',
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
ROOT_URLCONF = 'lefi.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'store.context_processors.cart_summary',
        'store.context_processors.storefront_information',
    ]},
}]
WSGI_APPLICATION = 'lefi.wsgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DEBUG and not DATABASE_URL:
    raise RuntimeError('Produção requer DATABASE_URL/PostgreSQL; não use SQLite efêmero no Render.')
if DATABASE_URL:
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True, ssl_require=(not DEBUG and 'localhost' not in DATABASE_URL))}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if x.strip()]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# Configuração SMTP de recuperação de senha deverá ser instalada antes de liberar o fluxo.

# InfinitePay Checkout Integrado. Segredos somente no Render > Environment.
INFINITEPAY_API_KEY = os.environ.get('INFINITEPAY_API_KEY', '').strip()
INFINITEPAY_TAG = os.environ.get('INFINITEPAY_TAG', '').strip().lstrip('$')
LEFI_CHECKOUT_ENABLED = os.environ.get('LEFI_CHECKOUT_ENABLED', '0') == '1'
# Frete FIXO provisório, definido pela loja (não é uma cotação de transportadora).
LEFI_SHIPPING_FLAT = os.environ.get('LEFI_SHIPPING_FLAT', '').strip()

# Notificações por Gmail Apps Script: opção gratuita, desligada até validar remetente.
LEFI_EMAIL_ENABLED = os.environ.get('LEFI_EMAIL_ENABLED', '0') == '1'
LEFI_MAIL_SCRIPT_URL = os.environ.get('LEFI_MAIL_SCRIPT_URL','').strip()
LEFI_MAIL_SCRIPT_SECRET = os.environ.get('LEFI_MAIL_SCRIPT_SECRET','').strip()

AUTHENTICATION_BACKENDS = ['store.backends.EmailOrUsernameBackend']
# Permite registrar pedido pendente, sem cobrança, quando o gateway estiver desligado.
LEFI_ACCEPT_MANUAL_ORDERS = os.environ.get('LEFI_ACCEPT_MANUAL_ORDERS', '0') == '1'


# Diagnóstico seguro de falhas HTTP 500 no Render.
# Não expõe DEBUG nem imprime configurações ou segredos em logs.
# Django anexa a pilha da exceção à mensagem de erro de requisição.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'render': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'render',
            'stream': 'ext://sys.stderr',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
