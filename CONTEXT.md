# CONTEXT — RiskCore

> Este archivo es la fuente de verdad del estado actual del proyecto.
> Actualizarlo cada vez que se completa una tarea o cambia de fase.
> Lo leen todos los agentes (Claude Code, Cursor, OpenCode) al inicio de cada sesión.

---

## ⛔ REGLA ABSOLUTA

**NUNCA ejecutar `git commit` ni `git push` sin confirmación explícita del usuario.**
"Implementa X" / "arregla Y" / "termina la tarea" → NO son permiso para commitear.
Esperar siempre a que el usuario diga explícitamente "sí, commitea" o "commitea el grupo N".

Permitido sin pedir permiso: `git status`, `git diff`, `git log`, `git branch`, `git stash`

---

## ⚠️ Reglas críticas para la fase actual

> Estas reglas cambian según la fase. Actualizarlas al cambiar de fase.

1. **Lógica de negocio en `services.py` — nunca en `views.py`**. Las views solo reciben HTTP, llaman al service, y devuelven la respuesta. Sin `if`, sin validación de negocio, sin queries complejas en la view.

2. **Tests junto con el código — nunca al final**. Cada paso del plan incluye tests. No marcar un paso como completo si no tiene tests. Mínimo 80% de cobertura en services.py y views.py.

3. **Formato de error estándar siempre**: `{"error": {"code": "UPPERCASE_CODE", "message": "lenguaje de negocio", "details": {}}, "request_id": "uuid"}`. Nunca devolver `{"detail": "..."}` ni `{"error": "texto plano"}`.

4. **No crear llamadas HTTP entre servicios** salvo claims→policy `/verify/`. Si necesitas datos de otro servicio, es via Kafka event (async). No añadir nuevos endpoints "internos".

---

## Estado actual

**Fase**: 1 — policy-service  
**Rama activa**: `feat/phase-1-policy-service`  
**Última tarea completada**: Claude Code — Auditoría Fase 1 completa: fix mock Kafka en test_services.py + factories corregidas en conftest.py  
**Próximo paso**: Fase 1 COMPLETA y auditada. Ejecutar `/commit-ready` para preparar commits antes del PR.  

---

## Plan detallado — Fase 1 (policy-service)

> Este plan es editable por cualquier agente. Marcar `[x]` al completar cada paso.  
> Rama: `feat/phase-1-policy-service` | Scope commits: `policy`  
> **Dos agentes trabajan en paralelo — ver tabla de división más abajo.**

### 🤖 Protocolo de avance automático entre rondas

1. Al terminar tu ronda, marca tus pasos `[x]` en este archivo
2. Revisa si los pasos del otro agente en esta ronda también están `[x]`
   - **Si sí** → empieza tu siguiente ronda directamente, sin esperar al usuario
   - **Si no** → avisa al usuario que terminaste y espera
3. Al terminar la fase completa (todos los `[x]`), avisa al usuario y espera instrucciones de commit

---

### 🔵 RONDA 1 — Paralelo (ambos agentes a la vez)

#### Paso 0 — core/ setup `[CLAUDE CODE]` ✅
> Prerrequisito para todos los demás pasos. Sin esto, views y serializers no tienen exception handler ni middleware.

- [x] `apps/core/exceptions.py` — `custom_exception_handler` + excepciones de dominio:
  - `PolicyNotFoundError`, `InvalidPolicyStatusError`, `CustomerNotFoundError`
  - Formato estándar: `{"error": {"code": "...", "message": "...", "details": {}}, "request_id": "uuid"}`
- [x] `apps/core/middleware.py` — `RequestIDMiddleware`:
  - Lee `X-Request-ID` del header o genera UUID nuevo
  - Llama `structlog.contextvars.bind_contextvars(request_id=request_id)`
  - Agrega `X-Request-ID` al response
- [x] `apps/core/pagination.py` — `StandardPagination` (PageNumber, page_size=20, max=100)
- [x] `apps/core/views.py` — `HealthCheckView` (ya existe en el esqueleto — verificar que está OK)
- [x] Registrar middleware en `config/settings/base.py`
- [x] Registrar `custom_exception_handler` en `REST_FRAMEWORK` settings

#### Paso 1 — Models + Migrations `[OPENCODE]` ✅
> No depende de core/. Se puede hacer en paralelo con Paso 0.

