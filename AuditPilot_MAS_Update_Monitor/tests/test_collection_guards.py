import httpx
import pytest
from auditpilot.collector import MASCollector, parse_document
from tests.test_collector import HTML, URL


def test_pdf_url_does_not_accept_html_as_a_regulation():
    with pytest.raises(ValueError, match="PDF"):
        parse_document("https://www.mas.gov.sg/-/media/mas-notice-626.pdf", HTML, "text/html")


def test_collector_respects_mas_crawl_delay(monkeypatch):
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nCrawl-delay: 2\nAllow: /")
        return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
    MASCollector(max_pages=1, delay=0, transport=httpx.MockTransport(handler)).collect([URL])
    assert waits == [2]
