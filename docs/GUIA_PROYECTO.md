# GUÍA DEL PROYECTO — RiskCore

> Leer este archivo antes de arrancar a programar.
> Explica qué es el proyecto, qué hace cada parte, y cómo encaja todo junto.

---

## ¿Qué es RiskCore?

RiskCore es el **sistema backend core de una aseguradora**. Simula exactamente lo que usaría una empresa como Mapfre o Allianz para gestionar su operación diaria: registrar clientes, emitir pólizas, procesar siniestros, notificar a los asegurados, y mantener un historial inmutable de todo lo que ocurre.

Está construido como **microservicios** — en lugar de ser una sola aplicación grande, son 4 servicios Django independientes que se comunican entre sí. Cada servicio hace una cosa, la hace bien, y no depende directamente de los otros para funcionar.

---

## El Dominio — Cómo Funciona una Aseguradora

Antes de entender el código, hay que entender el negocio. Una aseguradora funciona así:

```
1. Una persona se convierte en CLIENTE de la aseguradora.

2. El cliente contrata una PÓLIZA — un contrato que dice:
   "Yo (aseguradora) te cubro a ti (cliente) ante ciertos riesgos,
   a cambio de que me pagues una PRIMA mensual/anual."

3. La póliza tiene COBERTURAS — qué riesgos cubre y hasta qué monto.
   Ejemplo: póliza de VIDA con cobertura de fallecimiento hasta 100.000€
            y cobertura de invalidez hasta 50.000€.

4. Si ocurre un incidente (accidente, robo, incendio...), el cliente
   reporta un SINIESTRO — una reclamación al amparo de su póliza.

5. La aseguradora REVISA el siniestro, lo APRUEBA o RECHAZA,
   y finalmente lo RESUELVE pagando al cliente si fue aprobado.

6. Todo esto debe quedar registrado en un AUDIT LOG inmutable
   por requisito legal y regulatorio.

7. En cada paso importante, el cliente recibe una NOTIFICACIÓN por email.
```

Eso es exactamente lo que implementa RiskCore.

---

## Los 4 Microservicios

### 1. policy-service — El corazón del negocio

**¿Qué hace?**
Gestiona todo lo relacionado con clientes y pólizas. Es el servicio más importante porque todos los demás dependen (directa o indirectamente) de los datos que genera este servicio.

**Entidades que maneja:**
- `Customer` — el asegurado (nombre, DNI, email, teléfono)
- `Policy` — la póliza (tipo, fechas, prima, estado)
- `Coverage` — las coberturas de cada póliza
- `PolicyDocument` — documentos adjuntos a la póliza

**Operaciones principales:**
- Registrar un cliente nuevo
- Crear una póliza para ese cliente
- Consultar pólizas activas
- Cancelar una póliza
- Verificar si una póliza existe y está activa (llamado internamente por claims-service)

**Cuándo emite eventos Kafka:**
- Al crear una póliza → emite `policy.created`
- Al actualizar una póliza → emite `policy.updated`
- Al cancelar una póliza → emite `policy.cancelled`

---

### 2. claims-service — La gestión de siniestros

**¿Qué hace?**
Gestiona el ciclo de vida completo de un siniestro: desde que el cliente lo reporta hasta que queda resuelto.

**Entidades que maneja:**
- `Claim` — el siniestro (qué pasó, cuándo, dónde, monto estimado, estado actual)
- `ClaimDocument` — documentos del siniestro (fotos, informes, facturas)
- `ClaimStatusHistory` — historial de todos los cambios de estado

**La máquina de estados — el flujo de un siniestro:**

```
FILED          → El cliente acaba de reportarlo. Está registrado pero nadie lo revisó.
    ↓
UNDER_REVIEW   → Un perito o agente lo está analizando.
    ↓         ↘
APPROVED       REJECTED   → Se aprueba (con monto) o se rechaza (con justificación).
    ↓                ↓
RESOLVED       RESOLVED   → Caso cerrado. Si fue aprobado, el pago fue procesado.
```

**Operaciones principales:**
- Reportar un siniestro (primero valida que la póliza existe y está activa)
- Hacer transiciones de estado
- Consultar siniestros con filtros

**Comunicación con policy-service:**
Cuando alguien quiere reportar un siniestro sobre la póliza X, claims-service llama a policy-service via HTTP para verificar que esa póliza existe y está en estado ACTIVE. Si la póliza está cancelada o no existe, el siniestro no se puede crear. Esta es la **única comunicación síncrona** entre servicios.

**Cuándo emite eventos Kafka:**
- Al crear un siniestro → emite `claim.filed`
- Al cambiar el estado → emite `claim.status_changed`
- Al resolver → emite `claim.resolved`

