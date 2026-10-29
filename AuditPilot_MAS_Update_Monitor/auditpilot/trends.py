"""Observed review pressure, not a prediction of money laundering or bank risk."""
from datetime import timedelta
from typing import get_args
from .models import SubArea, now_utc


def rollup(events, window_days=30, now=None):
    if not 1 <= window_days <= 365:
        raise ValueError("window_days must be 1..365")
    now = now or now_utc()
    boundary = now - timedelta(days=window_days)
    beginning = boundary - timedelta(days=window_days)
    eligible = [e for e in events if e.source.provenance == "live" and e.change_type == "updated" and e.verification_status == "verified" and beginning <= e.observed_at <= now]
    weights = {"high": 3, "medium": 2, "low": 1}
    rows = []
    for area in get_args(SubArea):
        matching = [e for e in eligible if area in e.assessment.sub_areas]
        current = [e for e in matching if e.observed_at >= boundary]
        previous = [e for e in matching if e.observed_at < boundary]
        current_score = sum(weights[e.assessment.risk_level] for e in current)
        previous_score = sum(weights[e.assessment.risk_level] for e in previous)
        trend = "insufficient_data" if not current or not previous else "rising" if current_score > previous_score else "declining" if current_score < previous_score else "stable"
        rows.append({"sub_area": area, "trend": trend, "current_count": len(current), "previous_count": len(previous), "current_score": current_score, "previous_score": previous_score, "window_days": window_days, "metric": "observed_policy_change_review_pressure", "interpretation": "Weighted observed changes only (high=3, medium=2, low=1); actual money-laundering risk is not measured. Baselines and manual snapshots are excluded; empty windows are insufficient data, not zero risk."})
    return rows
