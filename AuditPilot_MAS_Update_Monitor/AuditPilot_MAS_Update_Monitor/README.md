# AuditPilot — MAS AML Update Monitor

Runnable MAS-only research MVP following `AuditPilot_Tech_Stack.docx`. Public sources only; no internal DBS data and no custom model training. It collects MAS publications, detects changed source text, asks an explicitly configured LLM for structured audit-review judgments, verifies factual quotes, stores accepted events in SQLite, and serves portable JSON plus a Streamlit dashboard.

**This is not an automatic policy amendment or compliance approval system.** It proposes review actions. All output requires human compliance/legal review. “Verified” means the factual claims equal quotes found in the retrieved source; summaries, applicability, risk ratings, recommendations, and model-supplied page/paragraph locators are not independently legally validated.

## Quick start

Python 3.11+ required. Python 3.12 is a practical deployment default; development here exercised Python 3.14.

```bash
python -m venv .venv
# Bash/Git Bash on Windows: source .venv/Scripts/activate
# Linux/macOS: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev,ui]'
python -m auditpilot.cli --help
```

### 1. Collect public MAS sources (no model needed)

```bash
python -m auditpilot.cli collect --max-pages 12 --out data/collection.json
```

Narrow to one notice when needed:

```bash
python -m auditpilot.cli collect --url https://www.mas.gov.sg/regulation/notices/notice-626 --max-pages 4 --out data/collection.json
```

The default seeds include the MAS AML landing page, Notice 626, its guidelines, PSN01 and PSN02. Relevant one-hop links are followed within a strict page budget. The collector validates every redirect, only requests official MAS HTTPS URLs, follows robots.txt restrictions and crawl-delay, limits response size/PDF pages, and rejects maintenance/HTML error pages even when HTTP status is 200. First observations are **baselines**, not evidence of a newly issued regulation. A changed hash means observed document change, not necessarily a legal amendment.

Optional Playwright fallback:

```bash
python -m pip install -e '.[browser]'
python -m playwright install chromium
python -m auditpilot.cli collect --browser-fallback --out data/collection.json
```

Fallback rendering does not bypass robots restrictions or guarantee access. Scanned PDFs without a text layer require separate OCR/human handling; they are not silently accepted.

### 2. Configure your model locally

There is **no rules-based assessment or synthetic-data fallback**. Choose either Ollama or an OpenAI-compatible endpoint supporting strict structured JSON output. The CLI reads environment variables, not `.env` automatically. `.env.example` documents the settings; do not commit API keys.

Ollama example, in Bash/Git Bash:

```bash
# Install/run Ollama separately, then pull a model you have capacity for:
ollama pull qwen3:8b
export AUDITPILOT_LLM_PROVIDER=ollama
export AUDITPILOT_LLM_BASE_URL=http://localhost:11434
export AUDITPILOT_LLM_MODEL=qwen3:8b
```

PowerShell equivalents:

```powershell
$env:AUDITPILOT_LLM_PROVIDER = 'ollama'
$env:AUDITPILOT_LLM_BASE_URL = 'http://localhost:11434'
$env:AUDITPILOT_LLM_MODEL = 'qwen3:8b'
```

For an API endpoint, set `AUDITPILOT_LLM_PROVIDER=openai`, `AUDITPILOT_LLM_BASE_URL` to the provider's `/v1` base, `AUDITPILOT_LLM_MODEL` to your available model/deployment, and `AUDITPILOT_LLM_API_KEY` locally. Endpoint-specific authentication or unsupported JSON-schema dialects may require an adapter; Claude/Gemini-native APIs are not implemented.

### 3. Analyze, export and view

```bash
python -m auditpilot.cli analyze --input data/collection.json --db data/auditpilot.sqlite --out data/run.json
python -m auditpilot.cli export --db data/auditpilot.sqlite --out data/events.json
python -m auditpilot.cli serve --db data/auditpilot.sqlite
```

In another terminal:

```bash
python -m streamlit run dashboard.py --browser.gatherUsageStats false
```

Default API: `http://127.0.0.1:8000`; dashboard: `http://localhost:8501`. Set `AUDITPILOT_API_URL` before starting the dashboard if the API uses another port.

Read-only endpoints:

| Endpoint | Output |
|---|---|
| `GET /health` | API health and human-review flag |
| `GET /events?limit=50&offset=0` | Event page, exact total and `has_more` |
| `GET /events/{id}` | Evidence, source, dates, proposed actions and diff |
| `GET /runs` | Analysis run history and coverage/error notes |
| `GET /rollup?window_days=30` | Four sub-area review-pressure summaries |
| `GET /schema` | Pydantic JSON schema |
| `GET /docs` | FastAPI interactive API documentation |

