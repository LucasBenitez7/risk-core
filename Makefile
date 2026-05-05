.PHONY: dev infra test lint kafka-setup logs shell help

# ─── Default ─────────────────────────────────────────
help:
	@echo "RiskCore — Development Commands"
	@echo ""
	@echo "  make dev              Start full stack (Docker Compose)"
	@echo "  make infra            Start only infrastructure (Kafka + Redis + PG + Grafana)"
	@echo "  make test s=<svc>     Run tests for a service (s=policy)"
	@echo "  make lint             Run ruff + mypy across all services"
	@echo "  make kafka-setup      Create all 6 Kafka topics"
	@echo "  make logs s=<svc>     Tail logs for a service (s=claims)"
	@echo "  make shell s=<svc>    Django shell for a service (s=audit)"

# ─── Docker Compose ──────────────────────────────────
dev:
	docker compose -f infra/docker-compose.yml up -d

infra:
	docker compose -f infra/docker-compose.yml up -d postgres redis kafka grafana loki prometheus

# ─── Testing ─────────────────────────────────────────
test:
	cd $(s)-service && uv run pytest

# ─── Linting ─────────────────────────────────────────
lint:
	@for dir in policy-service claims-service notification-service audit-service; do \
		echo "=== $$dir ==="; \
		cd $$dir && uv run ruff check . && uv run mypy . || true; \
		cd ..; \
	done

# ─── Kafka ──────────────────────────────────────────
kafka-setup:
	bash infra/kafka/create-topics.sh

# ─── Logs ───────────────────────────────────────────
logs:
	docker compose -f infra/docker-compose.yml logs -f $(s)-web

# ─── Shell ──────────────────────────────────────────
shell:
	docker compose -f infra/docker-compose.yml exec $(s)-web uv run python manage.py shell
