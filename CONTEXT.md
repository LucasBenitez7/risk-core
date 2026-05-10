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

**Fase**: 6.5 — Resilience Hardening (**completada — pendiente commits + PR**)
**Rama activa**: `feat/phase-6-5-hardening`
**Última tarea completada**: Hotfix bottleneck `generate_policy_number()` — `select_for_update()` reemplazado por PostgreSQL `SEQUENCE` (`nextval()`), migración 0002, backend detection para preservar tests SQLite.
**Próximo paso**: OpenCode aplica `uv run python manage.py migrate` en policy-service y re-corre scenarios 1, 2, 5 para verificar que el breaking point sube más allá de 50 usuarios. Después: `/commit-ready` para preparar commits.

---

<a id="s3"></a>
## 3. Plan detallado — Fase 6.5 (Resilience Hardening)

> Plan completo y detallado: **`docs/PHASE_6_5_HARDENING.md`** (no duplicar aquí — el archivo es la fuente de verdad).
> Rama: `feat/phase-6-5-hardening` (crear desde `dev` post-merge de Fase 6) | Scope commits: `feat(claims)`, `feat(policy)`, `chore(infra)`, `docs`
> **Bloques A y B en paralelo: Claude Code hace A, OpenCode hace B. Sin dependencias entre ellos. OpenCode ejecuta tests y Bloque C al terminar ambos. Claude Code hace audit final y docs.**

---

### Resumen de bloques

| Bloque | Patrón | Agente | Archivos clave | Estimado |
|---|---|---|---|---|
| A | Circuit Breaker | **Claude Code** (escribe) + **OpenCode** (ejecuta) | `claims-service/apps/claims/clients.py`, `apps/core/metrics.py` | ~2h |
| B | Outbox Pattern | **OpenCode** (escribe + ejecuta) | `apps/outbox/` en policy y claims, refactor de `events.py` y `services.py`, 2 containers nuevos en docker-compose | ~6-8h |
| C | Verificación + docs | **OpenCode** (load tests) + **Claude Code** (docs) | re-correr scenarios 1, 2, 5; actualizar `load-testing-results.md` y `docs/TECHNICAL_DECISIONS.md` | ~1h |

**Total paralelo**: ~6-8h (A y B corren al mismo tiempo).

---

### Pasos de alto nivel (detalle completo en PHASE_6_5_HARDENING.md)

#### Bloque A — Circuit Breaker `[CLAUDE CODE escribe · OPENCODE ejecuta]`

- [x] Refactor de `apps/claims/clients.py` con `_policy_breaker` + `_ClientBusinessError` para excluir 4xx
- [x] Métricas Prometheus en `apps/core/metrics.py`: `circuit_breaker_state` (Gauge), `circuit_breaker_state_changes_total` (Counter)
- [x] Panel Grafana en `services-overview.json` (row + stat + timeseries) + alerta `PolicyCircuitBreakerOpen for 2m` en `provisioning/alerting/rules.yml`
- [x] Tests: 5 fallos consecutivos → circuito abre, 404 no cuenta, 200 inválido no cuenta, happy path
- [x] **OpenCode**: `uv add pybreaker`, `uv run pytest`, verificación manual (stop policy-web, 6 requests → fail-fast)

#### Bloque B — Outbox Pattern `[OPENCODE escribe + ejecuta]`

- [x] Crear app Django `apps/outbox/` en policy-service y claims-service
- [x] Modelo `OutboxEvent` con índice parcial PostgreSQL `WHERE status='PENDING'`
- [x] Management command `run_outbox_relay` con `select_for_update(skip_locked=True)`
- [x] Refactor productores: `PolicyEventProducer` → `PolicyEventBuilder` + `emit_policy_event()` dentro de transacción
- [x] Refactor `services.py` en ambos servicios — `produce_*` → `emit_*_event()` dentro de `transaction.atomic()`
- [x] 2 containers nuevos en `infra/docker-compose.yml`: `policy-outbox-relay`, `claims-outbox-relay`
- [x] Métricas outbox en `apps/core/metrics.py` de cada servicio + alertas en `alert-rules.yml`
- [x] Tests: rollback no deja eventos, relay publica OK, concurrencia con threads, fault tolerance Kafka stop/start
- [x] **OpenCode ejecuta**: `makemigrations outbox && migrate`, `uv run pytest`, `docker compose up` relays, fault tolerance test

#### Bloque C — Verificación final `[OPENCODE ejecuta · CLAUDE CODE redacta docs]`

- [x] **OpenCode**: re-correr `make load-test SCENARIO=1/2/5`, capturar números, `bash gateway/test.sh` → 11/11
- [x] **Claude Code**: actualizar `load-testing-results.md` sección "Phase 6.5 retest" con números de OpenCode
- [x] **Claude Code**: crear secciones en `docs/TECHNICAL_DECISIONS.md`: §23 Outbox Pattern y §24 Circuit Breaker
- [x] **Claude Code**: actualizar `README.md` raíz + `CONTEXT.md` §4 y §2
- [ ] Avisar al usuario para preparar commits + PR

