"""Collect public evidence, analyze with an explicitly configured LLM, serve or export."""
import argparse
import json
import sys
from pathlib import Path
from .models import CollectionResult
from .storage import Store


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="AuditPilot: MAS AML external-driver research, not automatic policy approval")
    subs = parser.add_subparsers(dest="command", required=True)
    collect = subs.add_parser("collect", help="Direct official-source collection; no LLM needed")
    collect.add_argument("--url", action="append", help="Official MAS HTTPS seed; may be repeated")
    collect.add_argument("--max-pages", type=int, default=12)
    collect.add_argument("--browser-fallback", action="store_true")
    collect.add_argument("--out", default="data/collection.json")
    analyze = subs.add_parser("analyze", help="Analyze a collected JSON file using your configured LLM")
    analyze.add_argument("--input", required=True)
    analyze.add_argument("--db", default="data/auditpilot.sqlite")
    analyze.add_argument("--out", default="data/run.json")
    export = subs.add_parser("export")
    export.add_argument("--db", default="data/auditpilot.sqlite")
    export.add_argument("--out", default="data/events.json")
    serve = subs.add_parser("serve")
    serve.add_argument("--db", default="data/auditpilot.sqlite")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            from .collector import MASCollector
            result = MASCollector(max_pages=args.max_pages, browser_fallback=args.browser_fallback).collect(args.url)
            write_json(args.out, result.model_dump(mode="json"))
            print(json.dumps({"fetched_documents": len(result.documents), "issues": len(result.issues), "coverage_complete": result.coverage_complete, "output": args.out}))
            return 0 if result.coverage_complete else 1
        if args.command == "analyze":
            from .assessment import make_assessor_from_env
            from .pipeline import Monitor
            collection = CollectionResult.model_validate_json(Path(args.input).read_text(encoding="utf-8"))
            report = Monitor(Store(args.db), make_assessor_from_env()).process(collection)
            write_json(args.out, report.model_dump(mode="json"))
            print(json.dumps({"status": report.status, "new_events": report.new_events, "issues": len(report.issues), "output": args.out}))
            return 0 if report.status == "complete" else 1
        if args.command == "export":
            from .trends import rollup
            store = Store(args.db)
            events = store.events(limit=store.count_events())
            write_json(args.out, {"items": [e.model_dump(mode="json") for e in events], "total": len(events), "rollup": rollup(events)})
            print(json.dumps({"total": len(events), "output": args.out}))
            return 0
        if args.command == "serve":
            import uvicorn
            from .api import create_app
            uvicorn.run(create_app(Store(args.db)), host=args.host, port=args.port)
            return 0
    except Exception as exc:
        print(f"AuditPilot failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
