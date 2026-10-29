from pathlib import Path
import pytest
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
import httpx
from tests.test_storage import event


def test_dashboard_renders_source_quotes_and_review_actions(monkeypatch):
    def get(url, **kwargs):
        data = {"/events": {"items": [event().model_dump(mode="json")], "total": 1}, "/rollup": {"items": []}, "/runs": {"items": []}}[httpx.URL(url).path]
        return httpx.Response(200, json=data, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", get)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "dashboard.py")).run(timeout=15)
    assert not app.exception
    assert any("Banks shall identify beneficial owners." in x.value for x in app.code)
    assert any("Review CDD controls" in x.value for x in app.markdown)
