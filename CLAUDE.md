# RiskCore — Project Instructions for AI Agents

> Fuente de verdad para cualquier agente de IA (Claude Code, Cursor, OpenCode, Cline).
> Leer completo antes de escribir cualquier línea de código.

> 📍 **Lee `CONTEXT.md` primero** — tiene el estado actual del proyecto, la fase en curso y el próximo paso.

---

## Qué es este proyecto

**RiskCore** es un sistema backend de microservicios que simula el core de una aseguradora enterprise (estilo Mapfre/Allianz). Proyecto de portfolio orientado a consultoras que piden experiencia en sistemas distribuidos.

**Dominio**: gestión de pólizas y siniestros con event-driven architecture.
**Objetivo**: demostrar microservicios, Kafka, Celery, observabilidad, y patrones enterprise en Python + Next.js.

---

## Documentación del proyecto

Los docs viven en `docs/`. El `README.md` y este `CLAUDE.md` viven en la raíz.

| Archivo | Qué contiene |
|---|---|
| [`docs/GUIA_PROYECTO.md`](docs/GUIA_PROYECTO.md) | Dominio del negocio, flujos completos, preguntas de entrevista |
| [`docs/PLAN_COMPLETO.md`](docs/PLAN_COMPLETO.md) | Stack con versiones, estructura del monorepo, módulos |
| [`docs/TECHNICAL_DECISIONS.md`](docs/TECHNICAL_DECISIONS.md) | Justificación de cada decisión técnica |
| [`docs/API_DESIGN.md`](docs/API_DESIGN.md) | Endpoints completos con request/response + WebSocket |
| [`docs/PHASES.md`](docs/PHASES.md) | Fases de desarrollo con checklists y cierre de PR |

---

## Slash Commands disponibles (Claude Code)

Invocar con `/nombre` en Claude Code. Están en `.claude/commands/`.

| Comando | Cuándo usarlo |
|---|---|
| `/new-endpoint` | Crear un endpoint DRF completo (model → service → view → tests) |
| `/new-kafka-event` | Añadir producer + consumer + management command para un topic |
| `/new-celery-task` | Añadir una Celery task con retry strategy en notification-service |
| `/new-django-service` | Generar el esqueleto de un nuevo microservicio desde cero |
| `/write-tests` | Escribir tests unitarios e integración para un módulo |
| `/phase-checklist` | Ver qué falta en la fase actual |
| `/next-step` | Recomendar el próximo ítem a implementar |
| `/commit-ready` | Agrupar cambios y proponer mensajes de commit (sin ejecutar) |

---

## Stack — Versiones Exactas

### Backend (pyproject.toml por servicio)

| Tecnología | Versión | Rol |
|---|---|---|
| Python | 3.13 | — |
| uv | latest stable | Package manager + virtualenv — reemplaza pip/virtualenv/pip-tools |
| Django | 5.2.x LTS | Framework principal |
| Django REST Framework | 3.15.2 | API REST |
| djangorestframework-simplejwt | 5.5.x | JWT auth |
| drf-spectacular | 0.29.x | OpenAPI / Swagger |
| Apache Kafka | 3.7.x | Message broker (KRaft mode, sin Zookeeper) |
| confluent-kafka | 2.6.x | Cliente Python Kafka — **nunca usar kafka-python** |
| Celery | 5.4.x | Background jobs (notification-service únicamente) |
| Redis | 7.2.x | Cache + broker Celery + channel layer |
| PostgreSQL | 16.x | DB — una por servicio, nunca compartida |
| psycopg3 binary | 3.3.x | Driver async-ready |
| structlog | 25.x | JSON structured logs → Loki |
| django-prometheus | 0.3.x | Métricas → Prometheus |
| Django Channels | 4.1.x | WebSockets (audit-service → dashboard) |
| channels-redis | 4.2.x | Channel layer backend |
| django-unfold | 0.89.x | Admin UI |
| httpx | latest | HTTP inter-service con timeout explícito |
| python-decouple | 3.8.x | Variables de entorno — nunca hardcodear |
| django-health-check | 4.2.x | `/health/` endpoint |
| django-cors-headers | 4.9.x | CORS |
| Ruff | 0.15.x | Linting + formateo — **reemplaza flake8, black, isort** |
| mypy + django-stubs | 1.20.x / 6.0.x | Type checking |
| pytest + pytest-django | 9.x / 4.12.x | Tests |
| factory-boy + Faker | 3.3.x / 40.x | Test factories |
| locust | 2.43.x | Load testing |
| bandit | 1.9.x | Security scan |
| detect-secrets | 1.5.x | Secret detection |
| Flower | 2.x | Monitor Celery |

