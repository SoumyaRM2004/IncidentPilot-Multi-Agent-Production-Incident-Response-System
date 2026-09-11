import os
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="IncidentPilot - Autonomous Incident Response Agent",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ IncidentPilot")
st.caption("Autonomous Multi-Agent Production Incident Response & Triage System (V1)")


def check_api_health():
    """Verify backend API connectivity."""
    try:
        resp = requests.get(f"{API_BASE_URL}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def fetch_incidents():
    """Fetch incidents strictly through FastAPI backend."""
    try:
        resp = requests.get(f"{API_BASE_URL}/incidents", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        st.sidebar.error(f"API Error: HTTP {resp.status_code}")
    except requests.exceptions.RequestException as e:
        st.sidebar.error("⚠️ Backend API Unavailable. Ensure FastAPI server is running on " + API_BASE_URL)
    return []


# Check API availability first
if not check_api_health():
    st.error(
        f"🚨 **Backend API Unreachable**\n\n"
        f"IncidentPilot frontend strictly communicates via the REST API at `{API_BASE_URL}`. "
        f"Direct database and agent access from the UI is disabled by design.\n\n"
        f"To start the backend, run:\n```bash\nuvicorn app.main:app --host 0.0.0.0 --port 8000\n```"
    )
    st.stop()

# Sidebar: Incident Selection
st.sidebar.header("Incident Management")
incidents = fetch_incidents()
incident_options = {f"[{i['id']}] {i['service']} - {i['title'][:45]}...": i for i in incidents}

selected_label = st.sidebar.selectbox(
    "Select Active Incident:",
    options=list(incident_options.keys()) if incident_options else ["No incidents available"]
)

# Sidebar: Create New Incident Form
with st.sidebar.expander("➕ Report New Incident"):
    with st.form("new_incident_form"):
        new_title = st.text_input("Title")
        new_service = st.selectbox(
            "Service",
            ["payment-service", "order-service", "auth-service", "notification-service", "user-service", "api-gateway"]
        )
        new_severity = st.selectbox("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        new_desc = st.text_area("Symptoms & Impact Description")
        submitted = st.form_submit_button("Submit Incident to API")

        if submitted:
            if not new_title or not new_desc:
                st.warning("Please provide both title and description.")
            else:
                try:
                    resp = requests.post(
                        f"{API_BASE_URL}/incidents",
                        json={
                            "title": new_title,
                            "description": new_desc,
                            "service": new_service,
                            "severity": new_severity
                        },
                        timeout=5
                    )
                    if resp.status_code == 201:
                        st.success("Incident recorded in backend!")
                        st.rerun()
                    else:
                        st.error(f"Failed to create incident: {resp.text}")
                except Exception as e:
                    st.error(f"Failed to reach API: {e}")

# Main View
if incident_options and selected_label in incident_options:
    curr_inc = incident_options[selected_label]

    col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
    with col_meta1:
        st.metric("Incident ID", curr_inc["id"])
    with col_meta2:
        st.metric("Service", curr_inc["service"])
    with col_meta3:
        st.metric("Severity", curr_inc["severity"])
    with col_meta4:
        st.metric("Status", curr_inc["status"])

    st.markdown(f"**Description:** {curr_inc['description']}")

    # Trigger Autonomous Investigation
    st.divider()
    if st.button("🚀 Trigger Autonomous Multi-Agent Investigation", type="primary"):
        with st.spinner("Multi-agent system investigating logs, deployments, telemetry metrics, and runbooks..."):
            try:
                resp = requests.post(f"{API_BASE_URL}/incidents/{curr_inc['id']}/investigate", timeout=45)
                if resp.status_code == 200:
                    inv_data = resp.json()
                    st.session_state[f"inv_{curr_inc['id']}"] = inv_data
                    st.success("Investigation complete!")
                else:
                    st.error(f"Investigation failed: {resp.text}")
            except Exception as e:
                st.error(f"API communication error during investigation: {e}")

    # Display Investigation Findings
    inv_data = st.session_state.get(f"inv_{curr_inc['id']}")
    if inv_data:
        report = inv_data.get("report") or {}
        inv_id = inv_data.get("id")

        st.subheader("1. Agent Orchestration Trace")
        agent_steps = [
            ("Supervisor Agent", "Created plan & targeted specialist queries"),
            ("Log Agent", "Extracted log errors & frequency anomalies"),
            ("Deployment Agent", "Analyzed recent releases & changesets"),
            ("Metrics Agent", "Evaluated telemetry threshold saturation"),
            ("Runbook / RAG Agent", "Searched Qdrant vector store for guidance"),
            ("Root Cause Analyst", "Synthesized evidence-backed hypotheses"),
            ("Verification Agent", "Two-layer audit & evidence validation")
        ]
        cols = st.columns(len(agent_steps))
        for idx, (name, desc) in enumerate(agent_steps):
            with cols[idx]:
                st.success(f"**{name}**\n\n✅ Executed")

        st.subheader("2. Root Cause Analysis & Calibrated Confidence")
        selected_hyp = report.get("selected_hypothesis", {})
        verif = report.get("verification_result", {})

        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"### 🎯 Selected Root Cause: **{selected_hyp.get('selected_root_cause')}**")
            st.write(f"**Reasoning:** {selected_hyp.get('reasoning_summary')}")
            st.markdown(f"**Supporting Evidence IDs:** `{', '.join(selected_hyp.get('supporting_evidence_ids', []))}`")
        with c2:
            st.metric("Confidence", f"{int(report.get('confidence', 0.0) * 100)}%")
            v_status = "VERIFIED ✅" if verif.get("verified") else "CHALLENGED / INSUFFICIENT ⚠️"
            st.info(f"Verification: **{v_status}**")
            st.caption(verif.get("explanation", ""))

        st.subheader("3. Human-in-the-Loop Approval & Remediation")
        rec = report.get("recommended_action", {})
        st.warning("⚠️ **HUMAN APPROVAL GATING** — Destructive or production-modifying remediation is strictly gated.")
        st.info("ℹ️ *Notice: Simulated Remediation Gating — No real destructive production commands are executed.*")

        st.markdown(f"**Proposed Remediation:** `{rec.get('action')}`")
        st.markdown(f"**Target Service:** `{rec.get('target_service')}` | **Estimated Risk:** `{rec.get('estimated_risk', 'LOW')}`")
        st.markdown(f"**Rationale:** {rec.get('rationale')}")

        current_approval = inv_data.get("approval_status", "PENDING_APPROVAL")
        st.markdown(f"**Current Status:** `{current_approval}`")

        if inv_data.get("approved_at"):
            st.markdown(f"**Decision Recorded:** `{inv_data.get('operator_decision')}` at `{inv_data.get('approved_at')}`")
            if inv_data.get("operator_notes"):
                st.caption(f"Notes: {inv_data.get('operator_notes')}")

        if current_approval == "PENDING_APPROVAL":
            operator_name = st.text_input("Operator Identifier", value="sre-oncall-engineer", key=f"op_{inv_id}")
            operator_notes = st.text_input("Approval Notes / Audit Justification", value="Approved based on verified telemetry.", key=f"notes_{inv_id}")

            col_appr1, col_appr2 = st.columns(2)
            with col_appr1:
                if st.button("✅ Submit Operator Approval", key=f"approve_btn_{inv_id}"):
                    try:
                        resp = requests.post(
                            f"{API_BASE_URL}/investigations/{inv_id}/approve",
                            json={
                                "operator": operator_name,
                                "decision": "APPROVED",
                                "notes": operator_notes
                            },
                            timeout=5
                        )
                        if resp.status_code == 200:
                            st.session_state[f"inv_{curr_inc['id']}"] = resp.json()
                            st.success("Approval recorded in backend database!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Failed to record approval: {e}")

            with col_appr2:
                if st.button("❌ Reject / Escalate to Senior SRE", key=f"reject_btn_{inv_id}"):
                    try:
                        resp = requests.post(
                            f"{API_BASE_URL}/investigations/{inv_id}/reject",
                            json={
                                "operator": operator_name,
                                "decision": "REJECTED",
                                "notes": operator_notes
                            },
                            timeout=5
                        )
                        if resp.status_code == 200:
                            st.session_state[f"inv_{curr_inc['id']}"] = resp.json()
                            st.warning("Rejection and escalation recorded in backend database!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Failed to record rejection: {e}")

        st.subheader("4. Collected Evidence Catalog (Audit Trail)")
        evidence_list = report.get("evidence", [])
        if evidence_list:
            table_data = [
                {
                    "ID": e.get("evidence_id"),
                    "Type": e.get("source_type", "unknown"),
                    "Source": e.get("source"),
                    "Finding": e.get("finding")
                }
                for e in evidence_list
            ]
            st.dataframe(table_data, use_container_width=True)

        st.subheader("5. Detailed Multi-Agent Trace")
        with st.expander("View Chronological Agent Trace"):
            for h in report.get("agent_history", []):
                st.markdown(f"**{h.get('agent')}** ({h.get('timestamp')[:19]} UTC) — Iteration {h.get('iteration', 0)}:")
                st.markdown(f"- *Action:* {h.get('action')}")
                st.markdown(f"- *Findings:* {h.get('findings')}")
                st.divider()

else:
    st.info("No incident selected.")