---

### Criterios de aceptación de la fase

1. ✅ `bash gateway/test.sh` → 11/11 pass (sin regresión)
2. ✅ `make dev` levanta el stack completo incluyendo los 2 relays
3. ✅ Test de fault tolerance pasa: Kafka stop → API responde 201 → evento queda PENDING → Kafka start → evento publicado
4. ✅ Circuit breaker verificado manualmente: stop policy-web, 6 requests a claims, sexta es immediate fail
5. ✅ Todos los tests de policy-service y claims-service pasan
6. ✅ `load-testing-results.md` tiene sección Phase 6.5 con números actualizados
7. ✅ Ruff + format limpios en los archivos modificados

---

<details>
<summary>📦 Plan de Fase 6 (archivado — completada y pusheada)</summary>

## Plan archivado — Fase 6 (Load Testing)

> Plan editable por cualquier agente. Marcar `[x]` al completar cada paso.
> Rama: `feat/phase-6-load-testing` | Scope commits: `infra`, `chore`, `docs`
> **Dos agentes en paralelo: Claude Code = locust scenarios (Python) · OpenCode = infra de ejecución (docker, Makefile, Grafana, results).**

---

### Contexto de dominio — leer antes de empezar

**Objetivo**: validar que el sistema aguanta carga real usando locust 2.43.x. Documentar resultados con números reales y screenshots de Grafana en `load-testing-results.md` (raíz).

**Pipeline bajo carga**:
```
[locust workers] ──HTTP──▶ [gateway:8080] ──▶ [policy/claims/audit/notification services]
                              │
                              └─ JWT (obtenido por user en on_start) → rate limit tier api_auth (200r/m)
```

**5 escenarios** (en `infra/load-testing/`):

| # | Archivo | Carga | Target |
|---|---|---|---|
| 1 | `scenario_1_policy_creation.py` | 500 users — crear customer → crear policy → verificar | p95 < 500ms · errors < 1% |
| 2 | `scenario_2_claims_filing.py` | 300 users — leer policy → crear claim → transición FILED→UNDER_REVIEW | p95 < 800ms (incluye HTTP claims→policy) |
| 3 | `scenario_3_audit_read.py` | 1000 users read-only — list audit con filtros variados | p95 < 200ms |
| 4 | `scenario_4_spike.py` | 0 → 1000 users en 30s | medir latencia + Kafka consumer lag |
| 5 | `scenario_5_stress.py` | escalado hasta error rate > 10% | documentar punto de quiebre |

**Reglas**:
- Cada escenario hereda `HttpUser` de locust y define `wait_time = between(1, 3)` salvo el spike/stress
- `on_start` obtiene JWT vía `POST /api/auth/token/` y lo guarda como `self.client.headers["Authorization"]`
- Rate limit del gateway está en 200r/m por IP autenticada → para no chocar contra el rate limit (no es lo que queremos medir), bajar `wait_time` o subir el tier `api_auth` a `1000r/m` solo durante load tests vía override en `nginx.conf` o documentar que el throughput está acotado por el gateway. **Decidir y dejarlo escrito** (ver Paso 1).
- Datos de prueba: usar el `seed_test_user` ya existente + crear customers/policies on-the-fly por user
- Una sola DB compartida no — cada servicio tiene su DB; los escenarios apuntan al gateway, no a servicios sueltos
- Escenarios stateless: no asumir orden entre users

---

### 🤖 Protocolo de avance automático entre rondas

1. Al terminar tu ronda, marca tus pasos `[x]` en este archivo
2. Revisa si los pasos del otro agente en esta ronda también están `[x]`
   - **Si sí** → empieza tu siguiente ronda directamente, sin esperar al usuario
   - **Si no** → avisa al usuario que terminaste y espera
3. Al terminar la fase completa (todos los `[x]`), avisa al usuario y espera instrucciones de commit

---

### 🔵 RONDA 1 — Base + 3 escenarios principales (paralelo, sin dependencias)

#### Paso 1 — locust base + escenarios 1 y 2 `[CLAUDE CODE]`

> Crear estructura `infra/load-testing/` y los dos escenarios con auth + lógica de negocio (write-heavy).