---

### 3. notification-service — Las notificaciones

**¿Qué hace?**
Escucha los eventos Kafka de los otros servicios y envía emails a los clientes cuando algo importante ocurre. No sabe nada de pólizas ni siniestros directamente — solo reacciona a eventos.

**¿Por qué existe como servicio separado?**
Imaginate que cada vez que se crea una póliza, policy-service tuviera que esperar a que el email se envíe antes de responder al cliente. Si el servidor de email tarda 3 segundos, tu API tarda 3 segundos. Eso es malo.

Con notification-service separado:
1. policy-service crea la póliza → responde al cliente en 50ms
2. Emite un evento Kafka y sigue su vida
3. notification-service recibe el evento en segundo plano
4. Celery envía el email de forma asíncrona

Si el servidor de email cae, notification-service reintenta automáticamente. El cliente no nota nada.

**Qué escucha y qué envía:**

| Evento Kafka recibido | Email que envía |
|---|---|
| `policy.created` | "Tu póliza ha sido creada exitosamente" |
| `policy.cancelled` | "Tu póliza ha sido cancelada" |
| `claim.filed` | "Tu siniestro ha sido registrado con número CLM-XXX" |
| `claim.status_changed` | "El estado de tu siniestro ha cambiado a X" |
| `claim.resolved` | "Tu siniestro ha sido resuelto" |

**Cómo funciona internamente:**
```
Kafka consumer recibe evento
    → Crea registro Notification (status: PENDING)
    → Dispara Celery task send_email
        → Celery envía el email
        → Actualiza Notification a SENT (o FAILED si falla)
        → Guarda NotificationLog con el resultado
```

**¿Por qué Celery además de Kafka?**
Kafka entrega el evento al consumer rápido. Pero el consumer no debería hacer cosas lentas (como enviar emails) porque bloquearia el procesamiento del siguiente mensaje. Celery es una cola de tareas diseñada exactamente para eso: procesar trabajos lentos en workers separados, con reintentos automáticos y monitoreo via Flower.

---

### 4. audit-service — El historial inmutable

**¿Qué hace?**
Escucha **todos** los eventos Kafka y los guarda en una base de datos que nunca se modifica. Es el registro oficial de todo lo que ha pasado en el sistema.

**¿Por qué existe?**
En el mundo de los seguros, la auditoría es un requisito legal. Si un cliente reclama que su siniestro fue aprobado por 10.000€ pero solo recibió 8.000€, necesitás poder demostrar exactamente qué pasó, cuándo, y quién lo cambió. El audit log es esa prueba.

**Regla de oro**: `AuditEvent` nunca se modifica ni se borra. Solo INSERT. Para siempre.

**Qué guarda por cada evento:**
- El topic Kafka y el offset (posición exacta en el log de Kafka)
- El tipo de entidad (`policy` o `claim`) y su ID
- El tipo de evento (`policy.created`, `claim.filed`, etc.)
- El payload completo — un snapshot de todos los datos en ese momento
- El timestamp del evento y el timestamp de cuando lo registró

---

## Cómo Encaja Todo — El Flujo Completo

### Ejemplo real: Un cliente reporta un siniestro

```
1. Cliente llama a la API:
   POST /api/claims/claims/
   { "policy_id": "uuid-123", "incident_type": "ACCIDENTE", ... }

2. claims-service recibe el request.
   Llama sincrónicamente a policy-service:
   GET /api/policies/policies/uuid-123/verify/
   → policy-service responde: { "status": "ACTIVE", "is_valid": true }

3. claims-service crea el Claim en su propia base de datos.
   Status: FILED

4. claims-service responde al cliente: 201 Created
   { "claim_number": "CLM-2025-000001", "status": "FILED" }

5. En paralelo (sin que el cliente espere):
   claims-service publica en Kafka:
   topic: claim.filed
   payload: { claim_id, claim_number, claimant_email, incident_type, ... }

6. Kafka distribuye el mensaje a dos consumer groups independientes:

   audit-service recibe el mensaje:
   → Guarda AuditEvent en su DB (inmutable)
   → "Quedó registrado: claim.filed a las 10:23:45"

   notification-service recibe el mensaje:
   → Crea Notification (status: PENDING)
   → Dispara Celery task send_email
   → Celery envía email al cliente: "Su siniestro CLM-2025-000001 fue registrado"
   → Actualiza Notification a SENT

7. El dashboard Next.js, conectado via WebSocket a Django Channels,
   recibe el evento en tiempo real y lo muestra en el feed.
```

**Lo importante**: en el paso 4, el cliente ya tiene su respuesta. Todo lo que pasa después (pasos 5, 6, 7) ocurre de forma asíncrona, sin bloquear al cliente.

