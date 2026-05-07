# Skill: nuevo servicio Django

Genera el esqueleto completo de un nuevo microservicio Django en el monorepo RiskCore. Uso: `/new-django-service [nombre]`.

Ejemplo: `/new-django-service payments-service`

## Estructura a crear

```
[nombre]-service/
├── apps/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py       ← excepciones custom del proyecto
│   │   ├── pagination.py       ← CursorPagination configurado
│   │   ├── middleware.py       ← RequestIDMiddleware, LoggingMiddleware
│   │   └── views.py            ← health check view
│   └── [dominio]/
│       ├── __init__.py
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── services.py
│       ├── events.py
│       ├── consumers.py
│       ├── urls.py
│       ├── admin.py
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py
│           ├── test_models.py
│           ├── test_services.py
│           └── test_views.py
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── pyproject.toml
├── Dockerfile
├── .env.example
└── manage.py
```

## `config/settings/base.py` — configuración base obligatoria

```python
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

DJANGO_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "django_prometheus",
    "health_check",
    "health_check.db",
    "health_check.cache",
]

LOCAL_APPS = [
    "apps.core",
    "apps.[dominio]",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "apps.core.middleware.StructlogMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "config.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "[Nombre] Service API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

KAFKA_BOOTSTRAP_SERVERS = config("KAFKA_BOOTSTRAP_SERVERS", default="localhost:9092")
```

## `pyproject.toml` — dependencias base

```toml
[project]
name = "[nombre]-service"
version = "0.1.0"
requires-python = ">=3.13"

dependencies = [
    "django==5.2.*",
    "djangorestframework==3.15.2",
    "djangorestframework-simplejwt==5.5.*",
    "drf-spectacular==0.29.*",
    "django-unfold==0.89.*",
    "django-cors-headers==4.9.*",
    "django-health-check==4.2.*",
    "django-prometheus>=2.3,<2.5",
    "psycopg[binary]==3.3.*",
    "python-decouple==3.8.*",
    "confluent-kafka==2.6.*",
    "structlog==25.*",
    "httpx",
]

[dependency-groups]
dev = [
    "pytest==9.*",
    "pytest-django==4.12.*",
    "factory-boy==3.3.*",
    "Faker==40.*",
    "ruff==0.15.*",
    "mypy==1.20.*",
    "django-stubs==6.0.*",
    "bandit==1.9.*",
]

[tool.ruff]
target-version = "py313"
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.13"
plugins = ["mypy_django_plugin.main"]
strict = true

[tool.django-stubs]
django_settings_module = "config.settings.development"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
```

## `Dockerfile`

```dockerfile
FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

## `.env.example`

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=[nombre]_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
REDIS_URL=redis://localhost:6379/0
```

## Checklist post-creación

- [ ] `python manage.py migrate` corre sin errores
- [ ] `GET /health/` responde `{"status": "ok", "service": "[nombre]-service"}`
- [ ] `GET /api/schema/swagger-ui/` carga el docs
- [ ] `GET /metrics` expone métricas Prometheus
- [ ] `ruff check .` sin errores
- [ ] `mypy .` sin errores de tipo
- [ ] Añadir el servicio a `infra/docker-compose.yml`
- [ ] Añadir el servicio a `gateway/nginx.conf`
- [ ] Añadir el workflow CI en `.github/workflows/ci-[nombre]-service.yml`
