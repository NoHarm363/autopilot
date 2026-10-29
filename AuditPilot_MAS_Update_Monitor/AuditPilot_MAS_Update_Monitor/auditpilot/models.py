"""Portable contracts. Facts and source evidence are separate from audit judgment."""
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

SubArea = Literal["sanctions_proliferation", "crypto_virtual_assets", "customer_due_diligence", "transaction_monitoring_reporting"]
RiskLevel = Literal["high", "medium", "low"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceDocument(Contract):
    url: str
    title: str = Field(min_length=1)
    text: str = Field(min_length=20)
    retrieved_at: datetime = Field(default_factory=now_utc)
    published_date: date | None = None
    revised_date: date | None = None
    effective_date: date | None = None
    date_evidence: dict[str, str] = Field(default_factory=dict)
    document_type: Literal["notice", "guideline", "consultation", "enforcement", "statement", "other"] = "other"
    content_hash: str = ""
    retrieval_method: str = "direct_http"
    provenance: Literal["live", "manual_public_snapshot", "test_fixture"] = "live"
    links: list[str] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def official_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.hostname not in {"mas.gov.sg", "www.mas.gov.sg"} or parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise ValueError("Only official MAS HTTPS URLs are allowed")
        return value


class Claim(Contract):
    statement: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    locator: str | None = None


class Assessment(Contract):
    summary: str
    sub_areas: list[SubArea] = Field(min_length=1, max_length=4)
    risk_level: RiskLevel
    risk_rationale: str
    impacted_population: str
    actual_impact: str
    recommendations: list[str] = Field(min_length=1)
    auditable_focus_areas: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(min_length=1)
    assessment_method: str = "unconfigured"
    confidence: float = Field(default=0.5, ge=0, le=1)


class PolicyEvent(Contract):
    id: str
    source: SourceDocument
    assessment: Assessment
    verification_status: Literal["verified", "needs_review"]
    verification_notes: list[str] = Field(default_factory=list)
    change_type: Literal["baseline", "updated"]
    previous_hash: str | None = None
    diff: str | None = None
    observed_at: datetime = Field(default_factory=now_utc)
    human_review_required: Literal[True] = True


class FetchIssue(Contract):
    url: str
    stage: str = "fetch"
    reason: str


class CollectionResult(Contract):
    documents: list[SourceDocument] = Field(default_factory=list)
    issues: list[FetchIssue] = Field(default_factory=list)
    attempted_urls: list[str] = Field(default_factory=list)
    coverage_complete: bool = False


class RunReport(Contract):
    run_id: str
    started_at: datetime
    completed_at: datetime
    status: Literal["complete", "partial", "blocked"]
    attempted_urls: list[str]
    fetched_documents: int
    new_events: int
    unchanged_documents: int
    issues: list[FetchIssue]
    coverage_note: str