---

## Kafka — Qué Es y Por Qué Lo Usamos

Kafka es un **message broker** — un sistema intermediario que permite que los servicios se comuniquen sin conocerse directamente.

**Sin Kafka (el problema):**
```
claims-service quiere notificar que se creó un siniestro.
Tendría que llamar directamente a notification-service y audit-service.
¿Qué pasa si notification-service está caído? ¿Se pierde el evento?
¿Qué pasa si mañana queremos agregar un quinto servicio que también
necesita saber sobre los siniestros? Tendríamos que modificar claims-service.
```

**Con Kafka (la solución):**
```
claims-service publica un evento en el topic "claim.filed".
No sabe quién lo va a leer. No le importa.

notification-service está suscrito al topic.
audit-service está suscrito al topic.
Si notification-service está caído, Kafka guarda el mensaje.
Cuando vuelva, lo procesa. No se pierde nada.

Si mañana queremos un quinto servicio, solo lo suscribimos al topic.
claims-service no se entera ni necesita cambiar.
```

**Los topics en RiskCore:**

```
policy.created    ← cuando se emite una póliza nueva
policy.updated    ← cuando se modifica una póliza
policy.cancelled  ← cuando se cancela una póliza

claim.filed          ← cuando se reporta un siniestro
claim.status_changed ← cuando cambia el estado del siniestro
claim.resolved       ← cuando el siniestro queda cerrado
```

**Consumer Groups — por qué importan:**
Kafka permite que múltiples "grupos" lean el mismo topic de forma independiente. audit-service tiene su propio offset (posición de lectura) y notification-service tiene el suyo. Si notification-service procesa el mensaje 100 pero audit-service ya va en el 150, eso está bien — cada uno va a su ritmo.

---

## Celery — Qué Es y Por Qué Lo Usamos

Celery es una **cola de tareas asíncronas**. Sirve para ejecutar trabajo pesado o lento fuera del flujo principal de la aplicación.

**En RiskCore lo usamos en notification-service:**

```
Consumer Kafka (rápido — solo recibe y delega)
    → Celery task send_email (lento — hace la conexión SMTP)
```

**Por qué separar el consumer de la task:**
El consumer Kafka debe ser rápido. Si se tarda en procesar un mensaje, se acumula retraso (consumer lag) y los siguientes mensajes esperan. Enviar un email puede tardar 1-2 segundos. Si hay 1000 mensajes, eso es 16 minutos de retraso acumulado.

Con Celery: el consumer recibe el mensaje, crea la task, y commitea el offset en milisegundos. El worker de Celery envía el email en paralelo sin bloquear al consumer.

**Redis como broker de Celery:**
Celery necesita un lugar donde guardar las tareas pendientes. Usamos Redis para eso — el mismo Redis que usamos para cache.

**Flower:**
Es la UI web de Celery. Desde `http://localhost:5555` podés ver en tiempo real cuántas tasks están pendientes, cuántas fallaron, cuánto tardan en ejecutarse.

---

## Observabilidad — Grafana + Loki + Prometheus

**El problema**: tenemos 4 servicios corriendo. Si algo falla, ¿cómo sabés cuál falló, cuándo, y por qué?

**La solución**: tres herramientas que trabajan juntas.

### structlog → Loki (logs)
Cada servicio usa structlog para emitir logs en formato JSON:
```json
{
  "timestamp": "2025-01-15T10:23:45Z",
  "level": "error",
  "service": "claims-service",
  "event": "policy_service_timeout",
  "policy_id": "uuid-123",
  "request_id": "req-abc-456"
}
```

Loki recolecta todos esos logs. Desde Grafana podés buscar:
"Dame todos los errores de claims-service de los últimos 30 minutos"
"Dame todos los logs relacionados con el request req-abc-456"

### django-prometheus → Prometheus (métricas)
Cada servicio expone `/metrics` con números: cuántos requests recibió, cuántos fallaron, cuánto tardaron. Prometheus los recolecta cada 15 segundos.

### Grafana (visualización)
Grafana conecta con Loki y Prometheus y muestra dashboards:
- ¿Está subiendo el error rate? → gráfico en tiempo real
- ¿Hay consumer lag en Kafka? → alerta automática
- ¿Cuántas pólizas se crearon hoy? → business metrics

**El X-Request-ID:**
El gateway genera un ID único por cada request y lo propaga a todos los servicios. Si un cliente reporta "mi request falló a las 10:23", podés buscar ese ID en Grafana y ver exactamente qué pasó en cada servicio para ese request.

---

## El Dashboard Frontend

Next.js 15 conectado al backend via:
- **REST API** — para consultar pólizas, siniestros, audit log
- **WebSockets (Django Channels)** — para recibir eventos Kafka en tiempo real

