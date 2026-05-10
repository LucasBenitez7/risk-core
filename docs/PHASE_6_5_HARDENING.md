# PHASE 6.5 — Resilience Hardening

> **Audiencia**: OpenCode (ejecutor principal) + Claude Code (revisor/coordinador).
> **Cuándo leer este archivo**: al iniciar la fase 6.5, después de cerrar la fase 6 (load testing) y antes de la fase 7 (frontend).
> **Rama Git**: crear `feat/phase-6-5-hardening` desde `dev` cuando la fase 6 mergee.
> **Estimado**: ~1 día.
>
> Este archivo NO reemplaza a `CONTEXT.md`. Se mantiene aparte para que OpenCode pueda seguirlo paso a paso sin que el contexto activo lo distraiga. `CONTEXT.md` solo apuntará a este archivo durante la fase.

---

## 0. Contexto y motivación

Después de la fase 6 (load testing) el sistema funciona correctamente bajo carga, pero tiene **2 fragilidades clásicas de arquitecturas event-driven** que un tech lead va a detectar inmediatamente al revisar el código:

1. **Dual-write problem** entre DB y Kafka en `policy-service` y `claims-service`.
2. **Sin circuit breaker** en la llamada `claims-service → policy-service` → bajo fallo prolongado del policy-service, los workers de claims se saturan esperando timeouts.

Estos 2 patrones son el "checklist de adultos" para sistemas event-driven en producción. Al implementarlos:

- El proyecto pasa de "demo técnica completa" a "sistema con conciencia de fallos".
- Mencionarlos en una entrevista marca diferencia inmediata vs. candidatos que solo "conocen Kafka".
- No se rompe nada de lo que ya funciona — son adiciones, no reemplazos.

**Regla absoluta**: NUNCA `git commit` ni `git push` sin permiso explícito del usuario. Aplicar el self-audit al final de cada bloque (ver §5) antes de avisar que está listo.

---

## 1. Orden de ejecución y dependencias

| Bloque | Patrón | Servicios afectados | Estimado | Commit scope |
|---|---|---|---|---|
| A | Circuit Breaker | `claims-service` | ~2h | `feat(claims)` |
| B | Outbox Pattern | `policy-service`, `claims-service`, `infra` | ~6-8h | `feat(policy)`, `feat(claims)`, `chore(infra)` |
| C | Verificación final | Todo el stack | ~1h | `docs`, `chore` |

**Razón del orden**: A es pequeño y aislado → arranca con él para warm-up y progreso visible. B es invasivo (toca producers + nuevo container por servicio) y se hace con cabeza fresca. Ambos son independientes técnicamente pero este orden optimiza el esfuerzo.

OpenCode puede hacerlos en cualquier orden — no hay dependencias técnicas entre bloques. Sí debe respetar la división por commit (commits limpios separados por scope).

---

## 2. BLOQUE A — Circuit Breaker en claims → policy

### 2.1. Objetivo

Si `policy-service` está caído o degradado durante un periodo prolongado, los workers de `claims-service` no deben saturarse esperando timeouts de 5s en cada request. Después de N fallos consecutivos el circuit breaker abre, las siguientes llamadas fallan rápido (fail-fast) sin tocar la red, y periódicamente se intenta una llamada de prueba (half-open) para detectar recovery.

### 2.2. Librería

Usar **`pybreaker`** (`pybreaker = "^1.0.2"` en `pyproject.toml` de claims-service con `uv add pybreaker`).

Razón: es la implementación estándar de Python, es síncrona (compatible con httpx sync), tiene listeners para emitir métricas, y no introduce gevent/asyncio mismatches con el resto del stack.

### 2.3. Implementación

**Archivos a tocar**:

- `claims-service/pyproject.toml` (dependencia nueva via `uv add`)
- `claims-service/apps/claims/clients.py` (refactor)
- `claims-service/apps/core/metrics.py` (métricas nuevas)
- `claims-service/apps/claims/tests/test_clients.py` (tests nuevos o ampliar existente)

**Configuración del breaker** (en `clients.py`):

