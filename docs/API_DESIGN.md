# API DESIGN — RiskCore

> Todos los endpoints con request/response schemas definidos antes de programar.
> Base URL por servicio: cada servicio corre en su propio puerto (o path via gateway).

---

## Gateway Routes

| Servicio | Path base (via gateway) | Puerto local |
|---|---|---|
| policy-service | `/api/policies/` | 8001 |
| claims-service | `/api/claims/` | 8002 |
| notification-service | `/api/notifications/` | 8003 |
| audit-service | `/api/audit/` | 8004 |

---

## Autenticación

Todos los endpoints (excepto `/health`) requieren JWT en el header:

```
Authorization: Bearer <access_token>
```

El gateway valida el JWT y propaga `X-Request-ID` a todos los servicios.

---

## policy-service

### GET /api/policies/health/
Estado del servicio. Sin auth.

**Response 200**
```json
{
  "status": "ok",
  "service": "policy-service",
  "version": "0.1.0",
  "database": "ok",
  "kafka": "ok"
}
```

---

### POST /api/policies/customers/
Crear nuevo cliente.

**Request**
```json
{
  "full_name": "María García López",
  "email": "maria.garcia@email.com",
  "dni": "12345678A",
  "phone": "+34 612 345 678",
  "birth_date": "1985-03-15",
  "address": "Calle Mayor 123, Madrid"
}
```

