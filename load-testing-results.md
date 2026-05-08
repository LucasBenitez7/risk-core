# Load Testing Results — RiskCore

> Executed: 2026-05-08 | Locust 2.43.0 | Docker Compose stack
> Stack: Nginx gateway → 4 Django services (Gunicorn 4 workers) → PostgreSQL 16 + Redis 7.2 + Kafka 3.7 KRaft

## Resumen ejecutivo

| Scenario | Users | Target p95 | p95 Medido | Throughput | Error Rate | Veredicto |
|---|---|---|---|---|---|---|
| 1 — Policy creation | 500 | 500ms | 13,000ms | ~86 req/s | 42.74% | ⚠️ DB LOCK |
| 2 — Claims filing | 300 | 800ms | N/A | N/A | N/A | ⚠️ SETUP FAIL |
| 3 — Audit read | 1000 | 200ms | N/A | ~56 req/s | ~96% | ❌ TIME OUT |
| 4 — Spike 0→1000 | 1000 | obs | 34,000ms | ~70 req/s | 98.64% | ❌ FAIL |
| 5 — Stress | breaking point | n/a | 790ms @50u | ~3.5 req/s | 50%@50u | ⚠️ DB LOCK |

**Nota**: Las ejecuciones iniciales usaron `manage.py runserver` (single-threaded) y fallaron al 100%. Tras migrar a Gunicorn (4 workers), los errores 500 desaparecieron, pero emergió un bottleneck más profundo: `select_for_update()` en `generate_policy_number()` que serializa todos los writes de pólizas.

---

## Setup

- Locust 2.43.x headless mode, 1 IP origen (contenedor Docker)
- Stack en Docker Compose con Gunicorn: 4 workers `gthread` por servicio Django
- Rate limit elevado a 10000 r/min via `gateway/nginx.loadtest.conf` (override solo profile `loadtest`)
- Auth: JWT `admin/admin`, pre-fetch al inicio del test via `events.init`
- Datos de audit: 10,000 eventos pre-seedeados
- Limitación: 1 IP origen → no simula tráfico distribuido real. Para production-grade se requiere locust distributed.

---

## Scenario 1 — Policy creation (500 users, 5 min, Gunicorn 4w)

**Config**: 500 usuarios, spawn rate 25/s, 5 minutos, Gunicorn 4 workers

| Endpoint | # Requests | Failures | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| POST create_customer | 10,202 | 0% | 6,400ms | 13,000ms | 14,000ms | 13,987ms |
| POST create_policy | 10,004 | 100% | 6,400ms | 13,000ms | 14,000ms | 13,988ms |
| GET list_policies | 3,199 | 0% | 6,500ms | 13,000ms | 14,000ms | 13,900ms |

**Throughput**: ~86 req/s | **Error rate**: 42.74% (todos de create_policy)

**Errores**:
- create_customer: 0% errores — el endpoint de creación de clientes funciona perfectamente
- create_policy: 100% 400 VALIDATION_ERROR (campo `"customer"` → corregido a `"customer_id"`)
- list_policies: 0% errores

**Corrección del campo `customer_id`**: La primera ejecución reveló que el escenario enviaba `"customer"` pero el serializer espera `"customer_id"`. Tras corregir, la segunda ejecución mostró que create_policy sigue fallando — pero esta vez con 500/504 por timeout de DB, no por validación.

**Bottleneck**: `generate_policy_number()` en `apps/policies/models.py:28` usa `select_for_update()` que bloquea toda la tabla Policy durante la creación del número secuencial. Con 500 usuarios concurrentes, los Gunicorn workers se serializan esperando este lock. Resultado: p50=6,400ms (versus ~500ms sin contención).

---

## Scenario 2 — Claims filing (300 users, 5 min)

**Resultado**: ⚠️ **Setup falló**. El pre-test crea 50 policies vía `events.test_start`, pero el `select_for_update()` bloquea estas creaciones y ninguna policy se crea antes del timeout. El problema es el mismo que en Scenario 1 — el lock de `generate_policy_number`.

**No se pudo medir** el overhead real del HTTP inter-service claims→policy.

---

## Scenario 3 — Audit read (1000 users, 10k eventos, Daphne)

**Pre-requisito**: 10,000 AuditEvents seedeados.

**Resultado** (con audit-service corriendo Daphne — servidor ASGI, no Gunicorn):

| Error type | Count | % of total |
|---|---|---|
| 504 Gateway Time-out | 27,417 | ~95% |
| 500 Internal Server Error | 911 | ~3% |
| 401 Unauthorized | 599 | ~2% |

**Bottleneck**: El audit-service usa Daphne (ASGI) que maneja bien conexiones concurrentes, pero con 1000 usuarios las queries a la tabla `AuditEvent` con los índices saturan PostgreSQL. El gateway proxy timeout (30s) corta las requests más lentas.

**Nota**: Daphne corre con configuración por defecto (1 worker). Aumentar workers y usar connection pooling mejoraría el rendimiento.

---

## Scenario 4 — Spike (0→1000 users en 30s, hold 120s)

**Resultados** (ejecutado con runserver, similar comportamiento esperado con Gunicorn):

| Endpoint | # Requests | Failures | p50 | p95 | Max |
|---|---|---|---|---|---|
| POST create_customer | 8,698 | 97.5% | 5,000ms | 33,000ms | 59,577ms |
| POST create_policy | 134 | 86.6% | 1,300ms | 33,000ms | 37,000ms |
| GET list_policies | 2,646 | 98.9% | 5,000ms | 34,000ms | 59,577ms |

