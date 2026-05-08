# PRODUCTION DEPLOY — Cost-Controlled Portfolio Strategy

> **Audiencia**: usuario (Lucas) + OpenCode + Claude Code.
> **Cuándo aplicar**: después de cerrar la fase 7 (frontend), cuando todo el sistema funcione localmente.
> **Objetivo**: tener una URL pública que recruiters puedan visitar, manteniendo el costo bajo **$5-10/mes** (idealmente **$0/mes** si toleramos cold starts).
> **Rama Git**: crear `feat/production-deploy` desde `dev` cuando llegue el momento.
>
> Este archivo está dividido en **PARTE A** (lo que tú haces como usuario en consolas web de servicios externos) y **PARTE B** (lo que los agentes harán en código en este repo). Lee §1-§4 antes para entender la estrategia, después salta a la parte que corresponda.

---

## 1. Filosofía: portfolio ≠ production real

Un sistema de portfolio NO necesita las mismas garantías que un sistema productivo real:

| Aspecto | Portfolio | Production real |
|---|---|---|
| Tráfico esperado | <10 visitas/día | 1000+ req/s |
| Disponibilidad | "Funciona cuando alguien visita" | 99.9%+ SLA |
| Cold starts | Aceptables (~30s) | Inaceptables |
| Multi-region | No necesario | Sí |
| Backups | "El código está en GitHub" | RPO/RTO formales |
| Costo objetivo | <$10/mes | "lo que sea necesario" |

**Implicación**: en producción **simplificamos agresivamente** para reducir RAM y costo. La arquitectura local sigue siendo "production-grade" (eso es lo que demuestra ingeniería en el portfolio); el deploy real es una versión recortada que solo demuestra que funciona en una URL pública.

**Recordatorio importante**: la mayoría de reclutadores NO van a entrar a la URL de producción. Van a leer el README, ver el código, y quizá clonar y hacer `make dev`. La URL pública es opcional pero suma puntos.

---

## 2. Stack de producción elegido

| Componente | Servicio | Tier | Costo |
|---|---|---|---|
| Frontend Next.js | **Vercel** | Hobby | $0 (gratis para portfolios) |
| 4 Django services (web + consumer + relay combinados) | **Render** | Free | $0 (con cold starts) o **Starter** ($7/mes total fijo) |
| PostgreSQL | **Neon** | Free | $0 (0.5 GB, no sleep en compute, sí en autosuspend) |
| Kafka | **Upstash Kafka** | Free | $0 (10k msgs/día — sobra) |
| Redis | **Upstash Redis** | Free | $0 (10k commands/día) |
| Observabilidad (logs + métricas) | **Grafana Cloud** | Free | $0 (50 GB logs, 10k series métricas/mes) |
| Email (notification-service) | **Resend** | Free | $0 (3k emails/mes — basta) |
| Gateway Nginx | **Render** Web Service o **Caddy en frontend** | Free | $0 |
| Dominio | Subdominio gratis de Vercel | — | $0 |

**Total**: **$0/mes** con cold starts, **$7/mes** sin cold starts.

**Alternativa "todo Railway"** (si prefieres no fragmentar): Railway Hobby ($5/mes + uso) cubre el stack completo limitando RAM a 256MB/servicio → ~$10-15/mes pero todo en un solo dashboard.

---

## 3. Arquitectura local vs producción

| Servicio | Local | Producción |
|---|---|---|
| `policy-web` | Container propio | **Combinado en proceso único** con relay |
| `policy-outbox-relay` | Container propio | **Background thread** dentro de policy-web |
| `claims-web` | Container propio | Combinado con relay |
| `claims-outbox-relay` | Container propio | Background thread dentro de claims-web |
| `audit-web` | Container propio | Combinado con consumer |
| `audit-consumer` | Container propio | Background thread dentro de audit-web |
| `notification-web` | Container propio | Combinado con consumer + Celery worker en mismo proceso |
| `notification-consumer` | Container propio | Background thread |
| `celery-beat` | Container propio | **Eliminado** en prod (no hay tasks programadas que requieran beat) |
| `celery-worker` | Container propio | Combinado con notification-web |
| `postgres` | Container con 4 DBs | **Neon free tier**, 1 DB con 4 schemas |
| `kafka` | Container | **Upstash Kafka** managed |
| `redis` | Container | **Upstash Redis** managed |
| `grafana + loki + prometheus` | 3 containers | **Grafana Cloud** managed |
| `nginx-gateway` | Container | **Render Web Service** o reverse-proxy en Vercel rewrites |
| `frontend` | Container Next.js dev | **Vercel** |

