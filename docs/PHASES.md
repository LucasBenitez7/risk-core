# PHASES — RiskCore

> Fases de desarrollo ordenadas. Cada fase tiene rama Git propia, objetivo claro y checklist de entregables.
> Stack: Python + Django + Kafka + Redis + PostgreSQL + Next.js + Grafana/Loki.

---

## Resumen de Fases


| Fase | Nombre                               | Estimado | Rama                          |
| ---- | ------------------------------------ | -------- | ----------------------------- |
| 0    | Setup e Infraestructura              | 1 días   | `feat/phase-0-setup`          |
| 1    | policy-service                       | 1.5 días | `feat/phase-1-policy-service` |
| 2    | claims-service                       | 1.5 días | `feat/phase-2-claims-service` |
| 3    | audit-service + notification-service | 1 día    | `feat/phase-3-consumers`      |
| 4    | Observabilidad                       | 1 día    | `feat/phase-4-observability`  |
| 5    | Gateway + Rate Limiting              | 0.5 día  | `feat/phase-5-gateway`        |
| 6    | Load Testing                         | 0.5 día  | `feat/phase-6-load-testing`   |
| 6.5  | Resilience Hardening                 | 1 día    | `feat/phase-6-5-hardening`    |
| 7    | Frontend Dashboard                   | 1 día    | `feat/phase-7-frontend`       |


**Total estimado**: ~9 días trabajando en paralelo con la búsqueda de empleo.

**Nota sobre Fase 6.5**: añadida tras Fase 6 al detectarse en load testing un bottleneck real (`select_for_update()` en `generate_policy_number()`) y dos gaps de resiliencia frecuentes en arquitecturas event-driven (dual-write entre DB y Kafka, ausencia de circuit breaker en HTTP inter-service). El plan completo vive en `docs/PHASE_6_5_HARDENING.md`.

---

## Fase 0 — Setup e Infraestructura

**Rama**: `feat/phase-0-setup`
**Estimado**: 1 día

**Objetivo**: el monorepo existe, Docker Compose levanta todos los servicios en un comando, Kafka tiene los 6 topics creados, y cada servicio responde `GET /health`. No hay lógica de negocio todavía — solo el esqueleto.

### Entregables

**Git — lo primero**

- Repositorio creado en GitHub: `github.com/[usuario]/riskcore`
- Branch `main` protegida: requiere PR, al menos 1 review, CI en verde
- Branch `dev` creada desde `main`
- Branch `feat/phase-0-setup` creada desde `dev` — todo el trabajo de esta fase va aquí
- `.gitignore` correcto para Python, Node.js, Docker y secretos:
  ```
  # Python
  __pycache__/, *.pyc, .venv/, *.egg-info/
  # Secrets
  .env, .env.local, .env.*.local
  # Node
  node_modules/, .next/
  # Docker
  .docker/
  # IDEs
  .idea/, .vscode/
  ```

**Pre-commit hooks — calidad desde el primer commit**

