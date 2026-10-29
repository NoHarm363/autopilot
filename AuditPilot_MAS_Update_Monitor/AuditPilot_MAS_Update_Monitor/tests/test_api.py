import importlib.util
from fastapi.testclient import TestClient
from auditpilot.storage import Store
from tests.test_storage import event


def test_read_only_api_paginates_events_and_exposes_evidence(tmp_path):
    assert importlib.util.find_spec("auditpilot.api") is not None, "JSON API is missing"
    from auditpilot.api import create_app
    store = Store(tmp_path / "api.db")
    store.save_event(event())
    client = TestClient(create_app(store))
    assert client.get("/health").json()["status"] == "ok"
    response = client.get("/events?limit=1").json()
    assert response["total"] == 1 and response["has_more"] is False
    assert response["items"][0]["human_review_required"] is True
    assert client.get("/events/first").json()["assessment"]["claims"][0]["quote"]
    assert client.get("/events/missing").status_code == 404
    assert client.get("/events?limit=0").status_code == 422
    assert len(client.get("/rollup").json()["items"]) == 4
    assert client.get("/runs").json()["items"] == []
    assert client.get("/schema").json()["properties"]["source"]
    assert client.post("/events", json={}).status_code == 405
