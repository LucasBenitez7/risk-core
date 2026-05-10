# RiskCore — Infra de Observabilidad

## Stack

| Servicio | Puerto | Imagen | Notas |
|---|---|---|---|
| Loki | 3100 | `grafana/loki:2.9.14` | Almacenamiento filesystem, retention 7d |
| Promtail | — | `grafana/promtail:2.9.14` | Sidecar, lee logs de Docker vía socket |
| Prometheus | 9090 | `prom/prometheus:v2.55.1` | Scrape `/metrics` de los 4 servicios cada 15s |
| Grafana | 3000 | `grafana/grafana:11.6.0` | Dashboards + alerting provisionados automáticamente |

## Arquitectura

```
[4 servicios Django] ──JSON logs (stdout)──▶ [Promtail] ──▶ [Loki] ──┐
[4 servicios Django] ──/metrics──────▶ [Prometheus]──────────────────┤
                                                                     ├──▶ [Grafana]
[Celery worker]      ──JSON logs (stdout)──▶ [Promtail] ──▶ [Loki] ──┘
```

## Provisioning automático

Al levantar Grafana se carga automáticamente desde `infra/grafana/provisioning/`:

- **Datasources** (`provisioning/datasources/datasources.yml`): Prometheus (default) + Loki
- **Dashboards** (`provisioning/dashboards/dashboards.yml`): File provider desde `/etc/grafana/dashboards/`
- **Alert rules** (`provisioning/alerting/rules.yml`): 4 reglas de alerta pre-configuradas
- **Contact points** (`provisioning/alerting/contact-points.yml`): Webhook dummy en local

## Dashboards incluidos

| Dashboard | UID | Contenido |
|---|---|---|
| Services Overview | `riskcore-services-overview` | Health, throughput, error rate, latency |
| Kafka | `riskcore-kafka` | Message rate, duration p95, consumer logs |
| Celery | `riskcore-celery` | Task rate, success %, duration, task logs |
| Business Metrics | `riskcore-business` | Policies/h, claims by status, notifications |
| Gateway | `riskcore-gateway` | Requests/s, status codes, rate-limiting, latency, error logs |

## Alertas

| Alerta | Condición | Severidad |
|---|---|---|
| Service Down | `up == 0` por 30s | critical |
| High Error Rate | 5xx > 5% por 2min | warning |
| Kafka Consumer Stalled | 0 mensajes en 10min | warning |
| Celery Task Failures | >10% fallos en 5min | warning |

## Configuración local

Los archivos de configuración:

- `loki/loki-config.yml` — Loki single-binary, TSDB, 7d retention
- `promtail/promtail-config.yml` — Docker SD, JSON parsing, labels por container
- `prometheus/prometheus.yml` — 4 scrape jobs (`policy-service`, `claims-service`, `notification-service`, `audit-service`)
- `grafana/provisioning/` — Datasources, dashboards, alerting

## Comandos

```bash
make infra          # Levanta solo infra (PG + Redis + Kafka + Loki + Promtail + Prometheus + Grafana)
make dev            # Levanta todo el stack
make logs-loki svc=policy  # Consulta logs del policy-service en Loki vía API
make gateway-test   # Ejecuta el suite de tests de integración del gateway
```

## Acceso

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki API**: http://localhost:3100
- **Gateway**: http://localhost:8080

## Gateway

El gateway (Nginx) es el punto único de entrada a los servicios. Maneja rate limiting, autenticación JWT y logging JSON.

### Cómo acceder

```bash
curl http://localhost:8080/health/
```

### Obtener JWT

```bash
curl -s -X POST http://localhost:8080/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r .access
```

### Logs JSON en Loki

Los access logs del gateway usan formato JSON y se envían a Loki vía Promtail con label `service=gateway`:

```bash
# Buscar errores 4xx/5xx
curl -s "http://localhost:3100/loki/api/v1/query_range?query={service=\"gateway\"}|json|status=~\"[45]..\"&limit=20"

# Trazar un request_id end-to-end
curl -s "http://localhost:3100/loki/api/v1/query_range?query={service=~\"gateway|.*-service\"}|json|request_id=\"UUID\"&limit=5"
```

### Dashboard Gateway

El dashboard **Gateway** en Grafana (`riskcore-gateway`) muestra:
- Requests/s totales al gateway
- Requests por upstream (policy/claims/notifications/audit)
- Status codes (2xx/4xx/5xx)
- Rate-limiting (429 con `limit_req_status=REJECTED`)
- Latencia p50/p95/p99 (`request_time`)
- Últimos errores con `request_id` para traceabilidad

### Rate limit tiers

| Tier | Límite | Headers |
|---|---|---|
| Sin auth (IP) | 20 req/min | `X-RateLimit-Limit` en headers |
| Con JWT | 200 req/min | — |
| Whitelist admin | Sin límite | — |

## Añadir un dashboard nuevo

1. Crear el JSON en `grafana/dashboards/`
2. El file provider lo carga automáticamente (intervalo de escaneo: 30s)
3. Si se edita desde la UI, exportar el JSON y commitearlo

## Añadir una alerta nueva

1. Añadir la regla en `grafana/provisioning/alerting/rules.yml`
2. La regla debe tener un `uid` único
3. Reiniciar Grafana o esperar al reload de provisioning

## Load Testing

Locust-based load testing suite. Scenarios live in `infra/load-testing/`.

### Escenarios

| # | Archivo | Usuarios | Objetivo |
|---|---|---|---|
| 1 | `scenario_1_policy_creation.py` | 500 | Create customer → policy → verify, p95 < 500ms |
| 2 | `scenario_2_claims_filing.py` | 300 | File claim + transition, p95 < 800ms |
| 3 | `scenario_3_audit_read.py` | 1000 | Read-only audit queries, p95 < 200ms |
| 4 | `scenario_4_spike.py` | 0→1000 | Spike test, observar consumer lag |
| 5 | `scenario_5_stress.py` | hasta 5000 | Stress hasta error rate > 10% |

### Ejecutar

```bash
# Web UI (abrir http://localhost:8089)
make load-test-ui

# Headless por escenario
make load-test-1
make load-test-2
make load-test-3
make load-test-4
make load-test-5
```

### Dashboard

Abrir **Load Testing** (`load-testing`) en Grafana para monitorear durante los tests:
- Requests/s por servicio
- Error rate % (4xx+5xx / total)
- Latencia p50/p95/p99 del gateway
- Kafka consumer lag
- CPU por contenedor

### Reports HTML

Los reports HTML se guardan en `infra/load-testing/results/`:
- `scenario_N_report.html` — statistics, charts, failure breakdown

### Prerequisites

```bash
make dev          # Stack completo corriendo
make kafka-setup   # Topics de Kafka creados
```
