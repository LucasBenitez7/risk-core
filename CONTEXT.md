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

## ⚠️ Reglas críticas para la fase actual — Fase 2 (claims-service)

> Estas reglas cambian según la fase. Actualizarlas al cambiar de fase.

1. **Lógica de negocio en `services.py` — nunca en `views.py`**. Las views solo reciben HTTP, llaman al service, y devuelven la respuesta. Sin `if`, sin validación de negocio, sin queries complejas en la view.

2. **Tests junto con el código — nunca al final**. Cada paso del plan incluye tests. No marcar un paso como completo si no tiene tests. Mínimo 80% de cobertura en services.py y views.py.

3. **Formato de error estándar siempre**: `{"error": {"code": "UPPERCASE_CODE", "message": "lenguaje de negocio", "details": {}}, "request_id": "uuid"}`. Nunca devolver `{"detail": "..."}` ni `{"error": "texto plano"}`.

4. **La máquina de estados SOLO en `ClaimService.transition_status()`**. Nunca un PATCH directo al campo `status`. Toda transición debe guardar `ClaimStatusHistory` y emitir el evento Kafka correspondiente.

5. **HTTP inter-service SOLO para verificar póliza**. `PolicyServiceClient.verify_policy()` es la única llamada HTTP entre servicios. Timeout 5s → 503. Póliza inactiva → 400. No añadir más llamadas HTTP.

6. **Kafka producer se llama DESPUÉS del bloque `transaction.atomic()`**, nunca dentro. Si el DB falla, el evento no se emite.

---

## Estado actual

**Fase**: 2 — claims-service  
**Rama activa**: `feat/phase-2-claims-service`  
**Última tarea completada**: Paso 6 — Tests (OpenCode) ✅ — 39 tests, 96% services.py, 100% views.py  
**Próximo paso**: **FASE 2 COMPLETA.** Ejecutar verificación final y preparar commits.

---

## Plan detallado — Fase 2 (claims-service)

> Este plan es editable por cualquier agente. Marcar `[x]` al completar cada paso.  
> Rama: `feat/phase-2-claims-service` | Scope commits: `claims`  
> **Dos agentes trabajan en paralelo — ver tabla de división más abajo.**

---

### Contexto de dominio — leer antes de empezar

**Máquina de estados de Claim** (inmutable — no modificar):
```
FILED → UNDER_REVIEW → APPROVED  → RESOLVED
                    └→ REJECTED  → RESOLVED
```
```python
VALID_TRANSITIONS = {
    "FILED":        ["UNDER_REVIEW"],
    "UNDER_REVIEW": ["APPROVED", "REJECTED"],
    "APPROVED":     ["RESOLVED"],
    "REJECTED":     ["RESOLVED"],
    "RESOLVED":     [],
}
```
- Transición a APPROVED requiere `approved_amount`
- Transición a REJECTED requiere `notes`
- Toda transición guarda `ClaimStatusHistory` y emite Kafka event

**Verificación de póliza antes de crear Claim** (única llamada HTTP inter-service):
```python
# claims-service/apps/claims/clients.py
async with httpx.AsyncClient(timeout=5.0) as client:
    response = await client.get(f"{POLICY_SERVICE_URL}/api/policies/policies/{policy_id}/verify/")
# timeout → lanzar PolicyServiceUnavailableError → view devuelve 503
# is_valid=False → lanzar PolicyInactiveError → view devuelve 400
```

**Eventos Kafka que emite claims-service**:
- `claim.filed` — al crear un Claim con status FILED
- `claim.status_changed` — en cada transición de estado
- `claim.resolved` — cuando status llega a RESOLVED (además de `claim.status_changed`)

---

### 🤖 Protocolo de avance automático entre rondas

1. Al terminar tu ronda, marca tus pasos `[x]` en este archivo
2. Revisa si los pasos del otro agente en esta ronda también están `[x]`
   - **Si sí** → empieza tu siguiente ronda directamente, sin esperar al usuario
   - **Si no** → avisa al usuario que terminaste y espera
