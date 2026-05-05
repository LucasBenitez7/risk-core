# PLAN COMPLETO — RiskCore

> Sistema de microservicios para gestión de pólizas y siniestros.
> Dominio: aseguradora (preparación para consultoras tipo Mapfre).
> Stack: Python + Django + Kafka + Redis + PostgreSQL + Next.js + Grafana/Loki.

---

## Resumen del Proyecto

RiskCore es una plataforma backend de microservicios que simula el sistema core de una aseguradora. Gestiona el ciclo de vida completo de pólizas y siniestros, con mensajería event-driven via Kafka, notificaciones async via Celery, auditoría inmutable de eventos, y observabilidad completa con Grafana + Loki + Prometheus. Incluye un dashboard frontend en tiempo real con WebSockets.

**Fases de desarrollo**: ver [`PHASES.md`](PHASES.md)
**Decisiones técnicas detalladas**: ver [`TECHNICAL_DECISIONS.md`](TECHNICAL_DECISIONS.md)
**Diseño de API**: ver [`API_DESIGN.md`](API_DESIGN.md)
**Instrucciones para agentes IA**: ver [`../CLAUDE.md`](../CLAUDE.md)

---

## Stack Completo con Versiones

### Backend (cada servicio tiene su propio pyproject.toml)

| Capa | Tecnología | Versión | Razón |
|---|---|---|---|
| Package manager | uv | latest stable | Reemplaza pip + virtualenv + pip-tools — mismo autor que Ruff |
| Framework | Django | 5.2.x | LTS, lo pide Softtek, Python 3.13 |
| API | Django REST Framework | 3.15.2 | Estándar industry para Django |
| Auth | djangorestframework-simplejwt | 5.5.x | JWT stateless entre servicios |
| Docs | drf-spectacular | 0.29.x | OpenAPI automático por servicio |
| Message broker | Apache Kafka | 3.7.x | Event-driven, estándar enterprise financiero |
| Kafka client | confluent-kafka | 2.6.x | Más robusto que kafka-python (librdkafka) |
| Background jobs | Celery | 5.4.x | Notificaciones async |
| Cache / broker | Redis | 7.2.x | Cache + Celery broker + rate limit |
| Base de datos | PostgreSQL | 16.x | Un schema por servicio (Database per Service) |
| ORM driver | psycopg3 (binary) | 3.3.x | Async-ready, mismo que Acme Commerce |
| Logs estructurados | structlog | 25.x | JSON logs → Loki |
| Métricas | django-prometheus | 0.3.x | Expone /metrics → Prometheus |
| WebSockets | Django Channels | 4.1.x | Dashboard en tiempo real |
| Channel layer | channels-redis | 4.2.x | Redis backend para Channels |
| Admin | django-unfold | 0.89.x | Mismo que Acme Commerce |
| CORS | django-cors-headers | 4.9.x | — |
| Health check | django-health-check | 4.2.x | — |
| Env vars | python-decouple | 3.8.x | — |
| Linting | Ruff | 0.15.x | Mismo que Acme Commerce |
| Type check | mypy + django-stubs | 1.20.x / 6.0.x | Mismo que Acme Commerce |
| Tests | pytest + pytest-django | 9.x / 4.12.x | Mismo que Acme Commerce |
| Factories | factory-boy | 3.3.x | — |
| Fake data | Faker | 40.x | — |
| Load testing | locust | 2.43.x | Ya en tu pyproject.toml base |
| Security scan | bandit | 1.9.x | — |
| Secret detect | detect-secrets | 1.5.x | — |
| Monitoreo Celery | Flower | 2.x | UI para workers y tasks |

### Frontend

| Capa | Tecnología | Versión | Razón |
|---|---|---|---|
| Framework | Next.js | 15.5.9 | App Router + Turbopack |
| Runtime | React | 19.1.4 | — |
| Lenguaje | TypeScript | 5.9.x | — |
| Package manager | pnpm | 10.24.0 | — |
| Estilos | Tailwind CSS | 4.x | — |
| Componentes | Radix UI | últimas estables | Accesibilidad nativa |
| Animaciones | Framer Motion | 12.x | Transiciones del dashboard |
| Formularios | React Hook Form + Zod | 7.x / 4.x | — |
| Estado global | Zustand | 5.x | — |
| Notificaciones UI | Sonner | 2.x | — |
| Tests unitarios | Vitest + Testing Library | 4.x / 16.x | — |
| Tests E2E | Playwright | 1.58.x | — |
| Mocks | MSW | 2.x | — |
| Linting | ESLint 9 + Prettier | 9.x / 3.x | — |
| Git hooks | Husky + lint-staged | 9.x / 16.x | — |