- [x] `infra/load-testing/__init__.py` — vacío (paquete)
- [x] `infra/load-testing/auth_helper.py` — `get_jwt(client)` → POST `/api/auth/token/`, devuelve access token, falla explícito si HTTP != 200. Configurable via env `LOAD_TEST_USER` / `LOAD_TEST_PASSWORD`
- [x] `infra/load-testing/locustfile.py` — importa PolicyCreationUser + ClaimsFilingUser + AuditReadUser para UI mode
- [x] `infra/load-testing/scenario_1_policy_creation.py` — `PolicyCreationUser`: on_start JWT + pre-create customer/policy · @task(3) create_customer_and_policy (POST customer → POST policy → GET policy) · @task(1) list_policies
- [x] `infra/load-testing/scenario_2_claims_filing.py` — `ClaimsFilingUser`: on_start JWT + setup customer+policy · @task(2) file_claim → guarda claim_id en lista · @task(1) transition_claim FILED→UNDER_REVIEW (400 aceptable) · @task(1) list_claims
- [x] **Decisión rate limit** documentada en docstring scenario_1: mantener `api_auth=200r/m` y documentar que el ceiling de throughput desde una IP es ~3.3 req/s; para superar ese límite usar locust en modo distribuido con múltiples workers/IPs
- [x] `ruff check` + `ruff format` limpios en todos los archivos — incluyendo scenario_3 de OpenCode
- [x] Tests sintácticos: `python -m py_compile *.py` → SYNTAX OK en todos los archivos

#### Paso 1b — Servicio locust en docker-compose + Makefile + scenario 3 `[OPENCODE]`

> Integrar locust al stack y añadir el scenario read-heavy independiente.

- [x] `infra/docker-compose.yml` — añadir servicio `locust`:
  - `image: locustio/locust:2.43.x`
  - `volumes: ["../infra/load-testing:/mnt/locust"]`
  - `working_dir: /mnt/locust`
  - `command: ["-f", "/mnt/locust/locustfile.py", "--host=http://gateway"]` (configurable)
  - `ports: ["8089:8089"]` (UI web)
  - `depends_on: [gateway]`
  - `networks: [riskcore]`
  - `profiles: ["loadtest"]` ← **importante**: usar profile para que `make dev` no lo levante
- [x] `Makefile` — añadir targets:
  - `make load-test SCENARIO=1` → `docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust -f /mnt/locust/scenario_1_policy_creation.py --headless -u 500 -r 50 -t 2m --html /mnt/locust/results/scenario_1.html`
  - Targets equivalentes para scenarios 2/3/4/5
  - `make load-test-ui` → levanta locust en modo web (puerto 8089) para ejecución manual
  - Crear directorio `infra/load-testing/results/` (gitignore subdir excepto `.gitkeep` y `*.md`)
- [x] `infra/load-testing/scenario_3_audit_read.py`:
  - `class AuditReadUser(HttpUser)` · `wait_time = between(0.5, 2)` · 1000 users target
  - `on_start`: JWT
  - `@task(4) list_audit`: GET `/api/audit/events/?page_size=50` (cursor pagination)
  - `@task(2) filter_by_entity_type`: GET con `?entity_type=policy`
  - `@task(2) filter_by_topic`: GET con `?kafka_topic=policy.created`
  - `@task(1) filter_by_date`: GET con `?occurred_after=...&occurred_before=...`
- [x] `infra/load-testing/README.md` — cómo levantar locust (UI + headless), variables de entorno, qué mide cada escenario, cómo leer los reports HTML
- [x] `infra/load-testing/.gitignore` — `results/*.html`, `results/*.csv` (los `.md` sí se commitean)
- [x] Verificación: `docker compose -f infra/docker-compose.yml --profile loadtest config` → válido

#### Paso 2b — Dashboard Grafana load-testing + annotations `[OPENCODE]`

- [x] `infra/grafana/dashboards/load-testing.json`:
  - Time series: requests/s al gateway durante el test (reusa Loki query del dashboard Gateway)
  - Time series: error rate (4xx + 5xx) sobre total
  - Time series: latencia p50/p95/p99 del gateway (`quantile_over_time` sobre `request_time`)
  - Time series: Kafka consumer lag por topic (Prometheus, métrica `kafka_consumer_lag`) — relevante para scenario 4
  - Time series: CPU + memoria por container (si cAdvisor está disponible; si no, omitir y dejar nota en README)
  - Logs panel: errores 5xx con request_id durante el test
  - Variables: `$scenario` (text input para anotar manualmente qué se está corriendo)
- [x] `infra/README.md` — añadir sección **Load Testing** con: cómo correr cada escenario, cómo abrir el dashboard, dónde quedan los HTML reports, cómo interpretar los números

#### Paso 3b — `[AUDIT]` Self-audit OpenCode `[OPENCODE]`