### Frontend

| Tecnología | Versión |
|---|---|
| Next.js | 15.5.9 (App Router) — **nunca Pages Router** |
| React | 19.1.4 |
| TypeScript | 5.9.x — strict mode activado |
| pnpm | 10.24.0 — **nunca npm ni yarn** |
| Tailwind CSS | 4.x |
| Radix UI | últimas estables |
| Framer Motion | 12.x |
| React Hook Form + Zod | 7.x / 4.x |
| Zustand | 5.x |
| Sonner | 2.x |
| Vitest + Testing Library | 4.x / 16.x |
| Playwright | 1.58.x |
| MSW | 2.x |
| ESLint 9 + Prettier | 9.x / 3.x |
| Husky + lint-staged | 9.x / 16.x |

---

## Arquitectura

```
policy-service       → clientes y pólizas          (puerto 8001)
claims-service       → siniestros                  (puerto 8002)
notification-service → emails async via Celery      (puerto 8003)
audit-service        → registro inmutable + WS      (puerto 8004)
```

**Comunicación entre servicios:**
- **Async (default)**: Kafka topics `policy.*` y `claim.*`
- **Sync (única excepción)**: HTTP claims-service → policy-service para verificar póliza antes de crear un claim

**Database per service**: cada servicio tiene su propia PostgreSQL. Nunca JOINs entre servicios. Nunca DB compartida.

---

## Estructura del Monorepo

```
riskcore/
├── policy-service/          apps/core/ + apps/policies/
├── claims-service/          apps/core/ + apps/claims/
├── notification-service/    apps/core/ + apps/notifications/
├── audit-service/           apps/core/ + apps/audit/
├── gateway/                 nginx.conf + Dockerfile
├── frontend/                Next.js 15 App Router
├── infra/
│   ├── docker-compose.yml
│   ├── kafka/create-topics.sh
│   └── grafana/dashboards/
├── docs/
│   ├── GUIA_PROYECTO.md
│   ├── PLAN_COMPLETO.md
│   ├── TECHNICAL_DECISIONS.md
│   ├── API_DESIGN.md
│   └── PHASES.md
├── .github/workflows/       CI por servicio (path filters)
├── .claude/commands/        Slash commands del proyecto
├── .cursor/rules/           Reglas para Cursor
├── .clinerules              Reglas para OpenCode/Cline
├── .pre-commit-config.yaml
├── Makefile
├── CLAUDE.md                ← instrucciones para agentes IA (raíz)
└── README.md
```

---

## Estructura Interna de Cada Servicio Django

```
[servicio]/
├── apps/
│   ├── core/
│   │   ├── exceptions.py      ← custom_exception_handler + excepciones de dominio
│   │   ├── pagination.py      ← CursorPagination (audit) + PageNumberPagination
│   │   ├── middleware.py      ← RequestIDMiddleware + StructlogMiddleware
│   │   └── views.py           ← HealthCheckView
│   └── [dominio]/
│       ├── models.py          ← Solo ORM, sin lógica
│       ├── serializers.py     ← DRF schemas request/response
│       ├── views.py           ← ViewSets thin — solo HTTP, delega al service
│       ├── services.py        ← TODA la lógica de negocio aquí
│       ├── events.py          ← Kafka producers
│       ├── consumers.py       ← Kafka consumers (management command)
│       ├── tasks.py           ← Celery tasks (solo notification-service)
│       ├── clients.py         ← HTTP client (solo claims-service)
│       ├── admin.py           ← django-unfold
│       ├── urls.py
│       └── tests/
│           ├── conftest.py    ← factories (factory-boy)
│           ├── test_models.py
│           ├── test_services.py
│           └── test_views.py
├── config/
│   ├── settings/
│   │   ├── base.py            ← configuración común
│   │   ├── development.py     ← hereda base
│   │   ├── production.py      ← hereda base (Railway)
│   │   └── test.py            ← hereda base (pytest)
│   ├── urls.py
│   ├── asgi.py                ← requerido por Django Channels (audit-service)
│   └── celery.py              ← solo notification-service
├── pyproject.toml
├── uv.lock            ← lockfile reproducible — siempre commitear
├── .python-version    ← fija Python 3.13 para uv
├── Dockerfile
├── manage.py
└── .env.example
```