```python
import pybreaker

class _BreakerMetrics(pybreaker.CircuitBreakerListener):
    """Emite métricas Prometheus en cada cambio de estado del breaker."""
    def state_change(self, cb, old_state, new_state):
        circuit_breaker_state.labels(target="policy-service").set(
            {"closed": 0, "open": 1, "half-open": 2}[new_state.name]
        )
        circuit_breaker_state_changes_total.labels(
            target="policy-service",
            from_state=old_state.name,
            to_state=new_state.name,
        ).inc()


_policy_breaker = pybreaker.CircuitBreaker(
    fail_max=5,        # 5 fallos consecutivos abren el circuito
    reset_timeout=30,  # tras 30s en open, va a half-open
    exclude=[_ClientBusinessError],  # ver §2.4 — los 4xx no cuentan como fallo
    listeners=[_BreakerMetrics()],
)
```

### 2.4. Sutileza crítica — 4xx vs 5xx

El HTTP 404 ("póliza no existe") es un error de cliente, NO un fallo de infra. Pero `response.raise_for_status()` lo convierte en `HTTPStatusError`, que pybreaker contaría como fallo — bug latente: 5 usuarios con UUIDs inválidos abren el circuito para todos.

**Solución**: definir una excepción interna para 4xx que pybreaker excluye:

```python
class _ClientBusinessError(Exception):
    """Errores 4xx — no son fallos de infra, no cuentan para el breaker."""
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self.data = data
```

**Refactor del client** — separar la llamada HTTP cruda (que el breaker envuelve) del parsing y la lógica de negocio:

```python
class PolicyServiceClient:
    def __init__(self):
        self.base_url = settings.POLICY_SERVICE_URL.rstrip("/")
        self.timeout = settings.POLICY_SERVICE_TIMEOUT

    @_policy_breaker
    def _http_verify(self, policy_id: str) -> dict:
        """Llamada HTTP cruda. El breaker envuelve esto.
        Lanza _ClientBusinessError para 4xx (excluidos del breaker),
        httpx.* para errores de red (cuentan como fallo), o
        pybreaker.CircuitBreakerError si el circuito está abierto."""
        url = f"{self.base_url}/api/policies/policies/{policy_id}/verify/"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    raise _ClientBusinessError(
                        e.response.status_code, e.response.json()
                    ) from e
                raise  # 5xx → sí cuenta como fallo para el breaker
            return response.json()

    def verify_policy(self, policy_id: str) -> dict:
        try:
            data = self._http_verify(policy_id)
        except pybreaker.CircuitBreakerError:
            logger.warning("policy_circuit_open", policy_id=str(policy_id))
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None
        except _ClientBusinessError as e:
            if e.status_code == 404:
                raise PolicyInactiveError(
                    policy_id=policy_id, policy_status="NOT_FOUND"
                ) from None
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
            raise PolicyServiceUnavailableError(policy_id=policy_id) from None

        if not data.get("is_valid"):
            raise PolicyInactiveError(
                policy_id=policy_id, policy_status=data.get("status")
            )
        logger.info("policy_verified", policy_id=str(policy_id))
        return data
```

### 2.5. Métricas nuevas

Añadir a `claims-service/apps/core/metrics.py`:

```python
from prometheus_client import Counter, Gauge

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Estado del circuit breaker (0=closed, 1=open, 2=half-open)",
    ["target"],
)
circuit_breaker_state_changes_total = Counter(
    "circuit_breaker_state_changes_total",
    "Cambios de estado del circuit breaker",
    ["target", "from_state", "to_state"],
)
```

Añadir panel en `infra/grafana/dashboards/services.json`: "Circuit Breaker State — policy-service" con `circuit_breaker_state{target="policy-service"}` (valor 0/1/2).

Añadir alerta en `infra/grafana/alert-rules.yml`:
```yaml
- alert: PolicyCircuitBreakerOpen
  expr: circuit_breaker_state{target="policy-service"} == 1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Circuit breaker policy-service OPEN"
    description: "Claims-service no puede contactar a policy-service desde hace 2+ minutos."
```

### 2.6. Tests