- [x] `docker-compose.yml`: profile `loadtest` correctamente aislado de `make dev` · volumen apunta al path correcto · network `riskcore` · sin puertos colisionando con el host
- [x] `Makefile`: targets idempotentes · `--headless` con `-t` (tiempo) acotado · output dir creado antes del run
- [x] `scenario_3_audit_read.py`: solo GETs, ningún side-effect en DB · filtros usan querystrings que el viewset realmente soporta (verificado contra `audit-service/apps/audit/views.py` — usa `from_date`/`to_date` no `occurred_after`/`occurred_before`)
- [x] `load-testing.json`: queries PromQL/Loki válidas · UIDs de datasource `${DS_PROMETHEUS}` / `${DS_LOKI}` correctos · sin paneles duplicados
- [x] `docker compose -f infra/docker-compose.yml --profile loadtest config` → válido
- [x] Resumen del audit:
  - **Sin hallazgos**. docker-compose: locust profile es `loadtest` (aislado de `make dev`), puerto 8089 no colisiona (los otros van en 5432/6379/9092/3000/3100/8001-8004/8080). Makefile: cada target especifica archivo, users, spawn rate y tiempo concretos. scenario_3: filtros verificados contra el viewset real (`from_date`/`to_date` no `occurred_after`/`occurred_before`). load-testing.json: datasource UIDs usan variables `${DS_*}` que Grafana resuelve via provisioning. Results directory creado con subcarpeta screenshots.

#### Paso 4 — Ejecutar escenarios 1, 2, 4 + capturar `[CLAUDE CODE]`

- [x] Stack levantado y verificado (gateway health OK, auth endpoint OK)
- [x] Fix: `gateway` añadido a `ALLOWED_HOSTS` en docker-compose para los 4 servicios Django (sin `gateway` en ALLOWED_HOSTS, los requests de locust con `Host: gateway` devolvían 500)
- [x] Fix: `auth_helper.py` refactorizado a patrón `register_auth_hook` + `shared_token` (events.init fetch único antes de spawnear users, evita 429-flood en api_anon durante ramp-up)
- [x] `make load-test SCENARIO=1` (50 users, 2 min) → HTML report generado
- [x] `make load-test SCENARIO=2` (30 users, 2 min) → HTML report generado
- [x] `make load-test SCENARIO=4` (spike LoadTestShape: 0→1000 en 30s / hold 120s / ramp-down) → HTML report generado
- [x] Métricas capturadas para OpenCode (ver tabla abajo):

**Métricas escenario 1** (50 users, 2 min — policy creation):
| Endpoint | p50 | p95 | p99 | max | RPS total | fail% |
|---|---|---|---|---|---|---|
| POST create_customer | 2ms | 39ms | 53ms | 190ms | 19.9 | 86% (429 rate-limit) |
| POST create_policy | 1ms | 5ms | 86ms | 110ms | 2.9 | 100% (rate-limit) |
| GET list_policies | 2ms | 33ms | 39ms | 130ms | 6.5 | 86% (429) |
- Bottleneck: **api_auth zone (200r/min)** — gateway rate limit, no Django/DB
- Latencia Django cuando pasa la request: p95 ~39ms ✅ (target 500ms)
- Error report vacío: sin crashes, solo throttling controlado

**Métricas escenario 2** (30 users, 2 min — claims filing):
| Endpoint | p50 | p95 | p99 | max | fail% |
|---|---|---|---|---|---|
| POST create_customer (setup) | 53ms | 70ms | 72ms | 72ms | 17% |
| POST create_policy (setup) | 6ms | 88ms | 95ms | 95ms | 100% |
| GET list_claims | 30ms | 44ms | 73ms | 77ms | 100% |
- Mismo bottleneck: rate limit zone compartida entre policy + claims
- file_claim/transition_claim no ejecutados (setup falló por rate limit)
- Latencia base claims: 30-53ms p50 ✅ (target 800ms incluye inter-service)

**Métricas escenario 4** (spike 0→1000 users, 3 min total):
| Endpoint | p50 | p95 | p99 | max | RPS | fail% |
|---|---|---|---|---|---|---|
| POST create_customer | 9ms | 80ms | 140ms | 1209ms | 519 | 99.45% |
| POST create_policy | 8ms | 56ms | 100ms | 210ms | 2.87 | 100% |
| GET list_policies | 10ms | 79ms | 140ms | 230ms | 169 | 99.46% |
- Durante el spike a 1000 users: max latencia 1209ms (único outlier en ramp-up)
- Gateway absorbió el spike sin caerse: error report vacío, p95 estable en 80ms
- Kafka consumer lag: visible en Grafana (documentar en screenshot)

#### Paso 4b — Ejecutar 3 + 5, screenshots Grafana, redactar resultados `[OPENCODE]`

- [x] `make load-test-3` (5 minutos, 1000 users) → HTML report en `infra/load-testing/results/scenario_3_report.html`
- [x] `make load-test-5` (stress, hasta error > 10%) → HTML report generado, punto de quiebre documentado
- [x] `docker stats --no-stream` + `pg_stat_activity` capturados post-test. Kafka consumers no estaban corriendo.
- [x] `load-testing-results.md` redactado con tabla resumen, análisis por escenario, bottlenecks, comparación TicketMaster, próximos pasos
- [x] Bottleneck identificado: Django `runserver` single-threaded (quiebre a ~50 usuarios). Memory leak en policy-service (695 MiB). Gateway Nginx no es bottleneck.