- `.pre-commit-config.yaml` en la raíz del monorepo:
  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.15.0
      hooks:
        - id: ruff
          args: [--fix]
        - id: ruff-format
    - repo: https://github.com/Yelp/detect-secrets
      rev: v1.5.0
      hooks:
        - id: detect-secrets
    - repo: https://github.com/commitizen-tools/commitizen
      rev: v4.0.0
      hooks:
        - id: commitizen
          stages: [commit-msg]
  ```
- `pre-commit install` instalado localmente
- `pre-commit install --hook-type commit-msg` para validar mensajes

**Monorepo y estructura**

- Estructura de carpetas completa según `GUIA_PROYECTO.md`
- `README.md` raíz con instrucciones de setup local completas (`git clone` → `make dev` → `curl /health`)
- `.releaserc.json` configurado para semantic-release
- `Makefile` con comandos: `dev`, `infra`, `test`, `lint`, `kafka-setup`, `logs`, `shell`

**Docker Compose**

- `infra/docker-compose.yml` levanta:
  - PostgreSQL 16 con 4 databases (una por servicio)
  - Redis 7.2
  - Kafka 3.7 en **KRaft mode** (sin Zookeeper — más simple y moderno)
  - Grafana + Loki + Prometheus
  - Los 4 servicios Django (web + consumer donde aplica)
- `infra/kafka/create-topics.sh` crea los 6 topics con retención de 7 días:
  ```bash
  kafka-topics.sh --create --topic policy.created --partitions 3 --replication-factor 1 \
    --config retention.ms=604800000 --bootstrap-server localhost:9092
  # repetir para los 6 topics
  ```
- `make infra` levanta solo la infraestructura sin los servicios Django
- `make dev` levanta todo junto

**Cada servicio Django (los 4)**

- `Django 5.2.x` con todos los paquetes del `pyproject.toml` base
- `GET /health/` respondiendo:
  ```json
  {"status": "ok", "service": "[nombre]-service", "version": "0.1.0", "database": "ok"}
  ```
- Settings separados: `base.py`, `development.py`, `production.py`, `test.py`
- `.env.example` documentado con TODAS las variables
- `apps/core/` con: `exceptions.py`, `pagination.py`, `middleware.py` (RequestID + Structlog)
- Migraciones iniciales corriendo sin errores

**Calidad de código**

- Ruff configurado en cada `pyproject.toml` y corriendo sin errores
- mypy con django-stubs configurado
- bandit corriendo sin hallazgos high/medium
- detect-secrets baseline generado: `detect-secrets scan > .secrets.baseline`

**GitHub Actions CI — por servicio con path filters**

- `.github/workflows/ci-policy-service.yml` (repetir para claims, notification, audit):
  ```yaml
  name: CI — policy-service

  on:
    push:
      branches: [main, dev, 'feat/**']
      paths:
        - 'policy-service/**'
        - '.github/workflows/ci-policy-service.yml'
    pull_request:
      branches: [dev, main]
      paths:
        - 'policy-service/**'

  jobs:
    lint:
      name: Lint & Type Check
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: policy-service
      steps:
        - uses: actions/checkout@v4
        - uses: astral-sh/setup-uv@v4
        - run: uv sync --frozen
        - run: uv run ruff check .
        - run: uv run ruff format --check .
        - run: uv run mypy .

    security:
      name: Security Scan
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: policy-service
      steps:
        - uses: actions/checkout@v4
        - uses: astral-sh/setup-uv@v4
        - run: uv sync --frozen
        - run: uv run bandit -r apps/ -ll -q
        - run: uv run detect-secrets scan --baseline .secrets.baseline

    test:
      name: Tests
      runs-on: ubuntu-latest
      needs: lint
      services:
        postgres:
          image: postgres:16
          env:
            POSTGRES_DB: test_db
            POSTGRES_USER: postgres
            POSTGRES_PASSWORD: postgres
          ports:
            - 5432:5432
          options: >-
            --health-cmd pg_isready
            --health-interval 10s
            --health-timeout 5s
            --health-retries 5
      defaults:
        run:
          working-directory: policy-service
      env:
        SECRET_KEY: ci-test-secret-key
        DEBUG: "False"
        DB_NAME: test_db
        DB_USER: postgres
        DB_PASSWORD: postgres
        DB_HOST: localhost
        DB_PORT: "5432"
        KAFKA_BOOTSTRAP_SERVERS: localhost:9092
        DJANGO_SETTINGS_MODULE: config.settings.test
      steps:
        - uses: actions/checkout@v4
        - uses: astral-sh/setup-uv@v4
        - run: uv sync --frozen
        - run: uv run pytest --cov=apps --cov-report=xml --cov-fail-under=80
        - uses: codecov/codecov-action@v4
          with:
            file: ./coverage.xml
            flags: policy-service
  ```
- `.github/workflows/ci-frontend.yml`:
  ```yaml
  name: CI — Frontend

  on:
    push:
      branches: [main, dev, 'feat/**']
      paths:
        - 'frontend/**'
        - '.github/workflows/ci-frontend.yml'
    pull_request:
      branches: [dev, main]
      paths:
        - 'frontend/**'

  jobs:
    lint:
      name: Lint & Type Check
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: frontend
      steps:
        - uses: actions/checkout@v4
        - uses: pnpm/action-setup@v4
          with:
            version: 10.24.0
        - uses: actions/setup-node@v4
          with:
            node-version: '20'
            cache: 'pnpm'
            cache-dependency-path: frontend/pnpm-lock.yaml
        - run: pnpm install --frozen-lockfile
        - run: pnpm lint
        - run: pnpm type-check

    test:
      name: Unit Tests
      runs-on: ubuntu-latest
      needs: lint
      defaults:
        run:
          working-directory: frontend
      steps:
        - uses: actions/checkout@v4
        - uses: pnpm/action-setup@v4
          with:
            version: 10.24.0
        - uses: actions/setup-node@v4
          with:
            node-version: '20'
            cache: 'pnpm'
            cache-dependency-path: frontend/pnpm-lock.yaml
        - run: pnpm install --frozen-lockfile
        - run: pnpm test --coverage

    e2e:
      name: E2E Tests (Playwright)
      runs-on: ubuntu-latest
      needs: test
      defaults:
        run:
          working-directory: frontend
      steps:
        - uses: actions/checkout@v4
        - uses: pnpm/action-setup@v4
          with:
            version: 10.24.0
        - uses: actions/setup-node@v4
          with:
            node-version: '20'
            cache: 'pnpm'
            cache-dependency-path: frontend/pnpm-lock.yaml
        - run: pnpm install --frozen-lockfile
        - run: pnpm exec playwright install --with-deps chromium
        - run: pnpm exec playwright test
        - uses: actions/upload-artifact@v4
          if: failure()
          with:
            name: playwright-report
            path: frontend/playwright-report/
  ```
- `.github/workflows/cd.yml` — deploy a Railway solo cuando mergea a `main`:
  ```yaml
  name: CD — Deploy to Railway

  on:
    push:
      branches: [main]

  jobs:
    deploy-policy-service:
      name: Deploy policy-service
      runs-on: ubuntu-latest
      environment: production
      steps:
        - uses: actions/checkout@v4
        - name: Deploy to Railway
          uses: bervProject/railway-deploy@v1
          with:
            railway_token: ${{ secrets.RAILWAY_TOKEN }}
            service: policy-service

    deploy-claims-service:
      name: Deploy claims-service
      runs-on: ubuntu-latest
      needs: deploy-policy-service
      environment: production
      steps:
        - uses: actions/checkout@v4
        - uses: bervProject/railway-deploy@v1
          with:
            railway_token: ${{ secrets.RAILWAY_TOKEN }}
            service: claims-service

    deploy-notification-service:
      name: Deploy notification-service
      runs-on: ubuntu-latest
      needs: deploy-claims-service
      environment: production
      steps:
        - uses: actions/checkout@v4
        - uses: bervProject/railway-deploy@v1
          with:
            railway_token: ${{ secrets.RAILWAY_TOKEN }}
            service: notification-service

    deploy-audit-service:
      name: Deploy audit-service
      runs-on: ubuntu-latest
      needs: deploy-claims-service
      environment: production
      steps:
        - uses: actions/checkout@v4
        - uses: bervProject/railway-deploy@v1
          with:
            railway_token: ${{ secrets.RAILWAY_TOKEN }}
            service: audit-service

    deploy-frontend:
      name: Deploy frontend
      runs-on: ubuntu-latest
      needs: [deploy-policy-service, deploy-claims-service]
      environment: production
      steps:
        - uses: actions/checkout@v4
        - uses: bervProject/railway-deploy@v1
          with:
            railway_token: ${{ secrets.RAILWAY_TOKEN }}
            service: frontend
  ```
- `.github/pull_request_template.md`:
  ```markdown
  ## Qué hace este PR
  <!-- Describe brevemente los cambios -->

  ## Tipo de cambio
  - [ ] Nueva funcionalidad
  - [ ] Bug fix
  - [ ] Refactor
  - [ ] Tests
  - [ ] Docs / Infra

  ## Checklist
  - [ ] CI verde (lint + tests + security)
  - [ ] Cobertura no bajó del objetivo
  - [ ] No hay secrets hardcodeados
  - [ ] Tests añadidos para el cambio
  - [ ] CONTEXT.md actualizado
  - [ ] Conventional commit messages

  ## Evidencia (Swagger, Grafana, terminal — si aplica)
  ```
- GitHub Secrets configurados en el repo:
  - `RAILWAY_TOKEN` — token de Railway para el CD
  - `CODECOV_TOKEN` — token de Codecov para reportes de cobertura

**Verificación final de la fase**

```bash
# Verificar que todo el stack levanta
make dev
curl http://localhost:8001/health/   # {"status": "ok", "service": "policy-service"}
curl http://localhost:8002/health/   # {"status": "ok", "service": "claims-service"}
curl http://localhost:8003/health/   # {"status": "ok", "service": "notification-service"}
curl http://localhost:8004/health/   # {"status": "ok", "service": "audit-service"}

