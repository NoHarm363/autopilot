import importlib.util
from tests.test_storage import event


def test_evaluation_scores_retrieval_and_evidence_not_unmeasured_hallucinations():
    assert importlib.util.find_spec("auditpilot.evaluation") is not None, "Evaluation is missing"
    from auditpilot.evaluation import evaluate
    first = event()
    rows = [{"source_url": first.source.url, "sub_areas": ["customer_due_diligence"]}, {"source_url": "https://www.mas.gov.sg/regulation/notices/another-notice", "sub_areas": ["sanctions_proliferation"]}]
    scores = evaluate([first], rows)
    assert scores["source_url_recall"] == 0.5
    assert scores["supported_quote_fraction"] == 1
    assert scores["matched_sub_area_accuracy"] == 1
    first.assessment.claims[0].quote = "Not in MAS source"
    assert evaluate([first], rows)["supported_quote_fraction"] == 0
    assert evaluate([], rows)["supported_quote_fraction"] is None