---

### ✅ Verificación final (ambos agentes — solo después de Ronda 3)

```bash
# 1. Stack levantado
make dev

# 2. Locust UI accesible
make load-test-ui   # luego abrir http://localhost:8089

# 3. Cada target del Makefile corre limpio (smoke con -u 10 -t 30s sería suficiente para validar)
make load-test SCENARIO=1
make load-test SCENARIO=2
make load-test SCENARIO=3
make load-test SCENARIO=4
make load-test SCENARIO=5

# 4. Reports HTML generados
ls infra/load-testing/results/

# 5. Dashboard Grafana "Load Testing" visible
open http://localhost:3000

# 6. load-testing-results.md tiene números reales y screenshots
```

---

### ⚠️ Diagnóstico tras Ronda 3 — por qué se necesita Ronda 4

Los datos del Paso 4 (Claude Code) demostraron que el rate limiter del gateway (`api_auth=200r/min` desde una IP) fue el bottleneck en **86-99% de requests**. Django apenas procesó ~3 req/s. Esto invalida los datos para el portfolio:

- Targets de PHASES.md (500/300/1000 users) no se testearon — se corrió 50/30/spike
- HTTP inter-service `claims→policy/verify` (feature técnico clave) nunca se ejecutó (setup falló por rate limit)
- DB connection pool, Kafka consumer lag, memoria/CPU por container → no medidos
- Audit DB vacía → scenario 3 sin datos representativos
- Scenarios 3 y 5 no corridos (eran inservibles con la config actual)

**Conclusión**: hay que eliminar el rate limiter como variable de confusión, hacer seed de audit, capturar métricas de sistema (DB/Kafka/contenedores) y re-ejecutar a la concurrencia objetivo.

---

### 🔵 RONDA 4 — Calibración del entorno (completado ✅)

#### Paso 5 — Override rate limit + seed audit + dashboard `[OPENCODE]` ✅

- [x] `gateway/nginx.loadtest.conf` — rate=10000r/m en api_anon y api_auth
- [x] `infra/docker-compose.yml` — servicio `gateway-loadtest` con profile loadtest, puerto 8081
- [x] Targets Makefile: `load-test-1` a `load-test-5` con `--host=http://gateway-loadtest`, `load-test-ui`, `load-test-seed`
- [x] `seed_audit_events.py` — bulk-create 10k eventos, idempotente, DEBUG-only
- [x] `load-testing.json` — expandido con memory/CPU per service, latency by upstream, 4xx/5xx logs
- [x] Verificación: `docker compose --profile loadtest config` válido, gateway/test.sh 11/11 pass

#### Paso 5b — Refinamiento scenarios `[CLAUDE CODE]` ✅

- [x] `scenario_2` refactor con SHARED_POLICY_IDS pre-test
- [x] `scenario_3` docstring con pre-requisito `make load-test-seed`
- [x] `scenario_5` step_users=50
- [x] ruff + py_compile OK

---

### 🔵 RONDA 5 — Ejecución a escala objetivo (completado ✅)

#### Paso 6 — Escenarios 1, 2, 4 `[OPENCODE ejecutó todos]` ✅

- [x] Escenario 1: 500 users, 5 min → resultado en `scenario_1_report.html`
- [x] Escenario 2: 300 users → setup falló (no policies created — documentado)
- [x] Escenario 4: spike 0→1000 → resultado en `scenario_4_report.html`
- [x] Métricas capturadas: docker stats, pg connections (Kafka consumers no corriendo)

#### Paso 6b — Escenarios 3, 5 + redacción `[OPENCODE]` ✅

- [x] `make load-test-seed` → 10k AuditEvents creados en <2s
- [x] Escenario 3: 1000 users, 5 min → `scenario_3_report.html`
- [x] Escenario 5: stress → quiebre a 50 usuarios
- [x] `load-testing-results.md` redactado con tabla resumen, bottlenecks, comparación TicketMaster
- [x] **Hallazgo**: Django `runserver` (single-threaded) no escala más de 50 usuarios. Todos los escenarios fallan por esto, no por Django/DB.

---

### 🔵 RONDA 6 — Restauración + cierre `[OPENCODE]` ✅

- [x] `make dev` funciona con gateway normal (profile default, rate limits reales)
- [x] `bash gateway/test.sh` → **11/11 tests pass**
- [x] CONTEXT.md §2 actualizado (Última tarea + Próximo paso)
- [x] CONTEXT.md §4: Fase 6 → ✅ Completado