**Resultado**: 4 servicios Django en producción (en lugar de 11 containers en local). Cada uno con 1 thread principal (gunicorn) + 1-2 background threads.

---

## 4. Estimación de RAM por servicio

| Servicio prod | RAM esperada | Tier Render |
|---|---|---|
| policy-web (web + relay) | ~180 MB | Free 512MB OK |
| claims-web (web + relay) | ~180 MB | Free 512MB OK |
| audit-web (web + consumer) | ~200 MB | Free 512MB OK |
| notification-web (web + consumer + celery) | ~250 MB | Free 512MB OK |

Render Free Tier da 512MB RAM por servicio web. Tenemos margen.

---

## PARTE A — Lo que TÚ (usuario) debes hacer

Estas tareas requieren **acceso humano a consolas web** y NO pueden ser automatizadas por agentes. Hazlas en este orden.

### A.1. Crear cuentas (todas free, ningún tarjeta requerida en plan free)

- [ ] **GitHub** — ya lo tienes ✓
- [ ] **Vercel** — vercel.com → Sign up con GitHub → autoriza el repo `riskcore`
- [ ] **Render** — render.com → Sign up con GitHub → autoriza el repo
- [ ] **Neon** — neon.tech → Sign up con GitHub → crear proyecto `riskcore`
- [ ] **Upstash** — upstash.com → Sign up con GitHub → crear cluster Kafka + Redis (ambos free)
- [ ] **Grafana Cloud** — grafana.com/products/cloud → Sign up → free tier
- [ ] **Resend** — resend.com → Sign up → verificar dominio (o usar `onboarding@resend.dev` para testing)

### A.2. Obtener credenciales y guardarlas en un archivo seguro

Crea un archivo local **fuera del repo** llamado `prod-secrets.txt` (NO commitear) con:

```
# Neon Postgres
NEON_DATABASE_URL=postgresql://user:pass@host.neon.tech/dbname?sslmode=require  # pragma: allowlist secret

# Upstash Kafka (REST + SASL)
UPSTASH_KAFKA_REST_URL=https://...
UPSTASH_KAFKA_REST_USERNAME=...
UPSTASH_KAFKA_REST_PASSWORD=...
UPSTASH_KAFKA_BOOTSTRAP=...
UPSTASH_KAFKA_SASL_USERNAME=...
UPSTASH_KAFKA_SASL_PASSWORD=...

# Upstash Redis
UPSTASH_REDIS_URL=rediss://default:pass@host.upstash.io:6380  # pragma: allowlist secret

# Grafana Cloud
GRAFANA_CLOUD_LOGS_USER=...
GRAFANA_CLOUD_LOGS_API_KEY=...
GRAFANA_CLOUD_PROM_USER=...
GRAFANA_CLOUD_PROM_API_KEY=...

# Resend
RESEND_API_KEY=re_...

# Django
DJANGO_SECRET_KEY=<generar uno nuevo, ver abajo>
JWT_SIGNING_KEY=<generar uno nuevo>

# Frontend
NEXT_PUBLIC_API_URL=https://<gateway-render-url>
```

**Generar `DJANGO_SECRET_KEY`** (corre esto local):
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

**Generar `JWT_SIGNING_KEY`**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### A.3. Configurar Neon Postgres

1. En neon.tech → tu proyecto → SQL Editor
2. Crear los 4 schemas:
   ```sql
   CREATE SCHEMA policy;
   CREATE SCHEMA claims;
   CREATE SCHEMA audit;
   CREATE SCHEMA notifications;
   ```
3. Copiar la connection string desde Dashboard → Connection Details
4. Pegarla en `prod-secrets.txt` como `NEON_DATABASE_URL`

### A.4. Configurar Upstash Kafka

1. upstash.com → Kafka → Create Cluster
2. Region: misma que Render (us-east o eu-west)
3. En el cluster → Topics → crear 6 topics manualmente:
   - `policy.created`, `policy.updated`, `policy.cancelled`
   - `claim.filed`, `claim.status_changed`, `claim.resolved`
   - Cada topic: 1 partition, retención 7 días
4. Copiar credenciales SASL desde Details → REST API y SASL section
5. Pegar en `prod-secrets.txt`

### A.5. Configurar Grafana Cloud

