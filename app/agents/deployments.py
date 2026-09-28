from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.deployments import get_recent_deployments, get_deployment_details
from app.utils import normalize_timestamp
from app.config import settings


def run_deployment_agent(state: InvestigationState) -> InvestigationState:
    """Deployment Investigation Agent: Inspects releases and changesets based on Supervisor plan."""
    plan = state.get("investigation_plan", {})
    service = state["incident"].get("service", "")
    iteration = state.get("iteration_count", 0)

    # Track executed specialist in state
    if "executed_specialists" not in state:
        state["executed_specialists"] = []
    if "deployments" not in state["executed_specialists"]:
        state["executed_specialists"].append("deployments")

    window_minutes = plan.get("window_minutes", 60)

    # Anchor time window to incident reported_at (same pattern as log/metrics agents)
    incident = state.get("incident", {})
    reported_at = incident.get("reported_at") or incident.get("created_at")
    investigation_time = incident.get("investigation_started_at") or incident.get("investigation_time")

    start_time = None
    end_time = None

    if reported_at:
        reported_dt = normalize_timestamp(reported_at)
        start_time = reported_dt - timedelta(minutes=window_minutes)
        grace_minutes = settings.telemetry_post_report_grace_minutes
        end_time = reported_dt + timedelta(minutes=grace_minutes)
    elif investigation_time:
        inv_dt = normalize_timestamp(investigation_time)
        end_time = inv_dt
        start_time = inv_dt - timedelta(minutes=window_minutes)

    deployments = get_recent_deployments(
        service=service, limit=3,
        window_minutes=window_minutes,
        end_time=end_time, start_time=start_time,
    )
    new_evidence = []

    for dep in deployments:
        details = get_deployment_details(dep["evidence_id"])
        if not any(e["evidence_id"] == dep["evidence_id"] for e in state["collected_evidence"]):
            dep_evidence = details or dep
            new_evidence.append(dep_evidence)

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "deployments"

    most_recent = deployments[0].get("details", {}).get("version", "unknown") if deployments else "None"
    summary_findings = (
        f"Inspected deployments for {service} (window: {window_minutes or 'all'}m). Found {len(deployments)} relevant deployments. "
        f"Most recent: {most_recent}."
    )

    state["agent_history"].append({
        "agent_key": "deployments",
        "agent": "Deployment Investigation Agent",
        "status": "EXECUTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": f"Executed get_recent_deployments for {service} (window: {window_minutes or 'all'}m)",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
