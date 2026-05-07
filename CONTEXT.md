# CONTEXT — RiskCore

> Este archivo es la fuente de verdad del estado actual del proyecto.
> Actualizarlo cada vez que se completa una tarea o cambia de fase.
> Lo leen todos los agentes (Claude Code, Cursor, OpenCode) al inicio de cada sesión.

---

## Índice

> Las filas marcadas con **← actualizar** hay que cambiarlas al iniciar cada fase nueva.

| Sección | Cambia por fase |
|---|---|
| [1. Regla Absoluta](#s1) | No — nunca tocar |
| [2. Reglas críticas — fase actual](#s2) | **Sí ← actualizar** |
| [3. Estado actual](#s3) | **Sí ← actualizar** |
| [4. Plan detallado](#s4) | **Sí ← reemplazar** |
| [5. Progreso por fase](#s5) | Sí — acumulativo |
| [6. Qué está funcionando](#s6) | Sí — acumulativo |
| [7. Decisiones tomadas recientemente](#s7) | Sí — rotar por relevancia |
| [8. Bloqueos o pendientes](#s8) | Sí — limpiar al resolver |
| [9. Protocolo — al terminar tarea](#s9) | No — nunca tocar |
| [10. Protocolo — al terminar fase](#s10) | No — nunca tocar |
| [11. Coordinación multi-agente](#s11) | Parcial — actualizar tabla de agentes |
| [12. Guía permanente de estructura](#s12) | No — nunca tocar |

---

<a id="s1"></a>
## 1. ⛔ Regla Absoluta

**NUNCA ejecutar `git commit` ni `git push` sin confirmación explícita del usuario.**
"Implementa X" / "arregla Y" / "termina la tarea" → NO son permiso para commitear.
Esperar siempre a que el usuario diga explícitamente "sí, commitea" o "commitea el grupo N".

Permitido sin pedir permiso: `git status`, `git diff`, `git log`, `git branch`, `git stash`

---

<a id="s2"></a>
## 2. ⚠️ Reglas críticas — fase actual (Fase 4: observabilidad)

> Estas reglas cambian según la fase. Reemplazar completo al iniciar una fase nueva.
> Ver tabla de reglas por fase en [Sección 10](#s10).

1. **Logs en JSON con structlog — nunca `print()` ni `logging.info()` con formato libre**. Toda salida estructurada vía `structlog.get_logger()`. Cada log debe ser parseable como JSON por Loki sin transformaciones.

2. **`request_id` se propaga vía middleware — NUNCA pasarlo manualmente como parámetro**. `RequestIDMiddleware` ya hace `structlog.contextvars.bind_contextvars(request_id=...)`. Cualquier `logger.info(...)` dentro del request lo incluye automáticamente. No agregar `request_id=...` a mano salvo en consumers/tasks (donde no hay request HTTP).

3. **Campos obligatorios en cada log**: `timestamp`, `level`, `service`, `event` (snake_case del nombre del log), `request_id` (auto vía middleware en HTTP). No agregar campos redundantes como `module`/`logger_name` — structlog ya los incluye.

4. **`/metrics` endpoint expuesto en cada servicio Django** vía `django-prometheus`. En producción (Fase 5) se protegerá con IP whitelist en el gateway. En desarrollo abierto. URL: `/metrics` (no `/api/metrics/`).

5. **Métricas de negocio nombradas con prefijo `riskcore_`**. Ejemplos: `riskcore_policies_created_total`, `riskcore_claims_filed_total`, `riskcore_kafka_messages_processed_total`, `riskcore_notifications_sent_total`. Nunca `django_*` (ya existen) ni nombres genéricos.

6. **Dashboards Grafana versionados como JSON** en `infra/grafana/dashboards/`. Nada se configura por UI — todo provisioning automático vía `infra/grafana/provisioning/`. Si tocás un dashboard en la UI, exportá el JSON y commitéalo.

7. **Logs de Kafka consumer obligatorios**: cada `process_event` debe loguear `topic`, `partition`, `offset`, `event_type`, `processing_time_ms`. Errores con `exc_info=True` para que el stack trace llegue a Loki.

8. **Logs de Celery tasks obligatorios** (notification-service): `task_name`, `task_id`, `status` (`started`/`success`/`failed`/`retry`), `duration_ms`, `attempt` (en retries).

9. **Tests de instrumentación**: cada servicio debe tener al menos un test que verifique que `/metrics` responde 200 con un counter custom incrementado tras una operación. No mockear prometheus.

---

<a id="s3"></a>
## 3. Estado actual

**Fase**: 4 — Observabilidad
**Rama activa**: `feat/phase-4-observability`
**Última tarea completada**: Fase 4 completa — verificación end-to-end pasada ✅
**Próximo paso**: Pendiente confirmación del usuario para commits

---

<a id="s4"></a>
## 4. Plan detallado — Fase 4 (Observabilidad)

> Este plan es editable por cualquier agente. Marcar `[x]` al completar cada paso.
> Rama: `feat/phase-4-observability` | Scope commits: `infra`, `policy`, `claims`, `notifications`, `audit`
> **Dos agentes en paralelo: Claude Code = código (los 4 servicios) · OpenCode = infra (Loki/Prometheus/Grafana).**

---

### Contexto de dominio — leer antes de empezar

**Pipeline de observabilidad que construye esta fase:**

```
[4 servicios Django] ──JSON logs (stdout)──▶ [Promtail] ──▶ [Loki] ──┐
[4 servicios Django] ──/metrics──────▶ [Prometheus]──────────────────┤
                                                                     ├──▶ [Grafana] (dashboards + alerts)
[Celery worker]      ──JSON logs (stdout)──▶ [Promtail] ──▶ [Loki] ──┘
```

**Stack a añadir** (todas versiones del CLAUDE.md):
- `structlog 25.x` — ya está en el middleware, falta configurarlo en `LOGGING` y processors
- `django-prometheus 0.3.x` — middleware + `/metrics` endpoint + métricas DB/cache
- `prometheus-client` (transitivo) — para counters custom de negocio
- Loki 2.9.x · Promtail 2.9.x · Prometheus 2.55.x · Grafana 11.x (Docker images)

**Contrato de log JSON** (todos los servicios deben emitir esto):
```json
{
  "timestamp": "2026-05-07T10:00:00.000Z",
  "level": "info",
  "service": "policy-service",
  "event": "policy_created",
  "request_id": "uuid",
  "policy_id": "uuid",
  "customer_id": "uuid"
}
```

**Métricas custom requeridas (mínimo)**:
| Servicio | Métrica | Tipo | Labels |
|---|---|---|---|
| policy | `riskcore_policies_created_total` | Counter | `policy_type` |
| policy | `riskcore_policies_cancelled_total` | Counter | — |
| claims | `riskcore_claims_filed_total` | Counter | `incident_type` |
| claims | `riskcore_claims_status_changed_total` | Counter | `from_status`, `to_status` |
| audit | `riskcore_kafka_messages_processed_total` | Counter | `topic`, `result` (ok/duplicate/error) |
| audit | `riskcore_kafka_processing_duration_seconds` | Histogram | `topic` |
| notification | `riskcore_notifications_sent_total` | Counter | `event_type`, `status` (sent/failed) |
| notification | `riskcore_celery_task_duration_seconds` | Histogram | `task_name` |

**Puertos nuevos en docker-compose**:
- Loki: 3100
- Prometheus: 9090
- Grafana: 3000 (ya existe el placeholder)
- Promtail: sin puerto expuesto (sidecar)

---

### 🤖 Protocolo de avance automático entre rondas

1. Al terminar tu ronda, marca tus pasos `[x]` en este archivo
2. Revisa si los pasos del otro agente en esta ronda también están `[x]`
   - **Si sí** → empieza tu siguiente ronda directamente, sin esperar al usuario
   - **Si no** → avisa al usuario que terminaste y espera
3. Al terminar la fase completa (todos los `[x]`), avisa al usuario y espera instrucciones de commit

---

### 🔵 RONDA 1 — Fundamentos paralelos (sin dependencias entre agentes)

#### Paso 1 — Configurar structlog JSON en los 4 servicios `[CLAUDE CODE]`

> Aplicar el mismo patrón en `policy-service`, `claims-service`, `notification-service`, `audit-service`.

- [x] `structlog` ya presente en los 4 `pyproject.toml` (no requirió cambio)
- [x] En cada `config/settings/base.py`: `LOGGING` con `ProcessorFormatter` + `structlog.configure()` + `SERVICE_NAME`
- [x] `apps/core/logging.py` — creado, luego eliminado (código muerto): `add_service_name` movido como `_add_service_name` inline en `base.py` para evitar import circular
- [x] `apps/core/middleware.py` — `RequestLoggingMiddleware` añadido (logguea `method`, `path`, `status_code`, `duration_ms`)
- [x] `RequestLoggingMiddleware` añadido al final de `MIDDLEWARE` en los 4 servicios
- [x] Ruff limpio en los 4 servicios
- [x] Verificación: `curl http://localhost:8001/health/` → log JSON en stdout (requiere stack levantado)

#### Paso 1b — Loki + Promtail + Prometheus en docker-compose `[OPENCODE]`

- [x] `infra/loki/loki-config.yml` — config mínima single-binary, retention 7 días, filesystem storage
- [x] `infra/promtail/promtail-config.yml` — scrape de Docker logs, label `service` extraído del nombre del container, parsing JSON con `pipeline_stages.json`
- [x] `infra/prometheus/prometheus.yml` — scrape jobs para los 4 servicios (`policy-service:8001/metrics`, etc.) cada 15s
- [x] `infra/docker-compose.yml` — añadir servicios:
  - `loki` (image `grafana/loki:2.9.x`, port 3100, volume config + data)
  - `promtail` (image `grafana/promtail:2.9.x`, monta `/var/run/docker.sock` y `/var/lib/docker/containers`, depends_on loki)
  - `prometheus` (image `prom/prometheus:v2.55.x`, port 9090, volume config + data)
  - `grafana` (image `grafana/grafana:11.x`, port 3000, env `GF_SECURITY_ADMIN_PASSWORD=admin`, volumes provisioning + dashboards)
- [x] Configurar `logging.driver: json-file` y `logging.options` (max-size 10m, max-file 3) en los 4 servicios Django + `notification-consumer`, `audit-consumer`, `notification-celery`
- [x] Verificación: `make infra` levanta todo · `curl http://localhost:3100/ready` · `curl http://localhost:9090/-/ready` · `curl http://localhost:3000/api/health`

---

### 🔵 RONDA 2 — Métricas + Grafana datasources (requiere Ronda 1)

#### Paso 2 — django-prometheus + métricas custom en los 4 servicios `[CLAUDE CODE]`

- [x] `django-prometheus` ya presente en los 4 `pyproject.toml` (no requirió cambio)
- [x] `INSTALLED_APPS += ["django_prometheus"]` en los 4 `base.py`
- [x] `PrometheusBeforeMiddleware` primero, `PrometheusAfterMiddleware` último en los 4
- [x] `config/urls.py` — `path("", include("django_prometheus.urls"))` en los 4 servicios → expone `/metrics`
- [x] `apps/core/metrics.py` creado en los 4 servicios con counters/histograms `riskcore_*`
- [x] `policy-service/apps/policies/services.py` — `policies_created_total` + `policies_cancelled_total` instrumentados
- [x] `claims-service/apps/claims/services.py` — `claims_filed_total` + `claims_status_changed_total` instrumentados
- [x] `audit-service/apps/audit/kafka_consumer.py` — counter (ok/duplicate/error) + histogram instrumentados
- [x] `notification-service/apps/notifications/tasks.py` — counter (sent/failed) + histogram instrumentados
- [x] Ruff limpio en los 4 servicios
- [x] Verificación: `curl http://localhost:8001/metrics | grep riskcore_policies_created_total` (requiere stack)

#### Paso 2b — Grafana datasources + estructura de provisioning `[OPENCODE]`

- [x] `infra/grafana/provisioning/datasources/datasources.yml` — Loki (http://loki:3100) + Prometheus (http://prometheus:9090) como default
- [x] `infra/grafana/provisioning/dashboards/dashboards.yml` — provider `file` apuntando a `/etc/grafana/dashboards`
- [x] `infra/grafana/dashboards/services-overview.json` — Services Overview:
  - Stat panel: health status de los 4 servicios (query Prometheus `up{job=~".*-service"}`)
  - Time series: requests/s por servicio (`rate(django_http_requests_total_by_view_transport_method_total[5m])`)
  - Time series: error rate % por servicio (`rate(django_http_responses_total_by_status[5m])` filtrando 5xx)
  - Time series: latency p50/p95/p99 (`histogram_quantile` sobre `django_http_requests_latency_seconds_by_view_method`)
- [x] Verificación: abrir `http://localhost:3000` (admin/admin) → datasources OK → dashboard "Services Overview" carga sin errores

---

### 🔵 RONDA 3 — Logs estructurados específicos + dashboards de dominio (requiere Ronda 2)

#### Paso 3 — Logs estructurados de Kafka consumer + Celery `[CLAUDE CODE]`

- [x] `audit-service/apps/audit/kafka_consumer.py`:
  - `kafka_message_received` con `topic`, `partition`, `offset`, `event_type`
  - `kafka_message_processed` con `processing_time_ms`
  - `kafka_message_duplicate` con `event_id`, `topic`, `offset`
  - `kafka_message_failed` con `exc_info=True`
  - `bind_contextvars(event_id=...)` al inicio + `unbind_contextvars` en `finally`
- [x] `notification-service/apps/notifications/kafka_consumer.py` — mismo patrón (kafka_message_received/processed/duplicate/failed + processing_time_ms + exc_info=True)
- [x] `notification-service/apps/notifications/tasks.py`:
  - `celery_task_started` con `task_name`, `task_id`, `notification_id`, `event_type`, `attempt`
  - `celery_task_succeeded` con `duration_ms`, `recipient`, `attempt`
  - `celery_task_retry` con `next_retry_in=300`, `error`
  - `celery_task_failed` con `exc_info=True` (solo en último intento)
- [x] No hay `print()` ni formato legacy — todo usa structlog con kwargs

#### Paso 3b — Dashboards Kafka + Celery + Business `[OPENCODE]`

- [x] `infra/grafana/dashboards/kafka.json`:
  - Producer rate por topic (`rate(riskcore_kafka_messages_processed_total[5m])` agrupado por `topic`)
  - Processing duration p95 (`histogram_quantile(0.95, riskcore_kafka_processing_duration_seconds_bucket)`)
  - Logs panel (Loki): `{service="audit-service"} | json | event=~"kafka_.*"` últimos 15 min
- [x] `infra/grafana/dashboards/celery.json`:
  - Tasks por estado (counter `riskcore_notifications_sent_total` agrupado por `status`)
  - Duración promedio task (`histogram_quantile` sobre `riskcore_celery_task_duration_seconds`)
  - Tasa de éxito/fallo (24h) — gauge
  - Logs panel: `{service="notification-service"} | json | event=~"celery_.*"`
- [x] `infra/grafana/dashboards/business.json`:
  - Pólizas creadas/hora (`increase(riskcore_policies_created_total[1h])`)
  - Siniestros por estado (pie chart con `riskcore_claims_status_changed_total` agrupado por `to_status`)
  - Notificaciones enviadas/hora por `event_type`
- [x] Verificación: los 4 dashboards (services-overview + 3 nuevos) cargan automáticamente al levantar Grafana

---

### 🔵 RONDA 4 — Tests + alertas (requiere Ronda 3)

#### Paso 4 — Tests de instrumentación en los 4 servicios `[CLAUDE CODE]`

- [x] `policy-service/apps/policies/tests/test_metrics.py`: crear póliza → `GET /metrics` → assert `riskcore_policies_created_total{policy_type="VIDA"} >= 1`
- [x] `claims-service/apps/claims/tests/test_metrics.py`: filar claim → metrics expone counter incrementado
- [x] `audit-service/apps/audit/tests/test_metrics.py`: process_event → `riskcore_kafka_messages_processed_total{topic="policy.created",result="ok"} >= 1`
- [x] `notification-service/apps/notifications/tests/test_metrics.py`: ejecutar task → counter `riskcore_notifications_sent_total` incrementado
- [x] `apps/core/tests/test_logging.py` (uno por servicio): capturar log → parsear JSON → assert keys `timestamp`, `level`, `service`, `event`, `request_id`
- [x] `apps/core/tests/test_middleware.py` (uno por servicio): request_id generado/propagado, clear_contextvars antes de bind
- [x] Cobertura mantenida: policy 93% · claims 92% · audit 95% · notification 97%
- [x] Suite completa verde: 49 + 53 + 45 + 36 = 183 tests, 0 fallos

#### Paso 4b — Alertas Grafana + verificación end-to-end `[OPENCODE]`

- [x] `infra/grafana/provisioning/alerting/rules.yml` (Grafana unified alerting):
  - `HighErrorRate` — error rate > 5% en cualquier servicio durante 2 min
  - `KafkaConsumerLag` — consumer lag > 1000 mensajes durante 5 min (usar `kafka_consumer_lag` si está expuesto, o métrica custom)
  - `CeleryQueueBacklog` — `celery_tasks_pending > 500` durante 2 min
  - `ServiceDown` — `up{job=~".*-service"} == 0` durante 30s
- [x] `infra/grafana/provisioning/alerting/contact-points.yml` — contact point por defecto (puede ser webhook/email dummy en local)
- [x] Documentar en `infra/README.md` cómo cargan los dashboards y datasources
- [x] Actualizar `Makefile`: añadir `make logs-loki` (consulta logs vía LogQL desde CLI con logcli) si es trivial
- [x] Verificación final end-to-end (ver bloque debajo)

---

### ✅ Verificación final (ambos agentes — solo después de Ronda 4)

```bash
# 1. Levantar todo el stack
make dev

# 2. Health de la pipeline de observabilidad
curl http://localhost:3100/ready                          # Loki OK
curl http://localhost:9090/-/ready                        # Prometheus OK
curl http://localhost:3000/api/health                     # Grafana OK

# 3. Endpoints /metrics de los 4 servicios
for p in 8001 8002 8003 8004; do curl -s http://localhost:$p/metrics | head -3; done

# 4. Generar tráfico
curl -X POST http://localhost:8001/api/policies/customers/ \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test","email":"test@test.com","dni":"12345678A"}'
# (crear póliza, claim, transición — ver verificación de Fase 3)

# 5. Verificar métricas custom
curl -s http://localhost:8001/metrics | grep riskcore_policies_created_total
curl -s http://localhost:8004/metrics | grep riskcore_kafka_messages_processed_total

# 6. Verificar logs en Loki (vía API)
curl -s 'http://localhost:3100/loki/api/v1/query?query={service="policy-service"}' | jq '.data.result | length'

# 7. Grafana: abrir y validar
open http://localhost:3000   # admin/admin
# - Datasources: Loki + Prometheus en verde
# - 4 dashboards cargados (services-overview, kafka, celery, business)
# - Eventos generados en paso 4 visibles en business dashboard
# - Logs visibles en panel Loki de kafka.json

# 8. Tests
for s in policy-service claims-service audit-service notification-service; do
  cd $s && uv run pytest --cov=apps -v && cd ..
done
```

---

<a id="s5"></a>
## 5. Progreso por fase

| Fase | Nombre | Estado |
|---|---|---|
| 0 | Setup e Infraestructura | ✅ Completado |
| 1 | policy-service | ✅ Completado |
| 2 | claims-service | ✅ Completado |
| 3 | audit-service + notification-service | ✅ Completado |
| 4 | Observabilidad | ✅ Completado |
| 5 | Gateway + Rate Limiting | ❌ No iniciado |
| 6 | Load Testing | ❌ No iniciado |
| 7 | Frontend Dashboard | ❌ No iniciado |

---

<a id="s6"></a>
## 6. Qué está funcionando

- ✅ Documentación base (`docs/`)
- ✅ Instrucciones para agentes (CLAUDE.md, .cursor/rules, .clinerules)
- ✅ Slash commands (`.claude/commands/`)
- ✅ Skills instalados (`.agents/skills/`)
- ✅ Git workflow (main, dev, feat branches)
- ✅ `.gitignore` + `.pre-commit-config.yaml` (ruff, detect-secrets, commitizen)
- ✅ Docker Compose (PostgreSQL 16, Redis 7.2, Kafka 3.7 KRaft)
- ✅ Kafka 6 topics creados
- ✅ 4 Django 5.2 service esqueletos con health `/health/` respondiendo
- ✅ CI workflows (5) pasando en verde
- ✅ PR Phase 0 mergeado a dev
- ✅ PR Phase 1 mergeado a dev
- ✅ policy-service: models, serializers, services, views, Kafka events, admin, tests (36 tests, 97% cov)
- ✅ claims-service: models, serializers, services, PolicyServiceClient, views, Kafka events, admin, tests (39 tests, 96% services, 100% views)
- ✅ audit-service: AuditEvent model, API (list+retrieve+filtros), Kafka consumer, WebSocket, tests (29 tests, 97% services, 95% consumer)
- ✅ notification-service: Notification+NotificationLog models, Celery task, email templates, Kafka consumer, API, tests (21 tests, 100% tasks, 93% consumer)
- ✅ Observabilidad: structlog JSON en 4 servicios, Loki + Promtail + Prometheus + Grafana, 4 dashboards (Services Overview, Kafka, Celery, Business), 4 alert rules, /metrics expuestos, logs Kafka y Loki verificados end-to-end

---

<a id="s7"></a>
## 7. Decisiones tomadas recientemente

- **`custom_exception_handler` mejorado** — `isinstance(errors, list)` antes de iterar, evita descomponer `ErrorDetail` en caracteres cuando `validate()` lanza `ValidationError({"field": "msg"})`
- **`ClaimStatusHistory.from_status = ""`** — `CharField(blank=True)` sin `null=True` no admite NULL en PostgreSQL. Primer registro usa `""`.
- **`AuditEvent.event_id` UNIQUE** — idempotencia en consumer. `IntegrityError` = duplicado → commit offset y continuar, no crashear.
- **Emails via Celery, nunca en consumer directo** — consumer crea `Notification` y dispara `task.delay()`. Desacopla canal Kafka (crítico) de SMTP (no crítico).
- **Índices duplicados corregidos en AuditEvent** — `event_type` y `occurred_at` tenían `db_index=True` en campo Y en Meta.indexes. Eliminados de Meta, quedaron solo standalone + composite `entity_type+entity_id` + `kafka_topic`.
- **`occurred_at` fallback a `timezone.now()`** — `parse_datetime()` retorna None en datetime inválido. Fallback evita IntegrityError silencioso en DB.

---

<a id="s8"></a>
## 8. Bloqueos o pendientes importantes

_Ninguno por ahora._

---

<a id="s9"></a>
## 9. Protocolo — Al terminar cada tarea

1. Marcar `[x]` en el paso completado del plan
2. Actualizar "Última tarea completada" y "Próximo paso" en [Sección 3](#s3)
3. Añadir ítem en [Sección 6](#s6) si corresponde
4. **Avisar al usuario que la tarea está completa y ESPERAR instrucciones**
5. No commitear, no pushear — esperar a que el usuario pida `/commit-ready`

---

<a id="s10"></a>
## 10. Protocolo — Al terminar una fase completa

1. Verificar que TODOS los `[ ]` del plan están marcados `[x]`
2. Actualizar tabla de [Sección 5](#s5): ⏳ → ✅, siguiente fase → ⏳
3. **Sincronizar `docs/PHASES.md`** — actualizar la tabla resumen para que refleje el mismo estado que Sección 5
4. Reemplazar [Sección 2](#s2) con las reglas de la SIGUIENTE fase (ver tabla abajo)
5. Avisar al usuario: "Fase N completa. ¿Hago `/commit-ready` para preparar los commits?"
6. Solo después de commits confirmados y push → el usuario decide si crear PR

**Reglas críticas por fase** (usar para actualizar Sección 2 al cambiar de fase):

| Fase | Reglas clave |
|---|---|
| 1 (policy) | Lógica en services.py · Tests junto al código · Formato de error estándar |
| 2 (claims) | Todo de Fase 1 + Máquina de estados solo en services.py · HTTP inter-service solo para verify |
| 3 (consumers) | AuditEvent SOLO INSERT · Emails via Celery task, NUNCA en el consumer directo |
| 4 (observability) | Logs con structlog JSON · request_id vía middleware (no pasar manual) |
| 5 (gateway) | Rate limiting en Nginx, NO en Django · JWT validado en gateway |
| 7 (frontend) | Server Components por defecto · "use client" solo con interactividad · pnpm siempre |

---

<a id="s11"></a>
## 11. Coordinación multi-agente

> Cuando dos agentes trabajan simultáneamente en el mismo proyecto.
> Si es single-agente, mantener esta sección con una sola fila en la tabla.

### Reglas de convivencia

1. **Cada agente trabaja en su propio servicio/área** — sin pisar archivos del otro
2. **CONTEXT.md lo actualiza un solo agente a la vez** — el que termina primero
3. **Archivos compartidos** (`docker-compose.yml`, `Makefile`, `CLAUDE.md`) → solo los modifica el agente cuya tarea lo requiere explícitamente
4. **Orden de merge**: el agente que empezó primero mergea primero. El segundo hace rebase después.

### Agentes activos — Fase 4

| Agente | Área | Tareas asignadas |
|---|---|---|
| **Claude Code** | Código de los 4 servicios Django (instrumentación) | Paso 1 → Paso 2 → Paso 3 → Paso 4 |
| **OpenCode** | Infra de observabilidad (Loki/Prometheus/Grafana) | Paso 1b → Paso 2b → Paso 3b → Paso 4b |

### División de archivos — quién toca qué

| Área | Agente |
|---|---|
| `policy-service/`, `claims-service/`, `notification-service/`, `audit-service/` (settings, middleware, services, consumers, tasks, tests) | **Claude Code** |
| `infra/loki/`, `infra/promtail/`, `infra/prometheus/`, `infra/grafana/` (configs + dashboards JSON + provisioning) | **OpenCode** |
| `infra/docker-compose.yml` | **OpenCode** (añade Loki/Promtail/Prometheus/Grafana + logging drivers) |
| `Makefile` | **OpenCode** si añade targets de observabilidad |
| `pyproject.toml` de los 4 servicios | **Claude Code** (añade structlog + django-prometheus) |

### Resolución de conflictos

- Mismo archivo → el usuario decide quién lo modifica
- Migraciones en servicios distintos → no hay conflicto (DB separadas)
- Fix pequeño y obvio en código del otro (typo, import roto) → corregir sin pedir permiso si no cambia lógica de negocio

---

<a id="s12"></a>
## 12. 📋 Guía permanente — Cómo estructurar este archivo

> Esta sección NO cambia nunca. Es la referencia para cualquier agente que inicie una fase o un proyecto nuevo.

---

### Al iniciar una FASE nueva (proyecto existente)

Actualizar en este orden:

**1 → [Sección 2](#s2) — Reglas críticas**
Reemplazar el contenido completo con las reglas de la nueva fase.
Consultar la tabla de reglas en [Sección 10](#s10).

**2 → [Sección 3](#s3) — Estado actual**
```
**Fase**: N — nombre
**Rama activa**: feat/phase-N-nombre
**Última tarea completada**: Fase N-1 completada ✅
**Próximo paso**: RONDA 1 — [descripción]
```

**3 → [Sección 4](#s4) — Plan detallado**
Reemplazar el plan anterior completo con el nuevo. Usar la plantilla de abajo.

**4 → [Sección 11](#s11) — Agentes activos**
Actualizar tabla con los agentes y servicios de esta fase.
Si es single-agente, una sola fila con Claude Code.

---

### Al iniciar un PROYECTO nuevo

> Guía completa para estructurar las instrucciones de un proyecto nuevo desde cero.
> El objetivo: que cualquier agente de IA (Claude Code, Cursor, OpenCode, Cline) pueda incorporarse
> al proyecto en cualquier fase y producir código correcto sin supervisión constante.

---

#### Paso 1 — Crear `CONTEXT.md` (fuente de verdad del estado)

Crear con exactamente estas 12 secciones en este orden.
Contenido mínimo de cada sección al inicio:

```
1. Regla Absoluta          → copiar literal desde cualquier proyecto RiskCore
2. Reglas críticas         → reglas de la Fase 0/1 (setup + primer servicio)
3. Estado actual           → Fase 0, rama main, "proyecto inicializado"
4. Plan detallado          → plan de la Fase 0 con plantilla de Rondas
5. Progreso por fase       → tabla con todas las fases en ❌ No iniciado
6. Qué está funcionando    → vacío o solo "repo inicializado"
7. Decisiones recientes    → vacío
8. Bloqueos                → vacío
9. Protocolo — tarea       → copiar literal
10. Protocolo — fase       → copiar literal + tabla de reglas por fase
11. Coordinación           → tabla de agentes de la Fase 0
12. Esta guía              → copiar literal
```

**Principios de CONTEXT.md:**
- Es el archivo que MÁS cambia — se actualiza en CADA tarea completada
- Contiene el plan activo con checkboxes `[x]` / `[ ]`
- Cualquier agente que lea solo este archivo debe saber: qué fase, qué falta, qué reglas aplican ahora
- Máximo ~500 líneas — si crece más, comprimir secciones antiguas

---

#### Paso 2 — Crear `CLAUDE.md` (reglas permanentes del proyecto)

Este archivo contiene todo lo que NO cambia entre fases:

| Sección obligatoria | Contenido |
|---|---|
| **Regla Absoluta** | No commit/push sin permiso (idéntica a CONTEXT.md — refuerzo intencional) |
| **Jerarquía de instrucciones** | Qué archivo gana sobre cuál, cuándo leer cada doc |
| **Qué es el proyecto** | 2-3 líneas de contexto del dominio |
| **Stack con versiones exactas** | Tabla backend + frontend con versiones pinneadas |
| **Arquitectura** | Servicios, puertos, comunicación, estructura de carpetas |
| **Estructura interna de cada servicio** | Qué va en cada archivo (models, services, views, etc.) |
| **Reglas de código obligatorias** | Patrones con ejemplos: thin views, decouple, Kafka schema, logs, errores |
| **Reglas de negocio críticas** | Máquinas de estado, constraints regulatorios, validaciones cross-service |
| **Variables de entorno** | Por servicio, con defaults |
| **Testing** | Qué mockear, qué no, cobertura objetivo |
| **Git workflow** | Branches, conventional commits, formato de PR |
| **Comandos de desarrollo** | Makefile, uv, puertos |
| **Lo que NUNCA hacer** | Tabla de prohibiciones con justificación |

**Principios de CLAUDE.md:**
- Cambia POCO — solo al añadir tecnología, cambiar convenciones, o descubrir nuevos "NUNCA hacer"
- Es la referencia canónica del stack y patrones
- Si algo se dice aquí Y en otro archivo → CLAUDE.md es la fuente de verdad del CONTENIDO
- Skills y .clinerules deben apuntar aquí, no duplicar

---

#### Paso 3 — Crear `.clinerules` (referencia lean para Cline/OpenCode)

**NO duplicar CLAUDE.md.** Este archivo debe ser un puntero con reglas críticas resumidas:

```markdown
# [Proyecto] — Rules for Cline / OpenCode Agents

> Full rules in CLAUDE.md. This file is a quick reference.
> If conflict → CLAUDE.md wins.
> SYNC WARNING: When updating CLAUDE.md, verify this file.
> Last synced: YYYY-MM-DD.

## First Steps — Every Session
1. Read CONTEXT.md
2. Read CLAUDE.md

## Critical Rules (12 reglas máximo, las más importantes)
1. No commit sin permiso
2. Lógica en services.py
3. ...

## Architecture (tabla de 4 líneas)

## For Everything Else → see CLAUDE.md
```

**Máximo ~80 líneas.** Si crece más, estás duplicando.

---

#### Paso 4 — Crear `docs/PHASES.md` (checklists detallados por fase)

Contiene el checklist exhaustivo de entregables de CADA fase con:
- Modelos, endpoints, tests, verificación final, cierre de PR
- Código ejemplo donde sea útil (CI workflows, comandos de verificación)
- Tabla resumen al inicio con estado de cada fase

**Regla de sincronización:** al cerrar una fase, actualizar la tabla resumen de PHASES.md
para que coincida con CONTEXT.md Sección 5. CONTEXT.md es la fuente de verdad del ESTADO,
PHASES.md es la fuente de verdad del CONTENIDO DETALLADO de cada fase.

---

#### Paso 5 — Crear `.claude/commands/` (slash commands)

Cada comando es un archivo `.md` con instrucciones para el agente.

**Comandos recomendados para cualquier proyecto:**

| Comando | Propósito |
|---|---|
| `commit-ready.md` | Agrupar cambios y proponer mensajes de commit |
| `next-step.md` | Recomendar el próximo ítem a implementar |
| `phase-checklist.md` | Ver progreso de la fase actual |

**Comandos específicos del dominio** (añadir según el proyecto):

| Comando | Ejemplo de cuándo crearlo |
|---|---|
| `new-endpoint.md` | Proyectos con API REST |
| `new-kafka-event.md` | Proyectos event-driven |
| `write-tests.md` | Cuando hay patrones de test específicos del proyecto |
| `new-django-service.md` | Monorepos con múltiples servicios |

**Reglas para commands:**
- No duplicar reglas que ya están en CLAUDE.md — referenciar: "ver CLAUDE.md sección X"
- La fuente de verdad del estado es CONTEXT.md, no PHASES.md
- Cada command debe decir QUÉ leer, en QUÉ orden, y QUÉ formato de respuesta usar

---

#### Paso 6 — Configurar `.agents/skills/` (patrones genéricos reutilizables)

Los skills son **genéricos** — funcionan en múltiples proyectos. No contienen reglas específicas del proyecto.

**Regla de oro:** si un skill contradice CLAUDE.md → CLAUDE.md gana.
Esto ya está documentado en CLAUDE.md, pero recordar al configurar skills nuevos.

Skills recomendados según el stack:
- Django → `django-expert`, `django-patterns`
- Testing → `test-driven-development`
- Frontend → `next-best-practices`, `webapp-testing`
- Review → `code-review-excellence`

**No editar skills para adaptarlos al proyecto** — para eso está CLAUDE.md.
Los skills deben permanecer genéricos y reutilizables.

---

#### Paso 7 — Crear `docs/` (documentación de referencia)

| Archivo | Cuándo crearlo | Contenido |
|---|---|---|
| `GUIA_PROYECTO.md` | Al inicio | Dominio de negocio, flujos, glosario |
| `API_DESIGN.md` | Antes de la primera API | Schemas request/response, WebSocket |
| `TECHNICAL_DECISIONS.md` | Al tomar la primera decisión no obvia | ADRs: qué se decidió, por qué, alternativas descartadas |
| `PHASES.md` | Al inicio | Fases con checklists (ver Paso 4) |

---

#### Resumen: qué va en cada archivo (evitar duplicación)

| Información | Archivo canónico | Otros archivos |
|---|---|---|
| Estado actual (fase, rama, progreso) | `CONTEXT.md` | — |
| Plan activo con checkboxes | `CONTEXT.md` Sección 4 | — |
| Reglas de la fase actual | `CONTEXT.md` Sección 2 | — |
| Stack, versiones, patrones | `CLAUDE.md` | `.clinerules` solo referencia |
| Convenciones de código | `CLAUDE.md` | Skills son genéricos, no específicos |
| Reglas de negocio | `CLAUDE.md` | `docs/GUIA_PROYECTO.md` para contexto amplio |
| Checklist detallado por fase | `docs/PHASES.md` | `CONTEXT.md` tiene versión simplificada |
| Schemas de API | `docs/API_DESIGN.md` | — |
| Decisiones técnicas | `docs/TECHNICAL_DECISIONS.md` | `CONTEXT.md` Sección 7 solo las recientes |
| Formato de commit/PR | `CLAUDE.md` | `commit-ready.md` solo el flujo del comando |

**Regla anti-drift:** cuando necesites escribir una regla, pregúntate:
1. ¿Ya existe en CLAUDE.md? → No duplicar, referenciar
2. ¿Cambia entre fases? → Va en CONTEXT.md
3. ¿Es genérica y reutilizable? → Va en un skill
4. ¿Es un checklist de entregables? → Va en PHASES.md
5. ¿Es el flujo de un comando? → Va en `.claude/commands/`

---

### Plantilla del Plan detallado (copiar y adaptar cada fase)

```markdown
## 4. Plan detallado — Fase N (nombre)

> Marcar `[x]` al completar cada paso.
> Rama: feat/phase-N-nombre | Scope commits: scope1, scope2

---

### 🤖 Protocolo de avance automático entre rondas

1. Al terminar tu ronda, marca tus pasos [x]
2. Si los pasos del otro agente en esta ronda también están [x] → empieza la siguiente ronda
3. Si no → avisa al usuario y espera

---

### 🔵 RONDA 1 — [descripción] (paralelo / secuencial)

#### Paso 0 — [servicio]: [qué hace] `[CLAUDE CODE]`
- [ ] archivo — descripción

#### Paso 0b — [servicio]: [qué hace] `[OPENCODE]`   ← omitir si single-agente
- [ ] archivo — descripción

---

### 🔵 RONDA 2 — [descripción] (requiere Ronda 1)

#### Paso 1 — [servicio]: [qué hace] `[CLAUDE CODE]`
- [ ] ...

---

### ✅ Verificación final

```bash
# comandos concretos para probar que todo funciona
```
```

---

### Reglas del Plan

- **Una Ronda = trabajo que puede hacerse en paralelo** entre agentes (o en secuencia si single-agente)
- **Los pasos de Ronda N no dependen entre sí** — los de Ronda N+1 sí dependen de Ronda N
- **Marcar `[x]` inmediatamente** al terminar cada ítem, no al final del paso completo
- **Single-agente**: misma estructura, sin columna OPENCODE, avanzar rondas directamente sin esperar

### Qué NO tocar nunca

- Sección 1 — Regla Absoluta
- Sección 9 — Protocolo al terminar tarea
- Sección 10 — Protocolo al terminar fase
- Sección 11 — Reglas de convivencia (solo actualizar tabla de agentes)
- Sección 12 — Esta guía