1. grafana.com/products/cloud → Free → My Account → Create Stack
2. En el stack → Connections → Add → buscar "Loki" → copiar credenciales push API
3. Connections → Add → "Prometheus" → copiar remote_write URL + API key
4. Pegar en `prod-secrets.txt`

### A.6. Después de que los agentes hayan hecho la PARTE B

Cuando los agentes hayan terminado su trabajo (commit de cambios production), tú debes:

- [ ] **En Render**: crear 4 Web Services (uno por cada Django service)
  - Cada uno apunta a su carpeta del monorepo (Root Directory: `policy-service`, `claims-service`, etc.)
  - Build command: `pip install uv && uv sync --frozen`
  - Start command: `uv run gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 1`
  - Environment: copiar las variables relevantes de `prod-secrets.txt`
  - Plan: Free tier
- [ ] **En Render**: crear 1 Web Service para el gateway Nginx
  - Apunta a `gateway/`
  - Usa el `Dockerfile.prod` que los agentes habrán creado
  - Plan: Free tier
- [ ] **En Vercel**: importar el repo, Root Directory `frontend`
  - Build command: `pnpm build`
  - Output directory: `.next`
  - Variables: `NEXT_PUBLIC_API_URL` apuntando a la URL del gateway en Render
- [ ] **En cada Render service**: configurar Health Check Path = `/health/`
- [ ] **En cada Render service**: setear Auto-Deploy = `On Commit to main` (solo si quieres CD automático)
- [ ] **Manualmente**: visitar la URL de Vercel y verificar que carga
- [ ] **Manualmente**: hacer un POST de prueba al gateway para crear una póliza, verificar en Neon que el OutboxEvent se publicó

### A.7. Monitoreo de costos (rutina mensual)

Cada primer día del mes:
- [ ] Render dashboard → Billing → verificar que sigues en Free / Starter
- [ ] Vercel dashboard → Usage → verificar bandwidth dentro de free tier
- [ ] Upstash Kafka dashboard → Usage → mensajes/día
- [ ] Upstash Redis dashboard → Usage → commands/día
- [ ] Neon dashboard → Storage usage
- [ ] Grafana Cloud → Billing → logs ingested + active series

Si alguno se acerca al 80% del límite free → bajar el deploy o subir al tier de pago.

### A.8. Plan de apagado (si te quedas sin trabajo y no quieres pagar)

- [ ] Render: cada servicio → Settings → Suspend Service (no se borra, solo no corre)
- [ ] Vercel: dashboard → no hace falta apagar (free tier no expira)
- [ ] Neon: dashboard → tu proyecto → Pause (la DB queda preservada)
- [ ] Upstash: dashboard → Delete Cluster (puedes recrear sin perder configuración con script)
- [ ] Grafana Cloud: no hace falta apagar (free tier no expira)

Tiempo total para apagar todo: ~5 minutos. Tiempo para revivir: ~10 minutos.

---

## PARTE B — Lo que los agentes harán en código

> Esta sección es la guía de implementación para OpenCode + Claude Code. Aplicar después de la fase 7 frontend, en rama `feat/production-deploy`.

### B.1. Resumen de cambios

| Bloque | Qué se hace | Servicios afectados | Estimado |
|---|---|---|---|
| 1 | Settings producción + variables de entorno | Los 4 Django + frontend | 2h |
| 2 | Combinar web + consumer/relay en un proceso | audit, notification, policy, claims | 4h |
| 3 | Schema-based DB en lugar de 4 DBs | Los 4 Django (settings) | 2h |
| 4 | Kafka client adaptado a SASL/TLS para Upstash | Los 2 productores + 2 consumers + 2 relays | 2h |
| 5 | Grafana Cloud agent — push logs y métricas | Los 4 Django | 2h |
| 6 | Dockerfile.prod + render.yaml | Los 4 servicios + gateway | 2h |
| 7 | GitHub Actions deploy workflow | `.github/workflows/cd.yml` | 1h |
| 8 | Smoke tests post-deploy | tests/smoke/ | 1h |

**Total**: ~16h de trabajo de OpenCode (~2 días).

### B.2. Bloque 1 — Settings de producción

Cada Django service ya tiene `config/settings/production.py` (creado en fase 0). Hay que rellenarlos correctamente.

**Patrón a aplicar a los 4 servicios** (`policy`, `claims`, `audit`, `notification`):