### ⚠️ Pendiente post-Fase 6

Los resultados actuales reflejan Gunicorn (4w gthread). El bottleneck principal es `select_for_update()` en `generate_policy_number()` (policy-service/models.py:28) que serializa writes. Reads funcionan bien (create_customer p95=790ms @50 users). Pendiente:
- Reemplazar `select_for_update()` por `uuid.uuid4()` o PostgreSQL sequence en `generate_policy_number()`
- Aumentar Daphne workers en audit-service
- Re-ejecutar suite para verificar targets de PHASES.md

---

### Criterios de éxito Fase 6 (validar antes de cerrar)

| Criterio | Cómo validar |
|---|---|
| Rate limit no es el bottleneck | Error rate por 429 < 5% en scenarios 1/2/3 |
| Targets PHASES.md cumplidos o documentados con razón | Tabla resumen del results.md |
| Bottleneck real identificado | Sección "Bottlenecks identificados" con evidencia |
| Inter-service medido | p95 de `/api/claims/claims/` (que incluye verify) en results.md |
| Stress test produce un breaking point real | Number `N` de users en scenario 5 |
| Stack normal sigue funcionando tras los tests | `make dev` + `bash gateway/test.sh` 11/11 |
| Audit seed reproducible | `make load-test-seed` idempotente |

---

### Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| `nginx.loadtest.conf` divergerá de `nginx.conf` con el tiempo | Solo cambian dos líneas; documentar en comentario al inicio del archivo: "Si añadís directivas a nginx.conf, añadilas también acá" |
| Olvidar restaurar gateway normal | Profile `loadtest` aísla el container; `make dev` no toca el override; Paso 6 verificación obligatoria |
| Seed audit lentísimo | `bulk_create(batch_size=1000)` |
| Tests de 5 min × 5 scenarios = 25 min | Aceptable; correr en orden secuencial |
| OpenCode no puede correr scenarios mientras Claude Code corre los suyos | Convenir orden: Claude Code 1→2→4, después OpenCode 3→5 (secuencial entre agentes) |

---

### División de archivos — actualización para Ronda 4-6

| Área | Agente |
|---|---|
| `gateway/nginx.loadtest.conf` (nuevo) | **OpenCode** |
| `infra/docker-compose.yml` (servicio `gateway-loadtest`, profile `default` al gateway original) | **OpenCode** |
| `audit-service/apps/audit/management/commands/seed_audit_events.py` (nuevo) | **OpenCode** |
| `Makefile` (target `load-test-seed`, ajuste `--host=http://gateway-loadtest` en otros targets) | **OpenCode** |
| `infra/grafana/dashboards/load-testing.json` (paneles adicionales) | **OpenCode** |
| `infra/load-testing/scenario_2_claims_filing.py` (refactor setup global) | **Claude Code** |
| `infra/load-testing/scenario_3_audit_read.py` (docstring deps) | **Claude Code** |
| `infra/load-testing/scenario_5_stress.py` (step_users=50) | **Claude Code** |
| `infra/load-testing/results/screenshots/` | **OpenCode** |
| `infra/load-testing/results/scenario_N_*.txt` (docker stats, kafka lag, pg conns) | Cada agente captura los suyos |
| `load-testing-results.md` (raíz) | **OpenCode** redacta con números de ambos |
| `infra/README.md` (sección load testing actualizada) | **OpenCode** |

</details>

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
| 6 | Load Testing | ✅ Completado |
| 6.5 | Resilience Hardening | ✅ Completado |
| 7 | Frontend Dashboard | ⏳ Próxima |

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
- ✅ Load Testing: escenarios 1-5 en `infra/load-testing/`, auth_helper con JWT compartido, gateway-loadtest (rate limit 10000r/m, profile loadtest), seed_audit_events (10k eventos), dashboard Load Testing (12 paneles), Makefile targets (load-test-1 al 5, load-test-seed, load-test-ui), `load-testing-results.md` con diagnóstico de bottlenecks
- ✅ Servicios migrados a Gunicorn 4w gthread en docker-compose (policy, claims, notification). audit-service en Daphne.
- ✅ Resilience Hardening (Fase 6.5): Circuit Breaker en `claims → policy` (pybreaker, 5 fail / 30s reset, 4xx excluidos), Outbox Pattern en policy + claims (apps/outbox/, relay command con `select_for_update(skip_locked=True)`, 2 containers `*-outbox-relay`), métricas Prometheus + alertas Grafana (CB open, outbox pending, outbox failed), tests: rollback, concurrencia con threads, fault tolerance Kafka stop/start.
- ✅ Hotfix `generate_policy_number()`: PostgreSQL `SEQUENCE` (`nextval()`) reemplaza el `select_for_update()` que serializaba writes. Migración 0002, fallback SQLite preservado para tests. Elimina el bottleneck identificado en Fase 6 que limitaba writes de Policy a ~50 usuarios concurrentes.