`claims-service/apps/claims/tests/test_clients.py` — ampliar con:

- Mock `httpx.Client.get` para devolver 500 cinco veces consecutivas → al sexto intento, `PolicyServiceUnavailableError` se lanza **inmediatamente** sin tocar la red (verificar que el mock fue llamado solo 5 veces, no 6).
- Mock 404 cinco veces → circuit sigue cerrado (porque `_ClientBusinessError` está excluido) → `PolicyInactiveError` en cada llamada.
- Mock 200 OK con `is_valid=false` → circuit sigue cerrado → `PolicyInactiveError`.
- Para no esperar 30s reales: instanciar `PolicyServiceClient` con un breaker de test con `reset_timeout=0.01`.

### 2.7. Self-audit del bloque A

- [ ] `uv lock` actualizado en claims-service (pybreaker en las deps).
- [ ] Ruff + format limpios.
- [ ] Tests nuevos pasan.
- [ ] Verificación manual:
  ```bash
  docker compose stop policy-web
  # Hacer 6 requests a POST /api/claims/claims/ con un policy_id válido
  # → primeras 5: 503 (timeout real de 5s cada una)
  # → sexta: 503 INMEDIATA (sin esperar timeout) — confirmar en logs "policy_circuit_open"
  docker compose start policy-web
  # Esperar 30s, próxima request funciona
  ```
- [ ] Grafana muestra el cambio de estado del breaker.

---

## 3. BLOQUE B — Outbox Pattern (policy-service + claims-service)

### 3.1. Objetivo

Eliminar el **dual-write** entre DB y Kafka. El problema actual en `policy-service/apps/policies/services.py`:

```python
with transaction.atomic():
    policy = Policy.objects.create(...)
# transacción ya commiteada ↑
_get_producer().produce_policy_created(policy)  # ← si el proceso muere aquí, evento perdido para siempre
```

Con outbox, la intención de publicar se guarda **dentro de la misma transacción**:

```python
with transaction.atomic():
    policy = Policy.objects.create(...)
    OutboxEvent.objects.create(topic="policy.created", payload=...)
# Un proceso separado (relay) lee la tabla y publica a Kafka
```

**Garantía**: at-least-once delivery. Los consumers ya manejan duplicados via `IntegrityError` (en audit) — no se necesita trabajo extra en ellos.

### 3.2. Modelo OutboxEvent

Crear `apps/outbox/` en **ambos** servicios (policy-service y claims-service) como app Django propia:

```
policy-service/apps/outbox/__init__.py
policy-service/apps/outbox/apps.py
policy-service/apps/outbox/models.py
policy-service/apps/outbox/management/__init__.py
policy-service/apps/outbox/management/commands/__init__.py
policy-service/apps/outbox/management/commands/run_outbox_relay.py
policy-service/apps/outbox/migrations/
```

Añadir `"apps.outbox"` a `INSTALLED_APPS` en `config/settings/base.py` de cada servicio.

**Modelo** (idéntico en ambos servicios, solo cambia `service` hardcodeado):

```python
# apps/outbox/models.py
import uuid
from django.db import models


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        PUBLISHED = "PUBLISHED"
        FAILED = "FAILED"  # tras MAX_ATTEMPTS retries — investigar manualmente

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aggregate_type = models.CharField(max_length=50)   # "policy" | "claim"
    aggregate_id = models.UUIDField()
    event_type = models.CharField(max_length=100)      # "policy.created"
    topic = models.CharField(max_length=100)           # topic Kafka destino
    key = models.CharField(max_length=100, blank=True) # Kafka key (default: aggregate_id)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempts = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            # Índice parcial: Postgres solo indexa los PENDING → escala a millones de eventos publicados
            models.Index(
                fields=["status", "created_at"],
                name="outbox_pending_idx",
                condition=models.Q(status="PENDING"),
            ),
        ]
        ordering = ["created_at"]
```

**Notas**:
- No borrar registros `PUBLISHED` automáticamente → audit trail. Un comando `prune_outbox --older-than 30d` puede añadirse después si la tabla crece.
- El índice parcial (`condition=Q(status="PENDING")`) mantiene el índice pequeño aunque la tabla tenga millones de filas publicadas.

