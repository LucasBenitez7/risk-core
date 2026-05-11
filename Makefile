.PHONY: dev infra test lint kafka-setup logs logs-loki shell gateway-test load-test load-test-ui help

# ─── Default ─────────────────────────────────────────
help:
	@echo "RiskCore — Development Commands"
	@echo ""
	@echo "  make help              Show this help"
	@echo ""
	@echo "  make dev              Start full stack (Docker Compose)"
	@echo "  make infra            Start only infrastructure (Kafka + Redis + PG + Grafana)"
	@echo "  make test s=<svc>     Run tests for a service (s=policy)"
	@echo "  make lint             Run ruff + mypy across all services"
	@echo "  make kafka-setup      Create all 6 Kafka topics"
	@echo "  make logs s=<svc>     Tail logs for a service (s=claims)"
	@echo "  make logs-loki svc=<svc> Query JSON logs from Loki (svc=policy)"
	@echo "  make shell s=<svc>    Django shell for a service (s=audit)"
	@echo "  make gateway-test     Run gateway integration test suite"

# ─── Docker Compose ──────────────────────────────────
dev:
	docker compose -f infra/docker-compose.yml up -d

infra:
	docker compose -f infra/docker-compose.yml up -d postgres redis kafka loki promtail prometheus grafana

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

# ─── Loki Logs ──────────────────────────────────────
logs-loki:
	@curl -s "http://localhost:3100/loki/api/v1/query_range?query={service=\"$(svc)-service\"}&limit=50" | python -m json.tool

# ─── Load Testing ───────────────────────────────────────
load-test:
	docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
		-f /mnt/locust/scenario_$(SCENARIO)_policy_creation.py \
		--host=http://gateway-loadtest \
		--headless \
		-u 500 \
		-r 50 \
		-t 2m \
		--html /mnt/locust/results/scenario_$(SCENARIO)_report.html

load-test-1:
	docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
		-f /mnt/locust/scenario_1_policy_creation.py --host=http://gateway-loadtest \
		--headless -u 500 -r 50 -t 2m \
		--html /mnt/locust/results/scenario_1_report.html

load-test-2:
	docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
		-f /mnt/locust/scenario_2_claims_filing.py --host=http://gateway-loadtest \
		--headless -u 300 -r 30 -t 2m \
		--html /mnt/locust/results/scenario_2_report.html

load-test-3:
	docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
		-f /mnt/locust/scenario_3_audit_read.py --host=http://gateway-loadtest \
		--headless -u 1000 -r 100 -t 2m \
		--html /mnt/locust/results/scenario_3_report.html

load-test-4:
	docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
		-f /mnt/locust/scenario_4_spike.py --host=http://gateway-loadtest \
		--headless -u 1000 -r 35 -t 3m \
		--html /mnt/locust/results/scenario_4_report.html

load-test-5:
	docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
		-f /mnt/locust/scenario_5_stress.py --host=http://gateway-loadtest \
		--headless -u 5000 -r 100 -t 10m \
		--html /mnt/locust/results/scenario_5_report.html

load-test-seed:
	docker compose -f infra/docker-compose.yml exec audit-web python manage.py seed_audit_events --count 10000

load-test-ui:
	docker compose -f infra/docker-compose.yml --profile loadtest run --rm locust \
		-f /mnt/locust/locustfile.py --host=http://gateway-loadtest --port 8089

# ─── Gateway ────────────────────────────────────────
gateway-test:
	cd gateway && bash test.sh

# ─── Help ───────────────────────────────────────────
help:
	@echo "RiskCore — Development Commands"
	@echo ""
	@echo "  make help              Show this help"
	@echo ""
	@echo "  make dev              Start full stack (Docker Compose)"
	@echo "  make infra            Start only infrastructure (Kafka + Redis + PG + Grafana)"
	@echo "  make test s=<svc>     Run tests for a service (s=policy)"
	@echo "  make lint             Run ruff + mypy across all services"
	@echo "  make kafka-setup      Create all 6 Kafka topics"
	@echo "  make logs s=<svc>     Tail logs for a service (s=claims)"
	@echo "  make logs-loki svc=<svc> Query JSON logs from Loki (svc=policy)"
	@echo "  make shell s=<svc>    Django shell for a service (s=audit)"
	@echo "  make gateway-test     Run gateway integration test suite"
	@echo "  make load-test SCENARIO=N  Run locust scenario N in headless mode"
	@echo "  make load-test-ui      Run locust web UI on port 8089"