### Infraestructura

| Capa | Tecnología | Versión |
|---|---|---|
| Observabilidad logs | Grafana + Loki | latest stable |
| Observabilidad métricas | Prometheus | latest stable |
| Gateway | Nginx | latest stable |
| Contenedores local | Docker Compose | — |
| CI/CD | GitHub Actions | — |
| Deploy | Railway | — |

---

## Arquitectura

### Diagrama de Servicios

```
                    ┌──────────────────────┐
  Next.js ─────────►     Nginx Gateway     │
  Dashboard         │  JWT auth, rate limit │
                    └──────────┬───────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  policy-service  │ │  claims-service  │ │  audit-service   │
│  Django + DRF    │ │  Django + DRF    │ │  Django + DRF    │
│  PostgreSQL DB1  │ │  PostgreSQL DB2  │ │  PostgreSQL DB3  │
└────────┬─────────┘ └────────┬─────────┘ └─────────▲────────┘
         │                    │                      │
         └──────────┬─────────┘                      │
                    ▼                                 │
          ┌─────────────────┐                        │
          │  Apache Kafka   │────────────────────────┘
          │  Topics:        │
          │  policy.*       │──────────────────────────────┐
          │  claim.*        │                              │
          └─────────────────┘                              ▼
                                          ┌───────────────────────┐
                                          │  notification-service  │
                                          │  Django + Celery       │
                                          │  Redis + PostgreSQL DB4│
                                          └───────────────────────┘
```

### Kafka Topics

| Topic | Producer | Consumers |
|---|---|---|
| `policy.created` | policy-service | audit-service, notification-service |
| `policy.updated` | policy-service | audit-service |
| `policy.cancelled` | policy-service | audit-service, notification-service |
| `claim.filed` | claims-service | audit-service, notification-service |
| `claim.status_changed` | claims-service | audit-service, notification-service |
| `claim.resolved` | claims-service | audit-service, notification-service |

### Arquitectura Interna por Servicio Django

```
apps/
├── core/               ← health, exceptions, pagination, logging middleware
└── [dominio]/
    ├── models.py       ← Django ORM models
    ├── serializers.py  ← DRF request/response schemas
    ├── views.py        ← DRF ViewSets (thin — solo HTTP)
    ├── services.py     ← lógica de negocio aislada
    ├── events.py       ← Kafka producers
    ├── consumers.py    ← Kafka consumers (donde aplica)
    ├── tasks.py        ← Celery tasks (donde aplica)
    ├── urls.py
    ├── admin.py        ← django-unfold
    └── tests/
        ├── test_models.py
        ├── test_services.py
        └── test_views.py
```

---

## Estructura del Monorepo

```
riskcore/
├── .github/
│   └── workflows/
│       ├── ci-policy-service.yml       ← path filter: policy-service/**
│       ├── ci-claims-service.yml       ← path filter: claims-service/**
│       ├── ci-notification-service.yml
│       ├── ci-audit-service.yml
│       └── ci-frontend.yml             ← path filter: frontend/**
│
├── policy-service/
│   ├── apps/
│   │   ├── core/
│   │   └── policies/
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   ├── production.py
│   │   │   └── test.py
│   │   ├── urls.py
│   │   └── celery.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
│
├── claims-service/         ← misma estructura interna
├── notification-service/   ← misma estructura interna
├── audit-service/          ← misma estructura interna
│
├── gateway/
│   ├── nginx.conf
│   └── Dockerfile
│
├── frontend/
│   ├── app/                ← Next.js 15 App Router
│   │   ├── (dashboard)/
│   │   │   ├── page.tsx            ← overview métricas
│   │   │   ├── policies/page.tsx
│   │   │   ├── claims/page.tsx
│   │   │   ├── events/page.tsx     ← Kafka events viewer
│   │   │   └── audit/page.tsx
│   │   └── layout.tsx
│   ├── components/
│   ├── lib/
│   │   └── ws.ts               ← WebSocket client
│   ├── package.json            ← pnpm 10.24.0
│   └── .env.local.example
│
├── infra/
│   ├── docker-compose.yml      ← todos los servicios + Kafka + Redis + PG + Grafana
│   ├── kafka/
│   │   └── create-topics.sh
│   └── grafana/
│       ├── dashboards/
│       │   ├── services.json       ← requests/s, error rate, latencia p50/p95/p99
│       │   ├── kafka.json          ← consumer lag, mensajes/s por topic
│       │   ├── celery.json         ← tasks pending/active/failed, tiempos
│       │   └── business.json       ← pólizas/hora, siniestros por estado
│       └── provisioning/
│           ├── datasources/
│           └── dashboards/
│
├── .github/
│   └── workflows/
│       ├── ci-policy-service.yml
│       ├── ci-claims-service.yml
│       ├── ci-notification-service.yml
│       ├── ci-audit-service.yml
│       └── ci-frontend.yml
│
├── .claude/
│   └── commands/               ← slash commands del proyecto (/new-endpoint, etc.)
│
├── .cursor/
│   └── rules/riskcore.mdc      ← reglas para Cursor
│
├── docs/                       ← documentación técnica detallada
│   ├── GUIA_PROYECTO.md        ← dominio, flujos, preguntas de entrevista
│   ├── PLAN_COMPLETO.md        ← este archivo
│   ├── TECHNICAL_DECISIONS.md  ← justificación de decisiones técnicas
│   ├── API_DESIGN.md           ← endpoints + WebSocket
│   └── PHASES.md               ← fases con checklists
│
├── Makefile
├── .pre-commit-config.yaml     ← lint + conventional commits (monorepo)
├── .clinerules                 ← reglas para OpenCode/Cline
├── .releaserc.json
├── CLAUDE.md                   ← instrucciones para agentes IA (raíz, auto-cargado)
└── README.md                   ← setup rápido: git clone → make dev → curl /health
```

