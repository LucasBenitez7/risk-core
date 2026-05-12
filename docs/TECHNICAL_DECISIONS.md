# TECHNICAL DECISIONS — RiskCore

> Decisiones técnicas con justificación. Referencia para implementación.

---

## 1. Arquitectura de Microservicios

**Decisión**: 4 servicios Django independientes + gateway Nginx.

**Razón**: cada servicio tiene su propia DB, su propio ciclo de deploy, y se comunica exclusivamente via Kafka o HTTP. Implementa correctamente el patrón **Database per Service** — el anti-patrón más común en microservicios mal hechos es compartir DB entre servicios.

**Alternativa descartada**: monolito modular. Descartado porque el objetivo del proyecto es demostrar microservicios con event-driven architecture como portfolio.

---

## 2. Kafka como Message Broker

**Decisión**: Apache Kafka 3.7.x con `confluent-kafka` 2.6.x como cliente Python.

**Razón**: Kafka es el estándar en sistemas financieros y de seguros por su durabilidad y capacidad de replay. Un evento `claim.filed` puede ser consumido por audit-service y notification-service de forma independiente — si notification-service cae, los mensajes esperan en Kafka y se procesan cuando vuelve. Esto garantiza **at-least-once delivery**.

**Por qué confluent-kafka y no kafka-python**:
- Es el cliente oficial mantenido por Confluent (empresa detrás de Kafka)
- Mejor rendimiento — wrapper C sobre librdkafka
- Más activo en mantenimiento y soporte
- kafka-python tiene issues conocidos con reconexión en producción

**Alternativa descartada**: RabbitMQ. Descartado porque Kafka permite replay de mensajes históricos (fundamental para el audit log), tiene mejor throughput para miles de eventos/segundo, y es el estándar enterprise para sistemas event-driven.

**Patrón de Consumer Groups**:
```
topic: policy.created
  consumer-group: audit-consumers        → audit-service (offset propio)
  consumer-group: notification-consumers → notification-service (offset propio)
```
Cada consumer group mantiene su propio offset en el topic — si notification-service va más lento, no bloquea a audit-service.

---

## 3. Comunicación Inter-Service — Async por defecto

**Regla**: async via Kafka por defecto. HTTP síncrono solo cuando la respuesta inmediata es obligatoria para continuar.

| Caso | Tipo | Mecanismo | Razón |
|---|---|---|---|
| Póliza creada → auditar | Async | Kafka | No bloquea, el audit puede ir más lento |
| Póliza creada → notificar cliente | Async | Kafka → Celery | El email no es urgente para la respuesta API |
| Siniestro → validar que la póliza existe | Sync | HTTP entre servicios | No se puede crear el claim sin confirmar que la póliza es válida |
| Siniestro → auditar | Async | Kafka | — |

**Timeout y resiliencia para HTTP inter-service**: `httpx` con timeout de 5s. Si policy-service no responde, claims-service devuelve 503 con mensaje descriptivo. No hay circuit breaker completo (eso sería Kubernetes territory), pero sí manejo explícito del timeout.

---

## 4. Database per Service

**Decisión**: un PostgreSQL por servicio. En desarrollo local: mismo servidor PG, distintas databases. En Railway: un PostgreSQL addon por servicio.

| Servicio | Database | Tablas principales |
|---|---|---|
| policy-service | `riskcore_policies` | customers, policies, coverages, policy_documents |
| claims-service | `riskcore_claims` | claims, claim_documents, claim_status_history |
| notification-service | `riskcore_notifications` | notifications, notification_logs |
| audit-service | `riskcore_audit` | audit_events |

**Por qué PostgreSQL y no MongoDB**: los datos de pólizas y siniestros son altamente relacionales. Las pólizas tienen coberturas múltiples, los siniestros tienen historial de estados, los documentos tienen referencias cruzadas. PostgreSQL con constraints y foreign keys garantiza consistencia que MongoDB no puede ofrecer sin trabajo extra.

**Índices planificados**:
```sql
-- policy-service
CREATE INDEX idx_policies_customer ON policies(customer_id);
CREATE INDEX idx_policies_status ON policies(status);
CREATE INDEX idx_policies_dates ON policies(start_date, end_date);

-- claims-service
CREATE INDEX idx_claims_policy ON claims(policy_id);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claim_history ON claim_status_history(claim_id, changed_at DESC);

-- audit-service
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);
CREATE INDEX idx_audit_topic ON audit_events(kafka_topic);
CREATE INDEX idx_audit_created ON audit_events(created_at DESC);
```

---

## 5. Audit Service — Append-Only

**Decisión**: `AuditEvent` nunca se modifica ni elimina. Solo INSERT. Las views del servicio son solo ListAPIView y RetrieveAPIView — no hay UpdateAPIView ni DestroyAPIView.