### 3.3. Worker relay

```python
# apps/outbox/management/commands/run_outbox_relay.py
import json
import time

import structlog
from confluent_kafka import Producer
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.outbox.models import OutboxEvent

logger = structlog.get_logger()

BATCH_SIZE = 100
POLL_INTERVAL = 0.5  # segundos cuando no hay eventos pendientes
MAX_ATTEMPTS = 10


class Command(BaseCommand):
    help = "Outbox relay: publica OutboxEvents PENDING a Kafka."

    def handle(self, *args, **opts):
        producer = Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
        logger.info("outbox_relay_started")
        try:
            while True:
                published = self._process_batch(producer)
                if published == 0:
                    time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("outbox_relay_stopped")
            producer.flush(10)

    def _process_batch(self, producer) -> int:
        # select_for_update(skip_locked=True) → soporta múltiples relays sin pisarse
        with transaction.atomic():
            events = list(
                OutboxEvent.objects
                .select_for_update(skip_locked=True)
                .filter(status=OutboxEvent.Status.PENDING)
                .order_by("created_at")[:BATCH_SIZE]
            )
            if not events:
                return 0

            published_count = 0
            for event in events:
                try:
                    producer.produce(
                        topic=event.topic,
                        value=json.dumps(event.payload).encode("utf-8"),
                        key=(event.key or str(event.aggregate_id)).encode("utf-8"),
                    )
                    event.status = OutboxEvent.Status.PUBLISHED
                    event.published_at = timezone.now()
                    published_count += 1
                except Exception as e:
                    event.attempts += 1
                    event.last_error = str(e)[:1000]
                    if event.attempts >= MAX_ATTEMPTS:
                        event.status = OutboxEvent.Status.FAILED
                    logger.error(
                        "outbox_publish_failed",
                        event_id=str(event.id),
                        attempts=event.attempts,
                        error=str(e),
                    )
                event.save(
                    update_fields=["status", "published_at", "attempts", "last_error"]
                )

            # flush DENTRO de la transacción — garantiza que los eventos llegan
            # al broker ANTES de marcar published_at en DB
            producer.flush(5)
            return published_count
```

### 3.4. Refactor de productores en services.py

`PolicyEventProducer` (en `events.py`) deja de hablar con Kafka directamente. Se convierte en `PolicyEventBuilder` — solo construye payloads. Se añade `emit_policy_event()` que escribe al outbox.

**`policy-service/apps/policies/events.py`** — refactor completo:

```python
# apps/policies/events.py
from apps.outbox.models import OutboxEvent
from apps.policies.models import Policy


class PolicyEventBuilder:
    """Construye payloads de eventos. NO publica a Kafka — eso lo hace el relay."""

    @staticmethod
    def _base(event_type: str, policy: Policy) -> dict:
        import uuid
        from django.utils import timezone
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "occurred_at": timezone.now().isoformat(),
            "service": "policy-service",
            "data": {
                "policy_id": str(policy.id),
                "policy_number": policy.policy_number,
                "customer_id": str(policy.customer_id),
                "policy_type": policy.policy_type,
                "status": policy.status,
                "premium_amount": str(policy.premium_amount),
                "start_date": policy.start_date.isoformat() if policy.start_date else None,
                "end_date": policy.end_date.isoformat() if policy.end_date else None,
            },
        }

    @classmethod
    def build_created(cls, policy: Policy) -> dict:
        return cls._base("policy.created", policy)

    @classmethod
    def build_updated(cls, policy: Policy) -> dict:
        return cls._base("policy.updated", policy)

    @classmethod
    def build_cancelled(cls, policy: Policy) -> dict:
        payload = cls._base("policy.cancelled", policy)
        payload["data"]["cancellation_reason"] = policy.cancellation_reason
        return payload


def emit_policy_event(policy: Policy, event_type: str, payload: dict) -> None:
    """Crea un OutboxEvent. DEBE llamarse dentro de transaction.atomic()."""
    OutboxEvent.objects.create(
        aggregate_type="policy",
        aggregate_id=policy.id,
        event_type=event_type,
        topic=event_type,  # convención: topic == event_type
        key=str(policy.id),
        payload=payload,
    )
```