# Verificar Kafka topics creados
make kafka-setup
docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092
# debe mostrar: policy.created, policy.updated, policy.cancelled, claim.filed, claim.status_changed, claim.resolved

# Verificar Grafana
open http://localhost:3000   # admin/admin por defecto

# Verificar CI verde
# Hacer un commit de prueba y ver que todos los workflows pasan en GitHub Actions

# Verificar pre-commit
echo "feat(policy): test commit" | pre-commit run commitizen --hook-stage commit-msg
```

**Al finalizar la fase**

- Crear PR de `feat/phase-0-setup` → `dev` con descripción del setup realizado
- Mergear tras revisión propia
- Crear rama `feat/phase-1-policy-service` desde `dev`

---

## Fase 1 — policy-service

**Rama**: `feat/phase-1-policy-service`
**Estimado**: 1.5 días

**Objetivo**: se puede crear clientes, crear pólizas, consultarlas y cancelarlas via API. Cada operación emite el evento Kafka correspondiente. Los endpoints están documentados en Swagger.

### Entregables

**Modelos y migraciones**

- `Customer` — id (UUID), full_name, email, dni, phone, birth_date, address, created_at
- `Policy` — id (UUID), customer (FK), policy_type, status, start_date, end_date, premium_amount, payment_frequency, policy_number (auto-generado), created_at, updated_at
- `Coverage` — id, policy (FK), coverage_type, max_amount, description
- `PolicyDocument` — id, policy (FK), document_type, file_url, uploaded_at
- Todas las migraciones corriendo limpio
- Índices definidos en Meta (ver TECHNICAL_DECISIONS.md sección 4)

**API y lógica**

- `CustomerViewSet` — list, create, retrieve (sin update ni delete — clientes son inmutables)
- `PolicyViewSet` — list, create, retrieve, partial_update, cancel (action custom)
- `PolicyService` — `create_policy()`, `cancel_policy()`, `update_policy()` — la lógica de negocio NO está en las views
- Endpoint `GET /api/policies/policies/{id}/verify/` para uso interno de claims-service
- Paginación cursor-based para listas grandes
- Filtros: por status, policy_type, customer_id, rango de fechas
- OpenAPI docs accesibles en `/api/schema/swagger-ui/`

**Kafka**

- `PolicyEventProducer` en `apps/policies/events.py`
- Produce `policy.created` en create exitoso
- Produce `policy.updated` en update exitoso
- Produce `policy.cancelled` en cancel exitoso
- Schema del evento: `event_id`, `event_type`, `occurred_at`, `service`, `data` (ver API_DESIGN.md)

**Admin**

- django-unfold configurado con Customer y Policy registrados
- Filtros y búsqueda útiles en el admin

**Tests**

- `tests/test_services.py` — unit tests de PolicyService (Kafka mockeado con `unittest.mock`)
  - crear póliza válida → OK
  - crear póliza con customer inexistente → error
  - cancelar póliza activa → OK
  - cancelar póliza ya cancelada → error
- `tests/test_views.py` — integration tests con DB real (`@pytest.mark.django_db`)
  - POST /customers/ → 201
  - POST /policies/ → 201 + Kafka event emitido
  - GET /policies/?status=ACTIVE → lista filtrada correctamente
  - POST /policies/{id}/cancel/ → 200 + status CANCELLED
- Cobertura > 80% en `services.py`
- CI verde

**Verificación final de la fase**

```bash
# Crear cliente
curl -X POST http://localhost:8001/api/policies/customers/ \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Test User", "email": "test@test.com", "dni": "12345678A"}'

