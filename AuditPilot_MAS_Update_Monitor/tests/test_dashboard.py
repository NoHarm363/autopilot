from pathlib import Path
import pytest
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
import httpx


def test_dashboard_shows_empty_state_without_fabricating_updates(monkeypatch):
    path = Path(__file__).parents[1] / "dashboard.py"
    assert path.exists(), "Dashboard is missing"
    def get(url, **kwargs):
        data = {"/events": {"items": [], "total": 0}, "/rollup": {"items": []}, "/runs": {"items": []}}[httpx.URL(url).path]
        return httpx.Response(200, json=data, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", get)
    app = AppTest.from_file(str(path)).run(timeout=15)
    assert not app.exception
    assert any("No assessed events" in x.value for x in app.info)
    assert any("Human review" in x.value for x in app.warning)