```python
class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    kafka_topic = models.CharField(max_length=100)
    kafka_offset = models.BigIntegerField()
    entity_type = models.CharField(max_length=50)    # "policy", "claim"
    entity_id = models.UUIDField()
    event_type = models.CharField(max_length=100)    # "policy.created"
    payload = models.JSONField()                      # snapshot completo del evento
    occurred_at = models.DateTimeField()              # timestamp del evento Kafka
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
```

**Razón**: en el dominio de seguros, el audit trail es un requisito regulatorio. Cada cambio en una póliza o siniestro debe ser trazable e inmutable. El audit log es la fuente de verdad histórica.

---

## 6. Notification Service — Celery + Redis

**Decisión**: Kafka consumer recibe el evento → dispara una Celery task → la task envía el email.

**Por qué no enviar el email directamente en el consumer**:
- El consumer Kafka debe ser rápido — procesar y commitear el offset, no esperar un SMTP
- Celery gestiona reintentos automáticos si el email falla
- Flower da visibilidad sobre el estado de cada tarea
- Las tasks son testeables de forma aislada

**Retry strategy para Celery tasks**:
```python
@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minuto entre reintentos
    autoretry_for=(Exception,),
)
def send_email_notification(self, notification_id: str) -> None:
    ...
```

---

## 7. Django Channels — WebSockets para el Dashboard

**Decisión**: Django Channels 4.1.x con channels-redis como channel layer.

**Flujo**:
```
Evento Kafka recibido
    → consumer guarda en DB
    → consumer publica en Redis channel
        → Channels consumer lee Redis
            → WebSocket push al frontend Next.js
```

**Por qué no polling desde el frontend**: el dashboard necesita updates en tiempo real sin latencia. Con polling de 1s generarías 86.400 requests/día por usuario conectado. WebSockets mantienen una conexión abierta y el servidor pushea solo cuando hay eventos nuevos.

---

## 8. Logs Estructurados — structlog + Loki

**Decisión**: structlog configurado en cada servicio para emitir JSON logs. Loki los recolecta via Docker logging driver. Grafana los visualiza.

**Formato de log**:
```json
{
  "timestamp": "2025-01-15T10:23:45.123Z",
  "level": "info",
  "service": "policy-service",
  "event": "policy_created",
  "policy_id": "uuid-aqui",
  "customer_id": "uuid-aqui",
  "request_id": "x-request-id-del-gateway"
}
```

**Por qué JSON logs**: Loki puede filtrar y buscar por campos específicos. Con logs de texto plano tendrías que usar regex. Con JSON podés hacer `{service="policy-service"} | json | level="error"` directamente en Grafana.

**Request ID propagation**: el gateway genera un `X-Request-ID` UUID en cada request y lo propaga como header a todos los servicios. Cada servicio lo incluye en todos sus logs. Esto permite trazar una request completa a través de 3-4 servicios en Grafana.

---

## 9. Rate Limiting

**Decisión**: rate limiting en el gateway Nginx. No en cada servicio individualmente.

| Tier | Límite | Aplica a |
|---|---|---|
| Sin auth | 20 req/min por IP | Endpoints públicos (health) |
| Con JWT | 200 req/min por token | Endpoints autenticados |
| Admin | Sin límite | IPs de admin definidas en nginx.conf |

**Por qué en Nginx y no en Django**: el rate limiting en el gateway para el tráfico antes de que llegue a los servicios. Si lo hacés en Django, el proceso Django ya arrancó y consumió recursos. Nginx puede rechazar el request antes de tocar Python.

---

## 10. Observabilidad — Grafana + Loki + Prometheus

**Stack de observabilidad**:

| Herramienta | Qué monitorea | Fuente de datos |
|---|---|---|
| Prometheus | Métricas numéricas | `/metrics` de django-prometheus |
| Loki | Logs estructurados | Docker logging driver |
| Grafana | Visualización de todo | Prometheus + Loki como datasources |
| Flower | Celery tasks | Celery events |

**Dashboards planificados**:

1. **Services Overview**: requests/s por servicio, error rate (%), latencia p50/p95/p99
2. **Kafka Dashboard**: mensajes/s por topic, consumer lag por consumer group, particiones
3. **Celery Dashboard**: tasks pending/active/failed, tiempo promedio de ejecución
4. **Business Metrics**: pólizas creadas/día, siniestros por estado, notificaciones enviadas

**Alertas definidas**:
- Error rate > 5% en cualquier servicio → alerta inmediata
- Consumer lag Kafka > 1000 mensajes → alerta
- Celery queue > 500 tasks pendientes → alerta
- Servicio sin responder /health por > 30s → alerta crítica