### Qué va en `apps/core/`

**`exceptions.py`** — handler DRF estándar + excepciones del dominio:
```python
def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        request_id = context["request"].headers.get("X-Request-ID", "")
        response.data = {
            "error": {
                "code": getattr(exc, "code", "INTERNAL_ERROR"),
                "message": str(exc),
                "details": getattr(exc, "details", {}),
            },
            "request_id": request_id,
        }
    return response
```

**`middleware.py`** — RequestID propagation + structlog binding:
```python
class RequestIDMiddleware:
    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
```

**`pagination.py`** — paginación estándar y cursor-based:
```python
class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

class CursorPaginationByDate(CursorPagination):
    # Solo en audit-service — rendimiento constante para millones de registros
    ordering = "-occurred_at"
    page_size = 50
```

---

## Reglas de Código Obligatorias

### 1. Lógica en services.py — views son thin

```python
# CORRECTO
class PolicyViewSet(ModelViewSet):
    def cancel(self, request, pk):
        policy = get_object_or_404(Policy, pk=pk)
        result = PolicyService().cancel_policy(policy, reason=request.data.get("reason"))
        return Response(PolicySerializer(result).data)

# MAL — lógica en la view
class PolicyViewSet(ModelViewSet):
    def cancel(self, request, pk):
        if policy.status == "CANCELLED":  # ← va en services.py
            raise ValidationError(...)
```

### 2. Variables de entorno — siempre python-decouple

```python
from decouple import config
SECRET_KEY = config("SECRET_KEY")
DATABASE_URL = config("DATABASE_URL")
KAFKA_BOOTSTRAP_SERVERS = config("KAFKA_BOOTSTRAP_SERVERS", default="localhost:9092")
```

### 3. Schema de eventos Kafka — formato estándar inmutable

```python
{
    "event_id": str(uuid.uuid4()),
    "event_type": "policy.created",      # snake_case, nunca cambiar el campo
    "occurred_at": timezone.now().isoformat(),
    "service": "policy-service",
    "data": { ... }
}
```

### 4. Logs — structlog con request_id siempre

```python
import structlog
logger = structlog.get_logger()
# El request_id viene del middleware (ya está en el contexto via bind_contextvars)
logger.info("policy_created", policy_id=str(policy.id), customer_id=str(policy.customer_id))
```

### 5. Errores HTTP — formato estándar en todos los servicios

```json
{
  "error": {
    "code": "POLICY_CANCELLED",
    "message": "No se puede crear un siniestro sobre una póliza cancelada.",
    "details": { "policy_id": "uuid", "policy_status": "CANCELLED" }
  },
  "request_id": "uuid"
}
```
Nunca mensajes técnicos. Siempre lenguaje de negocio.

### 6. HTTP inter-service — httpx con timeout explícito

```python
async with httpx.AsyncClient(timeout=5.0) as client:
    response = await client.get(f"{POLICY_SERVICE_URL}/api/policies/policies/{policy_id}/verify/")
# timeout → 503 ServiceUnavailable
# póliza inválida → 400 BadRequest
```

### 7. Convenciones TypeScript / Next.js

- Componentes: PascalCase (`PolicyCard.tsx`), en `components/[feature]/`
- Páginas: `app/(dashboard)/policies/page.tsx` — App Router, nunca Pages Router
- Hooks custom: `useWebSocket.ts`, `usePolicies.ts` — en `lib/hooks/`
- API client: `lib/api/[service].ts` — wrapper sobre `fetch` con tipos Zod
- Tipos: inferir desde Zod schemas, nunca duplicar interfaces manuales
- Server Components por defecto; `"use client"` solo cuando se necesita interactividad
- Estado global en Zustand stores: `lib/stores/eventsStore.ts`

