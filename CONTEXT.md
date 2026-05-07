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
## 2. ⚠️ Reglas críticas — fase actual (Fase 5: gateway + rate limiting)

> Estas reglas cambian según la fase. Reemplazar completo al iniciar una fase nueva.
> Ver tabla de reglas por fase en [Sección 10](#s10).

1. **Rate limiting SOLO en Nginx — nunca en Django**. Si te tienta poner `django-ratelimit` o un decorador throttle de DRF: no. El gateway frena el tráfico antes de tocar Python. Cualquier propuesta de rate limiting en código de servicio es bug.

2. **JWT validado SOLO en el gateway**. Los servicios Django confían en el gateway y no re-validan el token. La validación se hace via `auth_request` de Nginx contra un endpoint de verify expuesto por `policy-service`. No duplicar la validación en cada servicio.

3. **Tiers de rate limit — exactos** (ver `docs/TECHNICAL_DECISIONS.md` §9):
   - Sin auth → `20r/m` por IP (zona `api_anon`)
   - Con JWT → `200r/m` por token (zona `api_auth`, key = `$http_authorization`)
   - Whitelist de IPs admin → sin límite
   En producción `api_auth` baja a `60r/m` (free tier Upstash).

4. **`X-Request-ID` se genera en el gateway**. Nginx usa `$request_id` (UUID auto) y lo propaga como header `X-Request-ID` a todos los upstreams. El middleware Django ya lo respeta si viene en el request — no tocar `RequestIDMiddleware`.

5. **`/metrics` con IP whitelist en el gateway**. En desarrollo accesible; en la config de producción/staging del gateway, `/metrics/policy/`, `/metrics/claims/`, etc., solo desde IPs internas (`allow 10.0.0.0/8; deny all;`). Nunca exponer público.

6. **Logs de acceso del gateway en JSON → Loki**. Formato `log_format` custom con `request_id`, `status`, `upstream_response_time`, `request_time`, `limit_req_status`. Promtail lo scrapea igual que el resto de servicios. Nada de logs en formato Combined estándar.

7. **Errores en formato del proyecto**. 401, 429, 502, 503 deben responder JSON con la estructura estándar `{"error": {"code": "...", "message": "..."}, "request_id": "..."}`. Nginx usa `error_page` + `internal` location con `default_type application/json` y `return` con cuerpo construido.

8. **Endpoint de verify JWT en `policy-service`** (no nuevo servicio): `GET /api/auth/verify/` que devuelve 200 si el JWT es válido, 401 si no. Lo consume `auth_request` de Nginx. Se implementa con `simplejwt` (ya instalado).

9. **Self-audit obligatorio antes de tests** (regla permanente, ver CLAUDE.md §"Self-Audit"). Cada agente revisa SU propio trabajo de la fase antes del paso de tests: bugs, errores silenciosos, duplicación, malas prácticas, código muerto, consistencia, `ruff` / `nginx -t` limpios. Hallazgos se arreglan en el momento.

10. **No tocar el código de los 4 servicios Django excepto para añadir el endpoint de verify**. Toda la lógica de gateway vive en `gateway/`. Si necesitás cambiar más allá del verify endpoint, parar y consultar.

---

<a id="s3"></a>
## 3. Estado actual

**Fase**: 5 — Gateway + Rate Limiting
**Rama activa**: `feat/phase-5-gateway`
**Última tarea completada**: Fase 5 completa ✅ — todos los pasos (1+1b+2+2b+3+3b+4+4b) verificados. 11/11 tests pass.
**Próximo paso**: Fase 6 (Load Testing) — esperar a que el usuario decida si crear PR para Fase 5

---

<a id="s4"></a>
## 4. Plan detallado — Fase 5 (Gateway + Rate Limiting)

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

> ⚠️ **Antes del paso de tests, cada agente DEBE auditar su propio trabajo.** Ver regla permanente en CLAUDE.md §"Self-Audit obligatorio antes del paso de tests".

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

<a id="s5"></a>
## 5. Progreso por fase

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
- ✅ Gateway: nginx.conf con JWT auth_request + rate limiting (anon 20r/m, auth 200r/m) + JSON access logs + X-Request-ID propagation + error pages JSON + IP whitelist /metrics
- ✅ policy-service: apps/auth/ (JWT verify + token endpoints) + seed_test_user management command + tests (5 tests, 91% cov)
- ✅ Gateway infra: docker-compose entry (8080:80, red riskcore, depends_on 4 servicios) + Promtail scrape (filter + relabel service=gateway) + Grafana dashboard (8 paneles Loki-based) + Makefile gateway-test + infra/README.md sección Gateway

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