# Crear póliza → debe emitir evento Kafka
curl -X POST http://localhost:8001/api/policies/policies/ \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "uuid", "policy_type": "VIDA", ...}'

# Verificar evento en Kafka
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic policy.created --from-beginning
```

**Al finalizar la fase**

- Crear PR de `feat/phase-1-policy-service` → `dev` con descripción y capturas del swagger
- Mergear tras revisión propia y CI verde
- Crear rama `feat/phase-2-claims-service` desde `dev`

---

## Fase 2 — claims-service

**Rama**: `feat/phase-2-claims-service`
**Estimado**: 1.5 días

**Objetivo**: se puede reportar un siniestro sobre una póliza existente, actualizar su estado siguiendo la máquina de estados definida, y resolver el siniestro. Cada transición emite evento Kafka. La comunicación síncrona con policy-service funciona correctamente.

### Entregables

**Modelos y migraciones**

- `Claim` — id (UUID), policy_id (UUID — referencia externa, sin FK real), claimant_name, claimant_email, incident_date, incident_type, description, estimated_damage, approved_amount, status, claim_number (auto-generado), filed_at
- `ClaimDocument` — id, claim (FK), document_type, file_url, uploaded_at
- `ClaimStatusHistory` — id, claim (FK), from_status, to_status, changed_by, changed_at, notes
- Índices correctos (ver TECHNICAL_DECISIONS.md)

**API y lógica**

- `ClaimViewSet` — list, create, retrieve + action `transition`
- `ClaimService` — `file_claim()`, `transition_status()` — con máquina de estados
- Máquina de estados implementada y validada (ver TECHNICAL_DECISIONS.md sección 13)
- Cada transición guarda `ClaimStatusHistory`
- Endpoint `POST /api/claims/claims/{id}/transition/` con validación de transiciones inválidas
- Filtros: por status, policy_id, incident_type, rango de fechas

**Comunicación inter-service**

- `PolicyServiceClient` en `apps/claims/clients.py` — llama a policy-service via httpx
- Timeout de 5 segundos en la llamada
- Si policy-service responde que la póliza no existe → 400 con mensaje claro
- Si policy-service no responde (timeout) → 503 con mensaje claro
- Lógica de negocio: póliza CANCELLED o EXPIRED → no se puede crear claim

**Kafka**

- `ClaimEventProducer` en `apps/claims/events.py`
- Produce `claim.filed` en create exitoso
- Produce `claim.status_changed` en cada transición
- Produce `claim.resolved` cuando el status llega a RESOLVED
- Mismo schema de evento que policy-service

**Tests**

- `tests/test_services.py` — unit tests con policy-service y Kafka mockeados
  - crear claim con póliza válida → OK
  - crear claim con póliza cancelada → error
  - crear claim con policy-service caído → error 503
  - transición válida → OK + history guardado
  - transición inválida → error con mensaje de qué transiciones son válidas
- `tests/test_views.py` — integration tests
  - POST /claims/ → 201
  - POST /claims/{id}/transition/ con transición inválida → 400
  - GET /claims/?status=FILED → lista filtrada
- CI verde

**Al finalizar la fase**

- Crear PR de `feat/phase-2-claims-service` → `dev`
- Verificar que el flujo completo funciona: policy → claim → evento Kafka emitido
- Mergear tras CI verde
- Crear rama `feat/phase-3-consumers` desde `dev`

---

## Fase 3 — audit-service + notification-service

**Rama**: `feat/phase-3-consumers`
**Estimado**: 1 día

**Objetivo**: los eventos Kafka son consumidos por dos servicios independientes. El audit-service registra todos los eventos de forma inmutable. El notification-service procesa los eventos relevantes y envía emails via Celery.

### Entregables

**audit-service — Kafka Consumer**

- `AuditKafkaConsumer` en `apps/audit/consumers.py`
- Suscrito a todos los topics: `policy.`* y `claim.*`
- Por cada mensaje: deserializar payload → guardar `AuditEvent` → commitear offset
- Consumer corre como management command Django: `python manage.py run_consumer`
- En Docker Compose, el audit-service tiene dos containers: el web (API) y el consumer
- `AuditEvent` es append-only — sin UpdateAPIView ni DestroyAPIView

**audit-service — API**

- `AuditEventViewSet` — solo list y retrieve (read-only)
- Filtros: entity_type, entity_id, event_type, kafka_topic, from_date, to_date
- Ordenado por `occurred_at DESC` por defecto
- Responde en <200ms para consultas con índice (verificado con EXPLAIN)

**notification-service — Kafka Consumer**

- `NotificationKafkaConsumer` en `apps/notifications/consumers.py`
- Suscrito a: `policy.created`, `policy.cancelled`, `claim.filed`, `claim.status_changed`, `claim.resolved`
- Por cada mensaje: crear `Notification` con status PENDING → disparar Celery task → commitear offset
- Consumer corre como management command: `python manage.py run_consumer`

**notification-service — Celery**

- `send_email_notification` task en `apps/notifications/tasks.py`
- Retry strategy: max 3 intentos, 60s entre reintentos
- Por cada intento: guardar `NotificationLog` con resultado
- Templates HTML por tipo de evento:
  - `policy_created.html` — "Su póliza ha sido creada exitosamente"
  - `policy_cancelled.html` — "Su póliza ha sido cancelada"
  - `claim_filed.html` — "Su siniestro ha sido registrado"
  - `claim_status_changed.html` — "El estado de su siniestro ha cambiado"
  - `claim_resolved.html` — "Su siniestro ha sido resuelto"
- Flower configurado y accesible en `http://localhost:5555`