---

## 11. Seguridad

**JWT entre servicios**: cada request al gateway incluye JWT. El gateway lo valida y propaga un header interno `X-Service-Token` a los servicios. Los servicios confían en el gateway — no re-validan el JWT (simplifica la arquitectura para portfolio).

**Variables de entorno**: python-decouple en backend, `.env.local` en frontend. Nunca hardcodeadas. `.env.example` documentado por servicio.

**bandit + detect-secrets**: corren en pre-commit y en CI. Ningún secret puede llegar al repo.

**CORS**: django-cors-headers configurado para aceptar solo el origen del frontend en producción.

---

## 12. Deploy en Railway

**Estrategia**: un proyecto Railway por servicio. Cada uno con su propio PostgreSQL addon y variables de entorno.

| Servicio | Railway Project | Addons |
|---|---|---|
| policy-service | insurance-policy | PostgreSQL |
| claims-service | insurance-claims | PostgreSQL |
| notification-service | insurance-notifications | PostgreSQL, Redis |
| audit-service | insurance-audit | PostgreSQL |

**Kafka en Railway**: Railway no tiene addon nativo de Kafka. Opciones:
- **Upstash Kafka** — managed Kafka con free tier, compatible con confluent-kafka
- **Redpanda Cloud** — compatible con Kafka protocol, free tier generoso

**Decisión**: Upstash Kafka para producción (Railway) + Kafka local con Docker para desarrollo.

---

## 13. Máquina de Estados — Claims

**Estados válidos y transiciones**:

```
FILED ──► UNDER_REVIEW ──► APPROVED ──► RESOLVED
                      │
                      └──► REJECTED ──► RESOLVED
```

**Reglas**:
- Solo el servicio puede cambiar el estado — no se acepta un PATCH directo al campo `status`
- Cada transición guarda un registro en `ClaimStatusHistory`
- Cada transición emite un evento Kafka `claim.status_changed`
- Transiciones inválidas devuelven 400 con mensaje descriptivo

```python
VALID_TRANSITIONS = {
    "FILED": ["UNDER_REVIEW"],
    "UNDER_REVIEW": ["APPROVED", "REJECTED"],
    "APPROVED": ["RESOLVED"],
    "REJECTED": ["RESOLVED"],
    "RESOLVED": [],  # estado terminal
}
```

---

## 14. Testing Strategy

**Regla**: los tests del módulo se escriben en la misma fase que el módulo, no al final.

**Qué mockear en tests unitarios**:
- `confluent_kafka.Producer` → mock — no necesitás Kafka para testear que el service llama al producer
- `httpx.AsyncClient` → mock — no necesitás policy-service corriendo para testear claims
- `django.core.mail` → mock — no necesitás SMTP para testear que Celery llama send_mail

**Qué NO mockear en tests de integración**:
- PostgreSQL → usás la DB real (pytest-django con `@pytest.mark.django_db`)
- Redis → usás Redis real en Docker para tests de integración de Channels/Celery

**Cobertura objetivo por tipo de código**:

| Tipo | Objetivo | Razón |
|---|---|---|
| services.py | 90%+ | Lógica de negocio crítica |
| views.py | 80%+ | Endpoints de la API |
| consumers.py | 80%+ | Procesamiento de eventos Kafka |
| models.py | 60%+ | Principalmente testeado via services |
| tasks.py | 80%+ | Notificaciones deben funcionar |

---

## 15. Frontend — Next.js 15 App Router

**Decisión**: Next.js 15.5.9 con App Router (no Pages Router).

**Razón**: App Router es la arquitectura actual de Next.js — Server Components, Server Actions, layouts anidados. Para 2025, construir con Pages Router es deuda técnica desde el día uno. App Router también da mejor integración con Turbopack para tiempos de build más rápidos.

**Por qué no Vite + React SPA**: el dashboard necesita SSR para carga inicial rápida y SEO básico en la página de login. Next.js da eso sin configuración extra.

---

## 16. Estado Global Frontend — Zustand

**Decisión**: Zustand 5.x para estado global del frontend.

**Razón**: el dashboard necesita estado compartido principalmente para el feed de eventos WebSocket (eventos que llegan en tiempo real y múltiples componentes deben mostrar). Zustand es la solución más simple para este caso: sin boilerplate, sin Provider wrapping, un store con slices.

**Alternativa descartada — Redux Toolkit**: demasiado boilerplate para el tamaño del estado que necesitamos. Redux tiene sentido cuando hay múltiples equipos tocando el mismo estado o cuando el estado es muy complejo. Para un dashboard con 3-4 stores pequeñas, Zustand es la elección correcta.

