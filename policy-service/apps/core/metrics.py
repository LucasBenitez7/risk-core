from prometheus_client import Counter, Gauge, Histogram

policies_created_total = Counter(
    "riskcore_policies_created_total",
    "Total policies created",
    ["policy_type"],
)

policies_cancelled_total = Counter(
    "riskcore_policies_cancelled_total",
    "Total policies cancelled",
)

# Outbox Pattern metrics
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
