from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.tools.logs import search_logs, get_error_frequency, get_service_logs


def run_log_agent(state: InvestigationState) -> InvestigationState:
    """Log Investigation Agent: Queries logs, detects error patterns, and collects evidence."""
    service = state["incident"].get("service", "")
    iteration = state.get("iteration_count", 0)

    # Deterministic tool execution
    error_freq = get_error_frequency(service=service, minutes=60)
    service_logs = get_service_logs(service=service, limit=10)
    error_logs = search_logs(service=service, level="ERROR", limit=5)

    new_evidence = []
    # Add frequency analytical evidence
    if error_freq["total_count"] > 0 or error_freq["error_count"] > 0:
        new_evidence.append({
            "evidence_id": error_freq["evidence_id"],
            "source": error_freq["source"],
            "service": service,
            "timestamp": datetime.utcnow().isoformat(),
            "finding": error_freq["finding"],
            "details": error_freq
        })

    # Add specific log traces as evidence
    for log_item in (error_logs if error_logs else service_logs[:3]):
        # Deduplicate evidence
        if not any(e["evidence_id"] == log_item["evidence_id"] for e in state["collected_evidence"]):
            new_evidence.append({
                "evidence_id": log_item["evidence_id"],
                "source": log_item["source"],
                "service": log_item["service"],
                "timestamp": log_item["timestamp"],
                "finding": log_item["finding"],
                "details": log_item
            })

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "logs"

    summary_findings = (
        f"Analyzed logs for {service}. Found {error_freq['error_count']} errors in past 60m. "
        f"Collected {len(new_evidence)} log evidence records."
    )

    state["agent_history"].append({
        "agent": "Log Investigation Agent",
        "timestamp": datetime.utcnow().isoformat(),
        "iteration": iteration,
        "action": f"Executed search_logs and get_error_frequency for {service}",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