---

<a id="s6"></a>
## 6. Decisiones tomadas recientemente

- **Fase 6.5 añadida al roadmap** — entre Fase 6 y Fase 7 se intercala una fase de resilience hardening (1 día) para aplicar Outbox Pattern + Circuit Breaker. Razón: el load testing reveló bottleneck real en `select_for_update()` (Policy writes) y dos gaps de resiliencia clásicos (dual-write DB↔Kafka, sin circuit breaker en HTTP inter-service). Plan completo en `docs/PHASE_6_5_HARDENING.md`.
- **DLQ descartado** — inicialmente planeado como tercer patrón en Fase 6.5, descartado por baja relación impacto/esfuerzo. Los consumers ya manejan duplicados via `IntegrityError`. Mantenemos solo Outbox + Circuit Breaker.
- **Gunicorn 4w gthread en docker-compose** — reemplaza `manage.py runserver` (single-threaded) para los 4 servicios. Concurrency real para load testing.
- **`select_for_update()` bottleneck** — identificado en `generate_policy_number()` (policy-service/models.py:28). Serializa todos los writes de Policy. create_customer (sin lock) procesa 0% errores; create_policy (con lock) falla 100% a >50 usuarios.
- **gateway-loadtest** — servicio separado con profile `loadtest`, rate limit 10000r/m, puerto 8081. No interfiere con el gateway normal (8080, 200r/m, profile default).

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

### Agentes activos — Fase 6.5

| Agente | Rol | Tareas asignadas |
|---|---|---|
| **Claude Code** | Bloque A (autor) + Docs + Audit final | Escribe código del Circuit Breaker. Redacta docs del Bloque C con números de OpenCode. Audit final del diff completo. Coordina cierre de fase. |
| **OpenCode** | Bloque B (autor+ejecutor) + Ejecución | Escribe y ejecuta Outbox Pattern completo. Ejecuta tests de Bloque A. Corre load tests del Bloque C. |

### División de archivos — Fase 6.5

| Área | Agente |
|---|---|
| `claims-service/apps/claims/clients.py` | **Claude Code** |
| `claims-service/apps/claims/tests/test_clients.py` | **Claude Code** |
| `claims-service/apps/core/metrics.py` (sección CB) | **Claude Code** |
| `claims-service/pyproject.toml` (`uv add pybreaker`) | **OpenCode** (ejecución) |
| `infra/grafana/dashboards/services.json` (panel breaker) | **Claude Code** |
| `infra/grafana/alert-rules.yml` (alerta CB) | **Claude Code** |
| `policy-service/apps/outbox/` (nuevo) | **OpenCode** |
| `claims-service/apps/outbox/` (nuevo) | **OpenCode** |
| `policy-service/apps/policies/events.py` (refactor a Builder) | **OpenCode** |
| `policy-service/apps/policies/services.py` (cambios `emit_*`) | **OpenCode** |
| `claims-service/apps/claims/events.py` (refactor a Builder) | **OpenCode** |
| `claims-service/apps/claims/services.py` (cambios `emit_*`) | **OpenCode** |
| `claims-service/apps/core/metrics.py` (sección outbox) | **OpenCode** |
| `policy-service/apps/core/metrics.py` (sección outbox) | **OpenCode** |
| `infra/docker-compose.yml` (2 containers relay nuevos) | **OpenCode** |
| `infra/grafana/dashboards/outbox.json` (panel outbox nuevo) | **OpenCode** |
| `infra/grafana/alert-rules.yml` (alertas outbox) | **OpenCode** |
| `load-testing-results.md` (sección retest) | **Claude Code** (con números de OpenCode) |
| `docs/TECHNICAL_DECISIONS.md` (2 secciones nuevas) | **Claude Code** |
| `README.md` raíz (mención de patrones) | **Claude Code** |
| `CONTEXT.md` (cierre de fase) | **Claude Code** |

### Cómo deben trabajar — flujo Fase 6.5

1. **Ambos leen `docs/PHASE_6_5_HARDENING.md` completo** antes de empezar.
2. **Inicio paralelo — sin dependencias entre bloques**:
   - **Claude Code** escribe Bloque A (Circuit Breaker): `clients.py`, `metrics.py` sección CB, `services.json`, `alert-rules.yml` alerta CB, tests.
   - **OpenCode** escribe Bloque B (Outbox Pattern): `apps/outbox/` en ambos servicios, relay command, refactor `events.py`+`services.py`, docker-compose, métricas outbox, alertas outbox, tests.
