import pytest
import httpx
import json
from auditpilot.models import SourceDocument
from tests.helpers import model_response

def source():
    return SourceDocument(url="https://www.mas.gov.sg/regulation/notices/notice-626", title="Notice 626", text="A bank shall identify the beneficial owners of the customer.", provenance="test_fixture")

def test_configuration_is_llm_only(monkeypatch):
    from auditpilot.assessment import make_assessor_from_env, LLMAssessor
    monkeypatch.setenv("AUDITPILOT_LLM_PROVIDER", "rules")
    with pytest.raises(ValueError, match="LLM-only"):
        make_assessor_from_env()
    monkeypatch.setenv("AUDITPILOT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AUDITPILOT_LLM_MODEL", "qwen-test")
    assert isinstance(make_assessor_from_env(), LLMAssessor)
    with pytest.raises(ValueError):
        LLMAssessor("openai", "http://remote.example/v1", "model")

def test_verifier_rejects_invented_quotes_and_paraphrases():
    from auditpilot.assessment import verify_assessment
    s = source(); a = model_response(s)
    assert verify_assessment(s, a) == []
    a.claims[0].statement = "MAS fined DBS ten million dollars."
    assert "verbatim" in verify_assessment(s, a)[0]
    a.claims[0].quote = a.claims[0].statement
    assert "absent" in verify_assessment(s, a)[0]

def test_openai_structured_request():
    from auditpilot.assessment import LLMAssessor
    s = source()
    def handler(request):
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert "untrusted" in body["messages"][0]["content"].lower()
        return httpx.Response(200, json={"choices": [{"message": {"content": model_response(s).model_dump_json()}}]})
    a = LLMAssessor("openai", "https://example.com/v1", "test-model", "test-key", transport=httpx.MockTransport(handler)).assess(s)
    assert a.assessment_method == "openai:test-model"

def test_ollama_structured_output():
    from auditpilot.assessment import LLMAssessor
    s = source()
    def handler(request):
        body = json.loads(request.content)
        assert body["stream"] is False
        assert "properties" in body["format"]
        return httpx.Response(200, json={"message": {"content": model_response(s).model_dump_json()}})
    assert LLMAssessor("ollama", "http://localhost:11434", "qwen", transport=httpx.MockTransport(handler)).assess(s).assessment_method == "ollama:qwen"