**`policy-service/apps/policies/services.py`** — cambios en los 3 métodos que producen eventos:

```python
# create_policy — antes:
with transaction.atomic():
    policy = Policy.objects.create(...)
_get_producer().produce_policy_created(policy)  # ← eliminar

# create_policy — después:
with transaction.atomic():
    policy = Policy.objects.create(...)
    emit_policy_event(policy, "policy.created", PolicyEventBuilder.build_created(policy))
```

Repetir el mismo patrón para `cancel_policy` y `update_policy`. Eliminar `_get_producer()` y la referencia a `PolicyEventProducer`.

**Claims-service**: hacer lo mismo para `ClaimEventProducer` → `ClaimEventBuilder` + `emit_claim_event()`. Inspeccionar `claims-service/apps/claims/events.py` y `services.py` y aplicar el mismo patrón.

### 3.5. Docker Compose — relay containers

Añadir 2 servicios a `infra/docker-compose.yml`:

```yaml
policy-outbox-relay:
  build:
    context: ../policy-service
  command: ["uv", "run", "python", "manage.py", "run_outbox_relay"]
  env_file: ../policy-service/.env
  environment:
    DJANGO_SETTINGS_MODULE: config.settings.development
  depends_on:
    postgres:
      condition: service_healthy
    kafka:
      condition: service_healthy
  networks: [riskcore]
  restart: unless-stopped

claims-outbox-relay:
  build:
    context: ../claims-service
  command: ["uv", "run", "python", "manage.py", "run_outbox_relay"]
  env_file: ../claims-service/.env
  environment:
    DJANGO_SETTINGS_MODULE: config.settings.development
  depends_on:
    postgres:
      condition: service_healthy
    kafka:
      condition: service_healthy
  networks: [riskcore]
  restart: unless-stopped
```

Estos containers NO usan el profile `loadtest` — deben correr siempre con `make dev`.

### 3.6. Migraciones

En cada servicio:
```bash
uv run python manage.py makemigrations outbox
uv run python manage.py migrate
```

Verificar que la migración crea la tabla con el índice parcial correcto (`outbox_pending_idx`).

### 3.7. Métricas

Añadir a `apps/core/metrics.py` de cada servicio (policy + claims):

```python
from prometheus_client import Counter, Gauge, Histogram

outbox_pending = Gauge("outbox_pending_total", "Eventos en outbox pendientes de publicar")
outbox_published_total = Counter(
    "outbox_published_total", "Eventos publicados desde outbox", ["topic"]
)
outbox_failed_total = Counter(
    "outbox_failed_total", "Eventos outbox marcados FAILED tras max retries", ["topic"]
)
outbox_lag_seconds = Histogram(
    "outbox_lag_seconds",
    "Latencia entre creación del OutboxEvent y publicación a Kafka",
    buckets=[0.05, 0.1, 0.5, 1, 5, 30, 120],
)
```

El relay actualiza `outbox_lag_seconds` con `(published_at - created_at).total_seconds()` al publicar cada evento.

**Alertas** en `infra/grafana/alert-rules.yml`:

```yaml
- alert: OutboxPendingHigh
  expr: outbox_pending_total > 1000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Outbox acumulando eventos — relay posiblemente caído"

- alert: OutboxEventFailed
  expr: increase(outbox_failed_total[10m]) > 0
  for: 0m
  labels:
    severity: critical
  annotations:
    summary: "Evento outbox marcado FAILED — investigar manualmente"
```

### 3.8. Tests

`apps/outbox/tests/test_relay.py` (nuevo en cada servicio):

