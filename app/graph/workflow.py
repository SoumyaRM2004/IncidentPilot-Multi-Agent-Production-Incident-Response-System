from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from app.graph.state import InvestigationState
from app.agents.supervisor import run_supervisor_agent
from app.agents.logs import run_log_agent
from app.agents.deployments import run_deployment_agent
from app.agents.metrics import run_metrics_agent
from app.agents.runbook import run_runbook_agent
from app.agents.root_cause import run_root_cause_agent
from app.agents.verification import run_verification_agent


def route_after_verification(state: InvestigationState) -> Literal["supervisor", "__end__"]:
    """Conditional routing based on verification result and iteration budget."""
    v_res = state.get("verification_result", {})
    verified = v_res.get("verified", False)
    status = state.get("investigation_status", "")

    # If verified, proceed to final report & human approval
    if verified or status == "SUCCESS":
        return "__end__"

    # If verification failed but iteration count is within budget, re-investigate
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 2)

    if iteration <= max_iterations and status != "INSUFFICIENT_EVIDENCE":
        return "supervisor"

    return "__end__"


def create_investigation_graph():
    """Constructs the compiled LangGraph multi-agent workflow."""
    workflow = StateGraph(InvestigationState)

    # Register agent nodes
    workflow.add_node("supervisor", run_supervisor_agent)
    workflow.add_node("logs", run_log_agent)
    workflow.add_node("deployments", run_deployment_agent)
    workflow.add_node("metrics", run_metrics_agent)
    workflow.add_node("runbook", run_runbook_agent)
    workflow.add_node("root_cause", run_root_cause_agent)
    workflow.add_node("verification", run_verification_agent)

    # Flow connections
    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "logs")
    workflow.add_edge("logs", "deployments")
    workflow.add_edge("deployments", "metrics")
    workflow.add_edge("metrics", "runbook")
    workflow.add_edge("runbook", "root_cause")
    workflow.add_edge("root_cause", "verification")

    # Conditional branch from verification: PASS -> END; FAIL -> supervisor (re-investigate) or END (insufficient)
    workflow.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "supervisor": "supervisor",
            "__end__": END
        }
    )

    return workflow.compile()


def create_initial_state(incident: Dict[str, Any], max_iterations: int = 2) -> InvestigationState:
    """Helper to initialize the shared LangGraph investigation state."""
    return {
        "incident": incident,
        "investigation_plan": {},
        "current_agent": "supervisor",
        "collected_evidence": [],
        "hypotheses": [],
        "selected_hypothesis": None,
        "verification_result": None,
        "confidence": 0.0,
        "recommended_action": None,
        "investigation_status": "RUNNING",
        "agent_history": [],
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "error_message": None
    }


def run_investigation(incident: Dict[str, Any], max_iterations: int = 2) -> InvestigationState:
    """Executes the full LangGraph investigation workflow for an incident."""
    graph = create_investigation_graph()
    initial_state = create_initial_state(incident=incident, max_iterations=max_iterations)
    final_state = graph.invoke(initial_state)
    return final_state