**Tests**

- `tests/test_consumers.py` (audit) — consumer recibe mensaje → AuditEvent guardado correctamente
- `tests/test_consumers.py` (notification) — consumer recibe mensaje → Celery task disparada
- `tests/test_tasks.py` — task ejecutada → Notification actualizada a SENT + log guardado
- Test de fallo: SMTP falla → Notification queda PENDING → retry programado

**Verificación final de la fase**

```bash
# Crear una póliza en policy-service
# Verificar en audit-service que el evento fue registrado
curl http://localhost:8004/api/audit/events/?event_type=policy.created

# Verificar en notification-service que la notificación fue enviada
curl http://localhost:8003/api/notifications/notifications/

# Ver Celery tasks en Flower
open http://localhost:5555
```

**Al finalizar la fase**

- Crear PR de `feat/phase-3-consumers` → `dev`
- Verificar flujo completo: póliza creada → AuditEvent guardado + email enviado + Flower muestra task SUCCEEDED
- Mergear tras CI verde
- Crear rama `feat/phase-4-observability` desde `dev`

---

## Fase 4 — Observabilidad

**Rama**: `feat/phase-4-observability`
**Estimado**: 1 día

**Objetivo**: Grafana muestra métricas en tiempo real y logs de todos los servicios. Se puede diagnosticar cualquier error sin conectarse al servidor. Los dashboards están preconfigurados y funcionan desde el primer `make dev`.