- Crear póliza → `OutboxEvent` con status PENDING existe en DB con payload correcto.
- **Prueba clave — rollback**: dentro de `transaction.atomic()`, crear póliza + outbox event, luego forzar rollback → **NO debe existir ningún OutboxEvent** en DB (esta es la garantía principal del patrón).
- `Command()._process_batch(mock_producer)` → evento pasa a PUBLISHED, `mock_producer.produce` llamado con topic/key/value correctos.
- Mock `producer.produce` que lanza excepción → `attempts` incrementado, `last_error` set, status sigue PENDING.
- 10 fallos consecutivos → status = FAILED.
- **Concurrencia**: simular 2 relays con threads sobre la misma DB → mismo evento NO se publica dos veces (gracias a `select_for_update(skip_locked=True)`).

`apps/policies/tests/test_services.py` — adaptar tests existentes:

- Los mocks de `PolicyEventProducer` ya no son necesarios.
- Reemplazar verificación `producer.produce.called` por `OutboxEvent.objects.filter(event_type="policy.created").count() == 1`.

### 3.9. Self-audit del bloque B

- [ ] Migraciones aplicadas en local: `uv run python manage.py migrate` en policy y claims.
- [ ] `make dev` levanta los 2 nuevos containers relay. `docker logs policy-outbox-relay` muestra `outbox_relay_started`.
- [ ] Ruff + format limpios en todos los archivos tocados.
- [ ] Tests pasan: `uv run pytest` en policy-service y claims-service.
- [ ] Tests viejos de Kafka producer adaptados (no fallan buscando el mock viejo).
- [ ] Verificación manual end-to-end:
  ```bash
  # Crear póliza via gateway
  curl -X POST http://localhost:8080/api/policies/customers/ ...
  curl -X POST http://localhost:8080/api/policies/policies/ ...

  # Verificar OutboxEvent en DB → status PUBLISHED, published_at != NULL
  docker exec postgres psql -U riskcore -d policy_db -c \
    "SELECT event_type, status, published_at,
            EXTRACT(EPOCH FROM (published_at - created_at)) AS lag_seconds
     FROM outbox_outboxevent ORDER BY created_at DESC LIMIT 5;"

  # Verificar que el evento llegó a Kafka
  docker exec kafka kafka-console-consumer.sh --topic policy.created \
    --bootstrap-server localhost:9092 --from-beginning --max-messages 1
  ```
- [ ] **Test de fault tolerance** (el más importante — demuestra el punto del patrón):
  ```bash
  docker compose stop kafka

  # Crear póliza → debe responder 201 OK inmediatamente
  curl -X POST http://localhost:8080/api/policies/policies/ ...
  # Confirmar que la API respondió rápido (no esperó a Kafka)

  # Verificar OutboxEvent en DB como PENDING (Kafka caído)
  docker exec postgres psql ... -c "SELECT status FROM outbox_outboxevent ORDER BY created_at DESC LIMIT 1;"

  docker compose start kafka
  # Esperar ~1s (POLL_INTERVAL del relay)
  # Verificar que el evento pasó a PUBLISHED
  docker exec postgres psql ... -c "SELECT status FROM outbox_outboxevent ORDER BY created_at DESC LIMIT 1;"
  ```
- [ ] Audit-service recibió el evento (flujo end-to-end completo).

---

## 4. BLOQUE C — Verificación final y documentación

### 4.1. Re-correr load testing

El Outbox Pattern añade una tabla extra al INSERT path → los resultados de escenarios 1 y 2 pueden cambiar ligeramente (+5-15ms en p95). Re-correr:

- Escenario 1 (policy creation, 500 users, 5 min)
- Escenario 2 (claims filing, 300 users, 5 min)
- Escenario 5 (stress test — el circuit breaker puede cambiar el breaking point si claims abre el breaker bajo carga extrema)

Escenarios 3 y 4 no necesitan re-correrse (audit read y spike no tocan outbox ni circuit breaker en happy path).

Actualizar `load-testing-results.md` con:
- Sección nueva "Phase 6.5 — Hardening retest" con números actualizados.
- Nota sobre las garantías de delivery: "antes: at-most-once con dual-write risk; ahora: at-least-once con outbox + idempotent consumer".

### 4.2. Documentación

Actualizar `docs/TECHNICAL_DECISIONS.md` con 2 secciones nuevas:

