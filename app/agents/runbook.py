from datetime import datetime, timezone
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.rag.retriever import get_retriever


def run_runbook_agent(state: InvestigationState) -> InvestigationState:
    """Runbook / RAG Agent: Searches Qdrant vector database for matching operational runbooks."""
    incident = state["incident"]
    service = incident.get("service", "")
    title = incident.get("title", "")
    iteration = state.get("iteration_count", 0)

    # Track executed specialist in state
    if "executed_specialists" not in state:
        state["executed_specialists"] = []
    if "runbook" not in state["executed_specialists"]:
        state["executed_specialists"].append("runbook")

    # Formulate search query using incident title and high-signal log findings
    log_snippets = [
        e["finding"] for e in state["collected_evidence"]
        if e.get("source_type") == "log"
    ][:2]
    combined_query = f"{title} {service} {' '.join(log_snippets)}"

    retriever = get_retriever()
    runbook_matches = retriever.search_runbooks(query=combined_query, limit=2)

    new_evidence = []
    for match in runbook_matches:
        if not any(e["evidence_id"] == match["evidence_id"] for e in state["collected_evidence"]):
            new_evidence.append(match)

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "runbook"

    match_names = [m["details"].get("source_doc", m["evidence_id"]) for m in runbook_matches]
    summary_findings = (
        f"Queried Qdrant runbook vector index for '{title[:40]}...'. "
        f"Retrieved {len(runbook_matches)} operational runbook chunks: {', '.join(match_names) if match_names else 'None'}."
    )

    state["agent_history"].append({
        "agent_key": "runbook",
        "agent": "Runbook / RAG Agent",
        "status": "EXECUTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": f"Executed Qdrant semantic search for runbooks matching {service} incident",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
