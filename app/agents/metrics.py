from datetime import datetime, timezone
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.metrics import get_service_metrics


def run_metrics_agent(state: InvestigationState) -> InvestigationState:
    """Metrics Investigation Agent: Queries telemetry metrics based on Supervisor plan."""
    plan = state.get("investigation_plan", {})
    service = state["incident"].get("service", "")
    iteration = state.get("iteration_count", 0)

    # Track executed specialist in state
    if "executed_specialists" not in state:
        state["executed_specialists"] = []
    if "metrics" not in state["executed_specialists"]:
        state["executed_specialists"].append("metrics")

    window_minutes = plan.get("window_minutes", 60)
    metric_names = plan.get("metric_names")
    new_evidence = []

    if metric_names:
        for m_name in metric_names:
            m_records = get_service_metrics(
                service=service,
                metric_name=m_name,
                window_minutes=window_minutes,
                limit=5
            )
            for m in m_records:
                if not any(e["evidence_id"] == m["evidence_id"] for e in state["collected_evidence"]):
                    new_evidence.append(m)
    else:
        all_metrics = get_service_metrics(
            service=service,
            window_minutes=window_minutes,
            limit=10
        )
        for m in all_metrics:
            if not any(e["evidence_id"] == m["evidence_id"] for e in state["collected_evidence"]):
                new_evidence.append(m)

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "metrics"

    summary_findings = (
        f"Evaluated service metrics for {service} over {window_minutes}m window. "
        f"Added {len(new_evidence)} metric evidence items."
    )

    state["agent_history"].append({
        "agent": "Metrics Investigation Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": f"Executed get_service_metrics for {service} (targets: {metric_names or 'all'}, window: {window_minutes}m)",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
