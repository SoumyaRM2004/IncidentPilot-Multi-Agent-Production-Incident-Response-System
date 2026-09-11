from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.rag.retriever import get_retriever


def run_runbook_agent(state: InvestigationState) -> InvestigationState:
    """Runbook / RAG Agent: Searches Qdrant vector database for matching operational runbooks."""
    incident = state["incident"]
    service = incident.get("service", "")
    title = incident.get("title", "")
    description = incident.get("description", "")
    iteration = state.get("iteration_count", 0)

    # Collect keywords from recent log findings to refine semantic search query
    log_snippets = [e["finding"] for e in state["collected_evidence"] if e.get("source") == "application_logs"][:2]
    combined_query = f"{title} {service} {' '.join(log_snippets)}"

    retriever = get_retriever()
    runbook_matches = retriever.search_runbooks(query=combined_query, limit=2, min_score=0.3)

    new_evidence = []
    for match in runbook_matches:
        if not any(e["evidence_id"] == match["evidence_id"] for e in state["collected_evidence"]):
            new_evidence.append({
                "evidence_id": match["evidence_id"],
                "source": "operational_runbook",
                "service": service,
                "timestamp": datetime.utcnow().isoformat(),
                "finding": match["finding"],
                "details": {
                    "source_doc": match["source"],
                    "section": match["section"],
                    "similarity_score": match["score"],
                    "content": match["content"]
                }
            })

    state["collected_evidence"].extend(new_evidence)
    state["current_agent"] = "runbook"

    match_names = [m["source"] for m in runbook_matches]
    summary_findings = (
        f"Queried Qdrant runbook vector index for '{title[:40]}...'. "
        f"Matched {len(runbook_matches)} runbook sections: {', '.join(match_names) if match_names else 'None'}."
    )

    state["agent_history"].append({
        "agent": "Runbook / RAG Agent",
        "timestamp": datetime.utcnow().isoformat(),
        "iteration": iteration,
        "action": f"Executed Qdrant semantic search for runbooks matching {service} incident",
        "findings": summary_findings,
        "evidence_added": [e["evidence_id"] for e in new_evidence]
    })

    return state