```python
# config/settings/production.py
from .base import *  # noqa
from decouple import config

DEBUG = False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# Database — Neon, single DB con schemas
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "sslmode": "require",
            "options": "-c search_path=<SCHEMA>,public",  # <SCHEMA>=policy/claims/audit/notifications
        },
        "CONN_MAX_AGE": 60,  # connection pooling — Neon free tier tiene límites de conexiones
    }
}

# Kafka — Upstash con SASL
KAFKA_BOOTSTRAP_SERVERS = config("KAFKA_BOOTSTRAP")
KAFKA_PRODUCER_CONFIG = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "SCRAM-SHA-256",
    "sasl.username": config("KAFKA_SASL_USERNAME"),
    "sasl.password": config("KAFKA_SASL_PASSWORD"),
}
KAFKA_CONSUMER_CONFIG = {
    **KAFKA_PRODUCER_CONFIG,
    "group.id": "<service-name>",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
}

# Redis (solo notification + audit usan Redis para Celery + cache)
REDIS_URL = config("REDIS_URL")

# Logging — JSON a stdout (Render lo recoge y reenvía a Grafana Cloud via agent)
LOGGING = {...}  # mantener structlog config existente

# Security
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
```

**Refactor de `events.py` y consumers** para leer de `KAFKA_PRODUCER_CONFIG` / `KAFKA_CONSUMER_CONFIG` en lugar de construir el dict inline. Esto permite que development siga funcionando con la config simple sin SASL.

### B.3. Bloque 2 — Combinar procesos

**Problema**: Render free tier da 512MB por servicio. Hoy `audit-service` tiene 2 containers (web + consumer); en producción los queremos en uno solo.

**Solución**: usar threads o `concurrent.futures` para correr el consumer/relay en background dentro del proceso de gunicorn.

**Patrón**: gunicorn `post_fork` hook arranca el thread.

Crear `<service>/config/gunicorn.conf.py`:

```python
# Solo en producción — local sigue usando containers separados
import os
import threading

def post_fork(server, worker):
    """Cada worker de gunicorn arranca su propio thread de relay/consumer."""
    if os.getenv("ENABLE_BACKGROUND_WORKER") != "true":
        return

    def _run_worker():
        # Diferente por servicio:
        # policy-service / claims-service → outbox relay
        # audit-service / notification-service → kafka consumer
        from django.core.management import call_command
        target = os.getenv("BACKGROUND_WORKER_COMMAND")  # "run_outbox_relay" | "run_consumer"
        call_command(target)

    thread = threading.Thread(target=_run_worker, daemon=True)
    thread.start()
    server.log.info("background_worker_started: %s", os.getenv("BACKGROUND_WORKER_COMMAND"))
```

**IMPORTANTE — caveat de gunicorn workers**:
- Si gunicorn tiene `workers=2`, cada uno arranca su propio thread de relay → 2 relays concurrentes. Está bien para outbox (gracias a `select_for_update(skip_locked=True)`) pero **mal para consumers de Kafka** (duplica el `group.id` instance lo cual está OK pero gasta el rate limit free de Upstash).
- **Solución**: en producción, usar `workers=1` y suficientes `threads=4` para HTTP. Esto es razonable para portfolio.

Setear en Render Environment Variables del servicio:
- `ENABLE_BACKGROUND_WORKER=true`
- `BACKGROUND_WORKER_COMMAND=run_outbox_relay` (o `run_consumer`)

**Notification-service caso especial**: necesita Celery worker + Kafka consumer. Lanzar 2 threads en `post_fork`. Celery beat se elimina (no hay tasks programadas obligatorias).

### B.4. Bloque 3 — Schema-based DB

En la production settings de cada servicio, `search_path=<schema>,public` hace que todas las tablas Django se creen en el schema correspondiente.

**Migraciones**: deben correr una sola vez por schema. Estrategia:

```bash
# En cada servicio, antes del primer deploy
DJANGO_SETTINGS_MODULE=config.settings.production uv run python manage.py migrate
```

Render permite "Pre-Deploy Command" — usarlo para correr migraciones automáticas:

```yaml
# render.yaml
preDeployCommand: "uv run python manage.py migrate --noinput"
```

**Caveat**: como los 4 servicios comparten la misma DB Neon, NO deben tener tablas con el mismo nombre (incluso en schemas diferentes esto puede causar conflictos en Django). Verificar:
- `policy.Policy` vs `claims.Claim` → OK
- `audit.AuditEvent` vs `notifications.Notification` → OK
- `auth.User`, `django_session`, `django_migrations` → **estas tablas Django built-in se duplicarán en cada schema**. Eso está OK pero ineficiente.

