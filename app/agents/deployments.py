from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.deployments import get_recent_deployments, get_deployment_details


def run_deployment_agent(state: InvestigationState) -> InvestigationState:
    """Deployment Investigation Agent: Inspects releases and temporal correlation."""
    service = state["incident"].get("service", "")
    iteration = state.get("iteration_count", 0)

    deployments = get_recent_deployments(service=service, limit=3)
    new_evidence = []

    for dep in deployments:
        # Check details for each recent deployment
        details = get_deployment_details(dep["evidence_id"])
        if not any(e["evidence_id"] == dep["evidence_id"] for e in state["collected_evidence"]):
            new_evidence.append({
                "evidence_id": dep["evidence_id"],
                "source": dep["source"],
                "service": dep["service"],
                "timestamp": dep["deployed_at"],
                "finding": dep["finding"],
                "details": details or dep
            })

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "deployments"

    summary_findings = (
        f"Inspected deployments for {service}. Retrieved {len(deployments)} recent deployment records. "
        f"Most recent version: {deployments[0]['version'] if deployments else 'None'}."
    )

    state["agent_history"].append({
        "agent": "Deployment Investigation Agent",
        "timestamp": datetime.utcnow().isoformat(),
        "iteration": iteration,
        "action": f"Executed get_recent_deployments and get_deployment_details for {service}",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
