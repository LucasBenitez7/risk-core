# Skill: nuevo evento Kafka

Añade un productor y/o consumidor Kafka para un nuevo evento en RiskCore. Uso: `/new-kafka-event [topic] [servicio-producer] [servicios-consumer]`.

Ejemplo: `/new-kafka-event policy.suspended policy-service audit-service,notification-service`

## Producer — en el servicio que emite el evento

Archivo: `apps/[dominio]/events.py`

```python
import json
import uuid
from django.utils import timezone
from confluent_kafka import Producer
from decouple import config

class [Dominio]EventProducer:
    def __init__(self):
        self.producer = Producer({"bootstrap.servers": config("KAFKA_BOOTSTRAP_SERVERS")})

    def produce_[evento](self, entity: [Model]) -> None:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": "[topic.nombre]",
            "occurred_at": timezone.now().isoformat(),
            "service": "[nombre-servicio]",
            "data": {
                # campos específicos del evento
            },
        }
        self.producer.produce(
            topic="[topic.nombre]",
            key=str(entity.id),
            value=json.dumps(payload).encode("utf-8"),
        )
        self.producer.flush()
```

El producer se llama desde `services.py`, nunca desde `views.py`.

## Consumer — en cada servicio que consume el evento

Archivo: `apps/[dominio]/consumers.py`

```python
import json
import logging
from confluent_kafka import Consumer, KafkaError
from decouple import config

logger = logging.getLogger(__name__)

class [Dominio]KafkaConsumer:
    TOPICS = ["[topic.nombre]"]  # lista de topics que consume

    def __init__(self):
        self.consumer = Consumer({
            "bootstrap.servers": config("KAFKA_BOOTSTRAP_SERVERS"),
            "group.id": "[servicio]-consumers",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,  # commit manual después de procesar
        })

    def start(self):
        self.consumer.subscribe(self.TOPICS)
        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("kafka_error", error=str(msg.error()))
                    continue
                self._process_message(msg)
                self.consumer.commit(msg)  # commit solo después de procesar
        finally:
            self.consumer.close()

    def _process_message(self, msg):
        payload = json.loads(msg.value().decode("utf-8"))
        event_type = payload.get("event_type")
        # dispatch según event_type
        handlers = {
            "[topic.nombre]": self._handle_[evento],
        }
        handler = handlers.get(event_type)
        if handler:
            handler(payload)

    def _handle_[evento](self, payload: dict) -> None:
        data = payload["data"]
        # lógica de procesamiento — si es lenta, delegar a Celery task
        # si es notification-service: crear Notification → disparar Celery task
        # si es audit-service: crear AuditEvent (solo INSERT)
```

Management command para correr el consumer:

Archivo: `apps/[dominio]/management/commands/run_consumer.py`

```python
from django.core.management.base import BaseCommand
from apps.[dominio].consumers import [Dominio]KafkaConsumer

class Command(BaseCommand):
    help = "Run Kafka consumer for [dominio]"

    def handle(self, *args, **options):
        self.stdout.write("Starting Kafka consumer...")
        [Dominio]KafkaConsumer().start()
```

## docker-compose.yml — añadir container del consumer

```yaml
[servicio]-consumer:
  build: ./[servicio]/
  command: python manage.py run_consumer
  env_file: ./[servicio]/.env
  depends_on:
    - kafka
    - [servicio]-db
  restart: unless-stopped
```

## Checklist

- [ ] Producer llama a `flush()` después de `produce()`
- [ ] Consumer usa `enable.auto.commit: False` + commit manual después de procesar
- [ ] Consumer group ID es único por servicio: `[servicio]-consumers`
- [ ] Mensajes lentos (emails, etc.) se delegan a Celery task, nunca en el consumer
- [ ] Nuevo topic añadido al script `infra/kafka/create-topics.sh`
- [ ] Nuevo topic documentado en la tabla de Kafka topics de `AGENTS.md`
- [ ] Tests del consumer en `tests/test_consumers.py` con Kafka mockeado
