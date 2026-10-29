"""Streamlit fallback UI from the proposed stack; consumes only the JSON API."""
import json
import os
import httpx
import streamlit as st

st.set_page_config(page_title="AuditPilot | MAS AML", page_icon="🛡️", layout="wide")
st.title("AuditPilot · MAS AML")
st.caption("External regulatory drivers · public sources only · no internal DBS data")
st.warning("Human review required. Verified means factual quote matching—not legal approval or measured bank risk.")
api = st.sidebar.text_input("JSON API URL", os.getenv("AUDITPILOT_API_URL", "http://127.0.0.1:8000")).rstrip("/")
st.sidebar.button("Refresh")
try:
    events = httpx.get(api + "/events", params={"limit": 500}, timeout=10).raise_for_status().json()
    trends = httpx.get(api + "/rollup", timeout=10).raise_for_status().json()
    runs = httpx.get(api + "/runs", timeout=10).raise_for_status().json()
except Exception as exc:
    st.error(f"API unavailable: {type(exc).__name__}. Start python -m auditpilot.cli serve.")
    st.stop()

items = events["items"]
left, middle, right = st.columns(3)
left.metric("Assessed source versions", events["total"])
middle.metric("Observed updates in this page", sum(x["change_type"] == "updated" for x in items))
right.metric("Latest run", runs["items"][0]["status"] if runs["items"] else "Not run")
event_tab, trend_tab, coverage_tab = st.tabs(["Evidence & recommendations", "Sub-area trends", "Collection coverage"])
with event_tab:
    if not items:
        st.info("No assessed events. Run collection and configure a model before analysis. No demo regulations are fabricated.")
    else:
        st.caption(f"Showing {len(items)} of {events['total']} source versions. Use the API to paginate the full history.")
        for event in items:
            source, assessment = event["source"], event["assessment"]
            with st.expander(f"{assessment['risk_level'].upper()} review priority · {source['title']} · {event['change_type']}"):
                st.link_button("Official MAS source", source["url"])
                st.write(assessment["summary"])
                st.caption(f"Method: {assessment['assessment_method']} · provenance: {source['provenance']} · verification: {event['verification_status']}")
                st.write("Review priority rationale:", assessment["risk_rationale"])
                st.write("Impacted population:", assessment["impacted_population"])
                st.write("Actual impact:", assessment["actual_impact"])
                st.subheader("Source evidence")
                for claim in assessment["claims"]:
                    st.code(claim["quote"], language=None)
                    if claim.get("locator"):
                        st.caption("Model-supplied locator (not separately verified): " + claim["locator"])
                st.subheader("Proposed review actions · not approved policy")
                for recommendation in assessment["recommendations"]:
                    st.write("• " + recommendation)
                if event.get("diff"):
                    st.code(event["diff"], language="diff")
                st.json(event)
    st.download_button("Download this JSON page", json.dumps(events, indent=2), "auditpilot-events.json", "application/json")
with trend_tab:
    st.caption("Weighted observed policy-change review pressure; not measured money-laundering risk. Baselines excluded.")
    if trends["items"]:
        st.dataframe(trends["items"], hide_index=True, width="stretch")
with coverage_tab:
    if not runs["items"]:
        st.info("No analysis runs recorded. Collection-only failures are saved in the CLI output file.")
    for run in runs["items"]:
        with st.expander(f"{run['started_at']} · {run['status']}"):
            st.write(run["coverage_note"])
            st.json(run)