3. Al terminar la fase completa (todos los `[x]`), avisa al usuario y espera instrucciones de commit

---

### 🔵 RONDA 1 — Paralelo (ambos agentes a la vez)

#### Paso 0 — core/ setup `[CLAUDE CODE]` ✅
> Prerrequisito: las excepciones de dominio deben existir antes de que services.py las use.

- [x] `apps/core/exceptions.py` — `custom_exception_handler` con field-level ValidationError + 4 excepciones de dominio añadidas
- [x] `apps/core/middleware.py` — `RequestIDMiddleware` OK (existía en esqueleto)
- [x] `apps/core/pagination.py` — `StandardPagination` OK (existía en esqueleto)
- [x] `apps/core/views.py` — `HealthCheckView` OK (existía en esqueleto)
- [x] `config/settings/base.py` — `RequestIDMiddleware` + `custom_exception_handler` ya registrados; `apps.claims` en INSTALLED_APPS
- [x] `POLICY_SERVICE_URL` y `POLICY_SERVICE_TIMEOUT` ya configurados via `python-decouple`

#### Paso 1 — Models + Migrations `[OPENCODE]` ✅
> No depende de core/. Se puede hacer en paralelo con Paso 0.

- [x] `apps/claims/models.py` — tres modelos:
  - `Claim`: `id` (UUID PK), `claim_number` (CLM-YYYY-NNNNNN, auto-gen, único), `policy_id` (UUID — NO FK real, referencia externa), `claimant_name`, `claimant_email`, `incident_date` (DateField), `incident_type` (choices: ACCIDENTE/ROBO/INCENDIO/INUNDACION/OTRO), `description`, `estimated_damage` (Decimal 12,2), `approved_amount` (Decimal 12,2, null/blank), `location` (blank), `status` (choices FILED/UNDER_REVIEW/APPROVED/REJECTED/RESOLVED, default FILED), `filed_at` (auto_now_add), `updated_at` (auto_now)
  - `ClaimStatusHistory`: `id` (UUID PK), `claim` (FK → Claim, CASCADE), `from_status` (blank — null para el primer registro), `to_status`, `changed_at` (auto_now_add), `notes` (blank)
  - `ClaimDocument`: `id` (UUID PK), `claim` (FK → Claim, CASCADE), `document_type`, `file_url` (URLField max 500), `uploaded_at` (auto_now_add)
  - Índices en `Claim`: `status`, `policy_id`, `filed_at`, `incident_type`
  - `generate_claim_number()` — formato CLM-YYYY-NNNNNN, igual que `generate_policy_number()` en policy-service, usando `select_for_update()` dentro del `transaction.atomic()` del service
- [x] Migraciones: `uv run python manage.py makemigrations` + `migrate` — sin errores
- [x] Registrar `apps.claims` en `INSTALLED_APPS` en `config/settings/base.py`

---

### 🔵 RONDA 2 — Paralelo (después de que Ronda 1 esté completa)

#### Paso 2 — Serializers `[CLAUDE CODE]` ✅
> Requiere modelos (Paso 1) y excepciones de core/ (Paso 0).

- [x] `apps/claims/serializers.py`:
  - `ClaimStatusHistorySerializer` — campos: `from_status`, `to_status`, `changed_at`, `notes` (read-only)
  - `ClaimDocumentSerializer` — campos: `id`, `document_type`, `file_url`, `uploaded_at` (read-only)
  - `ClaimSerializer` — campos: todos los de Claim + `status_history` nested (read-only) + `documents` nested (read-only). Write: `policy_id`, `claimant_name`, `claimant_email`, `incident_date`, `incident_type`, `description`, `estimated_damage`, `location`. Read-only: `id`, `claim_number`, `status`, `approved_amount`, `filed_at`, `updated_at`. Validar: `incident_date` no puede ser futura
  - `ClaimTransitionSerializer` — input de `/transition/`: `new_status` (requerido), `notes` (blank), `approved_amount` (Decimal, requerido solo si `new_status=APPROVED`)
  - `ClaimListSerializer` — versión ligera para listados (sin `status_history` ni `documents`)