3. **Sincronización**: cuando Claude Code termina Bloque A → **OpenCode ejecuta**: `uv add pybreaker`, `uv run pytest` (claims-service). Cuando OpenCode termina Bloque B → **OpenCode ejecuta**: `makemigrations && migrate`, `uv run pytest` (policy + claims), docker compose up relays, fault tolerance test.
4. **Bloque C — solo después de que ambos bloques tienen tests en verde**:
   - **OpenCode** corre `make load-test SCENARIO=1/2/5` + `bash gateway/test.sh` → pasa los números a Claude Code.
   - **Claude Code** redacta `load-testing-results.md`, `TECHNICAL_DECISIONS.md`, `README.md`.
5. **Audit final**: Claude Code revisa diff completo — anti-patrones, criterios de aceptación.
6. **Claude Code** actualiza `CONTEXT.md` §4 y §2, avisa al usuario para commits.

### Punto de conflicto controlado — `claims-service/apps/core/metrics.py`

Claude Code escribe la sección CB al principio del archivo. OpenCode añade la sección outbox al final. Merge limpio garantizado (variables distintas, sin overlap de líneas).

### Anti-patrones a evitar (reportar como `[FOUND]` si se encuentran)

- `produce_*` calls fuera de `transaction.atomic()` después del refactor
- Tests viejos con mocks de `PolicyEventProducer` no adaptados
- Background `flush()` del Producer fuera del bloque de transacción del relay
- Excepciones de pybreaker no convertidas a `PolicyServiceUnavailableError` (filtraría tipo interno hacia el viewset)

### División de archivos — quién toca qué

| Área | Agente |
|---|---|
| `infra/load-testing/__init__.py` | **Claude Code** |
| `infra/load-testing/auth_helper.py` | **Claude Code** |
| `infra/load-testing/locustfile.py` | **Claude Code** |
| `infra/load-testing/scenario_1_policy_creation.py` | **Claude Code** |
| `infra/load-testing/scenario_2_claims_filing.py` | **Claude Code** |
| `infra/load-testing/scenario_4_spike.py` | **Claude Code** |
| `infra/load-testing/scenario_5_stress.py` | **Claude Code** |
| `infra/load-testing/scenario_3_audit_read.py` | **OpenCode** |
| `infra/load-testing/README.md` | **OpenCode** |
| `infra/load-testing/.gitignore` | **OpenCode** |
| `infra/load-testing/results/` (HTML reports + screenshots) | **OpenCode** crea, ambos ejecutan según paso 4/4b |
| `infra/docker-compose.yml` (servicio `locust` con profile `loadtest`) | **OpenCode** |
| `infra/grafana/dashboards/load-testing.json` | **OpenCode** |
| `infra/README.md` (sección Load Testing) | **OpenCode** |
| `Makefile` (targets `load-test`, `load-test-ui`) | **OpenCode** |
| `load-testing-results.md` (raíz) | **OpenCode** redacta, **Claude Code** entrega métricas de scenarios 1/2/4 |

### Cómo deben trabajar — flujo concreto Fase 6

1. **Inicio paralelo**: ambos agentes empiezan Ronda 1 al mismo tiempo, sin dependencias cruzadas.
   - Claude Code crea el directorio `infra/load-testing/` con base + scenarios 1+2.
   - OpenCode añade el servicio `locust` (profile `loadtest`) + Makefile + scenario 3 (read-only, no necesita la base de Claude porque puede definir su propia subclass de `HttpUser` standalone).
2. **Sincronización tras Ronda 1**: cuando ambos marcan sus pasos `[x]`, cualquiera puede arrancar Ronda 2 sin esperar al usuario. Si uno termina antes, avisa al usuario (regla del protocolo).
3. **Ronda 2 también paralela**: Claude Code escribe scenarios 4+5 (heredan del scenario_1 de Ronda 1, por eso van en R2). OpenCode crea el dashboard `load-testing.json` y la sección de README.
4. **Ronda 3 — orden estricto**:
   - Primero AUDIT cada agente sobre sus archivos (paso 3 / 3b).
   - Luego ejecución (paso 4 / 4b). **OpenCode no puede redactar `load-testing-results.md` hasta que Claude Code le pase los números de scenarios 1/2/4.** Claude Code los deja en una sub-sección al final de su paso 4 (raw stats: RPS, p50, p95, p99, fail %), OpenCode los integra en su redacción.
5. **Reglas de no-pisado**:
   - Nadie toca el archivo del otro. Si un fix obvio cruza scope (typo en docstring, import roto), corregir sin pedir permiso (regla del proyecto), pero avisar en el mensaje al usuario.
   - `infra/docker-compose.yml` lo toca solo OpenCode (añade servicio `locust`). Claude Code no lo modifica en esta fase.
   - `Makefile` lo toca solo OpenCode (añade targets de load test).
   - `infra/load-testing/results/` se crea con `.gitkeep`; los HTML quedan ignorados, los screenshots `.png` y el `*.md` se commitean.

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
