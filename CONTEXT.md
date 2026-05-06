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
## 2. ⚠️ Reglas críticas — fase actual (Fase 3: consumers)

> Estas reglas cambian según la fase. Reemplazar completo al iniciar una fase nueva.
> Ver tabla de reglas por fase en [Sección 10](#s10).

1. **`AuditEvent` es APPEND-ONLY — nunca UPDATE ni DELETE**. Requisito regulatorio. No existe `UpdateAPIView` ni `DestroyAPIView` en audit-service. Solo INSERT. Nunca modificar un evento ya guardado.

2. **Emails SOLO vía Celery task — NUNCA en el consumer Kafka directamente**. El consumer crea el registro `Notification` y dispara `send_email_notification.delay(notification_id)`. La task envía el email. Esto desacopla el consumer (crítico) del canal de email (no crítico).

3. **`AuditEvent.event_id` es UNIQUE** — el campo `event_id` del payload Kafka se guarda y es único. Si el consumer procesa un evento duplicado (at-least-once), la IntegrityError se captura, se loggea como "ya procesado" y se hace commit del offset. Nunca re-lanzar la excepción.

4. **Commit de offset DESPUÉS del INSERT en DB** — `enable.auto.commit=False`. El consumer hace `consumer.commit(message=msg)` explícitamente solo después de guardar el AuditEvent / crear la Notification. Si el INSERT falla (excepto duplicado), NO commitear — el mensaje se re-procesará.

5. **Consumer group IDs fijos**: `group.id = "audit-service"` y `group.id = "notification-service"`. No cambiarlos — Kafka trackea el offset por group.id.

6. **Tests junto con el código — nunca al final**. Tests se escriben en la misma ronda que el módulo. Cobertura mínima: `consumers.py` 80%, `tasks.py` 80%, `services.py` 90%.

7. **Celery retry strategy** (production): `max_retries=3`, `countdown=300` (5 min entre reintentos). `soft_time_limit=25`. Configurado en `notification-service/config/celery.py` y en la task, no en base.py.

---

<a id="s3"></a>
## 3. Estado actual

**Fase**: 3 — audit-service + notification-service
**Rama activa**: `feat/phase-3-consumers`
**Última tarea completada**: RONDA 4 — OpenCode: Paso 4b notification-service (Tests, 21/21 ✅, tasks 100%, consumers 93%, views 100%)
**Próximo paso**: Fase 3 COMPLETA para ambos servicios. Verificación final y preparar commits.

---

<a id="s4"></a>
## 4. Plan detallado — Fase 3 (audit-service + notification-service)

> Este plan es editable por cualquier agente. Marcar `[x]` al completar cada paso.
> Rama: `feat/phase-3-consumers` | Scope commits: `audit`, `notifications`
> **Un agente por servicio — trabajan en paralelo desde el inicio.**

---

### Contexto de dominio — leer antes de empezar

**Flujo de eventos** (lo que esta fase implementa):
```
policy-service  ──kafka──▶  audit-service     (graba AuditEvent inmutable)
claims-service  ──kafka──▶  notification-service  (crea Notification → Celery → email)
```

**Topics que consume audit-service** (todos):
- `policy.created`, `policy.updated`, `policy.cancelled`
- `claim.filed`, `claim.status_changed`, `claim.resolved`

**Topics que consume notification-service** (solo los relevantes para email):
- `policy.created` → "Su póliza ha sido creada"
- `policy.cancelled` → "Su póliza ha sido cancelada"
- `claim.filed` → "Su siniestro ha sido registrado"
- `claim.status_changed` → "El estado de su siniestro ha cambiado"
- `claim.resolved` → "Su siniestro ha sido resuelto"

**Payload Kafka recibido** (formato estándar de Fases 1+2):
```json
{
  "event_id": "uuid",
  "event_type": "policy.created",
  "occurred_at": "2026-03-15T10:00:00Z",
  "service": "policy-service",
  "data": { "policy_id": "uuid", "claimant_email": "..." }
}
```

**Patrón de idempotencia en el consumer** (crítico — at-least-once delivery):
```python
try:
    AuditService().process_event(payload, topic=msg.topic())
    consumer.commit(message=msg)
except IntegrityError:
    logger.warning("duplicate_event", event_id=payload.get("event_id"))
    consumer.commit(message=msg)
except Exception as e:
    logger.error("event_processing_failed", error=str(e))
    # NO commitear → Kafka re-entregará el mensaje
```

**Patrón de Celery task en notification-service**:
```python
# consumer.py — SOLO crea Notification y dispara la task
notification = Notification.objects.create(event_type=event_type, ...)
send_email_notification.delay(str(notification.id))
consumer.commit(message=msg)

# tasks.py — aquí sí se envía el email
@shared_task(bind=True, max_retries=3, soft_time_limit=25)
def send_email_notification(self, notification_id: str):
    try:
        send_mail(...)
        notification.status = NotificationStatus.SENT
    except Exception as exc:
        notification.status = NotificationStatus.FAILED
        raise self.retry(exc=exc, countdown=300)
```

**WebSocket en audit-service** (Django Channels):
```python
from asgiref.sync import async_to_sync
async_to_sync(channel_layer.group_send)("audit_events", {
    "type": "audit.event",
    "payload": AuditEventSerializer(event).data,
})
```

---

### 🤖 Protocolo de avance automático entre rondas

1. Al terminar tu ronda, marca tus pasos `[x]` en este archivo
2. Revisa si los pasos del otro agente en esta ronda también están `[x]`
   - **Si sí** → empieza tu siguiente ronda directamente, sin esperar al usuario
   - **Si no** → avisa al usuario que terminaste y espera
3. Al terminar la fase completa (todos los `[x]`), avisa al usuario y espera instrucciones de commit

---

### 🔵 RONDA 1 — Paralelo (sin dependencias entre servicios)

#### Paso 0 — audit-service: core/ + AuditEvent model + migration `[CLAUDE CODE]`

- [x] `audit-service/apps/core/exceptions.py` — `custom_exception_handler` mejorado + `AuditEventNotFoundError`
- [x] `audit-service/apps/audit/models.py` — modelo `AuditEvent` (UUID PK, event_id UNIQUE, entity_type+entity_id, payload JSONField)
- [x] Migrations: `0001_initial` + `0002_fix_duplicate_indexes` aplicadas
- [x] `apps.audit` en `INSTALLED_APPS` (verificado)

#### Paso 0b — notification-service: core/ + models + Celery config `[OPENCODE]`

- [x] `notification-service/apps/core/exceptions.py` — `custom_exception_handler` + `NotificationNotFoundError`
- [x] `notification-service/apps/notifications/models.py` — `Notification` + `NotificationLog`
- [x] `notification-service/config/celery.py` — Celery con `result_expires`, `task_acks_late=True`, `worker_prefetch_multiplier=1`
- [x] Migrations aplicadas

---

### 🔵 RONDA 2 — Paralelo (requieren Ronda 1)

#### Paso 1 — audit-service: Serializer + ViewSet + URLs + Admin `[CLAUDE CODE]`

- [x] `audit-service/apps/audit/serializers.py` — `AuditEventSerializer` (detail) + `AuditEventListSerializer` (list)
- [x] `audit-service/apps/audit/views.py` — `AuditEventViewSet` (solo list+retrieve, filtros por event_type/entity_type/entity_id/kafka_topic/from_date/to_date)
- [x] `audit-service/apps/audit/urls.py` — `DefaultRouter`, prefix `events/`
- [x] `audit-service/config/urls.py` — ya incluía `api/audit/` (verificado)
- [x] `audit-service/apps/audit/admin.py` — django-unfold, todo readonly, sin add/change/delete

#### Paso 2 — notification-service: Celery task + email templates `[OPENCODE]`

- [x] `notification-service/apps/notifications/tasks.py` — `send_email_notification` task (max_retries=3, soft_time_limit=25)
- [x] `notification-service/templates/notifications/emails/` — 5 templates HTML
- [x] `notification-service/config/settings/base.py` — `TEMPLATES[0]["DIRS"]` configurado

---

### 🔵 RONDA 3 — Paralelo (requieren Ronda 2)

#### Paso 3 — audit-service: Kafka consumer + WebSocket consumer `[CLAUDE CODE]`

- [x] `audit-service/apps/audit/services.py` — `AuditService.process_event()` + `_broadcast_to_websocket()`
- [x] `audit-service/apps/audit/kafka_consumer.py` — `AuditKafkaConsumer` (6 topics, group.id="audit-service", manual commit)
- [x] `audit-service/apps/audit/management/commands/run_consumer.py`
- [x] `audit-service/apps/audit/ws_consumers.py` — `AuditEventsConsumer` (AsyncWebsocketConsumer)
- [x] `audit-service/config/routing.py` — URLRouter con `ws/events/`
- [x] `audit-service/config/asgi.py` — `ProtocolTypeRouter` (http + websocket)

#### Paso 3b — notification-service: Kafka consumer + ViewSet + Admin `[OPENCODE]`

- [x] `notification-service/apps/notifications/kafka_consumer.py` — `NotificationKafkaConsumer` (5 topics, group.id="notification-service")
- [x] `notification-service/apps/notifications/management/commands/run_consumer.py`
- [x] `notification-service/apps/notifications/serializers.py` — `NotificationSerializer` + `NotificationListSerializer`
- [x] `notification-service/apps/notifications/views.py` — `NotificationViewSet` (list+retrieve, filtros status/event_type)
- [x] `notification-service/apps/notifications/urls.py` + incluido en `config/urls.py`
- [x] `notification-service/apps/notifications/admin.py` — django-unfold

---

### 🔵 RONDA 4 — Paralelo (requieren Ronda 3)

#### Paso 4 — audit-service: Tests `[CLAUDE CODE]`

- [x] `audit-service/apps/audit/tests/conftest.py` — `AuditEventFactory`
- [x] `audit-service/apps/audit/tests/test_services.py` — process_event policy/claim, duplicado, fallbacks
- [x] `audit-service/apps/audit/tests/test_consumers.py` — válido, duplicado, JSON inválido, run() loop
- [x] `audit-service/apps/audit/tests/test_views.py` — list, retrieve, filtros, 404, 405
- [x] Cobertura: 29/29 ✅ — `services.py` 97%, `kafka_consumer.py` 95%, `views.py` 100%

#### Paso 4b — notification-service: Tests `[OPENCODE]`

- [x] `notification-service/apps/notifications/tests/conftest.py` — `NotificationFactory`, `NotificationLogFactory`
- [x] `notification-service/apps/notifications/tests/test_tasks.py` — SENT, FAILED+retry, idempotente
- [x] `notification-service/apps/notifications/tests/test_consumers.py` — policy.created, claim.filed, commit offset
- [x] `notification-service/apps/notifications/tests/test_views.py` — list, filter, retrieve, 404
- [x] Cobertura: 21/21 ✅ — `tasks.py` 100%, `consumers.py` 93%, `views.py` 100%

---

### ✅ Verificación final (ambos agentes)

```bash
# Levantar todo el stack
docker compose -f infra/docker-compose.yml up -d

# Crear póliza → verifica que audit-service la registra
curl -X POST http://localhost:8001/api/policies/customers/ \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test","email":"test@test.com","dni":"12345678A"}'

# Verificar AuditEvent en audit-service
curl http://localhost:8004/api/audit/events/?event_type=policy.created

# Verificar Notification en notification-service
curl http://localhost:8003/api/notifications/notifications/

# Tests
cd audit-service && uv run pytest --cov=apps/audit -v
cd notification-service && uv run pytest --cov=apps/notifications -v

# WebSocket (en segunda terminal)
wscat -c ws://localhost:8004/ws/events/
```

---

<a id="s5"></a>
## 5. Progreso por fase

| Fase | Nombre | Estado |
|---|---|---|
| 0 | Setup e Infraestructura | ✅ Completado |
| 1 | policy-service | ✅ Completado |
| 2 | claims-service | ✅ Completado |
| 3 | audit-service + notification-service | ⏳ En curso |
| 4 | Observabilidad | ❌ No iniciado |
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
2. Actualizar tabla de [Sección 5](#s5): ⏳ → ✅
3. Reemplazar [Sección 2](#s2) con las reglas de la SIGUIENTE fase (ver tabla abajo)
4. Avisar al usuario: "Fase N completa. ¿Hago `/commit-ready` para preparar los commits?"
5. Solo después de commits confirmados y push → el usuario decide si crear PR

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

### Agentes activos — Fase 3

| Agente | Servicio | Tareas asignadas |
|---|---|---|
| **Claude Code** | audit-service (8004) | Paso 0 → Paso 1 → Paso 3 → Paso 4 |
| **OpenCode** | notification-service (8003) | Paso 0b → Paso 2 → Paso 3b → Paso 4b |

### División de archivos — quién toca qué

| Área | Agente |
|---|---|
| `audit-service/` — todo | **Claude Code** |
| `notification-service/` — todo | **OpenCode** |

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

Crear un CONTEXT.md desde cero con exactamente estas 12 secciones en este orden.
Contenido mínimo de cada sección al inicio del proyecto:

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
