from datetime import datetime, timezone
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.deployments import get_recent_deployments, get_deployment_details


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

    window_minutes = plan.get("window_minutes")
    deployments = get_recent_deployments(service=service, limit=3, window_minutes=window_minutes)
    new_evidence = []

    for dep in deployments:
        details = get_deployment_details(dep["evidence_id"])
        if not any(e["evidence_id"] == dep["evidence_id"] for e in state["collected_evidence"]):
            dep_evidence = details or dep
            new_evidence.append(dep_evidence)

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "deployments"

    summary_findings = (
        f"Inspected deployments for {service} (window: {window_minutes or 'all'}m). Found {len(deployments)} relevant deployments. "
        f"Most recent: {deployments[0]['details']['version'] if deployments else 'None'}."
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