#### Paso 3 — Services + Client HTTP `[OPENCODE]` ✅
> Requiere modelos (Paso 1) y excepciones de core/ (Paso 0).

- [x] `apps/claims/clients.py` — clase `PolicyServiceClient`:
  - `verify_policy(policy_id: str) → dict` — llama `GET {POLICY_SERVICE_URL}/api/policies/policies/{policy_id}/verify/`
  - Timeout: `POLICY_SERVICE_TIMEOUT` segundos (default 5)
  - `httpx.TimeoutException` o `httpx.ConnectError` → lanza `PolicyServiceUnavailableError`
  - Respuesta con `is_valid=False` → lanza `PolicyInactiveError(policy_id, policy_status)`
  - Respuesta 404 → lanza `PolicyInactiveError`
  - **Usar `httpx` síncrono** (`httpx.Client`, no async) — Django views son síncronas
- [x] `apps/claims/services.py` — clase `ClaimService`:
  - `file_claim(data: dict) → Claim`:
    1. Llama `PolicyServiceClient().verify_policy(data["policy_id"])` — puede lanzar excepciones
    2. Dentro de `transaction.atomic()`: crea `Claim` + primer `ClaimStatusHistory(from_status=None, to_status="FILED", notes="Siniestro reportado")`
    3. Fuera del atomic: llama `ClaimEventProducer().produce_claim_filed(claim)`
  - `transition_status(claim: Claim, new_status: str, notes: str = "", approved_amount=None) → Claim`:
    1. Valida que `new_status` es una transición válida desde `claim.status` (usando `VALID_TRANSITIONS`) → si no, lanza `InvalidClaimStatusError`
    2. Si `new_status == "APPROVED"` y `approved_amount` es None → lanza `ValidationError`
    3. Dentro de `transaction.atomic()` con `select_for_update()`: actualiza `claim.status` + `claim.approved_amount` si aplica + guarda `ClaimStatusHistory`
    4. Fuera del atomic: emite `claim.status_changed` siempre + `claim.resolved` adicional si `new_status == "RESOLVED"`
  - `get_claims_queryset(*, status, policy_id, incident_type) → QuerySet` — filtros opcionales

---

### 🔵 RONDA 3 — Paralelo (después de que Ronda 2 esté completa)

#### Paso 4 — Views + URLs + Admin `[CLAUDE CODE]` ✅
> Requiere serializers (Paso 2) y services (Paso 3).

- [x] `apps/claims/views.py`:
  - `ClaimViewSet` — `list`, `create`, `retrieve` + acción custom:
    - `@action POST /claims/{id}/transition/` → llama `ClaimService().transition_status()`
  - `get_serializer_class()`: usar `ClaimListSerializer` en `list`, `ClaimSerializer` en el resto
  - `get_queryset()`: llama `ClaimService().get_claims_queryset()` con query params (`?status=`, `?policy_id=`, `?incident_type=`)
  - Views thin: sin lógica de negocio, sin queries directas
- [x] `apps/claims/urls.py` — `DefaultRouter`, prefijo `claims/`
- [x] `config/urls.py` — incluir `apps.claims.urls` con `api/claims/`
- [x] `apps/claims/admin.py` — django-unfold:
  - `ClaimAdmin`: list: `claim_number`, `policy_id`, `claimant_name`, `status`, `incident_type`, `filed_at`; filters: `status`, `incident_type`; search: `claim_number`, `claimant_name`, `policy_id`; inline `ClaimStatusHistoryInline` (read-only)

#### Paso 5 — Kafka Events `[CLAUDE CODE]` ✅
> Requiere modelos (Paso 1). Independiente de views/services para escribir el producer.

