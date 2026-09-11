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
st.caption("Autonomous Multi-Agent Production Incident Response & Triage System")


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
        return []
    except Exception:
        return []


def create_incident(title, service, severity, description):
    """Create incident via FastAPI REST API."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}/incidents",
            json={
                "title": title,
                "service": service,
                "severity": severity,
                "description": description
            },
            timeout=5
        )
        return resp.status_code == 201
    except Exception:
        return False


# 1. API Health Gating Banner
api_online = check_api_health()
if not api_online:
    st.error(f"⚠️ **FastAPI Backend is Offline or Unreachable** (`{API_BASE_URL}`).")
    st.info("Start the API server in a separate terminal: `uvicorn app.main:app --host 0.0.0.0 --port 8000`")
    st.stop()

# Sidebar: Incident Creation & Selection
st.sidebar.header("Incident Management")
incidents = fetch_incidents()

selected_incident_id = None
if incidents:
    incident_options = {
        f"[{inc['id']}] {inc['service']}: {inc['title'][:40]}... ({inc['status']})": inc['id']
        for inc in incidents
    }
    selected_label = st.sidebar.selectbox("Select Production Incident", list(incident_options.keys()))
    selected_incident_id = incident_options.get(selected_label)
else:
    st.sidebar.warning("No incidents found in database. Seed database or create one below.")

with st.sidebar.expander("➕ Report New Incident"):
    with st.form("new_incident_form"):
        new_title = st.text_input("Incident Title", "High database error rates and latency surge")
        new_service = st.selectbox("Affected Service", ["payment-service", "order-service", "auth-service", "notification-service", "user-service", "analytics-service"])
        new_severity = st.selectbox("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        new_desc = st.text_area("Symptoms & Context", "Multiple microservices experiencing connection acquisition failures.")
        submitted = st.form_submit_button("Submit Incident")
        if submitted:
            if create_incident(new_title, new_service, new_severity, new_desc):
                st.success("Incident created successfully!")
                st.rerun()
            else:
                st.error("Failed to create incident via API.")

# Main Dashboard
curr_inc = next((i for i in incidents if i["id"] == selected_incident_id), None)

if curr_inc:
    col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
    with col_meta1:
        st.metric("Incident ID", curr_inc["id"])
    with col_meta2:
        st.metric("Service", curr_inc["service"])
    with col_meta3:
        st.metric("Severity", curr_inc["severity"])
    with col_meta4:
        st.metric("Status", curr_inc["status"])

    st.markdown(f"### {curr_inc['title']}")
    st.write(f"**Description:** {curr_inc['description']}")
    st.caption(f"Reported at: {curr_inc.get('created_at', 'N/A')}")

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
        history = report.get("agent_history", [])

        # Derive actual executed agents dynamically from execution history
        executed_agents = set()
        for h in history:
            text = (h.get("agent", "") + " " + h.get("action", "")).lower()
            if "supervisor" in text:
                executed_agents.add("supervisor")
            if "log" in text:
                executed_agents.add("logs")
            if "deployment" in text:
                executed_agents.add("deployments")
            if "metric" in text:
                executed_agents.add("metrics")
            if "runbook" in text or "rag" in text:
                executed_agents.add("runbook")
            if "root cause" in text:
                executed_agents.add("root_cause")
            if "verification" in text:
                executed_agents.add("verification")

        st.subheader("1. Agent Orchestration Trace (Execution Status)")
        agent_steps = [
            ("supervisor", "Supervisor Agent"),
            ("logs", "Log Agent"),
            ("deployments", "Deployment Agent"),
            ("metrics", "Metrics Agent"),
            ("runbook", "Runbook / RAG Agent"),
            ("root_cause", "Root Cause Analyst"),
            ("verification", "Verification Agent")
        ]
        cols = st.columns(len(agent_steps))
        for idx, (key, label) in enumerate(agent_steps):
            with cols[idx]:
                if key in executed_agents:
                    st.success(f"**{label}**\n\n✅ Executed")
                else:
                    st.info(f"**{label}**\n\n⏭️ Skipped")

        st.subheader("2. Root Cause Analysis & Evidence Quality Score")
        selected_hyp = report.get("selected_hypothesis", {})
        verif = report.get("verification_result", {})
        conf_assessment = report.get("confidence_assessment") or {}

        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"### 🎯 Selected Root Cause: **{selected_hyp.get('selected_root_cause')}**")
            st.write(f"**Reasoning:** {selected_hyp.get('reasoning_summary')}")
            st.markdown(f"**Supporting Evidence IDs:** `{', '.join(selected_hyp.get('supporting_evidence_ids', []))}`")

            # Display explainable confidence factors
            factors = selected_hyp.get("confidence_rationale") or conf_assessment.get("factors") or []
            if factors:
                st.markdown("**Evidence Quality Factors:**")
                for f in factors:
                    st.markdown(f"- {f}")

        with c2:
            score = report.get("confidence", 0.0)
            level = conf_assessment.get("level", "MODERATE")
            st.metric("Quality Score", f"{int(score * 100)}% ({level})")

            v_status = "VERIFIED ✅" if verif.get("verified") else f"CHALLENGED ⚠️ ({verif.get('challenge_category', 'REJECTED')})"
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
                        else:
                            st.error(f"Failed to record approval: {resp.text}")
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
                        else:
                            st.error(f"Failed to record rejection: {resp.text}")
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
