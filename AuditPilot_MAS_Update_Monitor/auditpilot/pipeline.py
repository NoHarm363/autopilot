"""LangGraph assessment/verifier loop and version-aware collection processing."""
import difflib
import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from .assessment import verify_assessment
from .models import Assessment, CollectionResult, FetchIssue, PolicyEvent, RunReport, SourceDocument, now_utc
from .storage import Store, text_hash


class ReviewState(TypedDict, total=False):
    source: SourceDocument
    diff: str | None
    assessment: Assessment
    feedback: list[str]
    attempts: int
    failed: bool
    errors: list[str]


class Monitor:
    def __init__(self, store: Store, assessor):
        self.store, self.assessor = store, assessor
        graph = StateGraph(ReviewState)
        graph.add_node("classify_and_rate", self._assess)
        graph.add_node("verify", self._verify)
        graph.add_edge(START, "classify_and_rate")
        graph.add_edge("classify_and_rate", "verify")
        graph.add_conditional_edges("verify", self._route, {"retry": "classify_and_rate", "done": END})
        self.graph = graph.compile()

    def _assess(self, state):
        try:
            a = self.assessor.assess(state["source"], diff=state.get("diff"), feedback=state.get("feedback", []))
            return {"assessment": a, "attempts": state.get("attempts", 0) + 1, "errors": []}
        except Exception as exc:
            return {"attempts": state.get("attempts", 0) + 1, "errors": [f"Assessment request failed: {type(exc).__name__}; retry or review configuration"], "feedback": ["Request or output schema invalid"]}

    def _verify(self, state):
        errors = state.get("errors", []) or verify_assessment(state["source"], state["assessment"])
        return {"feedback": errors, "failed": bool(errors)}

    def _route(self, state):
        if not state["feedback"]:
            return "done"
        return "retry" if state["attempts"] < 2 else "done"

    def process(self, collection: CollectionResult) -> RunReport:
        started = now_utc()
        issues = list(collection.issues)
        inserted = unchanged = 0
        for source in collection.documents:
            source.content_hash = text_hash(source.text)
            previous = self.store.latest_source(source.url)
            if previous and text_hash(previous.text) == source.content_hash:
                unchanged += 1
                continue
            diff = "\n".join(difflib.unified_diff(previous.text.splitlines(), source.text.splitlines(), fromfile="previous", tofile="current", lineterm="")) if previous else None
            state = self.graph.invoke({"source": source, "diff": diff, "attempts": 0, "feedback": [], "failed": False})
            if state.get("failed", False):
                issues.append(FetchIssue(url=source.url, stage="assessment", reason="LLM unavailable or evidence rejected after two attempts; no rating generated. " + "; ".join(state.get("feedback", []))))
                continue
            notes = ["Verbatim factual claims matched the retrieved source. Risk, summary interpretation and recommendations remain analyst judgments."]
            event = PolicyEvent(id=str(uuid.uuid4()), source=source, assessment=state["assessment"], verification_status="verified", verification_notes=notes, change_type="updated" if previous else "baseline", previous_hash=previous.content_hash if previous else None, diff=diff)
            inserted += int(self.store.save_event(event))
        status = "blocked" if not collection.documents else "complete" if collection.coverage_complete and not issues else "partial"
        report = RunReport(run_id=str(uuid.uuid4()), started_at=started, completed_at=now_utc(), status=status, attempted_urls=collection.attempted_urls, fetched_documents=len(collection.documents), new_events=inserted, unchanged_documents=unchanged, issues=issues, coverage_note="Coverage is limited to configured seed URLs and one-hop relevant links within the page budget; not a complete inventory of MAS publications. First observations are baselines, not newly issued regulations.")
        self.store.save_run(report)
        return report