**Alternativa descartada — Jotai/Recoil**: atom-based state es ideal para estado derivado complejo. El dashboard no tiene ese nivel de complejidad reactiva.

---

## 17. WebSockets — Django Channels y Autenticación

**Decisión**: Django Channels 4.1.x con channels-redis como channel layer. Autenticación del WebSocket via JWT en el handshake inicial.

**Flujo de autenticación WebSocket**:
```
1. Frontend envía handshake WS con JWT en query param: ws://gateway/ws/?token=<jwt>
2. Channels middleware valida el JWT
3. Si válido → acepta la conexión y añade el canal al grupo del usuario
4. Si inválido → cierra la conexión con código 4001
5. Kafka consumer publica en Redis channel → Channels consumer hace push al WebSocket
```

**Por qué JWT en query param y no en header**: los WebSockets estándar del browser no permiten headers custom en el handshake. La alternativa es enviar el token como primer mensaje tras conectar, pero complica el consumer. Query param es el patrón estándar para WS auth.

**Channel groups**: todos los clientes conectados están en el grupo `"events"`. Cualquier evento Kafka llega a todos. Si en el futuro se necesita filtrado por usuario, se crean grupos individuales.

---

## 18. Formularios y Validación Frontend — React Hook Form + Zod

**Decisión**: React Hook Form 7.x para formularios, Zod 4.x para schemas de validación.

**Razón**: RHF + Zod es el estándar de facto para 2025. RHF no re-renderiza en cada keystroke (uncontrolled inputs), Zod da type inference automático desde el schema. La combinación es más eficiente que Formik + Yup.

**Patrón en RiskCore**: schema Zod define la forma, `zodResolver` conecta con RHF, los mismos tipos Zod se usan para tipar las requests a la API.

```typescript
const createPolicySchema = z.object({
  policy_type: z.enum(["VIDA", "HOGAR", "AUTO", "SALUD", "RESPONSABILIDAD_CIVIL"]),
  premium_amount: z.number().positive(),
  start_date: z.string().datetime(),
});

type CreatePolicyForm = z.infer<typeof createPolicySchema>; // tipo automático
```

---

## 19. Notificaciones UI — Sonner

**Decisión**: Sonner 2.x para toasts y notificaciones en el frontend.

**Razón**: Sonner es el componente de toast más usado en el ecosistema shadcn/Radix en 2025. Es accesible, personalizable, y tiene animaciones suaves sin configuración extra.

**Uso en RiskCore**: mostrar toasts cuando llega un nuevo evento Kafka via WebSocket ("Nueva póliza creada", "Siniestro actualizado") y para confirmaciones de acciones del usuario.

---

## 20. Git Workflow — Conventional Commits + Semantic Release

**Decisión**: Conventional Commits enforced via commitlint en pre-commit. `.releaserc.json` configurado para semantic-release.

**Razón**: conventional commits permiten generar changelogs automáticos y versionar con semantic-release.

**Reglas críticas del workflow**:
- Nunca commit directo a `main` o `dev`
- El agente de IA nunca hace commit ni push sin confirmación explícita del usuario
- Cada commit representa un cambio lógico coherente (no "varios cambios juntos")
- Un PR por fase de desarrollo

**Scopes válidos**: `policy`, `claims`, `notifications`, `audit`, `infra`, `frontend`, `gateway`, `api`

---

## 21. Linting y Formateo — Ruff (reemplaza todo)

**Decisión**: Ruff 0.15.x como única herramienta de linting y formateo. Reemplaza flake8, black, isort, pylint, y pep8 en un solo binario.

**Razón**: Ruff está escrito en Rust y es 10-100x más rápido que las herramientas que reemplaza. Para un monorepo con 4 servicios Python, la diferencia es notable en el tiempo del pre-commit hook y del CI. Es el estándar de 2025 para proyectos Django nuevos.

**Configuración en `pyproject.toml`**:
```toml
[tool.ruff]
target-version = "py313"
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["apps", "config"]
```

**Alternativa descartada**: black + flake8 + isort. Tres herramientas separadas con configuraciones separadas que a veces conflictúan entre sí.

---

## 22. Límites de Recursos y Control de Costos — Free Tier

> Aplica a producción en Railway + Upstash Kafka + Upstash Redis. En local, sin limitaciones.

El objetivo es que el sistema funcione en producción con coste cercano a cero durante la fase de portfolio. Cada servicio y componente tiene límites explícitos configurados para mantenerse en el free tier.

### Kafka — Upstash Free Tier

**Límites del plan gratuito**: 10.000 mensajes/día, 100 MB de almacenamiento total.