- [x] `apps/policies/models.py` — cuatro modelos:
  - `Customer`: `id` (UUID PK), `full_name`, `email` (único), `dni` (único), `phone`, `address`, `created_at`, `updated_at`
  - `Policy`: `id` (UUID PK), `policy_number` (POL-YYYY-NNNNNN, auto-gen, único), `customer` (FK), `policy_type` (LIFE/HEALTH/AUTO/HOME/BUSINESS), `status` (ACTIVE/SUSPENDED/CANCELLED/EXPIRED), `premium_amount` (Decimal), `start_date`, `end_date`, `description`, `cancellation_reason`, `created_at`, `updated_at`
  - `Coverage`: `id` (UUID PK), `policy` (FK), `coverage_type`, `coverage_amount` (Decimal), `description`
  - `PolicyDocument`: `id` (UUID PK), `policy` (FK), `document_type`, `file_url`, `uploaded_at`
  - Índices: `Policy.status`, `Policy.customer`, `Policy.policy_number`, `Policy.end_date`
  - [x] `generate_policy_number()` — formato POL-YYYY-NNNNNN con padding cero, auto-generado en `save()`
- [x] Migraciones: `uv run python manage.py makemigrations` + `migrate` — sin errores

---

### 🔵 RONDA 2 — Paralelo (después de que Ronda 1 esté completa)

#### Paso 2 — Serializers `[CLAUDE CODE]` ✅
> Requiere modelos (Paso 1). Usar excepciones de core/ (Paso 0).

- [x] `apps/policies/serializers.py`:
  - `CustomerSerializer` — todos los campos, validar `email` único (excluir instancia actual en update), validar `dni` único
  - `CoverageSerializer` — campos de Coverage
  - `PolicyDocumentSerializer` — campos de PolicyDocument
  - `PolicySerializer` — con `coverages` nested (read-only), `customer_id` para write, validar `premium_amount > 0`, validar `start_date < end_date`
  - `PolicyVerifySerializer` — respuesta de `/verify/`: `{"policy_id", "status", "is_valid", "customer_id"}`
  - `PolicyCancelSerializer` — input de `/cancel/`: `{"reason"}` (requerido)

#### Paso 3 — Services (lógica de negocio) `[OPENCODE]` ✅
> Requiere modelos (Paso 1) y excepciones de core/ (Paso 0).

- [x] `apps/policies/services.py` — clase `PolicyService`:
  - `create_policy(data: dict) → Policy` — valida customer existe, crea Policy + Coverages en transacción atómica
  - `cancel_policy(policy: Policy, reason: str) → Policy` — solo si ACTIVE o SUSPENDED; si ya CANCELLED/EXPIRED → lanza `InvalidPolicyStatusError`; guarda `cancellation_reason`
  - `update_policy(policy: Policy, data: dict) → Policy` — solo si no está CANCELLED ni EXPIRED; actualiza campos permitidos
  - `verify_policy(policy_id: UUID) → dict` — retorna `{"policy_id", "status", "is_valid": status=="ACTIVE", "customer_id"}`
  - `get_policies_queryset(filters: dict) → QuerySet` — aplica filtros: status, policy_type, customer_id, start_date_from, start_date_to
  - Cada método usa `select_for_update()` donde hay riesgo de concurrencia

---

### 🔵 RONDA 3 — Paralelo (después de que Ronda 2 esté completa)

#### Paso 4 — Views + URLs + Admin `[CLAUDE CODE]` ✅
> Requiere serializers (Paso 2) y services (Paso 3).

- [x] `apps/policies/views.py`:
  - `CustomerViewSet(ModelViewSet)` — solo `list`, `create`, `retrieve` (sin update/delete). Usa `StandardPagination`.
  - `PolicyViewSet(ModelViewSet)` — `list`, `create`, `retrieve`, `partial_update` + acciones custom:
    - `@action POST /policies/{id}/cancel/` → llama `PolicyService().cancel_policy()`
    - `@action GET /policies/{id}/verify/` → llama `PolicyService().verify_policy()` (sin auth, para claims-service)
  - Filtros en `list`: `?status=`, `?policy_type=`, `?customer_id=`, `?start_date_from=`, `?start_date_to=`
  - Views thin: sin lógica de negocio, sin queries directas
