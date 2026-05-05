# Skill: nueva Celery task

Añade una tarea asíncrona Celery en notification-service. Uso: `/new-celery-task [nombre-tarea]`.

Ejemplo: `/new-celery-task send-sms-notification`

## Cuándo usar Celery en RiskCore

Celery se usa **solo en notification-service** para tareas lentas que no deben bloquear el Kafka consumer:
- Envío de emails (SMTP puede tardar 1-2s)
- Cualquier IO externo (webhooks, SMS, etc.)

El flujo siempre es: `Kafka consumer recibe evento → crea Notification(status=PENDING) → dispara Celery task → task hace el trabajo lento`

## Task en `apps/notifications/tasks.py`

```python
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,       # 1 minuto entre reintentos
    autoretry_for=(Exception,),   # reintenta en cualquier excepción
    acks_late=True,               # ack después de completar (no al recibir)
)
def [nombre_task](self, notification_id: str) -> None:
    from apps.notifications.models import Notification, NotificationLog

    notification = Notification.objects.get(id=notification_id)

    try:
        # --- lógica de la task aquí ---
        # ejemplo: enviar email
        # send_mail(...)
        
        notification.status = "SENT"
        notification.save()
        NotificationLog.objects.create(
            notification=notification,
            attempt_number=self.request.retries + 1,
            error_message=None,
        )
        logger.info("[nombre_task]_success", notification_id=notification_id)

    except Exception as exc:
        notification.status = "FAILED"
        notification.save()
        NotificationLog.objects.create(
            notification=notification,
            attempt_number=self.request.retries + 1,
            error_message=str(exc),
        )
        logger.error("[nombre_task]_failed", notification_id=notification_id, error=str(exc))
        raise self.retry(exc=exc)
```

## Cómo disparar la task desde el consumer

```python
# En apps/notifications/consumers.py, dentro del handler del evento:
def _handle_[evento](self, payload: dict) -> None:
    notification = Notification.objects.create(
        event_type=payload["event_type"],
        recipient_email=payload["data"]["customer_email"],
        status="PENDING",
        payload=payload["data"],
    )
    # Disparar la task de forma asíncrona
    [nombre_task].delay(str(notification.id))
```

## Configuración Celery — `config/celery.py`

```python
from celery import Celery
from decouple import config

app = Celery("notification_service")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.update(
    broker_url=config("REDIS_URL"),
    result_backend=config("REDIS_URL"),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
)
```

## docker-compose — worker Celery

```yaml
notification-worker:
  build: ./notification-service/
  command: celery -A config.celery worker --loglevel=info --concurrency=4
  env_file: ./notification-service/.env
  depends_on:
    - redis
    - notification-db
  restart: unless-stopped

notification-flower:
  build: ./notification-service/
  command: celery -A config.celery flower --port=5555
  ports:
    - "5555:5555"
  depends_on:
    - redis
  restart: unless-stopped
```

## Checklist

- [ ] Task usa `bind=True` para acceder a `self.retry()`
- [ ] `acks_late=True` para no perder tasks si el worker cae
- [ ] `autoretry_for=(Exception,)` con `max_retries=3` y `default_retry_delay=60`
- [ ] Cada intento guarda un `NotificationLog` con el resultado
- [ ] Notification.status se actualiza a SENT o queda PENDING si falla
- [ ] Logs con `logger.info`/`logger.error` siempre incluyen `notification_id`
- [ ] Test de la task en `tests/test_tasks.py` (mail mockeado con `unittest.mock`)
- [ ] Test de fallo: excepción → status FAILED + log guardado + retry programado