Ingestion is CLI-only; there is no unauthenticated ingestion API. API binding defaults to loopback. Add authentication, TLS and authorization before exposing it publicly. The dashboard consumes the API rather than a second private output format.

Exit codes: `0` complete operation; `1` partial/blocked collection or analysis (output still written); `2` configuration/input/runtime failure. LLM or verifier failure produces an issue and **no event or substitute rating**. Retrying analysis with the same unaccepted source can try again because failures do not create accepted events.

## Stack recommendations mapped to code

| Document recommendation | Implementation / explicit scope |
|---|---|
| Scout → Extractor | `collector.py`: bounded direct HTTP, BeautifulSoup, PyMuPDF; optional Playwright |
| LangGraph orchestration | `pipeline.py`: classify/rate → quote verifier → one retry with feedback |
| API model, structured output | `assessment.py`: OpenAI-compatible strict JSON schema plus Pydantic validation |
| Open model fallback | Explicit Ollama provider option, not an automatic runtime fallback |
| Fact-first verification | Verbatim quote/statement checks; unsupported claims rejected |
| SQLite MVP | `storage.py`: versioned events and analysis runs |
| Deduplication | Exact normalized-text hash per source URL; cross-outlet semantic/Chroma deduplication deferred |
| JSON API | `api.py` and CLI JSON exports |
| UI | Streamlit fallback from the proposed stack; Next.js/Tailwind/shadcn/Recharts deferred |
| Trend rollup | `trends.py`: equal time windows, excluding baselines/manual snapshots |
| Evaluation | `evaluation.py`: URL recall, exact sub-area matches, quote-support fraction |
| Tracing | LangGraph's LangSmith integration can be enabled with local `LANGSMITH_*` variables; not exercised with a tracing account |
| Docker | Dockerfile provided; container build not exercised here |
| MAS/HKMA/OJK/FATF and news | This release is MAS-only; other regulators and Tavily/Exa/GDELT are deferred |
| Postgres / Vercel / Render / Railway | Deployment options, not implemented migrations or deployed services |

The four **provisional** sub-areas are sanctions/proliferation, crypto/virtual assets, customer due diligence, and transaction monitoring/reporting. The team still needs to approve its final taxonomy. “High/medium/low” is an LLM audit-review priority judgment, not an official MAS rating. Trends use weights 3/2/1 and are labelled observed policy-change review pressure—not measured financial-crime risk. Empty comparison windows return `insufficient_data`; collection gaps can distort trends.

Dates are extracted only with supporting source text. Multiple different effective dates are left unknown rather than selecting an arbitrary historical amendment. Full-document human review is required; model context currently caps source text at 45,000 characters and marks truncation. Production use needs chunk-level extraction/coverage before interpreting long documents.

MAS identifies Notice 626 as requirements for banks on AML/CFT; that is why it is a primary bank-focused seed.[1]

## Tests and evaluation

```bash
python -m pytest -q
```

`dev` alone runs core tests; UI tests skip if Streamlit is not installed. Install `.[dev,ui]` to exercise dashboard rendering too. Test fixtures and mocked model responses are synthetic and live only in `tests/`; they are not regulatory updates or proof of live LLM output.

For a manually curated public-source gold set, supply a JSON array of objects with `source_url` and `sub_areas`:

```bash
python -m auditpilot.evaluation --events data/events.json --ground-truth your-reviewed-ground-truth.json
```

No fabricated last-12-month ground-truth dataset is supplied. URL recall is not event-level coverage, and exact quote support is not a semantic hallucination score. A real event-level gold set, risk calibration, semantic review, and long-document evaluation remain required.

## Actual verification and blockers

- Source parser, storage, verifier retry, API pagination, rollup, CLI, structured provider request contracts, evaluation and Streamlit empty/event states were exercised with automated tests.
- A real FastAPI server returned HTTP responses; a real Streamlit server returned healthy status. Installation as an editable Python package succeeded.
- Local MAS HTTP requests and the browser returned maintenance content. The real CLI run retrieved **zero valid documents**, recorded two issues, and returned exit code 1. See `verification/live-collection.json`.
- No application LLM environment or reachable Ollama instance was available. Provider HTTP contracts were tested with mock responses; live model assessment was **not verified**.
- `verification/mas-page-evidence.txt` is a separately retrieved source-selection excerpt, not an application-ingested policy event. It must not be treated as fresh collection output.
- Python 3.14 emitted third-party LangSmith deprecation warnings during LangGraph setup. Docker and hosted deployment were not exercised.

See `verification/summary.json` and `verification/tests.txt` for the final recorded checks.

## Sources

[1] https://www.mas.gov.sg/regulation/notices/notice-626