- [x] `apps/policies/urls.py` — `DefaultRouter`, registrar ambos ViewSets. Prefijos: `customers/`, `policies/`
- [x] `config/urls.py` — ya incluido desde Fase 0
- [x] `apps/policies/admin.py` — django-unfold: `CustomerAdmin` (list: full_name, email, dni, created_at; search: full_name, email, dni), `PolicyAdmin` (list: policy_number, customer, policy_type, status, premium_amount; filters: status, policy_type; search: policy_number, customer__full_name)

#### Paso 5 — Kafka Events `[CLAUDE CODE]` ✅
> Requiere modelos (Paso 1). No depende de views/services para escribir el producer.

- [x] `apps/policies/events.py` — clase `PolicyEventProducer`:
  - `produce_policy_created(policy: Policy) → None`
  - `produce_policy_updated(policy: Policy) → None`
  - `produce_policy_cancelled(policy: Policy) → None`
  - Schema estándar en todos: `{"event_id", "event_type", "occurred_at", "service", "data": {...}}`
  - Usar `confluent_kafka.Producer` con `KAFKA_BOOTSTRAP_SERVERS` de settings
  - Loggear con structlog en `on_delivery` callback (success y error)
- [x] Llamar `produce_policy_created` desde `PolicyService.create_policy()`
- [x] Llamar `produce_policy_cancelled` desde `PolicyService.cancel_policy()`
- [x] Llamar `produce_policy_updated` desde `PolicyService.update_policy()`

#### Paso 6 — Tests `[OPENCODE]` ✅
> Requiere todo lo anterior completo.

- [x] `apps/policies/tests/conftest.py` — factories con factory-boy:
  - `CustomerFactory` — genera datos realistas con Faker
  - `PolicyFactory` — con `customer` SubFactory, status=ACTIVE por defecto
  - `CoverageFactory` — con `policy` SubFactory
- [x] `apps/policies/tests/test_models.py`:
  - `policy_number` se genera automáticamente en formato correcto
  - UUIDs generados como PKs
- [x] `apps/policies/tests/test_services.py` — unit tests, mock Kafka producer:
  - `create_policy()` con customer válido → Policy creada + evento emitido
  - `create_policy()` con customer inexistente → `CustomerNotFoundError`
  - `cancel_policy()` con ACTIVE → OK, status=CANCELLED, reason guardado
  - `cancel_policy()` con CANCELLED → `InvalidPolicyStatusError`
  - `update_policy()` con EXPIRED → `InvalidPolicyStatusError`
  - `verify_policy()` ACTIVE → `is_valid=True`
  - `verify_policy()` CANCELLED → `is_valid=False`
- [x] `apps/policies/tests/test_views.py` — integration tests con `@pytest.mark.django_db`:
  - `POST /api/policies/customers/` → 201, body correcto
  - `POST /api/policies/customers/` email duplicado → 400, formato error estándar
  - `GET /api/policies/customers/{id}/` → 200
  - `POST /api/policies/policies/` → 201, evento Kafka emitido (mock producer)
  - `GET /api/policies/policies/?status=ACTIVE` → solo pólizas ACTIVE
  - `POST /api/policies/policies/{id}/cancel/` → 200, status=CANCELLED
  - `POST /api/policies/policies/{id}/cancel/` (ya cancelada) → 400, error estándar
  - `GET /api/policies/policies/{id}/verify/` ACTIVE → `{"is_valid": true}`
- [x] Cobertura: `uv run pytest --cov=apps/policies --cov-report=term-missing` → services.py 99%, views.py 88%

---

### ✅ Verificación final (ambos agentes)
```bash
# Endpoints
curl -X POST http://localhost:8001/api/policies/customers/ -H "Content-Type: application/json" -d '{"full_name":"Ana García","email":"ana@test.com","dni":"12345678A","phone":"600000001","address":"Calle Mayor 1"}'
curl -X POST http://localhost:8001/api/policies/policies/ -H "Content-Type: application/json" -d '{"customer_id":"<uuid>","policy_type":"HEALTH","premium_amount":"150.00","start_date":"2026-01-01","end_date":"2027-01-01"}'
curl http://localhost:8001/api/policies/policies/?status=ACTIVE
curl -X POST http://localhost:8001/api/policies/policies/<uuid>/cancel/ -H "Content-Type: application/json" -d '{"reason":"Cliente solicitó cancelación"}'
curl http://localhost:8001/api/policies/policies/<uuid>/verify/

# Kafka
docker exec kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic policy.created --from-beginning

# Tests
cd policy-service && uv run pytest --cov=apps/policies -v

# OpenAPI
curl http://localhost:8001/api/schema/
```