- [x] `apps/claims/events.py` — clase `ClaimEventProducer`:
  - `produce_claim_filed(claim: Claim) → None` → topic `claim.filed`
  - `produce_claim_status_changed(claim: Claim, from_status: str) → None` → topic `claim.status_changed`
  - `produce_claim_resolved(claim: Claim) → None` → topic `claim.resolved`
  - Schema estándar en todos:
    ```python
    {
        "event_id": str(uuid4()),
        "event_type": "claim.filed",
        "occurred_at": timezone.now().isoformat(),
        "service": "claims-service",
        "data": {
            "claim_id": str(claim.id),
            "claim_number": claim.claim_number,
            "policy_id": str(claim.policy_id),
            "status": claim.status,
            "incident_type": claim.incident_type,
            "claimant_email": claim.claimant_email,
        }
    }
    ```
  - `_get_producer()` lazy import para evitar circular imports y facilitar mock en tests
  - Loggear con structlog en `on_delivery` callback

#### Paso 6 — Tests `[OPENCODE]` ✅
> Requiere todo lo anterior completo.

- [x] `apps/claims/tests/conftest.py` — factories:
  - `ClaimFactory` — `policy_id` como `LazyFunction(uuid4)`, status=FILED por defecto
  - `ClaimStatusHistoryFactory`
- [x] `apps/claims/tests/test_models.py`:
  - `claim_number` se genera en formato CLM-YYYY-NNNNNN
  - UUID PK generado
- [x] `apps/claims/tests/test_services.py` — unit tests, mock `PolicyServiceClient` y Kafka:
  - `file_claim()` con póliza ACTIVE → Claim creado, status=FILED, history guardado, evento emitido
  - `file_claim()` con póliza CANCELLED → `PolicyInactiveError` (400)
  - `file_claim()` con policy-service caído (timeout) → `PolicyServiceUnavailableError` (503)
  - `transition_status()` FILED → UNDER_REVIEW → OK, history guardado, evento emitido
  - `transition_status()` UNDER_REVIEW → APPROVED sin `approved_amount` → error
  - `transition_status()` UNDER_REVIEW → APPROVED con `approved_amount` → OK
  - `transition_status()` transición inválida (ej. FILED → APPROVED) → `InvalidClaimStatusError` con lista de transiciones válidas
  - `transition_status()` a RESOLVED → emite `claim.resolved` además de `claim.status_changed`
- [x] `apps/claims/tests/test_views.py` — integration tests con `@pytest.mark.django_db`:
  - `POST /api/claims/claims/` → 201, status=FILED (mock PolicyServiceClient)
  - `POST /api/claims/claims/` con póliza inactiva → 400, código `POLICY_INACTIVE`
  - `POST /api/claims/claims/` con policy-service caído → 503, código `POLICY_SERVICE_UNAVAILABLE`
  - `GET /api/claims/claims/?status=FILED` → lista filtrada
  - `GET /api/claims/claims/{id}/` → incluye `status_history`
  - `POST /api/claims/claims/{id}/transition/` FILED → UNDER_REVIEW → 200
  - `POST /api/claims/claims/{id}/transition/` transición inválida → 400, código `INVALID_CLAIM_STATUS`
  - `POST /api/claims/claims/{id}/transition/` → APPROVED sin `approved_amount` → 400
- [x] Cobertura: `uv run pytest --cov=apps/claims --cov-report=term-missing` → services.py 96% (≥90%), views.py 100% (≥80%)

---

### ✅ Verificación final (ambos agentes)
```bash
# Con policy-service levantado (puerto 8001) y claims-service (puerto 8002):

# Crear cliente y póliza en policy-service
curl -X POST http://localhost:8001/api/policies/customers/ \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Ana García","email":"ana@test.com","dni":"12345678A"}'

curl -X POST http://localhost:8001/api/policies/policies/ \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"<uuid>","policy_type":"HEALTH","premium_amount":"150.00","start_date":"2026-01-01","end_date":"2027-01-01"}'

# Crear siniestro (verifica póliza internamente via HTTP)
curl -X POST http://localhost:8002/api/claims/claims/ \
  -H "Content-Type: application/json" \
  -d '{"policy_id":"<uuid>","claimant_name":"Ana García","claimant_email":"ana@test.com","incident_date":"2026-03-15","incident_type":"ACCIDENTE","description":"Accidente en la A-6","estimated_damage":"5000.00"}'

# Transicionar estado
curl -X POST http://localhost:8002/api/claims/claims/<uuid>/transition/ \
  -H "Content-Type: application/json" \
  -d '{"new_status":"UNDER_REVIEW","notes":"Asignado a perito"}'

curl -X POST http://localhost:8002/api/claims/claims/<uuid>/transition/ \
  -H "Content-Type: application/json" \
  -d '{"new_status":"APPROVED","notes":"Daños confirmados","approved_amount":"4500.00"}'

# Verificar eventos Kafka
docker exec kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic claim.filed --from-beginning
docker exec kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic claim.status_changed --from-beginning

# Tests
cd claims-service && uv run pytest --cov=apps/claims -v

# OpenAPI
curl http://localhost:8002/api/schema/
```

