# Skill: escribir tests

Escribe tests completos para un módulo de RiskCore siguiendo la estrategia de testing del proyecto. Uso: `/write-tests [servicio] [módulo]`.

Ejemplo: `/write-tests policy-service policies`

## Niveles de test en RiskCore

```
E2E (Playwright)     ← solo frontend, en PRs a main
Integration          ← pytest con DB real, cada PR
Unit                 ← pytest con mocks, cada push
```

## Estructura de archivos

```
apps/[dominio]/tests/
├── __init__.py
├── conftest.py         ← factories y fixtures compartidas
├── test_models.py      ← validaciones del modelo, métodos __str__, Meta
├── test_services.py    ← unit tests de services.py (mocks de Kafka y HTTP)
└── test_views.py       ← integration tests de endpoints (DB real)
```

## `conftest.py` — factories con factory-boy

```python
import factory
from factory.django import DjangoModelFactory
from apps.[dominio].models import [Model]

class [Model]Factory(DjangoModelFactory):
    class Meta:
        model = [Model]

    # Definir todos los campos con valores realistas
    id = factory.LazyFunction(uuid.uuid4)
    email = factory.LazyAttribute(lambda o: f"{o.full_name.lower().replace(' ', '.')}@test.com")
    # ...campos específicos del modelo
```

## `test_services.py` — unit tests (mocks)

```python
import pytest
from unittest.mock import patch, MagicMock
from apps.[dominio].services import [Dominio]Service
from .conftest import [Model]Factory

@pytest.mark.django_db
class Test[Dominio]Service:

    def test_create_[entidad]_success(self):
        with patch("apps.[dominio].events.[Dominio]EventProducer.produce_[evento]") as mock_producer:
            result = [Dominio]Service().create_[entidad](data={...})
            
            assert result.id is not None
            assert result.status == "ACTIVE"
            mock_producer.assert_called_once()  # verificar que se emitió el evento

    def test_create_[entidad]_duplicate_raises_error(self):
        existing = [Model]Factory()
        with pytest.raises(ValidationError) as exc_info:
            [Dominio]Service().create_[entidad](data={"dni": existing.dni, ...})
        assert exc_info.value.code == "[ENTIDAD]_DUPLICATE"

    def test_cancel_[entidad]_already_cancelled_raises_error(self):
        entity = [Model]Factory(status="CANCELLED")
        with pytest.raises(ValidationError):
            [Dominio]Service().cancel_[entidad](entity)

    # Para claims-service: mock del HTTP call a policy-service
    def test_file_claim_with_cancelled_policy_raises_error(self):
        with patch("apps.claims.clients.PolicyServiceClient.verify_policy") as mock_client:
            mock_client.return_value = {"status": "CANCELLED", "is_valid": False}
            with pytest.raises(ValidationError) as exc_info:
                ClaimService().file_claim(data={"policy_id": "uuid", ...})
            assert "CANCELLED" in str(exc_info.value)

    def test_file_claim_policy_service_timeout_returns_503(self):
        with patch("apps.claims.clients.PolicyServiceClient.verify_policy") as mock_client:
            mock_client.side_effect = httpx.TimeoutException("timeout")
            with pytest.raises(ServiceUnavailableError):
                ClaimService().file_claim(data={...})
```

## `test_views.py` — integration tests (DB real)

```python
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from .conftest import [Model]Factory

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def authenticated_client(api_client):
    # Autenticar con JWT o usar force_authenticate para tests
    api_client.force_authenticate(user=UserFactory())
    return api_client

@pytest.mark.django_db
class Test[Dominio]Endpoints:

    def test_create_[entidad]_returns_201(self, authenticated_client):
        with patch("apps.[dominio].events.[Dominio]EventProducer.produce_[evento]"):
            response = authenticated_client.post(
                "/api/[dominio]/[entidades]/",
                data={...},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "ACTIVE"

    def test_create_[entidad]_without_auth_returns_401(self, api_client):
        response = api_client.post("/api/[dominio]/[entidades]/", data={...})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_[entidades]_with_status_filter(self, authenticated_client):
        [Model]Factory.create_batch(3, status="ACTIVE")
        [Model]Factory.create_batch(2, status="CANCELLED")
        
        response = authenticated_client.get("/api/[dominio]/[entidades]/?status=ACTIVE")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_cancel_[entidad]_returns_correct_error_format(self, authenticated_client):
        entity = [Model]Factory(status="CANCELLED")
        response = authenticated_client.post(f"/api/[dominio]/[entidades]/{entity.id}/cancel/")
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "code" in response.data["error"]
        assert "message" in response.data["error"]
        assert "request_id" in response.data
```

## `test_consumers.py` — tests de Kafka consumers

```python
import pytest
import json
from unittest.mock import MagicMock, patch
from apps.[dominio].consumers import [Dominio]KafkaConsumer

@pytest.mark.django_db
class Test[Dominio]KafkaConsumer:

    def _make_mock_message(self, payload: dict) -> MagicMock:
        msg = MagicMock()
        msg.error.return_value = None
        msg.value.return_value = json.dumps(payload).encode("utf-8")
        return msg

    def test_process_[evento]_creates_[entidad](self):
        consumer = [Dominio]KafkaConsumer()
        payload = {
            "event_id": "uuid",
            "event_type": "[topic.nombre]",
            "occurred_at": "2025-01-15T10:00:00Z",
            "service": "[nombre]-service",
            "data": { ... }
        }
        msg = self._make_mock_message(payload)
        
        consumer._process_message(msg)
        
        assert [Model].objects.count() == 1
        entity = [Model].objects.first()
        assert entity.[campo] == payload["data"]["[campo]"]
```

## Cobertura — verificar antes de hacer PR

```bash
pytest apps/[dominio]/tests/ -v --cov=apps/[dominio] --cov-report=term-missing
```

Targets: services.py 90%+, views.py 80%+, consumers.py 80%+
