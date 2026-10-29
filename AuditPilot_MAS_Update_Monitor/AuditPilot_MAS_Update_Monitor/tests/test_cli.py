import importlib.util
import json
from auditpilot.models import CollectionResult, SourceDocument


def test_collection_export_works_without_model_configuration(monkeypatch, tmp_path):
    assert importlib.util.find_spec("auditpilot.cli") is not None, "CLI is missing"
    from auditpilot.cli import main
    from auditpilot.collector import MASCollector
    source = SourceDocument(url="https://www.mas.gov.sg/regulation/notices/notice-626", title="Notice 626", text="Synthetic test fixture, not a real regulatory publication.", provenance="test_fixture")
    monkeypatch.setattr(MASCollector, "collect", lambda self, urls=None: CollectionResult(documents=[source], coverage_complete=True))
    output = tmp_path / "collection.json"
    assert main(["collect", "--out", str(output)]) == 0
    assert json.loads(output.read_text())["documents"][0]["provenance"] == "test_fixture"


def test_cli_exports_portable_events_without_llm(tmp_path):
    assert importlib.util.find_spec("auditpilot.cli") is not None, "CLI is missing"
    from auditpilot.cli import main
    from auditpilot.storage import Store
    from tests.test_storage import event
    db = tmp_path / "db.sqlite"
    Store(db).save_event(event())
    output = tmp_path / "events.json"
    assert main(["export", "--db", str(db), "--out", str(output)]) == 0
    assert json.loads(output.read_text())["total"] == 1


def test_analyze_fails_clearly_without_configured_model(monkeypatch, tmp_path):
    assert importlib.util.find_spec("auditpilot.cli") is not None, "CLI is missing"
    from auditpilot.cli import main
    monkeypatch.delenv("AUDITPILOT_LLM_MODEL", raising=False)
    input_file = tmp_path / "collection.json"
    input_file.write_text(CollectionResult().model_dump_json())
    assert main(["analyze", "--input", str(input_file), "--db", str(tmp_path / "db.sqlite"), "--out", str(tmp_path / "result.json")]) == 2