**Configuración de topics para minimizar almacenamiento**:
```bash
# Retención: 1 día en producción (en local: 7 días para desarrollo)
kafka-topics.sh --create --topic policy.created \
  --config retention.ms=86400000 \   # 1 día
  --config retention.bytes=10485760 \ # 10 MB máximo por topic
  --partitions 1 \                    # 1 partición (free tier, no necesitamos más)
  --replication-factor 1
```

**Regla de producción**: 1 partición por topic, retención de 1 día, sin compresión (overhead mayor que el ahorro para este volumen). En local Docker: 3 particiones, 7 días de retención.

**Si el límite de 10K msg/día se supera**: Upstash bloquea el producer. Los servicios deben manejar `KafkaException` en el producer sin interrumpir el flujo principal — el evento se pierde pero la operación de DB ya se completó.

```python
# en events.py — producción nunca debe fallar por Kafka
try:
    self._producer.flush(timeout=3)
except Exception:
    logger.warning("kafka_produce_failed", event_type=event_type, policy_id=...)
    # No re-raise — la operación DB ya commitió
```

### Redis — Upstash Redis Free Tier

**Límites del plan gratuito**: 10.000 comandos/día, 256 MB de almacenamiento.

**Usos de Redis en este proyecto**:
| Uso | Servicio | Comandos/día estimados |
|---|---|---|
| Celery broker (colas de tareas) | notification-service | ~500 (bajo volumen) |
| Celery result backend | notification-service | ~500 |
| Django Channels layer | audit-service | ~200 (WebSocket) |

**Configuración Celery para minimizar comandos Redis**:
```python
# config/celery.py — notification-service
app.conf.update(
    broker_url=config("REDIS_URL"),
    result_backend=config("REDIS_URL"),
    result_expires=3600,          # resultados expiran en 1 hora (libera memoria)
    task_serializer="json",
    result_serializer="json",
    worker_concurrency=1,         # 1 worker en producción (Railway free tier = 512MB RAM)
    worker_prefetch_multiplier=1, # no prefetch agresivo — procesar de a 1
    task_acks_late=True,          # ACK tras completar, no al recibir
)
```

**Regla**: `worker_concurrency=1` en producción. Railway Starter plan tiene 512MB RAM — múltiples workers Celery agotan la memoria. 1 worker es suficiente para el volumen de portfolio.

### PostgreSQL — Connection Pooling

**Problema**: cada proceso Django abre conexiones a PostgreSQL. Con `worker_concurrency=1` en Celery y Gunicorn con 2 workers, cada servicio abre ~4-6 conexiones. Railway PostgreSQL Starter tiene límite de 25 conexiones simultáneas en total.

**Configuración `CONN_MAX_AGE` para reusar conexiones**:
```python
# config/settings/production.py
DATABASES = {
    "default": {
        ...
        "CONN_MAX_AGE": 60,   # reusar conexión hasta 60s antes de cerrar
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}
```

**Distribución de conexiones por servicio** (máximo 25 totales Railway):
| Servicio | Workers Gunicorn | CONN_MAX_AGE | Conexiones máx |
|---|---|---|---|
| policy-service | 2 | 60s | 4 |
| claims-service | 2 | 60s | 4 |
| notification-service | 2 web + 1 Celery | 60s | 6 |
| audit-service | 2 | 60s | 4 |
| **Total** | | | **18** (margen de 7) |

### Gunicorn — Workers en Producción

**Regla**: `2 workers` por servicio en Railway Starter (512MB RAM por servicio).

```dockerfile
# En cada Dockerfile
CMD ["gunicorn", "config.wsgi:application",
     "--bind", "0.0.0.0:8000",
     "--workers", "2",
     "--timeout", "30",
     "--keep-alive", "5"]
```

La fórmula estándar `(2 × CPU) + 1` daría más workers, pero en Railway free tier con 0.5 vCPU compartida, 2 workers es el balance correcto entre concurrencia y memoria.

### Celery — Límites de Reintentos

**Problema**: reintentos infinitos o muy frecuentes queman Redis y Railway compute.

```python
# notification-service/apps/notifications/tasks.py
@shared_task(
    bind=True,
    max_retries=3,            # máximo 3 reintentos (no infinitos)
    default_retry_delay=300,  # 5 minutos entre reintentos (no 60s — menos Redis commands)
    soft_time_limit=25,       # la task debe completar en 25s
    time_limit=30,            # hard kill a los 30s
)
def send_email_notification(self, notification_id: str) -> None:
    ...
```

**Por qué 5 minutos entre reintentos**: con 60s de delay y 3 reintentos, si SMTP falla, quemas 3 slots de tus 10K comandos Redis en 3 minutos. Con 5 minutos, das tiempo a que SMTP se recupere y espacias el uso de Redis.