---

## Progreso por fase

| Fase | Nombre | Estado |
|---|---|---|---|
| 0 | Setup e Infraestructura | ✅ Completado |
| 1 | policy-service | ✅ Completado |
| 2 | claims-service | ✅ Completado |
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
- ✅ PR Phase 1 mergeado a dev
- ✅ policy-service: models, serializers, services, views, Kafka events, admin, tests (36 tests, 97% cov)
- ✅ claims-service: models (Claim, ClaimStatusHistory, ClaimDocument), migrations (2), serializers (5), services, PolicyServiceClient, views (ClaimViewSet), Kafka events (3 topics), admin, tests (39 tests, 96% services.py, 100% views.py) — **Fase 2 completa**

---

## Decisiones tomadas recientemente

- **Serializer `policy_id` writable**: Se agregó `extra_kwargs = {"policy_id": {"read_only": False}}` porque el modelo tiene `editable=False` y DRF lo volvía read-only automáticamente.
- **Mock de `verify_policy`**: Para tests de error se usa `side_effect` con la excepción de dominio, no `return_value`. El mock reemplaza TODO el método, así que la lógica interna de `is_valid` no se ejecuta.
- **ClaimStatusHistory.from_status**: modelo usa `null=True, blank=True`. El service guarda `""` (string vacío) para el primer registro FILED, no NULL. Compatible con PostgreSQL y SQLite.
- **`_get_producer()`** usa lazy import en services.py para que el código compile aunque events.py no esté creado aún.

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

### Agentes activos ahora — Fase 2 (completada)

| Agente | Rama | Tareas asignadas |
|---|---|---|
| **Claude Code** | `feat/phase-2-claims-service` | Paso 0, 2, 4, 5 ✅ |
| **OpenCode** | `feat/phase-2-claims-service` | Paso 1, 3, 6 ✅ |

> **Fase 2 completa.** Ambos agentes terminaron. Pendiente: commit y merge.

### División de archivos — quién toca qué

| Archivo | Agente responsable |
|---|---|
| `apps/core/exceptions.py` | Claude Code |
| `apps/core/middleware.py` | Claude Code (verificar, no modificar si ya OK) |
| `apps/core/pagination.py` | Claude Code (verificar, no modificar si ya OK) |
| `claims-service/apps/claims/models.py` | OpenCode |
| `claims-service/apps/claims/serializers.py` | Claude Code |
| `claims-service/apps/claims/services.py` | OpenCode |
| `claims-service/apps/claims/clients.py` | OpenCode |
| `claims-service/apps/claims/views.py` | Claude Code |
| `claims-service/apps/claims/urls.py` | Claude Code |
| `claims-service/apps/claims/admin.py` | Claude Code |
| `claims-service/apps/claims/events.py` | Claude Code |
| `claims-service/apps/claims/tests/conftest.py` | OpenCode |
| `claims-service/apps/claims/tests/test_models.py` | OpenCode |
| `claims-service/apps/claims/tests/test_services.py` | OpenCode |
| `claims-service/apps/claims/tests/test_views.py` | OpenCode |
| `claims-service/config/settings/base.py` | Claude Code (añadir POLICY_SERVICE_URL, apps.claims) |
| `claims-service/config/urls.py` | Claude Code (incluir URLs de claims) |

