# Load Testing — RiskCore

Locust-based load testing suite for validating system performance under realistic load.

## Quick Start

### Using the web UI (manual testing)

```bash
make load-test-ui
# Open http://localhost:8089
```

### Running a scenario headless

```bash
make load-test-1   # Policy creation (500 users, 2min)
make load-test-2   # Claims filing (300 users, 2min)
make load-test-3   # Audit read-only (1000 users, 2min)
make load-test-4   # Spike test (0→1000 users in 30s)
make load-test-5   # Stress test (up to 5000 users)
```

## Scenarios

| # | File | Target Load | Goal | p95 Target |
|---|---|---|---|---|
| 1 | `scenario_1_policy_creation.py` | 500 users | Create customer → policy → verify | < 500ms |
| 2 | `scenario_2_claims_filing.py` | 300 users | File claim with policy verify (HTTP inter-service) | < 800ms |
| 3 | `scenario_3_audit_read.py` | 1000 users | Read-only audit queries with filters | < 200ms |
| 4 | `scenario_4_spike.py` | 0→1000 in 30s | Measure latency during spike + Kafka consumer lag | — |
| 5 | `scenario_5_stress.py` | 100→5000 users | Find breaking point (stop at 10% error rate) | — |

## Authentication

All scenarios use JWT authentication via `POST /api/auth/token/`. The `on_start` hook obtains a token and adds it to subsequent request headers. Default test credentials:

- **Username**: `test_user`
- **Password**: `test_password`

## Rate Limiting

The gateway enforces rate limits:
- **Anonymous**: 20 requests/minute
- **Authenticated**: 200 requests/minute per IP

For load testing with high concurrency, this may limit throughput. To test without rate limiting, use the gateway container's internal IP or adjust the nginx configuration temporarily.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LOCUST_HOST` | `http://gateway` | Target host for load tests |

## Reports

HTML reports are saved to `infra/load-testing/results/`. They include:
- Requests per second
- Response time percentiles (p50, p95, p99)
- Error rate
- Failure breakdown

## Dashboard

Open Grafana at http://localhost:3000 to monitor system metrics during tests:
- Requests/s per service
- Error rate %
- Latency p50/p95/p99
- Kafka consumer lag

## Prerequisites

```bash
make dev          # Start full stack (or make infra for infrastructure only)
make kafka-setup  # Create Kafka topics
```

## Interpreting Results

| Verdict | Criteria |
|---|---|
| ✅ PASS | p95 < target AND error rate < 1% |
| ⚠️ WARNING | p95 within 50% of target OR error rate 1-5% |
| ❌ FAIL | p95 > target OR error rate > 5% |