### Rate Limiting — Protección de Costos

El rate limiting del gateway (Sección 9) también actúa como protección de costos: un cliente abusivo que hace 10.000 requests/hora podría agotar el free tier de Kafka (10K msg/día) en una hora. Con el límite de 200 req/min por JWT, el máximo teórico es 288.000 requests/día, pero solo ~10% generan eventos Kafka → ~28.000 eventos. Esto supera el free tier.

**Mitigación**: en producción, el límite con JWT debe reducirse a **60 req/min** (en vez de 200 req/min) para mantenerse dentro del free tier de Upstash:
```nginx
# gateway/nginx.conf — producción
limit_req_zone $http_authorization zone=api_auth:10m rate=60r/m;
```

En desarrollo local, mantener 200 req/min para no limitar las pruebas.

---

## 22. Package Manager Backend — uv

**Decisión**: uv (Astral) como única herramienta de gestión de entornos y dependencias Python. Reemplaza pip, virtualenv, pip-tools, y pyenv en un solo binario.

**Razón**: uv está escrito en Rust (mismo equipo que Ruff) y es 10-100x más rápido que pip. Para un monorepo con 4 servicios Python con sus propios `pyproject.toml`, la diferencia en tiempo de instalación es notable en CI/CD y en `docker build`. También resuelve el problema de conflictos de versiones al lockear exactamente con `uv.lock`.

**Comandos clave por servicio**:
```bash
uv sync                          # instala dependencias de pyproject.toml + uv.lock
uv add django==5.2.x             # añade dependencia y actualiza uv.lock
uv run pytest                    # ejecuta en el virtualenv del servicio
uv run python manage.py migrate  # cualquier manage.py command
uv run ruff check .              # linting
```

**Estructura por servicio**:
```
[servicio]/
├── pyproject.toml   ← dependencias declaradas
├── uv.lock          ← lockfile reproducible (commitear al repo)
└── .python-version  ← fija Python 3.13 para este servicio
```

**En Dockerfile**:
```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
```

**Alternativa descartada**: pip + requirements.txt. Demasiado manual — hay que actualizar el .txt a mano. pip-tools genera el lockfile pero añade una herramienta extra. Poetry es más completo pero más lento y tiene overhead de configuración para un monorepo.

**Package manager frontend**: pnpm 10.24.0 (no relacionado con uv — son ecosistemas separados).

---

## 23. Outbox Pattern — At-Least-Once Delivery DB↔Kafka

**Decisión**: Patrón Outbox transaccional en `policy-service` y `claims-service` para eliminar el dual-write entre PostgreSQL y Kafka.

**Problema que resuelve**: en el modelo previo (Fase 6), `services.py` hacía `Policy.objects.create()` y luego `producer.produce_policy_created()` fuera de la transacción. Si el proceso moría entre el commit de DB y el publish de Kafka, el evento se perdía para siempre — pero la API ya había respondido 201 al cliente. Inconsistencia silenciosa.

**Implementación**:
- App Django `apps/outbox/` en cada servicio con un único modelo `OutboxEvent` (status PENDING/PUBLISHED/FAILED)
- Productor (`emit_policy_event`, `emit_claim_event`): inserta `OutboxEvent` **dentro** del mismo `transaction.atomic()` que crea/actualiza el aggregate
- Relay separado (`run_outbox_relay` management command, container Docker propio): `select_for_update(skip_locked=True)` + `producer.flush()` dentro de la transacción del relay → garantiza que el evento llegó al broker antes de marcar `published_at` en DB
- Índice parcial PostgreSQL `WHERE status='PENDING'` → escala a millones de eventos publicados sin degradar el escaneo de pendientes

**Garantía**: at-least-once. Los consumers (`audit-service`, `notification-service`) ya manejan duplicados via `IntegrityError` por `event_id`, así que no requieren cambios.

**Trade-offs aceptados**:
- +1 INSERT por mutación (latencia +5-15ms en p95 — verificado en `load-testing-results.md` §Phase 6.5 retest, no introdujo regresión medible)
- +2 containers (`policy-outbox-relay`, `claims-outbox-relay`)
- Eventual consistency entre DB y Kafka (típicamente <500ms con `POLL_INTERVAL=0.5s`)

**Alternativa descartada — Debezium / CDC**: lee el WAL de PostgreSQL y publica cambios a Kafka. Más robusto en producción pero overkill para este monorepo dockerizado: requiere un Connect cluster, configuración de replicación, y rompe el modelo Database-per-Service (Debezium necesita acceso al WAL del cluster, no solo a una DB lógica). El relay-as-management-command da el 90% del beneficio con 1/10 del operational burden.

