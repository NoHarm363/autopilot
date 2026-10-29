import pytest
from pydantic import ValidationError


def test_source_requires_official_mas_https_url():
    from auditpilot.models import SourceDocument
    with pytest.raises(ValidationError):
        SourceDocument(url="https://evil.example/mas", title="Fake", text="a" * 100)


def test_event_retains_fact_evidence_separate_from_audit_judgment():
    from auditpilot.models import Assessment, Claim, PolicyEvent, SourceDocument
    s = SourceDocument(url="https://www.mas.gov.sg/regulation/notices/notice-626", title="Notice 626", text="Banks shall identify beneficial owners.")
    a = Assessment(summary="Source reports a requirement.", sub_areas=["customer_due_diligence"], risk_level="medium", risk_rationale="Review control scope.", impacted_population="Banks", actual_impact="Not quantified in source", recommendations=["Review onboarding controls"], claims=[Claim(statement="Banks shall identify beneficial owners.", quote="Banks shall identify beneficial owners.")])
    e = PolicyEvent(id="1", source=s, assessment=a, verification_status="verified", change_type="baseline")
    assert e.human_review_required is True
    assert e.assessment.claims[0].quote in e.source.text
    assert e.change_type == "baseline"
