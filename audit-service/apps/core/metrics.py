from prometheus_client import Counter, Histogram

kafka_messages_processed_total = Counter(
    "riskcore_kafka_messages_processed_total",
    "Total Kafka messages processed",
    ["topic", "result"],
)

kafka_processing_duration_seconds = Histogram(
    "riskcore_kafka_processing_duration_seconds",
    "Kafka message processing duration in seconds",
    ["topic"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)
