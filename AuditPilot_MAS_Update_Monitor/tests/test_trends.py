from datetime import datetime, timedelta, timezone
from auditpilot.models import Assessment, Claim, PolicyEvent, SourceDocument


def make_event(days, area="customer_due_diligence", provenance="live", change="updated"):
    s = SourceDocument(url="https://www.mas.gov.sg/regulation/notices/notice-626", title="Notice 626", text="A bank shall identify beneficial owners.", provenance=provenance)
    a = Assessment(summary=s.text, sub_areas=[area], risk_level="medium", risk_rationale="Provisional", impacted_population="Banks", actual_impact="Unknown", recommendations=["Review CDD"], claims=[Claim(statement=s.text, quote=s.text)])
    return PolicyEvent(id=str(days), source=s, assessment=a, verification_status="verified", change_type=change, observed_at=datetime.now(timezone.utc) - timedelta(days=days))


def test_rollup_requires_history_and_excludes_manual_baselines():
    from auditpilot.trends import rollup
    rows = rollup([make_event(1), make_event(2, change="baseline"), make_event(2, provenance="manual_public_snapshot")], window_days=30)
    cdd = next(row for row in rows if row["sub_area"] == "customer_due_diligence")
    assert cdd["trend"] == "insufficient_data"
    assert cdd["current_count"] == 1
    assert cdd["metric"] == "observed_policy_change_review_pressure"


def test_rollup_compares_equal_windows_without_claiming_actual_risk():
    from auditpilot.trends import rollup
    cdd = rollup([make_event(1), make_event(2), make_event(40)], window_days=30)[2]
    assert cdd["trend"] == "rising"
    assert cdd["current_score"] == 4
    assert cdd["previous_score"] == 2
    assert "not measured" in cdd["interpretation"].lower()