### Entregables

**Logs estructurados — structlog**

- structlog configurado en cada servicio para emitir JSON
- Cada log incluye: `timestamp`, `level`, `service`, `event`, `request_id` (del gateway header)
- Middleware de logging que captura: método, path, status code, latencia, request_id
- Logs de Kafka consumer: topic, offset, event_type, processing_time
- Logs de Celery tasks: task_name, task_id, status, duration
- Docker logging driver configurado en docker-compose.yml para enviar logs a Loki

**Métricas — django-prometheus**

- `django-prometheus` instalado en cada servicio
- `GET /metrics` expuesto (protegido por IP whitelist en producción)
- Prometheus scraping los 4 servicios cada 15s
- Métricas custom definidas:
  - `riskcore_policies_created_total` — counter
  - `riskcore_claims_filed_total` — counter
  - `insurance_kafka_messages_processed_total` — counter por topic
  - `riskcore_notifications_sent_total` — counter por event_type

**Dashboards Grafana** (JSON provisioning — se cargan automáticamente)

- `infra/grafana/dashboards/services.json` — Services Overview
  - Requests/s por servicio (últimos 5 min)
  - Error rate % por servicio
  - Latencia p50/p95/p99 por servicio
  - Status de health check por servicio (semáforo)
- `infra/grafana/dashboards/kafka.json` — Kafka Dashboard
  - Mensajes/s por topic (producer rate)
  - Consumer lag por consumer group
  - Offset actual por partition
- `infra/grafana/dashboards/celery.json` — Celery Dashboard
  - Tasks pending / active / failed
  - Tiempo promedio de ejecución por task
  - Tasa de éxito/fallo últimas 24h
- `infra/grafana/dashboards/business.json` — Business Metrics
  - Pólizas creadas/hora
  - Siniestros por estado (pie chart)
  - Notificaciones enviadas/hora por tipo

**Alertas**

- Error rate > 5% en cualquier servicio → alerta en Grafana
- Consumer lag Kafka > 1000 mensajes → alerta
- Celery queue > 500 tasks pendientes → alerta
- Health check sin responder 30s → alerta crítica

**Verificación final de la fase**

```bash
make dev
open http://localhost:3000   # Grafana con todos los dashboards cargados
# Crear algunas pólizas y siniestros
# Verificar que las métricas aparecen en los dashboards en <30s
# Buscar en Loki: {service="policy-service"} | json | level="error"
```

**Al finalizar la fase**

- Crear PR de `feat/phase-4-observability` → `dev`
- Verificar que los 4 dashboards Grafana cargan automáticamente con `make dev`
- Mergear tras CI verde
- Crear rama `feat/phase-5-gateway` desde `dev`

