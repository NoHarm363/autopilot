import httpx
import json
from auditpilot.assessment import LLMAssessor
from auditpilot.collector import parse_document
from tests.test_assessment import source
from tests.helpers import model_response
from tests.test_collector import HTML, URL


def test_openai_requests_a_strict_schema_with_every_property_required():
    s = source()
    def handler(request):
        schema = json.loads(request.content)["response_format"]["json_schema"]
        assert schema.get("strict") is True
        assert set(schema["schema"]["required"]) == set(schema["schema"]["properties"])
        return httpx.Response(200, json={"choices": [{"message": {"content": model_response(s).model_dump_json()}}]})
    LLMAssessor("openai", "https://example.com/v1", "test", transport=httpx.MockTransport(handler)).assess(s)


def test_guidelines_are_not_mislabelled_as_notices():
    body = HTML.replace(b"Notice 626 AML", b"Guidelines to Notice 626 AML")
    doc = parse_document("https://www.mas.gov.sg/regulation/guidelines/guidelines-to-notice-626", body, "text/html")
    assert doc.document_type == "guideline"


def test_assessment_has_no_rules_default():
    assert type(model_response(source())).model_fields["assessment_method"].default != "rules"