**Alternativa descartada — `transaction.on_commit(producer.produce)`**: parece equivalente pero no lo es. Si el proceso muere después del commit pero antes del callback `on_commit`, el evento se pierde. El outbox sobrevive a crashes de proceso porque el evento está en DB.

**Verificación de fault tolerance** (test manual documentado en el plan archivado de Fase 6.5 dentro de `CONTEXT.md §3`):
```bash
docker compose stop kafka
curl -X POST .../api/policies/policies/  # → 201 OK inmediato
# OutboxEvent queda PENDING
docker compose start kafka                # → relay publica en <1s
```

---

## 24. Circuit Breaker — claims → policy

**Decisión**: `pybreaker` envuelve la llamada HTTP `claims-service → policy-service /verify/`. Tras 5 fallos consecutivos de infra (5xx, timeouts), el circuito abre durante 30s y todas las llamadas fallan inmediatamente.

**Problema que resuelve**: sin breaker, una degradación prolongada de `policy-service` (caída total, latencia alta sostenida) hace que cada Gunicorn worker de `claims-service` espere 5 segundos por request a `verify`. Con 50 usuarios concurrentes file-claim, los 4 workers se saturan en segundos esperando timeouts. El sistema entero se cuelga aunque solo policy-service esté degradado.

**Configuración**:
```python
_policy_breaker = pybreaker.CircuitBreaker(
    fail_max=5,                      # 5 fallos consecutivos → open
    reset_timeout=30,                # tras 30s → half-open (prueba 1 request)
    exclude=[_ClientBusinessError],  # 4xx no cuentan como fallo
    listeners=[_BreakerMetrics()],
)
```

**Sutileza crítica — 4xx vs 5xx**: HTTP 404 ("póliza no existe") es error de cliente, no fallo de infra. Si pybreaker contara 404s, 5 usuarios con UUIDs inválidos abrirían el circuito para todos. La solución es separar la llamada HTTP cruda (`_http_verify` decorado por el breaker) del manejo de errores de negocio (`verify_policy`): los 4xx se convierten a `_ClientBusinessError`, que está en `exclude=[]` → no incrementan el contador.

**Métricas Prometheus**:
- `circuit_breaker_state{target="policy-service"}` — Gauge 0=closed, 1=open, 2=half-open
- `circuit_breaker_state_changes_total{target,from_state,to_state}` — Counter de transiciones

**Alerta Grafana**: `PolicyCircuitBreakerOpen` — `circuit_breaker_state >= 1` durante 2m → severity warning.

**Por qué pybreaker y no alternativas**:
- **`pybreaker`** ✅ — implementación canónica de Python, síncrona (compatible con `httpx.Client` síncrono que ya usamos), API de listeners limpia para emitir métricas
- ❌ **`circuitbreaker`** (decorador) — no soporta listeners, métricas requieren monkey-patching
- ❌ **`tenacity`** — es retry, no breaker. Útil con backoff exponencial, pero no protege contra cascada de timeouts si el upstream sigue caído
- ❌ **Hystrix-py** — abandonado desde 2018, basado en Hystrix de Netflix que el propio Netflix puso en mantenimiento mode

**Por qué thresholds 5/30s**: 5 fallos da margen para degradaciones transitorias (1 request lenta no abre). 30s es suficiente para que un policy-service en restart termine de levantarse. Ambos son configurables — el plan abre la puerta a tunearlos por servicio si se observan falsos positivos.

**No usado para `consumer → DB` o `consumer → Kafka`**: esos paths ya son retried por Kafka (auto-retry en consumer) o por confluent-kafka (auto-retry interno). El breaker solo agrega valor donde no hay retry automático — la llamada HTTP síncrona inter-service.

---

## 26. Frontend — Next.js 15 App Router + RSC

**Decisión**: Next.js 15 App Router con React Server Components por defecto. `"use client"` solo en componentes que necesitan interactividad (forms, WebSocket, hooks de estado del navegador).

**Por qué App Router**: RSC reduce el JS enviado al cliente y mejora el TTFB. Las páginas de listado y detalle son mayoritariamente lectura — renderizarlas en el servidor es la opción correcta. El cliente solo recibe JS para los formularios de cancelación/transición y el feed de eventos.

**JWT en httpOnly cookies + Next.js como proxy de auth**: el JWT nunca toca el contexto JS del navegador. Flujo:

