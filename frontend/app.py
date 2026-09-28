import os
import requests
import streamlit as st
from datetime import datetime

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="IncidentPilot - Autonomous Incident Response Agent",
    page_icon="🛡️",
    layout="wide"
)

# Custom CSS for clean, high-contrast, modern UI typography & badge styling
st.markdown("""
<style>
    /* Global Card & Container Styles */
    .incident-hero-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    .incident-meta-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        margin-bottom: 14px;
    }
    .incident-title-text {
        font-size: 1.65rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.35;
        margin-bottom: 12px;
        letter-spacing: -0.01em;
    }
    .incident-desc-box {
        background: rgba(15, 23, 42, 0.6);
        border-left: 3px solid #38bdf8;
        border-radius: 6px;
        padding: 12px 16px;
        color: #cbd5e1;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    /* Sleek Badges & Pills */
    .meta-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .pill-id {
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.35);
        font-family: monospace;
    }
    .pill-service {
        background: rgba(167, 139, 250, 0.15);
        color: #c084fc;
        border: 1px solid rgba(167, 139, 250, 0.35);
        font-family: monospace;
    }
    .pill-time {
        color: #94a3b8;
        font-size: 0.82rem;
        margin-left: auto;
    }

    /* Status Pills (Never Truncated) */
    .status-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .status-success {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .status-failed {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .status-running {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.4);
    }
    .status-open {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }

    /* Severity Pills */
    .sev-critical {
        background: rgba(225, 29, 72, 0.25);
        color: #fda4af;
        border: 1px solid rgba(225, 29, 72, 0.5);
    }
    .sev-high {
        background: rgba(234, 88, 12, 0.25);
        color: #fdba74;
        border: 1px solid rgba(234, 88, 12, 0.5);
    }
    .sev-medium {
        background: rgba(234, 179, 8, 0.2);
        color: #fde047;
        border: 1px solid rgba(234, 179, 8, 0.4);
    }
    .sev-low {
        background: rgba(100, 116, 139, 0.25);
        color: #cbd5e1;
        border: 1px solid rgba(100, 116, 139, 0.4);
    }

    /* Card Panels */
    .section-card {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

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


def fetch_latest_investigation(incident_id):
    """Retrieve the most recent investigation for an incident."""
    try:
        resp = requests.get(f"{API_BASE_URL}/incidents/{incident_id}/investigations", timeout=5)
        if resp.status_code == 200:
            invs = resp.json()
            return invs[0] if invs else None
        return None
    except Exception:
        return None


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


def format_timestamp(ts_raw):
    """Format raw ISO timestamp into a readable date/time string."""
    if not ts_raw:
        return "N/A"
    try:
        clean = ts_raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%b %d, %Y • %H:%M:%S UTC")
    except Exception:
        return str(ts_raw)[:19].replace("T", " ") + " UTC"


# 1. API Health Gating Banner
api_online = check_api_health()
if not api_online:
    st.error(f"⚠️ **FastAPI Backend is Offline or Unreachable** (`{API_BASE_URL}`).")
    st.info("Start the API server in a separate terminal: `uvicorn app.main:app --host 0.0.0.0 --port 8000`")
    st.stop()

# 2. Sidebar: Incident Selection & Creation
st.sidebar.header("Incident Management")
incidents = fetch_incidents()

selected_incident_id = None
if incidents:
    def get_incident_sidebar_label(inc):
        status = inc.get("status", "OPEN")
        icon = "🟢" if status == "ROOT_CAUSE_IDENTIFIED" else "🔴" if status == "INVESTIGATION_FAILED" else "🔵" if status == "INVESTIGATING" else "🟡"
        title = inc.get("title", "")
        # Keep title clean and readable in the dropdown without arbitrary truncation
        title_snippet = title if len(title) <= 65 else f"{title[:62]}..."
        return f"{icon} [{inc['id']}] {inc['service']} — {title_snippet}"

    incident_options = {
        get_incident_sidebar_label(inc): inc["id"]
        for inc in incidents
    }
    selected_label = st.sidebar.selectbox("Select Production Incident", list(incident_options.keys()))
    selected_incident_id = incident_options.get(selected_label)
else:
    st.sidebar.warning("No incidents found in database. Seed database or create one below.")

with st.sidebar.expander("➕ Report New Incident"):
    with st.form("new_incident_form"):
        new_title = st.text_input(
            "Incident Title",
            placeholder="e.g. High latency and 500 error spike in payment-service"
        )
        new_service = st.selectbox(
            "Affected Service",
            ["payment-service", "order-service", "auth-service", "notification-service", "user-service", "analytics-service"]
        )
        new_severity = st.selectbox("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        new_desc = st.text_area(
            "Symptoms & Context",
            placeholder="Describe observed symptoms, error spikes, database alerts, or degraded dependencies..."
        )
        submitted = st.form_submit_button("Submit Incident")
        if submitted:
            if not new_title.strip() or not new_desc.strip():
                st.error("Please provide both an incident title and description.")
            elif create_incident(new_title.strip(), new_service, new_severity, new_desc.strip()):
                st.success("Incident created successfully!")
                st.rerun()
            else:
                st.error("Failed to create incident via API.")

# 3. Main Dashboard View
curr_inc = next((i for i in incidents if i["id"] == selected_incident_id), None)

if curr_inc:
    # Resolve status pill styling and human-readable label
    status_raw = curr_inc.get("status", "OPEN")
    status_configs = {
        "ROOT_CAUSE_IDENTIFIED": ("status-success", "🟢 Root Cause Identified"),
        "INVESTIGATION_FAILED": ("status-failed", "🔴 Investigation Inconclusive"),
        "INVESTIGATING": ("status-running", "🔵 Investigating"),
        "OPEN": ("status-open", "🟡 Open"),
    }
    status_class, status_label = status_configs.get(status_raw, ("status-open", status_raw))

    # Resolve severity pill styling
    sev_raw = curr_inc.get("severity", "MEDIUM").upper()
    sev_class = f"sev-{sev_raw.lower()}"

    # Render Hero Incident Card with high readability & clear status
    reported_time_formatted = format_timestamp(curr_inc.get("created_at"))
    st.markdown(f"""
    <div class="incident-hero-card">
        <div class="incident-meta-bar">
            <span class="meta-pill pill-id">{curr_inc['id']}</span>
            <span class="meta-pill pill-service">{curr_inc['service']}</span>
            <span class="meta-pill {sev_class}">SEVERITY: {sev_raw}</span>
            <span class="status-pill {status_class}">{status_label}</span>
            <span class="pill-time">🕒 Reported: {reported_time_formatted}</span>
        </div>
        <div class="incident-title-text">{curr_inc['title']}</div>
        <div class="incident-desc-box">
            <strong style="color: #94a3b8;">Description & Symptoms:</strong><br>
            {curr_inc['description']}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Status-specific contextual banner
    if status_raw == "INVESTIGATION_FAILED":
        st.warning(
            "⚠️ **Investigation Inconclusive**: Telemetry in the requested window did not yield verified causal evidence, "
            "or automated causal reasoning was inconclusive. You can inspect the trace below or re-run the investigation."
        )
    elif status_raw == "ROOT_CAUSE_IDENTIFIED":
        st.success(
            "✅ **Root Cause Diagnosed**: Evidence has been verified. Review diagnostic hypothesis and operator approval gating below."
        )

    # Action Trigger Button
    btn_label = "🔄 Re-run Multi-Agent Investigation" if status_raw in ["ROOT_CAUSE_IDENTIFIED", "INVESTIGATION_FAILED"] else "🚀 Launch Autonomous Multi-Agent Investigation"
    if st.button(btn_label, type="primary"):
        with st.spinner("Multi-agent system investigating logs, deployments, telemetry metrics, and runbooks..."):
            try:
                resp = requests.post(f"{API_BASE_URL}/incidents/{curr_inc['id']}/investigate", timeout=45)
                if resp.status_code == 200:
                    inv_data = resp.json()
                    st.session_state[f"inv_{curr_inc['id']}"] = inv_data
                    st.success("Investigation complete!")
                    st.rerun()
                else:
                    st.error(f"Investigation failed: {resp.text}")
            except Exception as e:
                st.error(f"API communication error during investigation: {e}")

    # Fetch investigation data (from session state or directly from API)
    inv_data = st.session_state.get(f"inv_{curr_inc['id']}")
    if not inv_data and status_raw in ["ROOT_CAUSE_IDENTIFIED", "INVESTIGATION_FAILED"]:
        inv_data = fetch_latest_investigation(curr_inc["id"])
        if inv_data:
            st.session_state[f"inv_{curr_inc['id']}"] = inv_data

    # Display Investigation Findings
    if inv_data:
        report = inv_data.get("report") or {}
        inv_id = inv_data.get("id")
        history = report.get("agent_history", [])

        # Derive actual executed agents directly from machine-readable execution history
        executed_agents = {
            h.get("agent_key")
            for h in history
            if h.get("agent_key") and h.get("status") == "EXECUTED"
        }

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
            rc_title = selected_hyp.get('selected_root_cause') or 'Inconclusive / No Primary Cause Identified'
            st.markdown(f"### 🎯 Selected Root Cause: **{rc_title}**")
            st.write(f"**Reasoning:** {selected_hyp.get('reasoning_summary', 'N/A')}")
            
            supporting_ids = selected_hyp.get('supporting_evidence_ids', [])
            if supporting_ids:
                st.markdown(f"**Supporting Evidence IDs:** `{', '.join(supporting_ids)}`")
            else:
                st.markdown("**Supporting Evidence IDs:** *None*")

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

        st.markdown(f"**Proposed Remediation:** `{rec.get('action', 'N/A')}`")
        st.markdown(f"**Target Service:** `{rec.get('target_service', curr_inc['service'])}` | **Estimated Risk:** `{rec.get('estimated_risk', 'LOW')}`")
        st.markdown(f"**Rationale:** {rec.get('rationale', 'N/A')}")

        current_approval = inv_data.get("approval_status", "PENDING_APPROVAL")
        st.markdown(f"**Current Status:** `{current_approval}`")

        if inv_data.get("approved_at"):
            st.markdown(f"**Decision Recorded:** `{inv_data.get('operator_decision')}` at `{format_timestamp(inv_data.get('approved_at'))}`")
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
            try:
                st.dataframe(table_data, width="stretch")
            except (TypeError, ValueError):
                st.dataframe(table_data, use_container_width=True)

        st.subheader("5. Detailed Multi-Agent Trace")
        with st.expander("View Chronological Agent Trace"):
            for h in report.get("agent_history", []):
                st.markdown(f"**{h.get('agent')}** ({format_timestamp(h.get('timestamp'))}) — Iteration {h.get('iteration', 0)}:")
                st.markdown(f"- *Action:* {h.get('action')}")
                st.markdown(f"- *Findings:* {h.get('findings')}")
                st.divider()

else:
    st.info("No incident selected.")