El dashboard muestra:
- Feed en vivo de eventos Kafka (cada vez que se crea una póliza o se modifica un siniestro, aparece en pantalla en menos de 2 segundos)
- Estado de salud de los 4 servicios
- Métricas de negocio: pólizas activas, siniestros por estado
- Visor de audit log con filtros

---

## Arquitectura Completa en Una Vista

```
                    ┌─────────────────────────────┐
                    │        Next.js 15            │
                    │  Dashboard + Events Feed     │
                    └─────────┬─────────┬──────────┘
                              │ REST    │ WebSocket
                              ▼         ▼
                    ┌─────────────────────────────┐
                    │         Nginx Gateway        │
                    │   JWT auth  |  Rate limit    │
                    │   X-Request-ID propagation   │
                    └───┬─────────┬────────────┬───┘
                        │         │            │
              ┌─────────▼──┐ ┌────▼──────┐ ┌──▼────────────┐
              │policy-svc  │ │claims-svc │ │audit-svc      │
              │Django+DRF  │ │Django+DRF │ │Django+DRF     │
              │PG: policies│ │PG: claims │ │PG: audit      │
              └─────┬──────┘ └────┬──────┘ └──────▲────────┘
                    │  HTTP sync  │                │
                    │◄────────────┘                │ consume
                    │                              │
                    └──────────┬───────────────────┘
                               │ produce
                    ┌──────────▼──────────┐
                    │    Apache Kafka      │
                    │  policy.* / claim.* │
                    └──────────┬──────────┘
                               │ consume
                    ┌──────────▼──────────┐
                    │ notification-svc     │
                    │ Django + Celery      │
                    │ Redis + PG: notifs   │
                    │ → envía emails       │
                    └─────────────────────┘

                    ┌────────────────────────────────────────┐
                    │           Observabilidad                │
                    │  structlog → Loki → Grafana             │
                    │  django-prometheus → Prometheus → Grafana│
                    │  Flower (Celery monitor)                 │
                    └────────────────────────────────────────┘
```

---

## Preguntas que te Van a Hacer en Entrevista

### "¿Por qué microservicios y no un monolito?"
> "Para este dominio, los microservicios tienen sentido porque los ciclos de vida son independientes. El equipo que trabaja en siniestros puede deployar claims-service sin tocar policy-service. Además, si la carga de siniestros sube (temporada de tormentas, por ejemplo), podés escalar solo claims-service sin escalar toda la aplicación. Dicho eso, también entiendo que para un equipo pequeño un monolito modular puede ser más práctico — la decisión depende del contexto."

### "¿Por qué Kafka y no RabbitMQ?"
> "Kafka nos da durabilidad y replay. Si audit-service cae un momento, cuando vuelve puede releer los mensajes desde donde quedó — no se pierde ningún evento. Con RabbitMQ los mensajes se consumen y desaparecen. Para un audit log en el dominio de seguros, que es un requisito regulatorio, no podemos permitir pérdida de eventos."

### "¿Cómo manejás la consistencia entre servicios?"
> "Usamos consistencia eventual para la mayoría de los casos. Cuando se crea una póliza, el evento Kafka garantiza que audit-service y notification-service eventualmente lo van a procesar. Para el único caso donde necesitamos consistencia inmediata — verificar que la póliza existe antes de crear un siniestro — usamos HTTP síncrono entre servicios con timeout explícito."

### "¿Cómo trazás un error a través de múltiples servicios?"
> "El gateway genera un X-Request-ID único por cada request y lo propaga como header a todos los servicios. Cada servicio incluye ese ID en todos sus logs estructurados (JSON via structlog). En Grafana + Loki, puedo filtrar por ese ID y ver exactamente qué pasó en cada servicio para ese request específico."

### "¿Qué pasa si notification-service cae?"
> "Los mensajes siguen acumulándose en Kafka. Kafka los retiene según la política de retención configurada (por defecto 7 días). Cuando notification-service vuelve, continúa consumiendo desde donde se quedó usando el consumer group offset. El cliente recibirá su email con retraso, pero no se pierde."

---

## Resumen del Stack en Una Línea

**Backend**: Django 5.2 + DRF + confluent-kafka + Celery + Redis + PostgreSQL + structlog + django-prometheus + Django Channels

**Frontend**: Next.js 15 + React 19 + TypeScript + Tailwind CSS 4 + Zustand + Vitest + Playwright

**Infra**: Docker Compose + Nginx + Kafka + Grafana + Loki + Prometheus + Flower + Railway (deploy)

**Calidad**: Ruff + mypy + bandit + detect-secrets + pytest + factory-boy + locust + GitHub Actions
