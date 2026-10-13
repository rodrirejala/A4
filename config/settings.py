"""
Configuración de la app de Notas de Pedido - A4 GROUP S.A.

En producción (PythonAnywhere) se configuran variables de entorno:
    DJANGO_DEBUG=False
    DJANGO_SECRET_KEY=<clave_única_y_secreta>
    DJANGO_ALLOWED_HOSTS=tuusuario.pythonanywhere.com
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-0_!y_w1xsvrg+0*ew6-0m-)*t2c4b!d@3p8=8x^y7+@x+!tb@x')

# SECURITY WARNING: don't run with debug turned on in production!
# Local: True por defecto. En PythonAnywhere fijar DJANGO_DEBUG=False.
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# Hosts permitidos. En PythonAnywhere agregar el dominio generado a DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        '127.0.0.1,localhost,192.168.0.247',
    ).split(',') if h.strip()
]
ALLOWED_HOSTS.append('testserver')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pedidos',
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

ROOT_URLCONF = 'config.urls'

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
                'pedidos.context_processors.company',
                'pedidos.context_processors.rol',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Asuncion'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Datos de la empresa (aparecen en cabecera de la nota de pedido)
COMPANY = {
    'nombre': 'A4 GROUP S.A.',
    'clase': 'NOTA DE PEDIDO',
    'subtitulo': '(ORDEN DE COMPRA)',
    'ruc': 'R.U.C.: 80089731-5',
    'direccion': 'Pdte. González y Aquidabán, Edificio Maxwell',
    'telefono': 'Cel. 0985 428 328',
    'ciudad': 'B° San Roque, Encarnación',
}

# Máximo de ítems permitidos en la tabla (igual que la planilla Excel)
MAX_ITEMS = 11

# Prioridades posibles en una nota de pedido
PRIORIDADES = [
    ('Media', 'Media'),
    ('Alta', 'Alta'),
    ('Baja', 'Baja'),
]

# Estados posibles de la nota de pedido.
# El flujo real es: pendiente -> aprobada -> cerrado. ``cerrado`` significa que
# el material ya se compró, por eso el consolidado de /compras/ excluye las
# notas en este estado.
ESTADOS_NOTA = [
    ('pendiente', 'Pendiente'),
    ('aprobada', 'Aprobada'),
    ('cerrado', 'Cerrado'),
]

# Estados en los que la nota todavía genera demanda de compra. Todo lo que no
# esté en esta tupla se considera "ya comprado" y no aparece en el consolidado.
ESTADOS_ABIERTOS_NOTA = ['pendiente', 'aprobada']

# Transiciones de estado permitidas. Se usa en el formulario de edicion (solo
# admin) para no ofrecer combinaciones sin sentido.
TRANSICIONES_ESTADO = {
    'pendiente': ['pendiente', 'aprobada', 'cerrado'],
    'aprobada': ['aprobada', 'cerrado', 'pendiente'],
    'cerrado': ['cerrado', 'pendiente'],
}

# Autenticación
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'pedidos:panel'
LOGOUT_REDIRECT_URL = 'login'