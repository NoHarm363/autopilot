"""Read-only JSON API. Run ingestion through the CLI, not an unauthenticated endpoint."""
from fastapi import FastAPI, HTTPException, Query
from .models import PolicyEvent
from .storage import Store
from .trends import rollup


def create_app(store: Store):
    app = FastAPI(title="AuditPilot MAS AML Updates", version="0.1.0", description="Public-source research for human review; verified means quote matching only, not legal approval.")

    @app.get("/health")
    def health():
        return {"status": "ok", "scope": "MAS public-source research", "human_review_required": True}

    @app.get("/events")
    def events(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        items = store.events(limit, offset)
        total = store.count_events()
        return {"items": [e.model_dump(mode="json") for e in items], "total": total, "limit": limit, "offset": offset, "has_more": offset + len(items) < total}

    @app.get("/events/{event_id}")
    def event(event_id: str):
        result = store.get_event(event_id)
        if result is None:
            raise HTTPException(404, "Event not found")
        return result.model_dump(mode="json")

    @app.get("/runs")
    def runs(limit: int = Query(50, ge=1, le=500)):
        return {"items": [r.model_dump(mode="json") for r in store.runs(limit)]}

    @app.get("/rollup")
    def trends(window_days: int = Query(30, ge=1, le=365)):
        return {"items": rollup(store.events(limit=store.count_events()), window_days), "coverage_warning": "Observed changes within configured coverage only; collection gaps can distort trends."}

    @app.get("/schema")
    def schema():
        return PolicyEvent.model_json_schema()

    return app