---

## Progreso por fase

| Fase | Nombre | Estado |
|---|---|---|---|
| 0 | Setup e Infraestructura | ✅ Completado |
| 1 | policy-service | ✅ Completado |
| 2 | claims-service | ❌ No iniciado |
| 3 | audit-service + notification-service | ❌ No iniciado |
| 4 | Observabilidad | ❌ No iniciado |
| 5 | Gateway + Rate Limiting | ❌ No iniciado |
| 6 | Load Testing | ❌ No iniciado |
| 7 | Frontend Dashboard | ❌ No iniciado |

---

## Qué está funcionando

- ✅ Documentación base (`docs/`)
- ✅ Instrucciones para agentes (CLAUDE.md, .cursor/rules, .clinerules)
- ✅ Slash commands (`.claude/commands/`)
- ✅ Skills instalados (`.agents/skills/`)
- ✅ Git workflow (main, dev, feat branches)
- ✅ `.gitignore` + `.pre-commit-config.yaml` (ruff, detect-secrets, commitizen)
- ✅ `.secrets.baseline`
- ✅ `COMANDOS.md` + `Makefile` + `README.md`
- ✅ Docker Compose (PostgreSQL 16, Redis 7.2, Kafka 3.7 KRaft)
- ✅ Kafka 6 topics creados
- ✅ 4 Django 5.2 service esqueletos con health `/health/` respondiendo
- ✅ CI workflows (5) pasando en verde
- ✅ PR Phase 0 mergeado a dev
- ✅ policy-service: models, serializers, services, views, Kafka events, admin, tests (36 tests, 97% cov)

---

## Decisiones tomadas recientemente

- **custom_exception_handler** mejorado para manejar `ValidationError` con field-level errors → los pone en `details` y usa mensaje genérico "Error de validación de los datos enviados."
- **events.py** `_build_event` usa `_date_to_str()` helper para manejar tanto `date` objects como strings (compatibilidad SQLite en tests)
- **Policy types**: inglés (LIFE/HEALTH/AUTO/HOME/BUSINESS) alineado en modelos, API_DESIGN y CONTEXT

---

## Bloqueos o pendientes importantes

_Ninguno por ahora._

---

## Protocolo — Al terminar cada tarea

1. Marcar `[x]` en el paso completado del plan
2. Actualizar "Última tarea completada" y "Próximo paso"
3. Mover ítems en "Qué está funcionando"
4. **Avisar al usuario que la tarea está completa y ESPERAR instrucciones**
5. No commitear, no pushear — esperar a que el usuario pida `/commit-ready`

---

## Protocolo — Al terminar una fase completa

1. Verificar que TODOS los `[ ]` del plan están marcados `[x]`
2. Actualizar la tabla de progreso: ⏳ → ✅
3. Actualizar "Reglas críticas para la fase actual" con las reglas de la SIGUIENTE fase
4. Avisar al usuario: "Fase N completa. ¿Hago `/commit-ready` para preparar los commits?"
5. Solo después de commits confirmados y push → el usuario decide si crear PR

**Reglas críticas por fase** (actualizar al cambiar de fase):

| Fase | Reglas que aplican |
|---|---|
| 1 (policy) | Lógica en services.py · Tests junto al código · Formato de error estándar |
| 2 (claims) | Todo de Fase 1 + Máquina de estados solo en services.py · HTTP inter-service solo para verify |
| 3 (consumers) | AuditEvent SOLO INSERT · Emails via Celery task, NUNCA en el consumer directo |
| 4 (observability) | Logs con structlog JSON · request_id vía middleware (no pasar manual) |
| 5 (gateway) | Rate limiting en Nginx, NO en Django · JWT validado en gateway |
| 7 (frontend) | Server Components por defecto · "use client" solo con interactividad · pnpm siempre |

---

## Coordinación multi-agente

> Cuando dos agentes trabajan simultáneamente en el mismo proyecto.

### Reglas de convivencia