```typescript
// Patrón API client con Zod
const policySchema = z.object({ id: z.string().uuid(), status: z.enum(["ACTIVE", "CANCELLED"]) })
type Policy = z.infer<typeof policySchema>

async function getPolicy(id: string): Promise<Policy> {
  const res = await fetch(`/api/policies/policies/${id}/`)
  return policySchema.parse(await res.json())
}
```

---

## Reglas de Negocio Críticas

### Máquina de estados — Claims

```
FILED → UNDER_REVIEW → APPROVED  → RESOLVED
                    └→ REJECTED  → RESOLVED
```

```python
VALID_TRANSITIONS = {
    "FILED": ["UNDER_REVIEW"],
    "UNDER_REVIEW": ["APPROVED", "REJECTED"],
    "APPROVED": ["RESOLVED"],
    "REJECTED": ["RESOLVED"],
    "RESOLVED": [],
}
```
- Solo `services.py` cambia el estado, nunca un PATCH directo
- Cada transición guarda `ClaimStatusHistory`
- Cada transición emite Kafka `claim.status_changed`
- Transición inválida → 400 con lista de transiciones válidas

### AuditEvent — Append-Only (regulatorio)
Solo INSERT. Nunca UPDATE ni DELETE. No existe `UpdateAPIView` ni `DestroyAPIView` en audit-service.

### Verificación de póliza antes de crear claim
Claims-service DEBE verificar via HTTP que la póliza existe y está `ACTIVE`. Cualquier otro estado → 400.

---

## Variables de Entorno por Servicio

### Todas los servicios (base)
```env
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

### claims-service (extra)
```env
POLICY_SERVICE_URL=http://localhost:8001
POLICY_SERVICE_TIMEOUT=5
```

### notification-service (extra)
```env
REDIS_URL=redis://localhost:6379/0
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@riskcore.com
```

### audit-service (extra — Django Channels)
```env
REDIS_URL=redis://localhost:6379/1
```

### Frontend
```env
NEXT_PUBLIC_API_URL=http://localhost:80
NEXT_PUBLIC_WS_URL=ws://localhost:80/ws/events/
```

---

## Testing

### Qué mockear en unit tests
```python
# Kafka producer
with patch("apps.policies.events.PolicyEventProducer.produce_policy_created") as m: ...

# HTTP inter-service
with patch("apps.claims.clients.PolicyServiceClient.verify_policy") as m:
    m.return_value = {"status": "ACTIVE", "is_valid": True}

