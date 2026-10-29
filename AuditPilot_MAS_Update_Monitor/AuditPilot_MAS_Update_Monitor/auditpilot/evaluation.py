"""Limited measurable proxies; not a substitute for a curated event-level gold set."""
import argparse
import json
from pathlib import Path
from .assessment import normalize
from .models import PolicyEvent


def evaluate(events, ground_truth):
    expected = {row["source_url"]: set(row["sub_areas"]) for row in ground_truth}
    observed = {event.source.url: event for event in events}
    matched = expected.keys() & observed.keys()
    claims = [(event, claim) for event in events for claim in event.assessment.claims]
    supported = sum(normalize(claim.quote) in normalize(event.source.text) and normalize(claim.quote) == normalize(claim.statement) for event, claim in claims)
    correct = sum(expected[url] == set(observed[url].assessment.sub_areas) for url in matched)
    return {"expected_source_count": len(expected), "matched_source_count": len(matched), "source_url_recall": len(matched) / len(expected) if expected else None, "supported_quote_fraction": supported / len(claims) if claims else None, "matched_sub_area_accuracy": correct / len(matched) if matched else None, "semantic_hallucination_rate": None, "limitations": "URL recall is not event-level coverage. Quote matching does not verify summary interpretation, risk judgment, or legal applicability. Semantic hallucination rate requires human-labelled evaluation."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--ground-truth", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.events).read_text(encoding="utf-8"))
    events = [PolicyEvent.model_validate(row) for row in data["items"]]
    truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
    print(json.dumps(evaluate(events, truth), indent=2))


if __name__ == "__main__":
    main()