1. **Cada agente trabaja en su propia rama** — nunca dos agentes en la misma rama
2. **CONTEXT.md lo actualiza un solo agente a la vez** — el que termina primero
3. **Archivos compartidos** (`docker-compose.yml`, `Makefile`, `CLAUDE.md`) → solo los modifica el agente cuya tarea lo requiere explícitamente. Si hay duda, preguntar al usuario.
4. **Si otro agente está trabajando**, se indica en la sección "Agentes activos" abajo
5. **Orden de merge**: el agente que empezó primero mergea primero. El segundo hace rebase después.

### Agentes activos ahora — Fase 1

| Agente | Rama | Tareas asignadas |
|---|---|---|
| **Claude Code** | `feat/phase-1-policy-service` | Paso 0 (core/) → Paso 2 (Serializers) → Paso 4 (Views+URLs+Admin) → Paso 5 (Kafka events) |
| **OpenCode** | `feat/phase-1-policy-service` | Paso 1 (Models+Migrations) → Paso 3 (Services) → Paso 6 (Tests) |

### División de archivos — quién toca qué

| Archivo | Agente responsable |
|---|---|
| `apps/core/exceptions.py` | Claude Code |
| `apps/core/middleware.py` | Claude Code |
| `apps/core/pagination.py` | Claude Code |
| `apps/policies/models.py` | OpenCode |
| `apps/policies/serializers.py` | Claude Code |
| `apps/policies/services.py` | OpenCode |
| `apps/policies/views.py` | Claude Code |
| `apps/policies/urls.py` | Claude Code |
| `apps/policies/admin.py` | Claude Code |
| `apps/policies/events.py` | Claude Code |
| `apps/policies/tests/conftest.py` | OpenCode |
| `apps/policies/tests/test_models.py` | OpenCode |
| `apps/policies/tests/test_services.py` | OpenCode |
| `apps/policies/tests/test_views.py` | OpenCode |
| `config/settings/base.py` | Claude Code (agregar middleware + exception handler) |
| `config/urls.py` | Claude Code (incluir URLs de policies) |

> ⚠️ Si necesitas tocar un archivo que no es tuyo → pregunta al usuario primero.

### Orden de ejecución y dependencias

```
RONDA 1 (paralelo — sin dependencias entre sí):
  Claude Code → Paso 0: core/
  OpenCode    → Paso 1: Models + Migrations

    ↓ esperar a que ambos terminen Ronda 1 ↓

RONDA 2 (paralelo — requieren Ronda 1):
  Claude Code → Paso 2: Serializers  (necesita modelos)
  OpenCode    → Paso 3: Services     (necesita modelos + excepciones de core/)

    ↓ esperar a que ambos terminen Ronda 2 ↓

RONDA 3 (paralelo — requieren Ronda 2):
  Claude Code → Paso 4: Views + URLs + Admin  (necesita serializers + services)
  Claude Code → Paso 5: Kafka events          (puede ir junto al Paso 4)
  OpenCode    → Paso 6: Tests                 (necesita todo lo anterior)
```

> Cada agente avisa al usuario cuando termina su ronda. El usuario da el OK para avanzar a la siguiente.

### Resolución de conflictos

- Si dos agentes necesitan modificar el mismo archivo → el usuario decide quién lo hace
- Si un agente necesita una dependencia que otro también usa → documentar en "Decisiones tomadas recientemente"
- Migraciones de Django: si dos agentes crean migraciones en servicios DISTINTOS → no hay conflicto (DB separadas). Si es el MISMO servicio → no permitir trabajo paralelo en ese servicio.

### Autonomía para correcciones — sin pedir permiso

Si un agente encuentra un problema en el trabajo del otro (campo mal nombrado, excepción faltante, import roto, typo, inconsistencia de interfaz), puede corregirlo directamente **sin pedir permiso** si:

- El fix es pequeño y obvio (renombrar un campo, añadir una excepción, corregir un import)
- No cambia la lógica de negocio ni la arquitectura
- El cambio está dentro del alcance natural de su tarea actual

Al terminar, documenta qué corrigió en "Decisiones tomadas recientemente" para que el otro agente lo sepa.

**Sí pedir permiso si:**
- El fix requiere cambiar lógica de negocio en services.py
- Implica modificar modelos o migraciones ya creadas
- No está seguro de si es un bug o una decisión intencional
