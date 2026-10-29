import pytest

URL = "https://www.mas.gov.sg/regulation/notices/notice-626"
HTML = b'''<html><head><title>MAS</title></head><body><nav>Noise</nav><main><h1>Notice 626 AML</h1><p>Last Revised Date: 30 June 2025</p><p>A bank shall identify the beneficial owners of the customer.</p><p>This amendment takes effect from 1 July 2025.</p><a href="/-/media/notice-626.pdf">View Notice 626</a></main><footer>Copyright</footer></body></html>'''


def test_html_extracts_main_content_and_evidenced_dates():
    from auditpilot.collector import parse_document, canonical_url
    s = parse_document(URL, HTML, "text/html", provenance="test_fixture")
    assert s.title == "Notice 626 AML"
    assert "Noise" not in s.text and "Copyright" not in s.text
    assert s.revised_date.isoformat() == "2025-06-30"
    assert s.effective_date.isoformat() == "2025-07-01"
    assert s.date_evidence["effective_date"] in s.text
    assert s.links == ["https://www.mas.gov.sg/-/media/notice-626.pdf"]
    assert canonical_url(URL + "#section") == URL


def test_rejects_http_200_block_pages():
    from auditpilot.collector import parse_document, canonical_url
    with pytest.raises(ValueError, match="blocked"):
        parse_document(URL, b'<html><h1>Maintenance</h1><p>Sorry, this service is currently unavailable. Please try accessing the page using a different device.</p></html>', "text/html")
    with pytest.raises(ValueError):
        canonical_url("https://www.mas.gov.sg.evil.example/test")


def test_pdf_extracts_actual_text_and_rejects_error_pdf():
    from auditpilot.collector import parse_document
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "MAS Notice 626\nA bank shall identify beneficial owners and monitor suspicious transactions.\nLast revised on 30 June 2025")
    s = parse_document(URL, doc.tobytes(), "application/pdf", provenance="test_fixture")
    assert "[Page 1]" in s.text
    assert s.revised_date.isoformat() == "2025-06-30"
    page.insert_text((50, 150), "Sorry, this service is currently unavailable")
    with pytest.raises(ValueError, match="blocked"):
        parse_document(URL, doc.tobytes(), "application/pdf")
    doc.close()


def test_collection_tracks_failures_budget_and_rejects_external_redirect():
    from auditpilot.collector import MASCollector
    import httpx
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.url.path.endswith("notice-626"):
            return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
        return httpx.Response(302, headers={"location": "https://evil.example/document"})
    c = MASCollector(max_pages=2, delay=0, transport=httpx.MockTransport(handler))
    result = c.collect([URL, "https://www.mas.gov.sg/regulation/notices/notice-psn01"])
    assert len(result.documents) == 1
    assert result.coverage_complete is False
    assert result.issues
    assert not any("evil.example" in url for url in calls)


def test_robots_denial_is_not_bypassed():
    from auditpilot.collector import MASCollector
    import httpx
    def handler(request):
        assert request.url.path == "/robots.txt"
        return httpx.Response(200, text="User-agent: *\nDisallow: /")
    result = MASCollector(delay=0, transport=httpx.MockTransport(handler)).collect([URL])
    assert not result.documents
    assert "robots" in result.issues[0].reason
