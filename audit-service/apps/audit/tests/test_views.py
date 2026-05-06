import uuid

import pytest

from .conftest import AuditEventFactory


@pytest.mark.django_db
def test_list_events_returns_200(client):
    AuditEventFactory.create_batch(3)
    response = client.get("/api/audit/events/")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_list_events_filter_by_event_type(client):
    AuditEventFactory(event_type="policy.created")
    AuditEventFactory(event_type="claim.filed")
    response = client.get("/api/audit/events/?event_type=policy.created")
    assert response.status_code == 200
    data = response.json()
    assert all(e["event_type"] == "policy.created" for e in data["results"])


@pytest.mark.django_db
def test_list_events_filter_by_entity_id(client):
    target = AuditEventFactory(entity_type="policy")
    AuditEventFactory(entity_type="policy")
    response = client.get(f"/api/audit/events/?entity_id={target.entity_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["entity_id"] == str(target.entity_id)


@pytest.mark.django_db
def test_list_events_filter_by_entity_type(client):
    AuditEventFactory(entity_type="policy")
    AuditEventFactory(entity_type="claim")
    response = client.get("/api/audit/events/?entity_type=claim")
    assert response.status_code == 200
    data = response.json()
    assert all(e["entity_type"] == "claim" for e in data["results"])


@pytest.mark.django_db
def test_list_events_filter_by_kafka_topic(client):
    AuditEventFactory(kafka_topic="policy.created", event_type="policy.created")
    AuditEventFactory(kafka_topic="claim.filed", event_type="claim.filed")
    response = client.get("/api/audit/events/?kafka_topic=claim.filed")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["event_type"] == "claim.filed"


@pytest.mark.django_db
def test_list_events_filter_by_from_date(client):
    AuditEventFactory()
    response = client.get("/api/audit/events/?from_date=2020-01-01")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


@pytest.mark.django_db
def test_list_events_filter_by_to_date(client):
    AuditEventFactory()
    response = client.get("/api/audit/events/?to_date=2099-12-31")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


@pytest.mark.django_db
def test_retrieve_event_returns_payload(client):
    event = AuditEventFactory()
    response = client.get(f"/api/audit/events/{event.pk}/")
    assert response.status_code == 200
    data = response.json()
    assert "payload" in data
    assert data["event_id"] == event.event_id


@pytest.mark.django_db
def test_retrieve_nonexistent_event_returns_404(client):
    response = client.get(f"/api/audit/events/{uuid.uuid4()}/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "AUDIT_EVENT_NOT_FOUND"


@pytest.mark.django_db
def test_post_events_not_allowed(client):
    response = client.post(
        "/api/audit/events/", data={}, content_type="application/json"
    )
    assert response.status_code == 405


@pytest.mark.django_db
def test_put_event_not_allowed(client):
    event = AuditEventFactory()
    response = client.put(
        f"/api/audit/events/{event.pk}/", data={}, content_type="application/json"
    )
    assert response.status_code == 405


@pytest.mark.django_db
def test_delete_event_not_allowed(client):
    event = AuditEventFactory()
    response = client.delete(f"/api/audit/events/{event.pk}/")
    assert response.status_code == 405