**Response 201**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "María García López",
  "email": "maria.garcia@email.com",
  "dni": "12345678A",
  "phone": "+34 612 345 678",
  "birth_date": "1985-03-15",
  "address": "Calle Mayor 123, Madrid",
  "created_at": "2025-01-15T10:00:00Z"
}
```

**Errores**
- 400 — DNI ya registrado / email ya registrado / campos requeridos faltantes
- 422 — formato de email o DNI inválido

---

### GET /api/policies/customers/
Listar clientes con paginación y filtros.

**Query params**
- `page` — número de página (default: 1)
- `page_size` — resultados por página (default: 20, max: 100)
- `search` — búsqueda por nombre, email o DNI
- `ordering` — `created_at`, `-created_at`

**Response 200**
```json
{
  "count": 150,
  "next": "/api/policies/customers/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-...",
      "full_name": "María García López",
      "email": "maria.garcia@email.com",
      "dni": "12345678A",
      "created_at": "2025-01-15T10:00:00Z",
      "active_policies_count": 2
    }
  ]
}
```

---

### GET /api/policies/customers/{id}/
Detalle de cliente.

**Response 200**
```json
{
  "id": "550e8400-...",
  "full_name": "María García López",
  "email": "maria.garcia@email.com",
  "dni": "12345678A",
  "phone": "+34 612 345 678",
  "birth_date": "1985-03-15",
  "address": "Calle Mayor 123, Madrid",
  "created_at": "2025-01-15T10:00:00Z",
  "policies": [
    {
      "id": "uuid",
  "policy_type": "LIFE",
  "status": "ACTIVE",
  "premium_amount": "150.00"
    }
  ]
}
```

**Errores**
- 404 — cliente no encontrado

---

### POST /api/policies/policies/
Crear nueva póliza.

**Request**
```json
{
  "customer_id": "550e8400-...",
  "policy_type": "LIFE",
  "start_date": "2025-02-01",
  "end_date": "2026-02-01",
  "premium_amount": "150.00",
  "coverages": [
    {
      "coverage_type": "LIFE",
      "coverage_amount": "100000.00",
      "description": "Cobertura por fallecimiento del asegurado"
    },
    {
      "coverage_type": "DISABILITY",
      "coverage_amount": "50000.00",
      "description": "Cobertura por invalidez permanente"
    }
  ]
}
```

**Response 201**
```json
{
  "id": "uuid",
  "policy_number": "POL-2025-000001",
  "customer_id": "550e8400-...",
  "policy_type": "LIFE",
  "status": "ACTIVE",
  "start_date": "2025-02-01",
  "end_date": "2026-02-01",
  "premium_amount": "150.00",
  "coverages": [...],
  "created_at": "2025-01-15T10:00:00Z"
}
```

**Kafka event emitido**: `policy.created` con payload completo de la póliza.

**Errores**
- 400 — customer_id no existe / fechas inválidas / premium <= 0
- 404 — cliente no encontrado

**Tipos de póliza válidos**: `LIFE`, `HEALTH`, `AUTO`, `HOME`, `BUSINESS`

---

### GET /api/policies/policies/
Listar pólizas con filtros.

**Query params**
- `page`, `page_size`
- `status` — `ACTIVE`, `SUSPENDED`, `CANCELLED`, `EXPIRED`
- `policy_type` — `LIFE`, `HEALTH`, `AUTO`, `HOME`, `BUSINESS`
- `customer_id` — UUID
- `ordering` — `created_at`, `-created_at`, `premium_amount`, `-premium_amount`

**Response 200**
```json
{
  "count": 430,
  "next": "...",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "policy_number": "POL-2025-000001",
      "customer_id": "uuid",
      "customer_name": "María García López",
      "policy_type": "LIFE",
      "status": "ACTIVE",
      "premium_amount": "150.00",
      "start_date": "2025-02-01",
      "end_date": "2026-02-01"
    }
  ]
}
```

---

### GET /api/policies/policies/{id}/
Detalle de póliza con coberturas.

**Response 200**
```json
{
  "id": "uuid",
  "policy_number": "POL-2025-000001",
  "customer": {
    "id": "uuid",
    "full_name": "María García López",
    "email": "maria.garcia@email.com"
  },
  "policy_type": "LIFE",
  "status": "ACTIVE",
  "start_date": "2025-02-01",
  "end_date": "2026-02-01",
  "premium_amount": "150.00",
  "coverages": [
    {
      "id": "uuid",
      "coverage_type": "LIFE",
      "coverage_amount": "100000.00",
      "description": "..."
    }
  ],
  "documents": [],
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

---

### PATCH /api/policies/policies/{id}/
Actualizar datos de una póliza (no el estado — ese tiene su propio endpoint).

**Request**
```json
{
  "premium_amount": "175.00",
  "end_date": "2027-02-01"
}
```

**Response 200** — póliza actualizada completa.

**Kafka event emitido**: `policy.updated`

**Errores**
- 400 — intentar modificar una póliza CANCELLED o EXPIRED
- 404 — póliza no encontrada

---

### POST /api/policies/policies/{id}/cancel/
Cancelar una póliza activa.

**Request**
```json
{
  "reason": "Solicitud del cliente por cambio de proveedor"
}
```

**Response 200**
```json
{
  "id": "uuid",
  "status": "CANCELLED",
  "cancelled_at": "2025-01-15T10:00:00Z",
  "cancellation_reason": "Solicitud del cliente por cambio de proveedor"
}
```

**Kafka event emitido**: `policy.cancelled`

**Errores**
- 400 — póliza ya está CANCELLED o EXPIRED
- 404 — póliza no encontrada

---

### GET /api/policies/policies/{id}/verify/
Endpoint interno — verifica si una póliza existe y está activa. Llamado por claims-service.

**Response 200**
```json
{
  "id": "uuid",
  "status": "ACTIVE",
  "customer_id": "uuid",
  "policy_type": "LIFE",
  "is_valid": true
}
```

**Response 200** (póliza cancelada)
```json
{
  "id": "uuid",
  "status": "CANCELLED",
  "is_valid": false,
  "reason": "Policy is cancelled"
}
```

**Errores**
- 404 — póliza no existe

---

## claims-service

### GET /api/claims/health/
**Response 200**
```json
{
  "status": "ok",
  "service": "claims-service",
  "version": "0.1.0",
  "database": "ok",
  "kafka": "ok",
  "policy_service": "ok"
}
```

---

### POST /api/claims/claims/
Reportar un nuevo siniestro.

**Request**
```json
{
  "policy_id": "uuid-de-la-poliza",
  "claimant_name": "María García López",
  "claimant_email": "maria.garcia@email.com",
  "incident_date": "2025-01-10",
  "incident_type": "ACCIDENTE",
  "description": "Accidente de tráfico en la A-6, km 45. Colisión con otro vehículo.",
  "estimated_damage": "8500.00",
  "location": "Autovía A-6, km 45, Madrid"
}
```

**Proceso interno**:
1. Llamada HTTP síncrona a `GET /api/policies/policies/{policy_id}/verify/`
2. Si la póliza no existe o está cancelled → 400
3. Si es válida → crear Claim con status `FILED`
4. Emitir Kafka event `claim.filed`

**Response 201**
```json
{
  "id": "uuid",
  "claim_number": "CLM-2025-000001",
  "policy_id": "uuid",
  "claimant_name": "María García López",
  "claimant_email": "maria.garcia@email.com",
  "incident_date": "2025-01-10",
  "incident_type": "ACCIDENTE",
  "description": "...",
  "estimated_damage": "8500.00",
  "location": "...",
  "status": "FILED",
  "filed_at": "2025-01-15T10:00:00Z"
}
```

**Kafka event emitido**: `claim.filed`

**Errores**
- 400 — policy_id no existe / póliza no activa / incident_date en el futuro
- 503 — policy-service no disponible (timeout)

---

### GET /api/claims/claims/
Listar siniestros con filtros.

**Query params**
- `page`, `page_size`
- `status` — `FILED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `RESOLVED`
- `policy_id` — UUID
- `incident_type` — `ACCIDENTE`, `ROBO`, `INCENDIO`, `INUNDACION`, `OTRO`
- `ordering` — `filed_at`, `-filed_at`

**Response 200** — lista paginada estándar.

---

### GET /api/claims/claims/{id}/
Detalle de siniestro con historial de estados.

**Response 200**
```json
{
  "id": "uuid",
  "claim_number": "CLM-2025-000001",
  "policy_id": "uuid",
  "claimant_name": "María García López",
  "incident_date": "2025-01-10",
  "incident_type": "ACCIDENTE",
  "description": "...",
  "estimated_damage": "8500.00",
  "approved_amount": null,
  "status": "UNDER_REVIEW",
  "filed_at": "2025-01-15T10:00:00Z",
  "documents": [],
  "status_history": [
    {
      "from_status": null,
      "to_status": "FILED",
      "changed_at": "2025-01-15T10:00:00Z",
      "notes": "Siniestro reportado"
    },
    {
      "from_status": "FILED",
      "to_status": "UNDER_REVIEW",
      "changed_at": "2025-01-16T09:00:00Z",
      "notes": "Asignado a perito García"
    }
  ]
}
```

---

### POST /api/claims/claims/{id}/transition/
Cambiar el estado de un siniestro.

**Request**
```json
{
  "new_status": "APPROVED",
  "notes": "Daños confirmados por el perito. Aprobado por importe de 7.200€",
  "approved_amount": "7200.00"
}
```

**Transiciones válidas**:
- `FILED → UNDER_REVIEW`
- `UNDER_REVIEW → APPROVED` (requiere `approved_amount`)
- `UNDER_REVIEW → REJECTED` (requiere `notes`)
- `APPROVED → RESOLVED`
- `REJECTED → RESOLVED`

**Response 200**
```json
{
  "id": "uuid",
  "status": "APPROVED",
  "approved_amount": "7200.00",
  "updated_at": "2025-01-17T14:00:00Z"
}
```

**Kafka event emitido**: `claim.status_changed` o `claim.resolved`

**Errores**
- 400 — transición inválida (con mensaje indicando cuáles son válidas)
- 400 — `approved_amount` faltante al aprobar
- 404 — siniestro no encontrado

---

## notification-service

### GET /api/notifications/health/
**Response 200**
```json
{
  "status": "ok",
  "service": "notification-service",
  "database": "ok",
  "redis": "ok",
  "celery": "ok"
}
```

---

### GET /api/notifications/notifications/
Historial de notificaciones enviadas.

**Query params**
- `page`, `page_size`
- `status` — `PENDING`, `SENT`, `FAILED`
- `event_type` — `policy.created`, `claim.filed`, etc.
- `ordering` — `created_at`, `-created_at`

**Response 200**
```json
{
  "count": 890,
  "results": [
    {
      "id": "uuid",
      "event_type": "claim.filed",
      "recipient_email": "maria.garcia@email.com",
      "status": "SENT",
      "sent_at": "2025-01-15T10:00:15Z",
      "created_at": "2025-01-15T10:00:05Z"
    }
  ]
}
```

---

### GET /api/notifications/notifications/{id}/
Detalle de notificación con log de intentos.

**Response 200**
```json
{
  "id": "uuid",
  "event_type": "claim.filed",
  "recipient_email": "maria.garcia@email.com",
  "status": "SENT",
  "payload": {
    "claim_number": "CLM-2025-000001",
    "incident_type": "ACCIDENTE"
  },
  "logs": [
    {
      "attempt_number": 1,
      "sent_at": "2025-01-15T10:00:15Z",
      "error_message": null
    }
  ]
}
```

---

## audit-service

### GET /api/audit/health/
**Response 200**
```json
{
  "status": "ok",
  "service": "audit-service",
  "database": "ok",
  "kafka": "ok"
}
```

---

### GET /api/audit/events/
Listar eventos de auditoría. Read-only.

**Query params**
- `page`, `page_size`
- `entity_type` — `policy`, `claim`
- `entity_id` — UUID de la entidad
- `event_type` — `policy.created`, `claim.filed`, etc.
- `kafka_topic` — topic exacto
- `from_date` — ISO 8601
- `to_date` — ISO 8601
- `ordering` — `occurred_at` (default), `-occurred_at`

**Response 200**
```json
{
  "count": 12450,
  "next": "...",
  "results": [
    {
      "id": "uuid",
      "kafka_topic": "policy.created",
      "kafka_offset": 1042,
      "entity_type": "policy",
      "entity_id": "uuid",
      "event_type": "policy.created",
      "occurred_at": "2025-01-15T10:00:00Z",
      "recorded_at": "2025-01-15T10:00:01Z"
    }
  ]
}
```

---

### GET /api/audit/events/{id}/
Detalle completo de un evento, incluyendo el payload del evento Kafka.

**Response 200**
```json
{
  "id": "uuid",
  "kafka_topic": "claim.status_changed",
  "kafka_offset": 2318,
  "entity_type": "claim",
  "entity_id": "uuid",
  "event_type": "claim.status_changed",
  "payload": {
    "claim_id": "uuid",
    "claim_number": "CLM-2025-000001",
    "from_status": "FILED",
    "to_status": "UNDER_REVIEW",
    "changed_at": "2025-01-16T09:00:00Z",
    "notes": "Asignado a perito García"
  },
  "occurred_at": "2025-01-16T09:00:00Z",
  "recorded_at": "2025-01-16T09:00:01Z"
}
```

---

## Tabla Resumen de Endpoints

| Método | Endpoint | Servicio | Auth |
|---|---|---|---|
| GET | `/api/policies/health/` | policy | No |
| POST | `/api/policies/customers/` | policy | JWT |
| GET | `/api/policies/customers/` | policy | JWT |
| GET | `/api/policies/customers/{id}/` | policy | JWT |
| POST | `/api/policies/policies/` | policy | JWT |
| GET | `/api/policies/policies/` | policy | JWT |
| GET | `/api/policies/policies/{id}/` | policy | JWT |
| PATCH | `/api/policies/policies/{id}/` | policy | JWT |
| POST | `/api/policies/policies/{id}/cancel/` | policy | JWT |
| GET | `/api/policies/policies/{id}/verify/` | policy | Service token |
| GET | `/api/claims/health/` | claims | No |
| POST | `/api/claims/claims/` | claims | JWT |
| GET | `/api/claims/claims/` | claims | JWT |
| GET | `/api/claims/claims/{id}/` | claims | JWT |
| POST | `/api/claims/claims/{id}/transition/` | claims | JWT |
| GET | `/api/notifications/health/` | notification | No |
| GET | `/api/notifications/notifications/` | notification | JWT |
| GET | `/api/notifications/notifications/{id}/` | notification | JWT |
| GET | `/api/audit/health/` | audit | No |
| GET | `/api/audit/events/` | audit | JWT |
| GET | `/api/audit/events/{id}/` | audit | JWT |
| GET | `/api/policies/metrics/` | policy | JWT |
| GET | `/api/claims/metrics/` | claims | JWT |
| GET | `/api/notifications/metrics/` | notification | JWT |
| WS | `ws://gateway/ws/events/?token=<jwt>` | audit-service (Channels) | JWT query param |

---

## Formato de Errores Estándar

Todos los servicios devuelven el mismo formato de error:

```json
{
  "error": {
    "code": "POLICY_CANCELLED",
    "message": "No se puede crear un siniestro sobre una póliza cancelada.",
    "details": {
      "policy_id": "uuid",
      "policy_status": "CANCELLED"
    }
  },
  "request_id": "x-request-id-propagado-por-el-gateway"
}
```

**Regla**: nunca mensajes técnicos al cliente. Siempre lenguaje de negocio con contexto útil.

---

## Kafka Event Schemas

### policy.created
```json
{
  "event_id": "uuid",
  "event_type": "policy.created",
  "occurred_at": "2025-01-15T10:00:00Z",
  "service": "policy-service",
  "data": {
    "policy_id": "uuid",
    "policy_number": "POL-2025-000001",
    "customer_id": "uuid",
    "customer_email": "maria.garcia@email.com",
    "customer_name": "María García López",
    "policy_type": "LIFE",
    "premium_amount": "150.00",
    "start_date": "2025-02-01",
    "end_date": "2026-02-01"
  }
}
```

### claim.filed
```json
{
  "event_id": "uuid",
  "event_type": "claim.filed",
  "occurred_at": "2025-01-15T10:00:00Z",
  "service": "claims-service",
  "data": {
    "claim_id": "uuid",
    "claim_number": "CLM-2025-000001",
    "policy_id": "uuid",
    "claimant_name": "María García López",
    "claimant_email": "maria.garcia@email.com",
    "incident_type": "ACCIDENTE",
    "incident_date": "2025-01-10",
    "estimated_damage": "8500.00"
  }
}
```

### claim.status_changed
```json
{
  "event_id": "uuid",
  "event_type": "claim.status_changed",
  "occurred_at": "2025-01-16T09:00:00Z",
  "service": "claims-service",
  "data": {
    "claim_id": "uuid",
    "claim_number": "CLM-2025-000001",
    "claimant_email": "maria.garcia@email.com",
    "from_status": "FILED",
    "to_status": "UNDER_REVIEW",
    "notes": "Asignado a perito García"
  }
}
```

Todos los eventos siguen el mismo wrapper con `event_id`, `event_type`, `occurred_at`, `service`, y `data`.

---

## WebSocket — Dashboard en Tiempo Real

El dashboard Next.js se conecta a Django Channels via WebSocket para recibir eventos Kafka en tiempo real.

### Endpoint WebSocket

```
ws://gateway/ws/events/?token=<jwt_access_token>
```

**Autenticación**: JWT en query param (el browser no permite headers custom en WS handshake).

**Flujo de conexión**:
```
1. Frontend abre conexión: ws://gateway/ws/events/?token=<jwt>
2. Channels middleware valida el JWT
3. Si válido → conexión aceptada, cliente añadido al grupo "events"
4. Si inválido → conexión cerrada con código 4001
5. En cada evento Kafka procesado → push a todos los clientes del grupo "events"
```

### Formato de mensaje recibido por el cliente

```json
{
  "type": "kafka_event",
  "event_type": "policy.created",
  "occurred_at": "2025-01-15T10:00:00Z",
  "service": "policy-service",
  "data": {
    "policy_id": "uuid",
    "policy_number": "POL-2025-000001",
    "customer_name": "María García López",
    "policy_type": "LIFE"
  }
}
```

### Mensaje de heartbeat (keepalive)

El server envía un ping cada 30 segundos. El cliente debe responder con pong para mantener la conexión activa:

```json
{"type": "ping"}  ← server → client
{"type": "pong"}  ← client → server
```

### Reconexión automática (frontend)

```typescript
// lib/ws.ts
// Si la conexión cae, el cliente reintenta con backoff exponencial:
// 1s → 2s → 4s → 8s → 16s → max 30s
```

---

## API de Métricas del Dashboard

Endpoints de agregación para las tarjetas del dashboard. Añadidos en cada servicio que expone sus propios datos.

### GET /api/policies/metrics/
Métricas de pólizas para el dashboard. Sin paginación.

**Response 200**
```json
{
  "active_policies": 430,
  "policies_today": 12,
  "policies_by_type": {
    "LIFE": 180,
    "HOME": 120,
    "AUTO": 95,
    "HEALTH": 25,
    "BUSINESS": 10
  },
  "total_premium_active": "64500.00"
}
```

### GET /api/claims/metrics/
Métricas de siniestros para el dashboard.

**Response 200**
```json
{
  "open_claims": 47,
  "claims_today": 5,
  "claims_by_status": {
    "FILED": 12,
    "UNDER_REVIEW": 20,
    "APPROVED": 10,
    "REJECTED": 5,
    "RESOLVED": 890
  },
  "avg_resolution_days": 8.3
}
```

### GET /api/notifications/metrics/
Métricas de notificaciones para el dashboard.

**Response 200**
```json
{
  "sent_today": 34,
  "failed_today": 2,
  "pending": 0,
  "success_rate_7d": 98.5
}
```

---

## Paginación

Todos los endpoints de lista usan paginación basada en página (no cursor), excepto audit-service que usa cursor-based por volumen.

**Paginación estándar (policy, claims, notifications)**:
```json
{
  "count": 430,
  "next": "/api/policies/policies/?page=2",
  "previous": null,
  "page_size": 20,
  "results": [...]
}
```

**Query params de paginación**: `page` (default 1), `page_size` (default 20, max 100).

**Cursor-based (audit-service)**:
```json
{
  "next": "/api/audit/events/?cursor=cD0yMDI1LTAxLTE1",
  "previous": null,
  "results": [...]
}
```
El cursor está codificado en base64. No se puede saltar a una página arbitraria — solo siguiente/anterior. Esto garantiza rendimiento constante para millones de eventos.
