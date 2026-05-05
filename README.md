# RiskCore

Enterprise insurance core microservices system — policies, claims, event-driven Kafka, async notifications, immutable audit log, and real-time dashboard.

## Architecture

```
policy-service (8001) ────┐
claims-service (8002) ────┤
notification-service (8003)┤── Kafka ──► audit-service (8004)
                           │
                   Redis ──┘
```

| Service | Port | Role |
|---|---|---|
| policy-service | 8001 | Customers, policies, coverages |
| claims-service | 8002 | Claims, state machine, status history |
| notification-service | 8003 | Async emails via Celery |
| audit-service | 8004 | Immutable event log + WebSocket streaming |

## Quick Start

```bash
# Clone
git clone git@github.com:LucasBenitez7/risk-core.git
cd risk-core

# Start full stack
make dev

# Health checks
curl http://localhost:8001/health/   # policy-service
curl http://localhost:8002/health/   # claims-service
curl http://localhost:8003/health/   # notification-service
curl http://localhost:8004/health/   # audit-service

# Create Kafka topics
make kafka-setup
```

## Development Commands

See [COMANDOS.md](COMANDOS.md) for the full command reference.

```bash
make dev              # Start full stack
make infra            # Start infrastructure only (Postgres, Redis, Kafka)
make test s=policy    # Run tests for a service
make lint             # Lint all services
make kafka-setup      # Create all 6 Kafka topics
make logs s=claims    # Tail service logs
make shell s=audit    # Django shell
```

## Tech Stack

- **Python 3.13** + **Django 5.2** + **DRF 3.15**
- **Kafka 3.7** (KRaft mode, confluent-kafka)
- **Celery 5.4** + **Redis 7.2** (async notifications)
- **PostgreSQL 16** (database per service)
- **Django Channels 4.1** (WebSocket dashboard)
- **structlog** (JSON structured logging)
- **Grafana + Loki + Prometheus** (observability)
- **Next.js 15** + **TypeScript 5.9** (frontend dashboard)

## Project Structure

```
riskcore/
├── policy-service/          # Customers & policies
├── claims-service/          # Claims & state machine
├── notification-service/    # Email notifications (Celery)
├── audit-service/           # Immutable audit log (Channels)
├── gateway/                 # Nginx reverse proxy
├── frontend/                # Next.js dashboard
├── infra/                   # Docker Compose, Kafka, Grafana
└── docs/                    # Architecture & API documentation
```

## Documentation

| Document | Description |
|---|---|
| [docs/TECHNICAL_DECISIONS.md](docs/TECHNICAL_DECISIONS.md) | Why each technology was chosen |
| [docs/API_DESIGN.md](docs/API_DESIGN.md) | All endpoints with request/response schemas |
| [docs/PHASES.md](docs/PHASES.md) | Development phases and checklists |
| [docs/GUIA_PROYECTO.md](docs/GUIA_PROYECTO.md) | Project guide, architecture, and services |

## Status

Phase 0 — Setup e Infraestructura (in progress)

See [CONTEXT.md](CONTEXT.md) for current project state.

## License

MIT
