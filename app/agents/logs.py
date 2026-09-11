from datetime import datetime, timezone
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.logs import search_logs, get_error_frequency, get_service_logs


def run_log_agent(state: InvestigationState) -> InvestigationState:
    """Log Investigation Agent: Executes targeted log queries based on Supervisor plan."""
    plan = state.get("investigation_plan", {})
    required_agents = plan.get("required_agents", ["logs"])
    service = state["incident"].get("service", "")
    iteration = state.get("iteration_count", 0)

    # Skip if supervisor plan did not select logs
    if "logs" not in required_agents:
        return state

    window_minutes = plan.get("window_minutes", 60)
    log_query = plan.get("log_query")

    # Deterministic log inspections
    error_freq = get_error_frequency(service=service, minutes=window_minutes)
    error_logs = search_logs(service=service, query=log_query, level="ERROR", window_minutes=window_minutes, limit=5)
    service_logs = get_service_logs(service=service, limit=5) if not error_logs else []

    new_evidence = []

    # Frequency analysis evidence
    if error_freq["details"]["total_count"] > 0:
        if not any(e["evidence_id"] == error_freq["evidence_id"] for e in state["collected_evidence"]):
            new_evidence.append(error_freq)

    # Individual log trace evidence
    for log_item in (error_logs if error_logs else service_logs):
        if not any(e["evidence_id"] == log_item["evidence_id"] for e in state["collected_evidence"]):
            new_evidence.append(log_item)

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "logs"

    summary_findings = (
        f"Analyzed logs for {service} (window: {window_minutes}m). "
        f"Found {error_freq['details']['error_count']} errors. Added {len(new_evidence)} new evidence items."
    )

    state["agent_history"].append({
        "agent": "Log Investigation Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": f"Executed search_logs and get_error_frequency for {service} (window: {window_minutes}m)",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
