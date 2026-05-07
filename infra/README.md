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
```

## Acceso

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki API**: http://localhost:3100

## Añadir un dashboard nuevo

1. Crear el JSON en `grafana/dashboards/`
2. El file provider lo carga automáticamente (intervalo de escaneo: 30s)
3. Si se edita desde la UI, exportar el JSON y commitearlo

## Añadir una alerta nueva

1. Añadir la regla en `grafana/provisioning/alerting/rules.yml`
2. La regla debe tener un `uid` único
3. Reiniciar Grafana o esperar al reload de provisioning
