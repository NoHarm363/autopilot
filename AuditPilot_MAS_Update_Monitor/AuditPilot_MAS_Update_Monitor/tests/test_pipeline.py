from auditpilot.models import CollectionResult, SourceDocument
from auditpilot.storage import Store
from tests.helpers import model_response

def collection(text="A bank shall identify beneficial owners and monitor suspicious transactions."):
    return CollectionResult(documents=[SourceDocument(url="https://www.mas.gov.sg/regulation/notices/notice-626", title="Notice 626", text=text, document_type="notice", provenance="test_fixture")], attempted_urls=["https://www.mas.gov.sg/regulation/notices/notice-626"], coverage_complete=True)

class TestModel:
    __test__ = False
    def assess(self, source, diff=None, feedback=None):
        return model_response(source)

def test_pipeline_baselines_then_diffs_updated_documents(tmp_path):
    from auditpilot.pipeline import Monitor
    store = Store(tmp_path / "audit.db"); monitor = Monitor(store, TestModel())
    assert monitor.process(collection()).new_events == 1
    assert store.events()[0].change_type == "baseline"
    assert monitor.process(collection()).new_events == 0
    assert monitor.process(collection("A bank shall identify beneficial owners and monitor suspicious transactions. Banks must screen sanctions lists daily.")).new_events == 1
    latest = store.events()[0]
    assert latest.change_type == "updated" and "Banks must screen sanctions" in latest.diff
    assert latest.verification_status == "verified"

def test_bad_model_does_not_create_substitute_rating(tmp_path):
    from auditpilot.pipeline import Monitor
    class BadModel:
        calls = 0
        def assess(self, source, diff=None, feedback=None):
            self.calls += 1
            a = model_response(source); a.claims[0].quote = "Invented regulation absent from MAS."
            return a
    model = BadModel(); store = Store(tmp_path / "audit.db")
    report = Monitor(store, model).process(collection())
    assert model.calls == 2
    assert store.events() == []
    assert report.status == "partial" and report.issues[0].stage == "assessment"
    assert "no rating" in report.issues[0].reason.lower()

def test_model_outage_does_not_fabricate_events(tmp_path):
    from auditpilot.pipeline import Monitor
    class Offline:
        def assess(self, *args, **kwargs):
            raise ConnectionError("offline")
    store = Store(tmp_path / "audit.db")
    assert Monitor(store, Offline()).process(collection()).status == "partial"
    assert store.count_events() == 0