---

## Módulos por Servicio

### policy-service

| Modelo | Campos clave |
|---|---|
| `Customer` | id (UUID), full_name, email, dni, phone, created_at |
| `Policy` | id (UUID), customer, policy_type, status, start_date, end_date, premium_amount |
| `Coverage` | id, policy, coverage_type, max_amount, description |
| `PolicyDocument` | id, policy, document_type, file_url, uploaded_at |

Estados de póliza: `ACTIVE` → `SUSPENDED` → `CANCELLED` / `EXPIRED`

### claims-service

| Modelo | Campos clave |
|---|---|
| `Claim` | id (UUID), policy_id (ref externa), claimant_name, incident_date, description, status |
| `ClaimDocument` | id, claim, document_type, file_url |
| `ClaimStatusHistory` | id, claim, from_status, to_status, changed_by, changed_at, notes |

Máquina de estados: `FILED → UNDER_REVIEW → APPROVED / REJECTED → RESOLVED`

### notification-service

| Modelo | Campos clave |
|---|---|
| `Notification` | id, event_type, recipient_email, status, payload (JSON) |
| `NotificationLog` | id, notification, attempt_number, sent_at, error_message |

### audit-service

| Modelo | Campos clave |
|---|---|
| `AuditEvent` | id (UUID), kafka_topic, kafka_offset, entity_type, entity_id, event_type, payload (JSON), occurred_at, recorded_at |

Solo INSERT — sin UPDATE ni DELETE jamás.

---

## Estrategia de Testing

```
       /E2E\          ← Playwright (frontend) — PR a main
      /------\
     / Integr  \      ← pytest con DB real — cada PR
    /------------\
   /  Unit Tests   \  ← pytest mockeando Kafka — cada push
```

| Tipo | Herramienta | Cuándo | Objetivo |
|---|---|---|---|
| Unit backend | pytest + pytest-django | cada push | 80%+ en services/ |
| Integration backend | pytest con PostgreSQL real | cada PR | endpoints críticos |
| Unit frontend | Vitest + Testing Library | cada push | componentes clave |
| E2E frontend | Playwright | PR a main | flujos del dashboard |
| Load | locust | manual | documentado en results.md |

---

## Git Strategy

### Branches
- `main` — producción, protegida, solo PR
- `dev` — integración de todas las fases
- `feat/phase-N-nombre` — una rama por fase (ver [`PHASES.md`](PHASES.md))

### Conventional Commits
```
feat(policy): add cancellation endpoint
fix(claims): validate policy status before filing
chore(infra): add kafka topic creation script
test(audit): add consumer integration tests
docs(api): update claims endpoint schemas
```

### CI — path filters por servicio
```yaml
on:
  push:
    paths:
      - 'policy-service/**'
      - '.github/workflows/ci-policy-service.yml'
```

---

## Comandos del Makefile

```bash
make dev             # docker compose up — todo el stack
make infra           # solo Kafka + Redis + PG + Grafana
make test s=policy   # tests de policy-service
make lint            # ruff + mypy en todos los servicios
make kafka-setup     # crear los 6 topics
make logs s=claims   # logs de un servicio específico
make shell s=audit   # shell de Django de un servicio
```