> ⚠️ Si necesitas tocar un archivo que no es tuyo → pregunta al usuario primero.

### Orden de ejecución y dependencias

```
RONDA 1 (paralelo — sin dependencias entre sí):
  Claude Code → Paso 0: core/ exceptions + verificar settings
  OpenCode    → Paso 1: Models + Migrations (Claim, ClaimStatusHistory, ClaimDocument)

    ↓ avisar al usuario cuando ambos terminen Ronda 1 ↓

RONDA 2 (paralelo — requieren Ronda 1):
  Claude Code → Paso 2: Serializers       (necesita modelos)
  OpenCode    → Paso 3: Services + Client (necesita modelos + excepciones de core/)

    ↓ avisar al usuario cuando ambos terminen Ronda 2 ↓

RONDA 3 (paralelo — requieren Ronda 2):
  Claude Code → Paso 4: Views + URLs + Admin  (necesita serializers + services)
  Claude Code → Paso 5: Kafka events          (se hace junto al Paso 4)
  OpenCode    → Paso 6: Tests                 (necesita todo lo anterior)
```

> Cada agente avisa al usuario cuando termina su ronda. El usuario coordina el avance.

### Resolución de conflictos

- Si dos agentes necesitan modificar el mismo archivo → el usuario decide quién lo hace
- Si un agente necesita una dependencia que otro también usa → documentar en "Decisiones tomadas recientemente"
- Migraciones de Django: si dos agentes crean migraciones en servicios DISTINTOS → no hay conflicto (DB separadas). Si es el MISMO servicio → no permitir trabajo paralelo en ese servicio.

### Autonomía para correcciones — sin pedir permiso

Si un agente encuentra un problema en el trabajo del otro (campo mal nombrado, excepción faltante, import roto, typo, inconsistencia de interfaz), puede corregirlo directamente **sin pedir permiso** si:

- El fix es pequeño y obvio (renombrar un campo, añadir una excepción, corregir un import)
- No cambia la lógica de negocio ni la arquitectura
- El cambio está dentro del alcance natural de su tarea actual

---

## Plan de commits — Fase 2 (claims-service)

> Orden de ejecucion: 1 -> 2 -> 3. Cada commit es atomico.
> Ejecutar `git add` + `git commit -m "..."`. No pushear hasta confirmacion.

### Commit 1: `feat(claims): add models, serializers, services, client, events, views, urls, admin`

Todo el codigo de produccion de claims-service mas excepciones de dominio y el fix del handler.

```
git add claims-service/apps/claims/models.py \
        claims-service/apps/claims/migrations/ \
        claims-service/apps/claims/serializers.py \
        claims-service/apps/claims/services.py \
        claims-service/apps/claims/clients.py \
        claims-service/apps/claims/events.py \
        claims-service/apps/claims/views.py \
        claims-service/apps/claims/admin.py \
        claims-service/apps/claims/urls.py \
        claims-service/apps/core/exceptions.py

git commit -m "feat(claims): add models, serializers, services, client, events, views, urls, admin"
```

### Commit 2: `test(claims): add 39 unit and integration tests`

```
git add claims-service/apps/claims/tests/

git commit -m "test(claims): add 39 unit and integration tests"
```

### Commit 3: `chore: update deps, docs, context, and fix policy-service exception handler`

```
git add CONTEXT.md \
        docs/PHASES.md \
        docs/TECHNICAL_DECISIONS.md \
        claims-service/pyproject.toml \
        claims-service/uv.lock \
        policy-service/apps/core/exceptions.py

git commit -m "chore: update deps, docs, context, and fix policy-service exception handler"
```

### Cobertura: 39 tests | services.py 96% | views.py 100%

Al terminar, documenta qué corrigió en "Decisiones tomadas recientemente" para que el otro agente lo sepa.

**Sí pedir permiso si:**
- El fix requiere cambiar lógica de negocio en services.py
- Implica modificar modelos o migraciones ya creadas
- No está seguro de si es un bug o una decisión intencional
