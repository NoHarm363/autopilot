"""Bounded official-source collection. Block pages are failures, not policy updates."""
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from .models import SourceDocument
from .storage import text_hash

BLOCK_PATTERNS = ("sorry, this service is currently unavailable", "performing security verification", "verify you are human", "just a moment", "access denied", "the requested url was rejected", "checking your browser", "attention required")
DATE_TOKEN = r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}"


def canonical_url(url: str) -> str:
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in {"mas.gov.sg", "www.mas.gov.sg"} or p.username or p.password or p.port not in {None, 443}:
        raise ValueError("Only official MAS HTTPS URLs are allowed")
    return urlunsplit(("https", "www.mas.gov.sg", p.path or "/", p.query, ""))


def parse_document(url: str, body: bytes, content_type: str, retrieval_method="direct_http", provenance="live") -> SourceDocument:
    url = canonical_url(url)
    if len(body) > 15_000_000:
        raise ValueError("Document exceeds 15MB safety limit")
    links = []
    if body.lstrip().startswith(b"%PDF"):
        import pymupdf
        with pymupdf.open(stream=body, filetype="pdf") as doc:
            if doc.is_encrypted or len(doc) > 500:
                raise ValueError("Encrypted or oversized PDF is unsupported")
            text = "\n".join(f"[Page {i + 1}]\n{page.get_text()}" for i, page in enumerate(doc))
            title = (doc.metadata or {}).get("title") or next((line.strip() for line in text.splitlines() if len(line.strip()) > 15 and not line.startswith("[Page")), urlsplit(url).path.rsplit("/", 1)[-1])
    else:
        if "pdf" in content_type.lower() or urlsplit(url).path.lower().endswith(".pdf"):
            raise ValueError("Expected PDF but received an HTML/error body")
        if not any(t in content_type.lower() for t in ("html", "text/plain")):
            raise ValueError("Unsupported content type")
        soup = BeautifulSoup(body, "html.parser")
        raw_text = soup.get_text(" ", strip=True).lower()
        if any(p in raw_text for p in BLOCK_PATTERNS):
            raise ValueError("MAS blocked or unavailable page")
        for tag in soup.select("script, style, nav, footer, header, aside, .related-content, .related-resources"):
            tag.decompose()
        main = soup.select_one("main, article, #main-content, .main-content") or soup.body or soup
        h1 = main.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else (soup.title.get_text(" ", strip=True) if soup.title else urlsplit(url).path.rsplit("/", 1)[-1])
        text = main.get_text("\n", strip=True)
        for anchor in main.find_all("a", href=True):
            try:
                link = canonical_url(urljoin(url, anchor["href"]))
                if link != url and link not in links:
                    links.append(link)
            except ValueError:
                pass
    if any(p in text.lower() for p in BLOCK_PATTERNS) or ("maintenance" in title.lower() and len(text) < 2500):
        raise ValueError("MAS blocked or unavailable document")
    if len(text.strip()) < 80:
        raise ValueError("Insufficient extracted text; possible scan or empty page")
    dates, evidence = {}, {}
    patterns = {
        "revised_date": rf"(?:Last\s+Revised\s+(?:Date)?|Last\s+revised\s+on)\s*:?\s*({DATE_TOKEN})",
        "published_date": rf"(?:Published\s+Date|Publication\s+Date)\s*:?\s*({DATE_TOKEN})",
        "effective_date": rf"(?:takes?\s+effect\s+from|with\s+effect\s+from|effective\s+(?:date\s*:|from|on))\s*({DATE_TOKEN})",
    }
    normalized = re.sub(r"\s+", " ", text)
    for field, pattern in patterns.items():
        match = re.search(pattern, normalized, re.I)
        if match:
            token = match.group(1)
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    dates[field] = datetime.strptime(token, fmt).date()
                    evidence[field] = match.group(0)
                    break
                except ValueError:
                    pass
    # Multiple historical effective dates are not the current document's effective date.
    effective_matches = list(re.finditer(patterns["effective_date"], normalized, re.I))
    if len({m.group(1).lower() for m in effective_matches}) > 1:
        dates.pop("effective_date", None)
        evidence.pop("effective_date", None)
    kind = "guideline" if "guideline" in (url + title).lower() else "notice" if "/notices/" in url or "notice" in title.lower() else "consultation" if "consultation" in url else "enforcement" if "enforcement" in (url + title).lower() else "statement" if "statement" in url else "other"
    return SourceDocument(url=url, title=title, text=text, date_evidence=evidence, document_type=kind, content_hash=text_hash(text), retrieval_method=retrieval_method, provenance=provenance, links=links, **dates)


