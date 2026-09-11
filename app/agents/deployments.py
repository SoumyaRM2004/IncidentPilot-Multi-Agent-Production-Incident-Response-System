from datetime import datetime, timezone
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.deployments import get_recent_deployments, get_deployment_details


def run_deployment_agent(state: InvestigationState) -> InvestigationState:
    """Deployment Investigation Agent: Inspects releases and changesets based on Supervisor plan."""
    plan = state.get("investigation_plan", {})
    required_agents = plan.get("required_agents", ["deployments"])
    service = state["incident"].get("service", "")
    iteration = state.get("iteration_count", 0)

    # Skip if supervisor plan did not select deployments
    if "deployments" not in required_agents:
        return state

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
        f"Inspected deployments for {service}. Found {len(deployments)} relevant deployments. "
        f"Most recent: {deployments[0]['details']['version'] if deployments else 'None'}."
    )

    state["agent_history"].append({
        "agent": "Deployment Investigation Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": f"Executed get_recent_deployments for {service}",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
