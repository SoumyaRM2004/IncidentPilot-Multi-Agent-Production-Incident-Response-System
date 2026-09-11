from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.metrics import get_service_metrics, get_metric_window


def run_metrics_agent(state: InvestigationState) -> InvestigationState:
    """Metrics Investigation Agent: Queries telemetry for resource exhaustion and degradation."""
    service = state["incident"].get("service", "")
    iteration = state.get("iteration_count", 0)

    # Deterministic metric retrieval
    metrics = get_service_metrics(service=service)
    new_evidence = []

    for m in metrics:
        if not any(e["evidence_id"] == m["evidence_id"] for e in state["collected_evidence"]):
            new_evidence.append({
                "evidence_id": m["evidence_id"],
                "source": m["source"],
                "service": m["service"],
                "timestamp": m["timestamp"],
                "finding": m["finding"],
                "details": m
            })

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "metrics"

    metric_summary = ", ".join([f"{m['metric_name']}={m['value']}" for m in metrics[:4]]) if metrics else "No metrics found"
    summary_findings = f"Evaluated system metrics for {service}: {metric_summary}. Added {len(new_evidence)} metric records."

    state["agent_history"].append({
        "agent": "Metrics Investigation Agent",
        "timestamp": datetime.utcnow().isoformat(),
        "iteration": iteration,
        "action": f"Executed get_service_metrics for {service}",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