DEFAULT_SEEDS = [
    "https://www.mas.gov.sg/regulation/anti-money-laundering",
    "https://www.mas.gov.sg/regulation/notices/notice-626",
    "https://www.mas.gov.sg/regulation/guidelines/guidelines-to-notice-626-on-prevention-of-money-laundering-and-cft-for-banks",
    "https://www.mas.gov.sg/regulation/notices/psn01-aml-cft-notice---specified-payment-services",
    "https://www.mas.gov.sg/regulation/notices/psn02-aml-cft-notice---digital-payment-token-service",
]


class MASCollector:
    def __init__(self, max_pages=12, browser_fallback=False, delay=0.7, timeout=25, transport=None):
        if not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be 1..100")
        self.max_pages, self.browser_fallback, self.delay = max_pages, browser_fallback, delay
        self.timeout, self.transport = timeout, transport

    def _get(self, client, url):
        # Validate every hop before requesting it; never follow external redirects.
        for _ in range(5):
            url = canonical_url(url)
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = canonical_url(urljoin(url, response.headers["location"]))
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 15_000_000:
                        raise ValueError("Response exceeds 15MB")
                    chunks.append(chunk)
                return b"".join(chunks), response.headers.get("content-type", "text/html")
        raise ValueError("Redirect limit reached")

    def _browser_get(self, url):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                def guard(route):
                    try:
                        canonical_url(route.request.url)
                        route.continue_()
                    except ValueError:
                        route.abort()
                page.route("**/*", guard)
                page.goto(url, wait_until="domcontentloaded", timeout=int(self.timeout * 1000))
                page.wait_for_timeout(1500)
                canonical_url(page.url)
                return page.content().encode("utf-8"), "text/html"
            finally:
                browser.close()

    def collect(self, urls=None):
        import time
        import httpx
        from urllib.robotparser import RobotFileParser
        from .models import CollectionResult, FetchIssue
        result = CollectionResult()
        pending, seen = [(canonical_url(u), 0) for u in (urls or DEFAULT_SEEDS)], set()
        user_agent = "AuditPilotPublicResearch/0.1"
        with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=False, headers={"User-Agent": user_agent, "Accept": "text/html,application/pdf"}) as client:
            robots = RobotFileParser()
            try:
                body, _ = self._get(client, "https://www.mas.gov.sg/robots.txt")
                robots_text = body.decode("utf-8", errors="replace")
                if "user-agent:" not in robots_text.lower():
                    raise ValueError("robots.txt unavailable or invalid; collection stopped conservatively")
                robots.parse(robots_text.splitlines())
            except Exception as exc:
                result.issues.append(FetchIssue(url="https://www.mas.gov.sg/robots.txt", reason=str(exc)))
                return result
            while pending and len(result.attempted_urls) < self.max_pages:
                url, depth = pending.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                result.attempted_urls.append(url)
                if not robots.can_fetch(user_agent, url):
                    result.issues.append(FetchIssue(url=url, reason="Disallowed by MAS robots.txt; not bypassed"))
                    continue
                time.sleep(max(self.delay, robots.crawl_delay(user_agent) or 0))
                try:
                    body, content_type = self._get(client, url)
                    try:
                        source = parse_document(url, body, content_type)
                    except ValueError:
                        if not self.browser_fallback or "pdf" in content_type.lower():
                            raise
                        body, content_type = self._browser_get(url)
                        source = parse_document(url, body, content_type, retrieval_method="playwright")
                    result.documents.append(source)
                    if depth < 1:
                        for link in source.links:
                            relevant = any(t in link.lower() for t in ("money-laundering", "aml", "notice-626", "guidelines-to-notice-626", "psn01", "psn02", "fatf-statement", "sanction"))
                            if relevant and link not in seen and link not in [u for u, _ in pending]:
                                pending.append((link, depth + 1))
                except Exception as exc:
                    result.issues.append(FetchIssue(url=url, reason=str(exc)))
            if pending:
                result.issues.append(FetchIssue(url="https://www.mas.gov.sg/regulation/anti-money-laundering", stage="discovery", reason=f"Page budget reached; {len(pending)} discovered URLs unvisited"))
        result.coverage_complete = not result.issues and not pending
        return result
