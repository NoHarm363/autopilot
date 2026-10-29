from datetime import datetime, timezone
from auditpilot.models import Assessment, Claim, PolicyEvent, SourceDocument


def event(text="Banks shall identify beneficial owners.", id="first"):
    source = SourceDocument(url="https://www.mas.gov.sg/regulation/notices/notice-626", title="Notice 626", text=text)
    a = Assessment(summary=text, sub_areas=["customer_due_diligence"], risk_level="medium", risk_rationale="Provisional review priority", impacted_population="Banks", actual_impact="Unknown", recommendations=["Review CDD controls"], claims=[Claim(statement=text, quote=text)])
    return PolicyEvent(id=id, source=source, assessment=a, verification_status="verified", change_type="baseline")


def test_store_does_not_make_repeated_fetch_another_update(tmp_path):
    from auditpilot.storage import Store
    store = Store(tmp_path / "events.db")
    e = event()
    assert store.save_event(e) is True
    assert store.save_event(e.model_copy(update={"id": "second"})) is False
    assert len(store.events()) == 1
    assert store.latest_source(e.source.url).text == e.source.text


def test_store_keeps_versions_and_audit_run_history(tmp_path):
    from auditpilot.models import RunReport
    from auditpilot.storage import Store
    store = Store(tmp_path / "events.db")
    first = event()
    second = event("Banks shall identify and verify beneficial owners.", "changed")
    second.change_type = "updated"
    assert store.save_event(first)
    assert store.save_event(second)
    assert store.count_events() == 2
    assert store.get_event("changed").source.text == second.source.text
    now = datetime.now(timezone.utc)
    report = RunReport(run_id="run-1", started_at=now, completed_at=now, status="partial", attempted_urls=[first.source.url], fetched_documents=1, new_events=1, unchanged_documents=0, issues=[], coverage_note="Seed coverage only")
    store.save_run(report)
    assert store.runs()[0].status == "partial"
    assert store.get_event("missing") is None