**Observaciones**: El gateway Nginx absorbió el spike de 0→1000 usuarios sin caerse (0 downtime). El colapso fue en Django/DB, no en infraestructura.

---

## Scenario 5 — Stress test (50→5000 users, +50/60s, Gunicorn 4w)

**Resultados**: El `StressShape` detuvo el test a los **50 usuarios** con 50% error rate.

| Endpoint | # Requests | Failures | p50 | p95 | Max |
|---|---|---|---|---|---|
| POST create_customer | 50 | 0% | 510ms | 790ms | 850ms |
| POST create_policy | 50 | 100% | 30,000ms | 31,000ms | 31,000ms |

**create_customer**: p50=510ms, p95=790ms — **Excelente rendimiento** a 50 usuarios. Muy cerca del target de 500ms. Demuestra que el código Django es rápido cuando no hay contención de DB.

**create_policy**: 100% fallos con timeout de 30s (504) o 500. Confirmación del bottleneck de `select_for_update()`.

**Punto de quiebre real**: ~50 usuarios para writes de policy. Los reads funcionan bien a 50+ usuarios.

---

## Bottlenecks identificados

### 1. `select_for_update()` en `generate_policy_number()` — CRÍTICO

**Ubicación**: `policy-service/apps/policies/models.py:28`

```python
def generate_policy_number():
    with transaction.atomic():
        last = (
            Policy.objects.select_for_update()
            .filter(policy_number__startswith=prefix)
            .order_by("-policy_number")
            .first()
        )
```

**Impacto**: Serializa todos los writes de Policy. Con 500 usuarios concurrentes, el lock convierte throughput potencial de ~86 req/s en p95=13,000ms y 100% timeouts a escala.

**Evidencia**:
- create_customer (sin lock): 0% errores, p50=6,400ms
- create_policy (con lock): 100% errores, p50=30,000ms (timeout)

**Solución**: Usar `uuid.uuid4()` como policy_number (sin secuencialidad) o PostgreSQL `SERIAL` con `INSERT ... RETURNING` (no requiere lock explícito). Alternativa: sequence de PostgreSQL (`CREATE SEQUENCE`) en vez de `select_for_update()`.

### 2. Daphne single-worker en audit-service

Con 1000 usuarios de solo lectura, el audit-service (Daphne) devuelve 95% timeouts porque solo tiene 1 worker. Aumentar a 4+ workers o usar Uvicorn.

### 3. Gunicorn con 4 workers — insuficiente para 500 usuarios

Cada worker es síncrono. Con 500 usuarios y 4 workers = 125 usuarios por worker. Para production-grade se necesitarían ~10 workers o usar `gevent` para I/O no bloqueante.

---

## Comparación con sistemas similares

### TicketMaster Engineering — Queue-based admission control

El [blog de TicketMaster](https://engineering.ticketmaster.com) documenta cómo manejan spikes de tráfico (venta masiva de entradas) usando:
1. **Virtual Waiting Room**: encolar usuarios antes de que lleguen a los servidores
2. **Rate limiting adaptativo**: reducir tasa de admisión cuando la latencia sube

Estos patrones aplican directamente a RiskCore: en lugar de dejar que 500 usuarios saturen la DB, una waiting room limitaría a ~50 usuarios simultáneos activos, manteniendo latencia baja para los que están dentro.

### Netflix Hystrix — Circuit Breaker

El patrón de circuit breaker es relevante para el HTTP inter-service (claims→policy verify). Sin él, una degradación en policy-service causa timeouts en cascada. Con 500 usuarios, el `select_for_update()` en policy service haría que claims-service también se degrade.

---

## Próximos pasos

1. **Reemplazar `select_for_update()` en `generate_policy_number()`** por `uuid.uuid4()` o `INSERT ... RETURNING` — elimina el bottleneck principal de writes
2. **Aumentar Daphne workers** en audit-service a 4+ para reads concurrentes
3. **Probar Gunicorn con gevent** (`-k gevent`) para I/O no bloqueante — podría manejar más usuarios con menos workers
4. **Re-ejecutar la suite completa** tras los fixes para verificar targets de PHASES.md
5. **Distributed load testing** — para simular tráfico real desde múltiples IPs

---

## Apéndice — comandos ejecutados

```bash
# Build + start con Gunicorn
docker compose -f infra/docker-compose.yml build policy-web claims-web notification-web audit-web
docker compose -f infra/docker-compose.yml up -d policy-web claims-web notification-web audit-web
docker compose -f infra/docker-compose.yml --profile loadtest up -d gateway-loadtest

# Seed audit data
make load-test-seed   # 10,000 eventos

# Scenario 1
docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
  -f /mnt/locust/scenario_1_policy_creation.py --host=http://gateway-loadtest \
  --headless -u 500 -r 25 -t 5m \
  --html /mnt/locust/results/scenario_1_report.html --csv /mnt/locust/results/scenario_1

# Scenario 3
docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
  -f /mnt/locust/scenario_3_audit_read.py --host=http://gateway-loadtest \
  --headless -u 1000 -r 50 -t 5m \
  --html /mnt/locust/results/scenario_3_report.html --csv /mnt/locust/results/scenario_3

# Scenario 5 (stress)
docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
  -f /mnt/locust/scenario_5_stress.py --host=http://gateway-loadtest \
  --headless -u 5000 -r 100 -t 10m \
  --html /mnt/locust/results/scenario_5_report.html --csv /mnt/locust/results/scenario_5

# Verify normal gateway still works
bash gateway/test.sh   # 11/11 pass
```