1. `POST /api/auth/login` (Route Handler de Next.js) recibe credenciales del cliente, llama al gateway `/api/auth/token/`, y setea `access_token` y `refresh_token` como cookies httpOnly + `SameSite=Lax` + `Secure` en producción. Devuelve solo `{ username }` al cliente. Un `username` no-httpOnly se setea para que la UI lo pueda mostrar.
2. **Server Components** usan `serverFetch()` que lee la cookie con `next/headers` y agrega `Authorization: Bearer` directamente al request al gateway.
3. **Client components** usan `apiFetch()` que pega a `/api/proxy/[...path]` (Route Handler genérico) — éste lee la cookie httpOnly, agrega el Bearer y reenvía al gateway. El cliente nunca ve el token.
4. **WebSocket** llama primero a `/api/auth/ws-token` (Route Handler que devuelve el access token desde la cookie) para abrir `ws://gateway/ws/events/?token=<jwt>`. El token vive solo en memoria del client durante la vida del socket — nunca se persiste. Es la única ventana donde el JWT toca JS, y solo para ser pasado al WS handshake (Channels valida en su middleware).

**Por qué este patrón en vez de pegar directo al gateway con `credentials: "include"`**: el gateway espera `Authorization: Bearer`, no cookies. Reenviar la cookie como header en otro origen es un CORS pain que además expone al gateway a cookies cross-origin. El proxy interno mantiene la cookie y el gateway desacoplados.

**Zod como única fuente de tipos**: los schemas Zod en `lib/api/schemas.ts` son la fuente de verdad. Los tipos TypeScript se derivan con `z.infer<typeof schema>`. Nunca se duplican interfaces a mano — esto garantiza que si el backend cambia el schema, el frontend falla en tiempo de parse (runtime) en lugar de en producción silenciosamente.

**WebSocket — validación JWT en Channels, no en nginx**: `auth_request` de nginx no funciona con Upgrade headers. El handshake HTTP→WS es una sola request; nginx no puede subrequestearla sin cerrar el upgrade. La solución es validar el token en el propio middleware de Django Channels (`JWTAuthMiddleware`) que parsea el `?token=` del query string con `simplejwt.tokens.AccessToken` (no hace DB hit — el token es auto-contenido). El gateway solo pasa el header `Upgrade`.

**Backoff exponencial en WS**: 1s → 2s → 4s → … → cap 30s. Evita tormentas de reconexión tras un restart del servidor. La UI muestra "Reconectando…" para no confundir al usuario.

---

## 25. Deploy — Railway

**Decisión**: Railway para producción. Un proyecto Railway por microservicio.

**Razón**: Railway tiene el mejor balance entre simplicidad (no necesita DevOps expertise) y capacidades (deploys automáticos desde GitHub, addons de PostgreSQL/Redis, variables de entorno por entorno). Para un portfolio project, es la opción más práctica que demuestra que el proyecto funciona en producción real sin las complejidades de Kubernetes.

**Kafka en producción**: Upstash Kafka (managed, free tier, compatible con confluent-kafka) en lugar de desplegar Kafka propio.

**Alternativa descartada**: Heroku. Eliminó el free tier y es más caro que Railway para el mismo resultado. Render es similar a Railway pero tiene menos opciones de networking entre servicios.

---

## 27. Uvicorn vs Daphne en audit-service

**Decisión**: Reemplazar Daphne por Uvicorn con 4 workers en audit-service.

**Problema**: El load test Scenario 3 (1000 usuarios concurrentes, solo lectura sobre 10k eventos de auditoría) mostró ~96% de errores 504 (Gateway Timeout) con Daphne. Daphne es single-process y no soporta múltiples workers — con 1000 usuarios, las requests se encolan y el gateway corta a los 30s.

**Resultado post-migración**:
- Error rate: ~96% → 66.48%
- Throughput: 56 req/s → 79.99 req/s
- p50: timeout (>30s) → 7500ms
- Tipo de error: 504 (gateway timeout) → 500 (DB connection pool exhausted)

**Interpretación**: Uvicorn mitigó el bottleneck de Daphne single-process, pero expuso el siguiente cuello de botella: el pool de conexiones de PostgreSQL. Con 4 workers, audit-service acepta más requests concurrentes de las que la base de datos puede atender con la configuración por defecto (`max_connections=100` compartido entre todos los servicios). Los 500s son `django.db.utils.OperationalError: FATAL: sorry, too many clients already`.

**Por qué Uvicorn y no Daphne**:
- Uvicorn soporta múltiples workers nativamente (`--workers 4`)
- `uvicorn[standard]` incluye `websockets`, `uvloop` y `httptools` — compatible con Django Channels 4.1
- Daphne está diseñado para desarrollo; en producción se recomienda Uvicorn o Hypercorn para mayor throughput

**Próximo paso**: Para resolver completamente Scenario 3, se requiere tuning del pool de conexiones (CONN_MAX_AGE en Django, pgBouncer, o aumentar `max_connections` en PostgreSQL) o reducir el número de workers de Uvicorn hasta que el DB pool no se agote.

---
