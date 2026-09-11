import os
import json
import streamlit as st
import requests
from datetime import datetime

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="IncidentPilot - Autonomous Incident Response Agent",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ IncidentPilot")
st.caption("Autonomous Multi-Agent Production Incident Response & Triage System (V1)")

# Sidebar: Controls & Incident Selection
st.sidebar.header("Active Incidents")

def fetch_incidents():
    try:
        resp = requests.get(f"{API_BASE_URL}/incidents", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        # Fallback to direct DB read if API is not running
        from app.db.database import SessionLocal
        from app.db.models import Incident
        db = SessionLocal()
        try:
            incs = db.query(Incident).order_by(Incident.created_at.desc()).all()
            return [
                {
                    "id": i.id,
                    "title": i.title,
                    "description": i.description,
                    "service": i.service,
                    "severity": i.severity,
                    "status": i.status,
                    "created_at": i.created_at.isoformat()
                }
                for i in incs
            ]
        finally:
            db.close()
    return []

incidents = fetch_incidents()
incident_options = {f"[{i['id']}] {i['service']} - {i['title'][:50]}...": i for i in incidents}

selected_label = st.sidebar.selectbox(
    "Select Incident to Investigate:",
    options=list(incident_options.keys()) if incident_options else ["No incidents found"]
)

# Sidebar: Create new incident modal
with st.sidebar.expander("➕ Report New Incident"):
    with st.form("new_incident_form"):
        new_title = st.text_input("Incident Title")
        new_service = st.selectbox("Service", ["payment-service", "order-service", "auth-service", "notification-service", "user-service"])
        new_severity = st.selectbox("Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        new_desc = st.text_area("Incident Description")
        submitted = st.form_submit_button("Submit Incident")
        if submitted and new_title and new_desc:
            payload = {
                "title": new_title,
                "description": new_desc,
                "service": new_service,
                "severity": new_severity
            }
            try:
                r = requests.post(f"{API_BASE_URL}/incidents", json=payload, timeout=5)
                if r.status_code == 201:
                    st.success("Incident created successfully!")
                    st.rerun()
            except Exception:
                from app.db.database import SessionLocal
                from app.db.models import Incident
                import uuid
                db = SessionLocal()
                try:
                    inc = Incident(
                        id=f"INC-{uuid.uuid4().hex[:6].upper()}",
                        title=new_title,
                        description=new_desc,
                        service=new_service,
                        severity=new_severity,
                        status="OPEN"
                    )
                    db.add(inc)
                    db.commit()
                    st.success("Incident saved to local database!")
                    st.rerun()
                finally:
                    db.close()

# Main Layout
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

    # Investigation Action
    st.divider()
    if st.button("🚀 Trigger Autonomous Investigation", type="primary"):
        with st.spinner("Multi-agent system investigating logs, deployments, metrics, and runbooks..."):
            report_data = None
            try:
                resp = requests.post(f"{API_BASE_URL}/incidents/{curr_inc['id']}/investigate", timeout=30)
                if resp.status_code == 200:
                    report_data = resp.json().get("report")
            except Exception:
                # Direct LangGraph fallback execution
                from app.graph.workflow import run_investigation
                final_state = run_investigation(curr_inc)
                report_data = {
                    "incident_summary": curr_inc,
                    "investigation_plan": final_state.get("investigation_plan"),
                    "evidence": final_state.get("collected_evidence", []),
                    "hypotheses": final_state.get("hypotheses", []),
                    "selected_hypothesis": final_state.get("selected_hypothesis"),
                    "confidence": final_state.get("confidence"),
                    "verification_result": final_state.get("verification_result"),
                    "recommended_action": final_state.get("recommended_action"),
                    "agent_history": final_state.get("agent_history", []),
                    "iteration_count": final_state.get("iteration_count", 0),
                    "human_approval_required": True,
                    "approval_status": "PENDING_APPROVAL"
                }

            if report_data:
                st.session_state[f"report_{curr_inc['id']}"] = report_data

    # Display Investigation Findings if available
    report = st.session_state.get(f"report_{curr_inc['id']}")
    if report:
        st.subheader("1. Agent Orchestration Workflow")
        agent_steps = [
            ("Supervisor Agent", "Created investigation plan and coordinated agents"),
            ("Log Investigation Agent", "Queried application logs & error frequency"),
            ("Deployment Agent", "Analyzed deployment history and temporal correlation"),
            ("Metrics Agent", "Checked telemetry metrics and thresholds"),
            ("Runbook / RAG Agent", "Searched Qdrant vector database for runbooks"),
            ("Root Cause Analyst", "Formulated & ranked root-cause hypotheses"),
            ("Verification Agent", "Audited evidence validity & challenged hypothesis")
        ]

        cols = st.columns(len(agent_steps))
        for idx, (agent_name, role) in enumerate(agent_steps):
            with cols[idx]:
                st.success(f"**{agent_name}**\n\n✅ Done")

        st.subheader("2. Root Cause Analysis & Confidence")
        selected_hyp = report.get("selected_hypothesis", {})
        verif = report.get("verification_result", {})

        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"### 🎯 Selected Root Cause: **{selected_hyp.get('selected_root_cause')}**")
            st.write(f"**Reasoning:** {selected_hyp.get('reasoning_summary')}")
            st.markdown(f"**Supporting Evidence IDs:** `{', '.join(selected_hyp.get('supporting_evidence_ids', []))}`")
        with c2:
            st.metric("Confidence", f"{int(report.get('confidence', 0.0) * 100)}%")
            v_status = "VERIFIED ✅" if verif.get("verified") else "INSUFFICIENT EVIDENCE ⚠️"
            st.info(f"Verification: **{v_status}**")

        st.subheader("3. Human-in-the-Loop & Recommended Action")
        rec = report.get("recommended_action", {})
        st.warning("⚠️ **HUMAN APPROVAL REQUIRED** - Destructive or production-modifying remediation is strictly gated.")
        st.markdown(f"**Recommended Action:** `{rec.get('action')}`")
        st.markdown(f"**Target Service:** `{rec.get('target_service')}` | **Risk Level:** `{rec.get('estimated_risk', 'LOW')}`")
        st.markdown(f"**Rationale:** {rec.get('rationale')}")

        col_appr1, col_appr2 = st.columns(2)
        with col_appr1:
            if st.button("✅ Approve Simulated Remediation", key="approve_btn"):
                st.success("Remediation approved by operator! Simulated execution completed.")
        with col_appr2:
            if st.button("❌ Reject / Escalate to Senior SRE", key="reject_btn"):
                st.error("Remediation rejected. Incident escalated to on-call human SRE.")

        st.subheader("4. Collected Evidence Catalog (Audit Trail)")
        evidence_list = report.get("evidence", [])
        if evidence_list:
            table_data = [
                {
                    "ID": e.get("evidence_id"),
                    "Source": e.get("source"),
                    "Finding": e.get("finding")
                }
                for e in evidence_list
            ]
            st.dataframe(table_data, use_container_width=True)

        st.subheader("5. Detailed Agent Execution Trace")
        with st.expander("View Agent Trace Log"):
            for h in report.get("agent_history", []):
                st.markdown(f"**{h.get('agent')}** ({h.get('timestamp')[:19]}):")
                st.markdown(f"- *Action:* {h.get('action')}")
                st.markdown(f"- *Findings:* {h.get('findings')}")
                st.divider()

else:
    st.info("No incident selected.")