# Email
with patch("django.core.mail.send_mail") as m: ...
```

### Qué NO mockear en integration tests
- PostgreSQL → real con `@pytest.mark.django_db`
- Redis → real en Docker para Channels/Celery tests

### Cobertura objetivo
| Archivo | Target |
|---|---|
| `services.py` | 90%+ |
| `views.py` | 80%+ |
| `consumers.py` | 80%+ |
| `tasks.py` | 80%+ |

Tests se escriben en la misma fase que el módulo. Nunca al final.

---

## Git — Reglas Absolutas

### Nunca commitear ni pushear sin permiso explícito del usuario

Implementar ≠ permiso para commitear. El agente siempre pregunta antes de `git commit` o `git push`.

Comandos OK sin permiso: `git status`, `git diff`, `git log`, `git branch`, `git stash`

### Branches

```
main                    ← producción — solo PRs desde dev, nunca commits directos
dev                     ← integración — recibe PRs desde feat branches
feat/phase-N-nombre     ← una rama por fase
```

### Conventional Commits (obligatorio, enforced por commitlint)

```
feat(policy): add Customer model and migration
fix(claims): validate policy status before filing
chore(infra): add kafka topic creation script
test(audit): add consumer integration tests
docs(api): update claims endpoint schemas
refactor(notifications): extract email template rendering
```

Scopes válidos: `policy`, `claims`, `notifications`, `audit`, `infra`, `frontend`, `gateway`, `api`

Regla: un commit por cambio lógico coherente. No mezclar modelos + views + tests en un solo commit.

### Pull Requests

PRs: `feat/phase-N` → `dev`. Releases: `dev` → `main`.
El agente nunca abre ni mergea un PR sin confirmación del usuario.

Usar `/commit-ready` para preparar commits agrupados antes de pedir permiso.

---

## Comandos de Desarrollo

```bash
make dev              # levanta todo el stack
make infra            # solo Kafka + Redis + PG + Grafana (sin servicios Django)
make test s=policy    # tests de un servicio (uv run pytest)
make lint             # ruff + mypy en todos los servicios
make kafka-setup      # crea los 6 topics
make logs s=claims    # logs de un servicio
make shell s=audit    # Django shell de un servicio
```

**Comandos uv directos** (dentro de un servicio):
```bash
uv sync               # instala dependencias del pyproject.toml
uv add django         # añade una dependencia y actualiza uv.lock
uv run pytest         # ejecuta pytest en el virtualenv del servicio
uv run python manage.py migrate
```

### Puertos locales

| Servicio | Puerto |
|---|---|
| policy-service | 8001 |
| claims-service | 8002 |
| notification-service | 8003 |
| audit-service | 8004 |
| Grafana | 3000 |
| Flower | 5555 |
| Frontend | 3001 |

---

## Kafka Topics

| Topic | Producer | Consumers |
|---|---|---|
| `policy.created` | policy-service | audit-service, notification-service |
| `policy.updated` | policy-service | audit-service |
| `policy.cancelled` | policy-service | audit-service, notification-service |
| `claim.filed` | claims-service | audit-service, notification-service |
| `claim.status_changed` | claims-service | audit-service, notification-service |
| `claim.resolved` | claims-service | audit-service, notification-service |

Consumers corren como management command: `python manage.py run_consumer`.
En Docker Compose: dos containers por servicio con consumer (`web` + `consumer`).

---

## Fases de Desarrollo

| Fase | Nombre | Rama |
|---|---|---|
| 0 | Setup e Infraestructura | `feat/phase-0-setup` |
| 1 | policy-service | `feat/phase-1-policy-service` |
| 2 | claims-service | `feat/phase-2-claims-service` |
| 3 | audit-service + notification-service | `feat/phase-3-consumers` |
| 4 | Observabilidad | `feat/phase-4-observability` |
| 5 | Gateway + Rate Limiting | `feat/phase-5-gateway` |
| 6 | Load Testing | `feat/phase-6-load-testing` |
| 7 | Frontend Dashboard | `feat/phase-7-frontend` |

Ver [`docs/PHASES.md`](docs/PHASES.md) para checklists completos y cierre de cada fase.

---

## Lo que NUNCA Hacer

| Prohibido | Por qué |
|---|---|
| `git commit/push` sin permiso explícito | Regla del workflow con el usuario |
| Commit directo a `main` o `dev` | Solo via PRs desde feat branches |
| Mezclar cambios no relacionados en un commit | Un commit = un cambio lógico |
| Compartir DB entre servicios | Viola Database per Service |
| Lógica en views.py | Va en services.py |
| Usar `kafka-python` | Siempre `confluent-kafka` |
| Hardcodear secrets o URLs | Siempre `python-decouple` + `.env` |
| Modificar o borrar `AuditEvent` | Solo INSERT — requisito regulatorio |
| HTTP entre servicios salvo claims→policy verify | Usa Kafka para todo lo demás |
| Enviar emails en el Kafka consumer | Delegar a Celery task |
| Rate limiting en Django | Va en Nginx (gateway) |
| Tests al final de la fase | Se escriben junto con el módulo |
| Usar `pip install` o `requirements.txt` | Siempre `uv` + `pyproject.toml` |
| Usar `flake8` o `black` | Siempre `ruff` |
| Usar `npm` o `yarn` | Siempre `pnpm` |
| Usar Pages Router en Next.js | Siempre App Router |
| JOINs entre DBs de distintos servicios | Comunicación via Kafka o HTTP |

---

## Observabilidad

| Herramienta | Qué monitorea | URL local |
|---|---|---|
| Grafana | Dashboards de métricas y logs | http://localhost:3000 |
| Loki | Logs JSON de todos los servicios | via Grafana |
| Prometheus | Métricas numéricas (`/metrics`) | via Grafana |
| Flower | Celery tasks en tiempo real | http://localhost:5555 |

Dashboards pre-configurados en `infra/grafana/dashboards/` (se cargan automáticamente).

---

## Deploy

| Entorno | Tecnología |
|---|---|
| Local | Docker Compose (`make dev`) |
| Producción | Railway (un proyecto por servicio) |
| Kafka producción | Upstash Kafka (free tier, compatible con confluent-kafka) |
| Kafka local | Docker KRaft mode |
