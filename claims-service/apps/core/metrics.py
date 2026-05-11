from prometheus_client import Counter, Gauge, Histogram

# --- Circuit Breaker (Bloque A) ---
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["target"],
)
circuit_breaker_state_changes_total = Counter(
    "circuit_breaker_state_changes_total",
    "Total circuit breaker state transitions",
    ["target", "from_state", "to_state"],
)

# --- Claims business metrics ---
claims_filed_total = Counter(
    "riskcore_claims_filed_total",
    "Total claims filed",
    ["incident_type"],
)

claims_status_changed_total = Counter(
    "riskcore_claims_status_changed_total",
    "Total claim status transitions",
    ["from_status", "to_status"],
)

# --- Outbox Pattern metrics ---
outbox_pending = Gauge(
    "outbox_pending_total",
    "Eventos en outbox pendientes de publicar",
)
outbox_published_total = Counter(
    "outbox_published_total",
    "Eventos publicados desde outbox",
    ["topic"],
)
outbox_failed_total = Counter(
    "outbox_failed_total",
    "Eventos outbox marcados FAILED tras max retries",
    ["topic"],
)
outbox_lag_seconds = Histogram(
    "outbox_lag_seconds",
    "Latencia entre creacion del OutboxEvent y publicacion a Kafka",
    buckets=[0.05, 0.1, 0.5, 1, 5, 30, 120],
)