**Decisión**: aceptamos la duplicación de tablas built-in en cada schema. Es la opción más simple.

### B.5. Bloque 4 — Kafka SASL para Upstash

`confluent-kafka` ya soporta SASL nativo (a diferencia de `kafka-python` que tiene bugs con SCRAM-SHA-256). Solo necesitamos pasar la config.

Refactor en cada `events.py` y cada consumer:

```python
# Antes:
self._producer = Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})

# Después:
from django.conf import settings
self._producer = Producer(settings.KAFKA_PRODUCER_CONFIG)
```

En desarrollo, `settings.KAFKA_PRODUCER_CONFIG` es simplemente `{"bootstrap.servers": "kafka:9092"}`. En producción incluye SASL.

### B.6. Bloque 5 — Logs y métricas a Grafana Cloud

**Logs**: Grafana Cloud Loki acepta push directo desde structlog vía `python-logging-loki` o desde Render via su feature de log streaming.

Opción más simple: **Render → Grafana Cloud log stream**.
- En cada Render service → Settings → Log Streams → Add → Grafana Cloud Loki
- Configurar URL + credentials desde `prod-secrets.txt`
- No requiere cambios de código

**Métricas**: usar Grafana Agent en sidecar NO es viable en Render free tier. Alternativa: hacer que Django exponga `/metrics` y que **Grafana Cloud Prometheus haga scrape externo** (Hosted Grafana → Connections → Prometheus → Scrape Configuration).

Solo cambio de código necesario: asegurar que `/metrics` esté accesible públicamente con auth. Añadir en cada service:

```python
# urls.py — proteger metrics con basic auth
from django.contrib.auth.decorators import login_required

urlpatterns = [
    ...
    path("metrics/", basic_auth_required(metrics_view), name="prometheus-metrics"),
]
```

Configurar `METRICS_USER` y `METRICS_PASSWORD` en environment variables → Grafana Cloud usa esas credenciales para hacer scrape.

### B.7. Bloque 6 — Dockerfile.prod + render.yaml

Crear `policy-service/Dockerfile.prod` (mismo patrón en los 4 servicios):

```dockerfile
FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV DJANGO_SETTINGS_MODULE=config.settings.production
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "config.wsgi", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "30", \
     "--config", "config/gunicorn.conf.py"]
```

Crear `render.yaml` en raíz del repo con los 5 servicios (4 Django + gateway):

```yaml
services:
  - type: web
    name: policy-service
    runtime: docker
    dockerfilePath: ./policy-service/Dockerfile.prod
    plan: free
    region: oregon
    healthCheckPath: /health/
    autoDeploy: false  # disparar manualmente desde dashboard
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: config.settings.production
      - key: ENABLE_BACKGROUND_WORKER
        value: "true"
      - key: BACKGROUND_WORKER_COMMAND
        value: run_outbox_relay
      # secrets vienen del dashboard manualmente, no commiteados

  - type: web
    name: claims-service
    runtime: docker
    dockerfilePath: ./claims-service/Dockerfile.prod
    # ... idem
    
  # repetir para audit, notification, gateway
```

### B.8. Bloque 7 — GitHub Actions deploy

Modificar `.github/workflows/cd.yml` para usar Render API en lugar de Railway (que estaba originalmente en `PHASES.md`):

```yaml
name: CD — Deploy to Render

on:
  push:
    branches: [main]
  workflow_dispatch:  # permite trigger manual

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Trigger Render deploys
        run: |
          for service_id in ${{ secrets.RENDER_SERVICE_IDS }}; do
            curl -X POST "https://api.render.com/v1/services/$service_id/deploys" \
              -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}"
          done
```

Variables a setear en GitHub repo Settings → Secrets:
- `RENDER_API_KEY` (desde Render Account Settings)
- `RENDER_SERVICE_IDS` (space-separated, desde cada service URL)

### B.9. Bloque 8 — Smoke tests post-deploy

Crear `tests/smoke/test_production.py`:

