# TECHNICAL DECISIONS — RiskCore

> Decisiones técnicas con justificación. Referencia para implementación y para explicar en entrevista.

---

## 1. Arquitectura de Microservicios

**Decisión**: 4 servicios Django independientes + gateway Nginx.

**Razón**: cada servicio tiene su propia DB, su propio ciclo de deploy, y se comunica exclusivamente via Kafka o HTTP. Implementa correctamente el patrón **Database per Service** — el anti-patrón más común en microservicios mal hechos es compartir DB entre servicios.

**Alternativa descartada**: monolito modular. Descartado porque el objetivo del proyecto es demostrar microservicios con event-driven architecture como portfolio.

**Cómo explicarlo en entrevista**:
> "Cada servicio tiene su propia base de datos — policy-service no puede hacer JOIN con la tabla de claims. Toda comunicación es via eventos Kafka o HTTP síncrono cuando la consistencia inmediata es necesaria."

---

## 2. Kafka como Message Broker

**Decisión**: Apache Kafka 3.7.x con `confluent-kafka` 2.6.x como cliente Python.

**Razón**: Kafka es el estándar en sistemas financieros y de seguros por su durabilidad y capacidad de replay. Un evento `claim.filed` puede ser consumido por audit-service y notification-service de forma independiente — si notification-service cae, los mensajes esperan en Kafka y se procesan cuando vuelve. Esto garantiza **at-least-once delivery**.

**Por qué confluent-kafka y no kafka-python**:
- Es el cliente oficial mantenido por Confluent (empresa detrás de Kafka)
- Mejor rendimiento — wrapper C sobre librdkafka
- Más activo en mantenimiento y soporte
- kafka-python tiene issues conocidos con reconexión en producción

**Alternativa descartada**: RabbitMQ. Descartado porque Kafka permite replay de mensajes históricos (fundamental para el audit log), tiene mejor throughput para miles de eventos/segundo, y es lo que usan empresas enterprise tipo Mapfre en sus core systems.

**Patrón de Consumer Groups**:
```
topic: policy.created
  consumer-group: audit-consumers        → audit-service (offset propio)
  consumer-group: notification-consumers → notification-service (offset propio)
```
Cada consumer group mantiene su propio offset en el topic — si notification-service va más lento, no bloquea a audit-service.

**Cómo explicarlo en entrevista**:
> "Usamos consumer groups para que cada servicio consuma los eventos a su propio ritmo. Si notification-service tiene un pico de carga, sus mensajes no se pierden — siguen en Kafka esperando. El offset de cada consumer group es independiente."

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

**Cómo explicarlo en entrevista**:
> "Usamos App Router porque es el futuro de Next.js. Server Components nos permiten hacer fetch de datos iniciales sin exponer la API key al cliente, y los layouts anidados simplifican la estructura del dashboard sin prop drilling."

---

## 16. Estado Global Frontend — Zustand

**Decisión**: Zustand 5.x para estado global del frontend.

**Razón**: el dashboard necesita estado compartido principalmente para el feed de eventos WebSocket (eventos que llegan en tiempo real y múltiples componentes deben mostrar). Zustand es la solución más simple para este caso: sin boilerplate, sin Provider wrapping, un store con slices.

**Alternativa descartada — Redux Toolkit**: demasiado boilerplate para el tamaño del estado que necesitamos. Redux tiene sentido cuando hay múltiples equipos tocando el mismo estado o cuando el estado es muy complejo. Para un dashboard con 3-4 stores pequeñas, Zustand es la elección correcta.

**Alternativa descartada — Jotai/Recoil**: atom-based state es ideal para estado derivado complejo. El dashboard no tiene ese nivel de complejidad reactiva.

**Cómo explicarlo en entrevista**:
> "Zustand porque el estado del dashboard es simple: websocket events, filtros activos, UI state. No necesitamos Redux para eso — la regla es usar la herramienta más simple que resuelva el problema."

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

**Cómo explicarlo en entrevista**:
> "Django Channels nos da WebSockets sobre ASGI con muy poco código. El JWT va en el query param porque el browser no permite headers en el WS handshake. El canal Redis conecta el consumer Kafka con el consumer WebSocket — cuando llega un evento Kafka, el consumer lo publica en Redis y Channels lo pushea a todos los clientes conectados."

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

**Razón**: conventional commits permiten generar changelogs automáticos y versionar con semantic-release. Para un portfolio, tener un CHANGELOG.md bien formado es un diferencial. Los recruiters técnicos revisan el historial de commits.

**Reglas críticas del workflow**:
- Nunca commit directo a `main` o `dev`
- El agente de IA nunca hace commit ni push sin confirmación explícita del usuario
- Cada commit representa un cambio lógico coherente (no "varios cambios juntos")
- Un PR por fase de desarrollo

**Scopes válidos**: `policy`, `claims`, `notifications`, `audit`, `infra`, `frontend`, `gateway`, `api`

**Cómo explicarlo en entrevista**:
> "Conventional commits nos dan trazabilidad y la posibilidad de automatizar releases. El CI verifica el formato del mensaje antes de aceptar el PR — si el mensaje no cumple el formato, el pipeline falla."

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

**Cómo explicarlo en entrevista**:
> "Usamos uv del mismo equipo que Ruff — ambos escritos en Rust para máximo rendimiento. En CI, instalar las dependencias de un servicio tarda menos de 5 segundos con uv frente a 30-60 con pip. El uv.lock garantiza que desarrollo, CI y Railway tienen exactamente las mismas versiones."

---

## 23. Deploy — Railway

**Decisión**: Railway para producción. Un proyecto Railway por microservicio.

**Razón**: Railway tiene el mejor balance entre simplicidad (no necesita DevOps expertise) y capacidades (deploys automáticos desde GitHub, addons de PostgreSQL/Redis, variables de entorno por entorno). Para un portfolio project, es la opción más práctica que demuestra que el proyecto funciona en producción real sin las complejidades de Kubernetes.

**Kafka en producción**: Upstash Kafka (managed, free tier, compatible con confluent-kafka) en lugar de desplegar Kafka propio.

**Alternativa descartada**: Heroku. Eliminó el free tier y es más caro que Railway para el mismo resultado. Render es similar a Railway pero tiene menos opciones de networking entre servicios.

**Cómo explicarlo en entrevista**:
> "Railway nos da deploys automáticos desde GitHub, base de datos managed, y networking privado entre servicios sin DevOps overhead. Para un proyecto de portfolio, lo que importa es que el sistema funcione en producción — Railway nos permite demostrarlo sin invertir semanas en infraestructura."