---

## Fase 5 — Gateway + Rate Limiting

**Rama**: `feat/phase-5-gateway`
**Estimado**: 0.5 día

**Objetivo**: hay un único punto de entrada al sistema. El gateway valida JWT, aplica rate limiting, y propaga X-Request-ID a todos los servicios para trazar requests en Grafana.

### Entregables

**Nginx**

- `gateway/nginx.conf` con upstream por cada servicio
- Reverse proxy: `/api/policies/`* → policy-service:8001, etc.
- JWT validado en el gateway (via auth_request a un endpoint Django simple)
- Rate limiting configurado (ver TECHNICAL_DECISIONS.md sección 9)
- `X-Request-ID` generado si no viene en el request, propagado a todos los servicios
- Access logs en JSON → Loki (misma pipeline que los servicios)
- `gateway/Dockerfile` y entry en docker-compose.yml

**Tests**

- Request sin JWT → 401
- Request con JWT válido → pasa al servicio correcto
- Request excede rate limit → 429 con `Retry-After` header
- Servicio caído → 502 con mensaje descriptivo

**Al finalizar la fase**

- Crear PR de `feat/phase-5-gateway` → `dev`
- Verificar: request sin JWT → 401, rate limit excedido → 429, X-Request-ID en todos los logs
- Mergear tras CI verde
- Crear rama `feat/phase-6-load-testing` desde `dev`

---

## Fase 6 — Load Testing

**Rama**: `feat/phase-6-load-testing`
**Estimado**: 0.5 día

**Objetivo**: el sistema aguanta carga real. Se documentan los resultados con locust en contexto distribuido.

### Entregables

**Escenarios locust** en `infra/load-testing/`

- `scenario_1_policy_creation.py` — creación masiva de pólizas
  - 500 usuarios concurrentes
  - Cada usuario: crear customer → crear póliza → verificar creación
  - Target: p95 < 500ms, error rate < 1%
- `scenario_2_claims_filing.py` — reporte de siniestros bajo carga
  - 300 usuarios concurrentes
  - Cada usuario: consultar póliza existente → crear claim → hacer transición
  - Target: p95 < 800ms (incluye llamada inter-service)
- `scenario_3_audit_read.py` — consulta de audit log (read-heavy)
  - 1000 usuarios concurrentes solo leyendo
  - Filtros variados: por entity_type, por fecha, por topic
  - Target: p95 < 200ms (queries con índice)
- `scenario_4_spike.py` — spike test
  - 0 → 1000 usuarios en 30 segundos
  - Observar latencia durante el spike y recovery
  - Documentar el comportamiento de Kafka consumer lag durante el spike
- `scenario_5_stress.py` — stress hasta encontrar el punto de quiebre
  - Incrementar usuarios hasta que error rate > 10%
  - Documentar el límite

**Resultados documentados**

- `load-testing-results.md` (en la raíz, no en docs/) con:
  - Tabla de resultados por escenario
  - Screenshots de Grafana durante los tests
  - Bottlenecks encontrados y qué los causó
  - Comparación con TicketMaster (mismo tipo de análisis)

**Al finalizar la fase**

- Crear PR de `feat/phase-6-load-testing` → `dev`
- `load-testing-results.md` incluido en el PR con los números reales
- Mergear tras CI verde
- Crear rama `feat/phase-7-frontend` desde `dev`

---

## Fase 6.5 — Resilience Hardening

**Rama**: `feat/phase-6-5-hardening`
**Estimado**: 1 día

**Objetivo**: aplicar dos patrones de resiliencia clásicos en arquitecturas event-driven que diferencian un sistema "demo" de un sistema "production-grade": Outbox Pattern (elimina dual-write entre DB y Kafka) y Circuit Breaker (en la llamada HTTP claims→policy).

**Plan detallado**: `docs/PHASE_6_5_HARDENING.md` — incluye 3 bloques (Circuit Breaker → Outbox → Verificación), código de referencia, tests obligatorios, métricas Prometheus nuevas y self-audit por bloque.

### Entregables

**Circuit Breaker (`pybreaker`)**

