from prometheus_client import Counter, Histogram

notifications_sent_total = Counter(
    "riskcore_notifications_sent_total",
    "Total notifications processed",
    ["event_type", "status"],
)

celery_task_duration_seconds = Histogram(
    "riskcore_celery_task_duration_seconds",
    "Celery task execution duration in seconds",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 25.0],
)
