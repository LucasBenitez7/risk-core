# CONTEXT — RiskCore

> Este archivo es la fuente de verdad del estado actual del proyecto.
> Actualizarlo cada vez que se completa una tarea o cambia de fase.
> Lo leen todos los agentes (Claude Code, Cursor, OpenCode) al inicio de cada sesión.

---

## Índice

> Las reglas del proyecto viven en **`AGENTS.md`** — este archivo solo contiene estado y plan activos.
> Las filas marcadas con **← actualizar** cambian al iniciar cada fase nueva.

| Sección | Cambia por fase |
|---|---|
| [1. Regla Absoluta](#s1) | No — nunca tocar |
| [2. Estado actual](#s2) | **Sí ← actualizar** |
| [3. Plan detallado](#s3) | **Sí ← reemplazar** |
| [4. Progreso por fase](#s4) | Sí — acumulativo |
| [5. Qué está funcionando](#s5) | Sí — acumulativo |
| [6. Decisiones tomadas recientemente](#s6) | Sí — rotar por relevancia |
| [7. Bloqueos o pendientes](#s7) | Sí — limpiar al resolver |
| [8. Protocolo — al terminar tarea](#s8) | No — nunca tocar |
| [9. Protocolo — al terminar fase](#s9) | No — nunca tocar |
| [10. Coordinación multi-agente](#s10) | Parcial — actualizar tabla de agentes |
| [11. Guía permanente de estructura](#s11) | No — nunca tocar |

---

<a id="s1"></a>
## 1. ⛔ Regla Absoluta

**NUNCA ejecutar `git commit` ni `git push` sin confirmación explícita del usuario.**
"Implementa X" / "arregla Y" / "termina la tarea" → NO son permiso para commitear.
Esperar siempre a que el usuario diga explícitamente "sí, commitea" o "commitea el grupo N".

Permitido sin pedir permiso: `git status`, `git diff`, `git log`, `git branch`, `git stash`

---

<a id="s2"></a>
## 2. Estado actual

**Fase**: 5 — Gateway + Rate Limiting
**Rama activa**: `feat/phase-5-gateway`
**Última tarea completada**: Fase 5 completa ✅ — todos los pasos (1+1b+2+2b+3+3b+4+4b) verificados. 11/11 tests pass.
**Próximo paso**: Fase 6 (Load Testing) — esperar a que el usuario decida si crear PR para Fase 5

---

<a id="s3"></a>
## 3. Plan detallado — Fase 5 (Gateway + Rate Limiting)

> Plan editable por cualquier agente. Marcar `[x]` al completar cada paso.
> Rama: `feat/phase-5-gateway` | Scope commits: `gateway`, `infra`, `policy`
> **Dos agentes en paralelo: Claude Code = Nginx + verify endpoint Django · OpenCode = docker-compose + Promtail + Grafana dashboard.**

---

### Contexto de dominio — leer antes de empezar

**Pipeline final tras Fase 5:**

```
[client] ──HTTP──▶ [gateway:80 (Nginx)] ─┬─▶ policy-service:8001
                       │                  ├─▶ claims-service:8002
                       │                  ├─▶ notification-service:8003
                       │                  └─▶ audit-service:8004
                       │
                       ├─ JWT verify ──▶ policy-service:/api/auth/verify/ (auth_request)
                       ├─ rate limit  ──▶ 429 si excede (zona api_anon o api_auth)
                       ├─ X-Request-ID ──▶ propagado a upstream
                       └─ access logs JSON ──▶ Promtail ──▶ Loki
```

**Stack a añadir** (ya disponibles, solo configurar):
- `nginx:alpine` — base del gateway
- `djangorestframework-simplejwt 5.5.x` — ya en `policy-service/pyproject.toml`
- Promtail (ya está) — añadir job que scrapee logs del container `gateway`
- Grafana (ya está) — añadir un dashboard nuevo `gateway.json`

**Contrato de respuesta de error del gateway** (todos los 4xx/5xx):
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Demasiadas peticiones. Intente nuevamente en unos segundos.",
    "details": {}
  },
  "request_id": "uuid-del-gateway"
}
```

**Códigos de error estándar** del gateway:
| HTTP | code | Cuándo |
|---|---|---|
| 401 | `UNAUTHORIZED` | JWT ausente o inválido |
| 429 | `RATE_LIMIT_EXCEEDED` | Excede tier de rate limit |
| 502 | `BAD_GATEWAY` | Servicio upstream caído |
| 503 | `SERVICE_UNAVAILABLE` | Timeout upstream |

**Puertos**:
- Gateway: 80 (en docker-compose, mapeado a host 8080 para no chocar con nada del host)
- Servicios: siguen en 8001-8004 internos (no exponer al host en producción, solo dev)

---

### 🤖 Protocolo de avance automático entre rondas

1. Al terminar tu ronda, marca tus pasos `[x]` en este archivo
2. Revisa si los pasos del otro agente en esta ronda también están `[x]`
   - **Si sí** → empieza tu siguiente ronda directamente, sin esperar al usuario
   - **Si no** → avisa al usuario que terminaste y espera
3. Al terminar la fase completa (todos los `[x]`), avisa al usuario y espera instrucciones de commit

---

### 🔵 RONDA 1 — Core del gateway (paralelo, sin dependencias entre agentes)

#### Paso 1 — Nginx con JWT, rate limiting y JSON logs `[CLAUDE CODE]`

> Reescribir `gateway/nginx.conf` (actualmente solo proxy_pass básico). Añadir verify endpoint en policy-service.

- [x] `gateway/nginx.conf` — reescrito con: `log_format json_combined` (http-level en conf.d, dentro de http{}), `access_log` en server{} para no conflictuar con el global de Alpine, `limit_req_zone` api_anon + api_auth, `limit_req_status 429`, `X-Request-ID $request_id` en server{}, `error_page` + locations internal JSON para 401/429/502/503, `auth_request /auth/verify` en todas las locations `/api/...`, `/metrics/*/` con IP whitelist, `/health/` sin auth, `/api/auth/` con rate limit anon, headers de seguridad, timeouts upstream
- [x] `gateway/Dockerfile` — sin cambios (copia a `conf.d/default.conf`, válido porque conf.d se incluye dentro de http{} en nginx:alpine)
- [x] `policy-service/apps/auth/` — app creada: `views.py` (JWTVerifyView → 200 si JWT válido, 401 por custom_exception_handler), `urls.py` (verify + token + token/refresh), `apps.py` (label auth_app para no colisionar con django.contrib.auth), `config/urls.py` registrado, `base.py` INSTALLED_APPS actualizado
- [x] `policy-service/apps/auth/management/commands/seed_test_user.py` — idempotente, solo en DEBUG=True, structlog
- [x] `ruff check` + `ruff format` limpios en `apps/auth/`
- [x] `nginx -t` — no executable localmente sin red Docker, validado por revisión de sintaxis + confirmación de que conf.d se incluye en http{} en Alpine
- [x] Tests: 5 nuevos en `apps/auth/tests/test_verify.py` (valid JWT, no token, invalid token, token_obtain, token_refresh) — todos ✅ · Suite completa: 54 tests, 0 fallos, 91% cobertura

#### Paso 1b — docker-compose + Promtail scrape del gateway `[OPENCODE]`

- [x] `infra/docker-compose.yml` — añadir servicio `gateway`:
  - `build: ../gateway`
  - `ports: ["8080:80"]` (mapear a 8080 host, 80 container — evita choque con IIS/admin en Windows)
  - `depends_on:` policy-web, claims-web, notification-web, audit-web
  - `logging.driver: json-file` con `max-size: 10m, max-file: 3`
  - `networks: [riskcore]` (todas los servicios migrados a red `riskcore` explícita)
- [x] `infra/docker-compose.yml` — modificar entry de `policy-web`: añadido `command: sh -c "python manage.py migrate && python manage.py seed_test_user && python manage.py runserver 0.0.0.0:8001"`.
- [x] `infra/promtail/promtail-config.yml` — añadido filtro `".*-gateway-.*"` + relabel `service=gateway`. El pipeline JSON existente maneja correctamente el formato de access logs del gateway (campos faltantes `timestamp`/`level` se ignoran, los demás persisten para queries `| json` en Loki).
- [x] `Makefile` — añadido target `make gateway-test` (`cd gateway && bash test.sh`) + actualizado help y .PHONY.
- [x] Verificación: `make dev` levanta también el gateway · `curl http://localhost:8080/health/` → 200

---

### 🔵 RONDA 2 — Refinamiento y observabilidad del gateway (requiere Ronda 1)

#### Paso 2 — Pulido de errores, IP whitelist `/metrics` y headers `[CLAUDE CODE]`

- [x] Endpoints `/metrics/policy|claims|notifications|audit/` con `allow 127.0.0.1; allow 172.16.0.0/12; allow 10.0.0.0/8; deny all;` — implementados en Ronda 1 directamente
- [x] Headers de seguridad en server{}: `X-Content-Type-Options nosniff`, `X-Frame-Options DENY`, `Referrer-Policy no-referrer` con `always`
- [x] `proxy_connect_timeout 5s; proxy_read_timeout 30s; proxy_send_timeout 10s;` en server{}
- [x] Comentarios mínimos donde el por qué no es obvio (`proxy_pass_request_body off`, `access_log` en server vs http)

#### Paso 2b — Dashboard Grafana del gateway `[OPENCODE]`

- [x] `infra/grafana/dashboards/gateway.json`:
  - Stat: total requests/s al gateway (`sum(rate({service="gateway"} | json | status != "" [1m]))`)
  - Time series: requests por upstream (`sum by (upstream_addr) (rate(...))`)
  - Time series: status codes por servicio
  - Time series: rate-limited (`limit_req_status="REJECTED"`)
  - Time series: latency p50/p95/p99 (`quantile_over_time(... unwrap request_time)`)
  - Logs panel: últimos 4xx/5xx con `request_id` clickable
- [x] Datasource Loki ya está; reutilizado (`${DS_LOKI}` con UID `P8E80F9AEF21F6940`)
- [x] Verificación: dashboard `Gateway` carga junto a los otros 4

---

### 🔵 RONDA 3 — Self-audit + Tests + Verificación (requiere Ronda 2)

> ⚠️ **Antes del paso de tests, cada agente DEBE auditar su propio trabajo.** Ver regla permanente en AGENTS.md §"Self-Audit obligatorio antes del paso de tests".

#### Paso 3 — `[AUDIT]` Self-audit Claude Code `[CLAUDE CODE]`

- [x] Releer `gateway/nginx.conf` línea por línea — `auth_request` en las 4 locations `/api/...` ✅ · `limit_req` en las 4 ✅ · `error_page` apunta a locations `internal` existentes ✅ · `X-Request-ID $request_id` en server{} global ✅
- [x] Releer `policy-service/apps/auth/` — lógica trivial en view es OK (sin services.py) ✅ · custom_exception_handler maneja el 401 automáticamente ✅ · nada hardcodeado ✅
- [x] `ruff check` + `ruff format` en `policy-service` → limpios ✅
- [x] `nginx -t` — validado por revisión de sintaxis (host resolution falla fuera de Docker, esperado) ✅
- [x] Duplicación resuelta: `proxy_set_header` y timeouts subidos al bloque `server {}` ✅
- [x] Código muerto: ninguno (ruff lo confirmó) ✅
- [x] Consistencia: zona `api_anon` para /api/auth/, zona `api_auth` para /api/*, /metrics/* separado
  - Resumen: **Sin hallazgos de bugs. Un ajuste proactivo: `access_log` movido a server{} para no conflictuar con el global de Alpine. Headers de seguridad y timeouts subidos al nivel server{} para evitar duplicación por location.**

#### Paso 3b — `[AUDIT]` Self-audit OpenCode `[OPENCODE]`

- [x] Releer la entry `gateway` en `docker-compose.yml`: `depends_on` 4 servicios ✅ · `logging` json-file con max-size/max-file ✅ · puerto mapeado 8080:80 (no expone 80 directo) ✅ · `networks: [riskcore]` ✅
- [x] Releer `promtail-config.yml`: filtro `".*-gateway-.*"` añadido ✅ · relabel `service=gateway` ✅ · pipeline JSON existente maneja access logs del gateway (campos `timestamp`/`level`/`event` no presentes → omitidos, resto del JSON persiste para `| json` en LogQL) ✅
- [x] Releer `gateway.json`: queries LogQL válidas (Loki range queries con `queryType: "range"` + `quantile_over_time` para latencia) · 8 paneles sin duplicados · títulos en español consistente con otros dashboards · datasources Loki y Prometheus con UIDs correctos ✅
- [x] `docker compose -f infra/docker-compose.yml config` → válido ✅
- [x] Scope OpenCode respetado: `infra/docker-compose.yml`, `infra/promtail/promtail-config.yml`, `infra/grafana/dashboards/gateway.json`, `infra/README.md`, `Makefile` — sin tocar servicios Django ni `gateway/nginx.conf` ✅
  - Resumen: **Sin hallazgos. docker-compose config válido, red `riskcore` explícita para todos los servicios, gateway correctamente mapeado a 8080, promtail captura gateway via Docker SD + relabel, dashboard con 8 paneles (Overview stats, Traffic, Rate Limiting, Latency, Error Logs) usando Loki datasource. Sin código duplicado ni labels incorrectos.**

#### Paso 4 — Tests del gateway `[CLAUDE CODE]`

- [x] `gateway/test.sh` — script bash con curl que:
  - Sin JWT a `/api/policies/policies/` → 401 + body JSON con `code: "UNAUTHORIZED"`
  - Obtener JWT vía `POST /api/auth/token/` con credenciales de un user de fixture → 200 + token
  - Con JWT válido a `/api/policies/policies/` → 200
  - Con JWT inválido (`Authorization: Bearer xxx`) → 401
  - 25 requests rápidos sin auth → primeros 20 ok, después 429 + body JSON con `code: "RATE_LIMIT_EXCEEDED"`
  - Verificar header `X-Request-ID` presente en respuesta y propagado al upstream (chequear log de policy-service por ese request_id)
  - `/metrics/policy/` desde 127.0.0.1 (host) → respuesta de Prometheus si está en red interna; si no llega, omitir y verificar manualmente
- [x] `policy-service/apps/auth/tests/test_verify.py` — 5 tests: valid JWT → 200, no token → 401, invalid token → 401, token_obtain → access+refresh, token_refresh → new access. Todos ✅
- [x] Cobertura `apps/auth/` — incluida en suite completa: 54 tests, 91% cobertura total

#### Paso 4b — Verificación end-to-end + docs `[OPENCODE]`

- [x] `infra/README.md` — añadida sección "Gateway" con: acceso (puerto 8080), obtención de JWT (curl), logs JSON en Loki (queries LogQL), dashboard Gateway (descripción de paneles), rate limit tiers.
- [x] Ejecutar `bash gateway/test.sh` end-to-end con stack levantado → 11/11 tests pass ✅
- [x] Abrir Grafana → dashboard Gateway provisionado (UID `riskcore-gateway`) ✅
- [x] Buscar en Loki: `{service="gateway"} | json | status=~"4.."` → 401 y 429 visibles con `request_id` ✅
- [x] Trazar un request_id end-to-end: gateway → Loki encuentra el log con el request_id ✅

---

### ✅ Verificación final (ambos agentes — solo después de Ronda 3)

```bash
# 1. Levantar todo
make dev

# 2. Health del gateway
curl -s http://localhost:8080/health/ | jq

# 3. Sin auth → 401
curl -i http://localhost:8080/api/policies/policies/

# 4. Obtener JWT (asume fixture user creado en Paso 4)
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r .access)

# 5. Con JWT → 200
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/policies/policies/ | jq

# 6. Rate limit anon (sin auth, 25 requests rápidos)
for i in $(seq 1 25); do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/policies/policies/; done | sort | uniq -c
# Esperado: 20 x 401 + 5 x 429  (las primeras 20 entran y son rechazadas por auth con 401, las siguientes ya las corta el rate limit con 429)

# 7. X-Request-ID propagado
RID=$(curl -s -i http://localhost:8080/health/ | grep -i x-request-id | awk '{print $2}' | tr -d '\r')
echo "Request ID: $RID"

# 8. Test suite
bash gateway/test.sh

# 9. Dashboards: abrir http://localhost:3000 → dashboard "Gateway" muestra el tráfico generado
```

---

<a id="s4"></a>
## 4. Progreso por fase

| Fase | Nombre | Estado |
|---|---|---|
| 0 | Setup e Infraestructura | ✅ Completado |
| 1 | policy-service | ✅ Completado |
| 2 | claims-service | ✅ Completado |
| 3 | audit-service + notification-service | ✅ Completado |
| 4 | Observabilidad | ✅ Completado |
| 5 | Gateway + Rate Limiting | ✅ Completado |
| 6 | Load Testing | ❌ No iniciado |
| 7 | Frontend Dashboard | ❌ No iniciado |

---

<a id="s5"></a>
## 5. Qué está funcionando

- ✅ Documentación base (`docs/`)
- ✅ Instrucciones para agentes (AGENTS.md fuente de verdad · CLAUDE.md, .clinerules, .cursor/rules como punteros)
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
- ✅ Gateway: nginx.conf con JWT auth_request + rate limiting (anon 20r/m, auth 200r/m) + JSON access logs + X-Request-ID propagation + error pages JSON + IP whitelist /metrics
- ✅ policy-service: apps/auth/ (JWT verify + token endpoints) + seed_test_user management command + tests (5 tests, 91% cov)
- ✅ Gateway infra: docker-compose entry (8080:80, red riskcore, depends_on 4 servicios) + Promtail scrape (filter + relabel service=gateway) + Grafana dashboard (8 paneles Loki-based) + Makefile gateway-test + infra/README.md sección Gateway

---

<a id="s6"></a>
## 6. Decisiones tomadas recientemente

- **`custom_exception_handler` mejorado** — `isinstance(errors, list)` antes de iterar, evita descomponer `ErrorDetail` en caracteres cuando `validate()` lanza `ValidationError({"field": "msg"})`
- **`ClaimStatusHistory.from_status = ""`** — `CharField(blank=True)` sin `null=True` no admite NULL en PostgreSQL. Primer registro usa `""`.
- **`AuditEvent.event_id` UNIQUE** — idempotencia en consumer. `IntegrityError` = duplicado → commit offset y continuar, no crashear.
- **Emails via Celery, nunca en consumer directo** — consumer crea `Notification` y dispara `task.delay()`. Desacopla canal Kafka (crítico) de SMTP (no crítico).
- **Índices duplicados corregidos en AuditEvent** — `event_type` y `occurred_at` tenían `db_index=True` en campo Y en Meta.indexes. Eliminados de Meta, quedaron solo standalone + composite `entity_type+entity_id` + `kafka_topic`.
- **`occurred_at` fallback a `timezone.now()`** — `parse_datetime()` retorna None en datetime inválido. Fallback evita IntegrityError silencioso en DB.

---

<a id="s7"></a>
## 7. Bloqueos o pendientes importantes

_Ninguno por ahora._

---

<a id="s8"></a>
## 8. Protocolo — Al terminar cada tarea

1. Marcar `[x]` en el paso completado del plan
2. Actualizar "Última tarea completada" y "Próximo paso" en [Sección 2](#s2)
3. Añadir ítem en [Sección 5](#s5) si corresponde
4. **Avisar al usuario que la tarea está completa y ESPERAR instrucciones**
5. No commitear, no pushear — esperar a que el usuario pida `/commit-ready`

---

<a id="s9"></a>
## 9. Protocolo — Al terminar una fase completa

1. Verificar que TODOS los `[ ]` del plan están marcados `[x]`
2. Actualizar tabla de [Sección 4](#s4): ⏳ → ✅, siguiente fase → ⏳
3. **Sincronizar `docs/PHASES.md`** — actualizar la tabla resumen para que refleje el mismo estado que Sección 4
4. Reemplazar [Sección 2 (Estado actual)](#s2) y [Sección 3 (Plan detallado)](#s3) con los datos de la siguiente fase
5. Avisar al usuario: "Fase N completa. ¿Hago `/commit-ready` para preparar los commits?"
6. Solo después de commits confirmados y push → el usuario decide si crear PR

> **Las reglas del proyecto NO se duplican en CONTEXT.md.** Viven en `AGENTS.md` y aplican siempre. Si una fase introduce una invariante nueva (ej: "rate limiting solo en Nginx"), añadirla a `AGENTS.md` (sección "Reglas de código" o tabla "NUNCA hacer"), nunca a CONTEXT.md.

---

<a id="s10"></a>
## 10. Coordinación multi-agente

> Cuando dos agentes trabajan simultáneamente en el mismo proyecto.
> Si es single-agente, mantener esta sección con una sola fila en la tabla.

### Reglas de convivencia

1. **Cada agente trabaja en su propio servicio/área** — sin pisar archivos del otro
2. **CONTEXT.md lo actualiza un solo agente a la vez** — el que termina primero
3. **Archivos compartidos** (`docker-compose.yml`, `Makefile`, `AGENTS.md`) → solo los modifica el agente cuya tarea lo requiere explícitamente
4. **Orden de merge**: el agente que empezó primero mergea primero. El segundo hace rebase después.

### Agentes activos — Fase 5

| Agente | Área | Tareas asignadas |
|---|---|---|
| **Claude Code** | Nginx config + endpoint JWT verify en policy-service + tests del gateway | Paso 1 → Paso 2 → Paso 3 (AUDIT) → Paso 4 |
| **OpenCode** | docker-compose entry del gateway + Promtail scrape + dashboard Grafana + verificación end-to-end | Paso 1b → Paso 2b → Paso 3b (AUDIT) → Paso 4b |

### División de archivos — quién toca qué

| Área | Agente |
|---|---|
| `gateway/nginx.conf`, `gateway/Dockerfile`, `gateway/test.sh` | **Claude Code** |
| `policy-service/apps/auth/` (verify endpoint + token endpoints + tests) | **Claude Code** |
| `policy-service/config/settings/base.py` (solo si requiere ajustes mínimos para simplejwt) | **Claude Code** |
| `infra/docker-compose.yml` (entry `gateway`) | **OpenCode** |
| `infra/promtail/promtail-config.yml` (verificar/ajustar scrape del gateway) | **OpenCode** |
| `infra/grafana/dashboards/gateway.json` | **OpenCode** |
| `infra/README.md` (sección Gateway) | **OpenCode** |
| `Makefile` (target `gateway-test`) | **OpenCode** |

### Resolución de conflictos

- Mismo archivo → el usuario decide quién lo modifica
- Migraciones en servicios distintos → no hay conflicto (DB separadas)
- Fix pequeño y obvio en código del otro (typo, import roto) → corregir sin pedir permiso si no cambia lógica de negocio

---

<a id="s11"></a>
## 11. 📋 Guía permanente — Cómo estructurar este archivo

> Esta sección NO cambia nunca. Es la referencia para cualquier agente que inicie una fase o un proyecto nuevo.

---

### Al iniciar una FASE nueva (proyecto existente)

Actualizar en este orden:

**1 → [Sección 2](#s2) — Estado actual**
```
**Fase**: N — nombre
**Rama activa**: feat/phase-N-nombre
**Última tarea completada**: Fase N-1 completada ✅
**Próximo paso**: RONDA 1 — [descripción]
```

**2 → [Sección 3](#s3) — Plan detallado**
Reemplazar el plan anterior completo con el nuevo. Usar la plantilla de abajo.

**3 → [Sección 10](#s10) — Agentes activos**
Actualizar tabla con los agentes y servicios de esta fase.
Si es single-agente, una sola fila con Claude Code.

> **No actualizar reglas en CONTEXT.md.** Las reglas viven en `AGENTS.md`. Si esta fase introduce una invariante nueva (ej: "JWT solo en gateway"), añadirla a `AGENTS.md`, no aquí.

---

### Al iniciar un PROYECTO nuevo

> **No vive en este archivo.** La guía completa para arrancar un proyecto desde cero (CONTEXT/AGENTS/punteros, slash commands, skills, GitHub Actions, herramientas, etc.) está en:
>
> **`C:\Users\lucas\Desktop\codigos_servibles\iniciar-proyecto.md`**
>
> Es la plantilla maestra que se reutiliza entre proyectos. Mantenerla actualizada con la estructura actual (AGENTS.md canónico, CLAUDE.md/.clinerules/.cursor/rules como punteros finos, CONTEXT.md sin reglas).
>
> En este archivo (§11) solo está la guía de **cómo armar el CONTEXT.md y el plan de cada fase nueva** dentro de un proyecto que ya existe (sección "Al iniciar una FASE nueva" arriba, plantilla del Plan abajo).

---

---


### Plantilla del Plan detallado (copiar y adaptar cada fase)

```markdown
## 3. Plan detallado — Fase N (nombre)   ← plantilla, número real depende del archivo

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

### 🔵 RONDA FINAL — Self-audit + Tests + Verificación

> ⚠️ **OBLIGATORIO en cada fase.** Antes del paso de tests, cada agente DEBE auditar su propio trabajo.
> Ver regla permanente en `AGENTS.md` §"Self-Audit obligatorio antes del paso de tests".

#### Paso N — `[AUDIT]` Self-audit Claude Code `[CLAUDE CODE]`
- [ ] Releer cada archivo modificado: bugs, condiciones invertidas, off-by-one, returns olvidados, except: pass
- [ ] Errores silenciosos: try/except sin log + re-raise, mensajes genéricos
- [ ] Duplicación: bloques copiados, helpers ya existentes en core/, constantes mágicas
- [ ] Malas prácticas del proyecto: lógica en views, print() en vez de structlog, hardcode
- [ ] Código muerto: imports no usados, funciones nunca llamadas, ramas inalcanzables
- [ ] `ruff check` + `ruff format --check` limpios
- [ ] Resumen del audit (qué se revisó, qué se arregló, o "sin hallazgos"):
  - _(rellenar al hacerlo)_

#### Paso Nb — `[AUDIT]` Self-audit OpenCode `[OPENCODE]`   ← omitir si single-agente
- [ ] Mismo checklist sobre los archivos del agente OpenCode (configs, infra, dashboards)
- [ ] Validaciones específicas según área: `nginx -t`, `docker compose config`, JSON válido
- [ ] Resumen del audit:
  - _(rellenar al hacerlo)_

#### Paso N+1 — Tests `[CLAUDE CODE]`
- [ ] Tests del módulo en `tests/`
- [ ] Cobertura objetivo cumplida
- [ ] Suite completa verde

#### Paso N+1b — Verificación end-to-end `[OPENCODE]`   ← omitir si single-agente
- [ ] Comandos curl / smoke tests del flujo completo

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
- **Ronda final SIEMPRE incluye AUDIT antes de tests** — regla permanente del proyecto, no opcional

### Qué NO tocar nunca

- Sección 1 — Regla Absoluta
- Sección 8 — Protocolo al terminar tarea
- Sección 9 — Protocolo al terminar fase
- Sección 10 — Reglas de convivencia (solo actualizar tabla de agentes)
- Sección 11 — Esta guía