**Outbox Pattern** — qué problema resuelve (dual-write), tradeoff (latencia +~5ms por el INSERT extra), por qué no Debezium/CDC (overkill para un monorepo dockerizado), garantía de at-least-once.

**Circuit Breaker** — librería elegida (pybreaker vs alternativas), thresholds (5 fallos, 30s reset), por qué excluimos 4xx del conteo de fallos.

Actualizar `README.md` raíz con párrafo en la sección de arquitectura mencionando los 2 patrones.

### 4.3. Self-audit final

- [ ] `bash gateway/test.sh` → 11/11 pass (ninguna regresión).
- [ ] `make dev` levanta el stack completo incluyendo los 2 relays.
- [ ] Escenarios 1, 2, 5 re-corridos y `load-testing-results.md` actualizado.
- [ ] `docs/TECHNICAL_DECISIONS.md` tiene las 2 secciones nuevas.
- [ ] Todos los tests de policy-service y claims-service pasan.
- [ ] Avisar al usuario para crear PR.

---

## 5. Self-audit común (aplicar al final de cada bloque)

- [ ] Lógica de negocio sigue en `services.py`, no en `views.py` ni `models.py`.
- [ ] Importaciones de Kafka usan **`confluent-kafka`**, no `kafka-python`. Si OpenCode encuentra `kafka-python` en `pyproject.toml`, es un bug previo — corregir y mencionarlo.
- [ ] Dependency management con **`uv`** — `uv add <pkg>`, NO editar `pyproject.toml` a mano + `pip install`.
- [ ] Lint/format con **`Ruff`** — `uv run ruff check . && uv run ruff format .` limpio.
- [ ] Type checking: `uv run mypy .` — errores nuevos NO suben respecto al baseline.
- [ ] Tests nuevos cubren el patrón añadido.
- [ ] No hay `print()`, `pdb`, `breakpoint()`, ni TODOs sin issue.
- [ ] No hay secretos hardcodeados.
- [ ] Commits NO creados todavía — esperar al usuario.
- [ ] **Si OpenCode encontró un bug ajeno al bloque actual**: reportarlo al final del bloque con `[FOUND] <descripción>`, NO arreglarlo en ese commit. Anotarlo en `CONTEXT.md §7`.

---

## 6. Autoridad de OpenCode durante esta fase

**Puede decidir solo**:
- Nombres internos de variables, archivos auxiliares, helpers privados.
- Tests adicionales más allá de los listados (si detecta gaps).
- Reorganizar imports en archivos que ya está modificando.

**NO puede hacer sin consultar al usuario**:
- Commits o pushes (regla absoluta del proyecto).
- Cambiar decisiones de diseño fijadas aquí (librería pybreaker, schema de OutboxEvent, thresholds del breaker). Si algo le parece equivocado, debe parar, escribirlo en `CONTEXT.md §7` y esperar respuesta.
- Tocar archivos fuera del scope del bloque actual.
- Saltarse el self-audit.

---

## 7. Plan de cierre

Cuando los 3 bloques están en verde y el self-audit final pasa:

1. OpenCode avisa al usuario con resumen: N tests nuevos, X métricas nuevas, Y dashboards actualizados.
2. Usuario revisa diff: `git diff dev...feat/phase-6-5-hardening`.
3. Usuario aprueba commits — OpenCode los crea agrupados por scope:
   - `feat(claims): add circuit breaker for policy-service calls with pybreaker`
   - `feat(policy): implement outbox pattern for at-least-once Kafka delivery`
   - `feat(claims): implement outbox pattern for at-least-once Kafka delivery`
   - `chore(infra): add outbox relay containers to docker-compose`
   - `docs: add outbox and circuit breaker to TECHNICAL_DECISIONS`
4. Usuario aprueba push y PR.
5. PR title: `[Phase 6.5] resilience: outbox pattern and circuit breaker for production-grade event delivery`
6. PR description en inglés, formato copy-paste para GitHub (ver §"Pull Requests" en `AGENTS.md`).
7. Tras CI verde y merge a `dev`, crear rama `feat/phase-7-frontend` desde `dev`.