- `claims-service/apps/claims/clients.py` refactorizado con `@_policy_breaker` decorator
- Excepción interna `_ClientBusinessError` para excluir 4xx del conteo de fallos
- Métricas: `circuit_breaker_state` (gauge) + `circuit_breaker_state_changes_total` (counter)
- Alerta Grafana: `PolicyCircuitBreakerOpen for 2m`
- Tests: 5 fallos consecutivos → circuito abre, 404 no cuenta, recovery tras `reset_timeout`

**Outbox Pattern (policy-service + claims-service)**

- App Django `apps/outbox/` en ambos servicios con modelo `OutboxEvent` (índice parcial PostgreSQL `WHERE status='PENDING'`)
- Management command `run_outbox_relay` con `select_for_update(skip_locked=True)` (soporta múltiples relays concurrentes)
- Refactor de productores: `PolicyEventProducer` → `PolicyEventBuilder` (solo construye payloads) + `emit_policy_event()` (escribe al outbox dentro de la transacción)
- 2 containers nuevos en docker-compose: `policy-outbox-relay`, `claims-outbox-relay`
- Métricas: `outbox_pending_total`, `outbox_published_total{topic}`, `outbox_lag_seconds`
- Alertas: `OutboxPendingHigh > 1000 for 5m`, `OutboxEventFailed`
- Tests: rollback no deja eventos, relay publica correctamente, fault tolerance (Kafka caído → API responde 201, evento queda PENDING, se publica al recovery)

**Verificación final**

- Re-correr scenarios 1, 2, 5 con outbox + breaker activos
- Actualizar `load-testing-results.md` con sección "Phase 6.5 retest"
- Actualizar `docs/TECHNICAL_DECISIONS.md` con secciones Outbox y Circuit Breaker

**Al finalizar la fase**

- Crear PR de `feat/phase-6-5-hardening` → `dev`
- PR title: `[Phase 6.5] resilience: outbox pattern and circuit breaker for production-grade event delivery`
- Mergear tras CI verde
- Crear rama `feat/phase-7-frontend` desde `dev`

---

## Fase 7 — Frontend Dashboard

**Rama**: `feat/phase-7-frontend`
**Estimado**: 1 día

**Objetivo**: dashboard visual en Next.js 15 que muestra el estado del sistema en tiempo real via WebSockets. No es el foco del portfolio (es backend), pero demuestra que podés integrar un frontend moderno.

### Entregables

**Setup**

- Next.js 15.5.9 con App Router, TypeScript 5.9, pnpm 10.24.0
- Tailwind CSS 4.x configurado
- ESLint 9 + Prettier configurados
- Husky + lint-staged activos
- Vitest + Testing Library + Playwright configurados
- `.env.local.example` documentado

**Páginas y componentes**

- `/` — Dashboard Overview
  - Tarjetas de métricas: pólizas activas, siniestros abiertos, notificaciones enviadas hoy
  - Feed de eventos Kafka en tiempo real (WebSocket)
  - Estado de salud de cada servicio (semáforo: verde/rojo)
- `/policies` — Listado de pólizas
  - Tabla con paginación
  - Filtros: status, policy_type
  - Click en una póliza → detalle con coberturas
- `/claims` — Listado de siniestros
  - Tabla con estado visual (badge por status)
  - Historial de estados al expandir
- `/events` — Kafka Events Viewer
  - Stream en tiempo real de todos los eventos Kafka
  - Filtro por topic
  - Click en evento → payload completo (JSON viewer)
- `/audit` — Audit Log
  - Tabla de AuditEvents con filtros
  - Búsqueda por entity_id

**WebSocket**

- `lib/ws.ts` — cliente WebSocket que conecta a Django Channels
- Reconexión automática si se pierde la conexión
- Events feed actualiza sin reload de página

**Tests**

- Vitest: componentes de tarjetas de métricas
- Vitest: lógica del WebSocket client (mock)
- Playwright E2E: dashboard carga → métricas visibles → crear póliza desde API → aparece en el feed

**Verificación final de la fase**

```bash
cd frontend && pnpm dev
open http://localhost:3001
# Crear una póliza via curl → verificar que aparece en el Events feed en <2s
```

**Al finalizar la fase — proyecto completo**

- Crear PR de `feat/phase-7-frontend` → `dev`
- Verificar E2E: dashboard carga, métricas visibles, evento aparece en feed en <2s
- Mergear `dev` → `main` (release final del proyecto)
- Tag de versión: `git tag v1.0.0`
- Actualizar `README.md` con capturas del sistema funcionando
- Deploy en Railway con todos los servicios funcionando