```python
"""Smoke tests — corren contra producción después de cada deploy."""
import os
import pytest
import requests

BASE_URL = os.environ["SMOKE_TEST_BASE_URL"]
TIMEOUT = 30  # generoso, prod puede tener cold start


def test_gateway_health():
    r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    assert r.status_code == 200


def test_policy_health():
    r = requests.get(f"{BASE_URL}/api/policies/health/", timeout=TIMEOUT)
    assert r.status_code == 200


def test_claims_health():
    r = requests.get(f"{BASE_URL}/api/claims/health/", timeout=TIMEOUT)
    assert r.status_code == 200


def test_audit_health():
    r = requests.get(f"{BASE_URL}/api/audit/health/", timeout=TIMEOUT)
    assert r.status_code == 200


def test_notifications_health():
    r = requests.get(f"{BASE_URL}/api/notifications/health/", timeout=TIMEOUT)
    assert r.status_code == 200


def test_create_policy_e2e():
    """Verifica que el flujo completo funciona en prod."""
    # Login
    auth = requests.post(f"{BASE_URL}/api/auth/token/",
                         json={"username": os.environ["SMOKE_USER"],
                               "password": os.environ["SMOKE_PASS"]},
                         timeout=TIMEOUT)
    assert auth.status_code == 200
    token = auth.json()["access"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create customer
    r = requests.post(f"{BASE_URL}/api/policies/customers/", headers=headers,
                      json={...}, timeout=TIMEOUT)
    assert r.status_code == 201
    customer_id = r.json()["id"]

    # Create policy
    r = requests.post(f"{BASE_URL}/api/policies/policies/", headers=headers,
                      json={"customer_id": customer_id, ...}, timeout=TIMEOUT)
    assert r.status_code == 201
```

Añadir a `cd.yml` un step que ejecute estos tests después del deploy.

### B.10. Self-audit del deploy

- [ ] `production.py` settings completos en los 4 servicios.
- [ ] `Dockerfile.prod` builds limpiamente local: `docker build -f policy-service/Dockerfile.prod .` etc.
- [ ] `render.yaml` valida con Render's blueprint validator.
- [ ] Smoke tests pasan localmente contra `make dev` (sanity check).
- [ ] CI/CD workflow se dispara correctamente.
- [ ] Avisar al usuario para hacer Parte A.6 (deploy real).

---

## 5. Reglas de oro durante deploy

- **NUNCA commitear secretos**. El archivo `prod-secrets.txt` vive fuera del repo. Las variables de entorno se setean manualmente en cada dashboard.
- **NUNCA usar el mismo `DJANGO_SECRET_KEY` que en development**. Generar uno nuevo para producción.
- **Render free tier sleeps después de 15 min sin tráfico**. Cold start ~30s. Aceptable para portfolio.
- **Si una request al frontend dispara cold start de varios servicios**, el primer hit puede tardar 1-2 minutos. Considerar añadir un loader explicativo en el frontend ("Despertando servicios... esto pasa solo si nadie ha visitado en los últimos 15 minutos").
- **Health check loops**: Render ping cada 30s al `/health/` para mantener servicios vivos. Esto puede agotar el free tier si los 4 servicios reciben 60 pings/min cada uno → revisar consumo de Neon (compute hours).
- **Si te acercas al límite de Neon free tier (compute hours)**: Neon "auto-suspends" después de 5 min sin queries. Esto SE ACUMULA con los cold starts de Render → un visitante puede tener que esperar 60-90s. Solución: subir a Neon Launch tier ($19/mes) si te molesta.

---

## 6. Cuándo escalar

Si el portfolio empieza a recibir tráfico real (sucede a veces si te haces conocido):

| Síntoma | Acción |
|---|---|
| Cold starts molestos para visitas | Render Free → Starter $7/mes (no sleep) |
| Neon free 0.5GB lleno | Neon Launch $19/mes (10GB) |
| Upstash Kafka >10k msgs/día | Upstash Pay-as-you-go (~$0.20 por 100k msgs) |
| Grafana logs >50GB/mes | Grafana Cloud Pro ($8/mes para 100GB) |

Subes los servicios uno por uno cuando duele, no antes.

---

## 7. Rollback / shutdown

Si algo va catastróficamente mal en producción:

```bash
# Inmediato — desactiva el frontend (deja de servir tráfico)
# En Vercel dashboard → tu proyecto → Pause Deployment

# Pausar Render services (NO los borra)
# En Render dashboard → cada servicio → Suspend Service

# Pausar Neon (la DB queda preservada)
# En Neon dashboard → Pause Compute

# Total: ~3 minutos para apagar todo, $0 de coste mientras esté apagado.
```

Para volver: invertir los pasos. Re-deployar tarda ~5 minutos.
