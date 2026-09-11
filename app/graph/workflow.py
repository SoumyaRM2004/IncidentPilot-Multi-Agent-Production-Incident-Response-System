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
from app.config import settings


def route_next_specialist(state: InvestigationState) -> Literal["logs", "deployments", "metrics", "runbook", "root_cause"]:
    """Determines the next specialist agent to execute based on supervisor plan.

    Routes to root_cause once all required specialists for this iteration have executed.
    """
    plan = state.get("investigation_plan", {})
    required = plan.get("required_agents", [])
    executed = state.get("executed_specialists", [])

    for agent in required:
        if agent not in executed:
            return agent

    return "root_cause"


def route_after_verification(state: InvestigationState) -> Literal["supervisor", "__end__"]:
    """Conditional routing based on verification result and iteration budget."""
    v_res = state.get("verification_result", {})
    verified = v_res.get("verified", False)
    status = state.get("investigation_status", "")

    # If verified or reached terminal status, terminate graph execution
    if verified or status in ("SUCCESS", "INSUFFICIENT_EVIDENCE", "INVESTIGATION_FAILED", "VERIFICATION_UNAVAILABLE"):
        return "__end__"

    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", settings.max_investigation_iterations)

    # Invariant: Verification Agent increments iteration_count prior to routing (e.g., 0 -> 1, 1 -> 2).
    # Thus iteration_count is the target iteration for the upcoming loop.
    # When max_iterations=2, iteration_count=2 represents the final allowable pass.
    # Any iteration > max_iterations terminates immediately.
    if iteration <= max_iterations:
        return "supervisor"

    return "__end__"


def create_investigation_graph():
    """Constructs the compiled LangGraph multi-agent workflow with genuine dynamic specialist routing."""
    workflow = StateGraph(InvestigationState)

    # Register agent nodes
    workflow.add_node("supervisor", run_supervisor_agent)
    workflow.add_node("logs", run_log_agent)
    workflow.add_node("deployments", run_deployment_agent)
    workflow.add_node("metrics", run_metrics_agent)
    workflow.add_node("runbook", run_runbook_agent)
    workflow.add_node("root_cause", run_root_cause_agent)
    workflow.add_node("verification", run_verification_agent)

    # Entry edge
    workflow.add_edge(START, "supervisor")

    # Dynamic specialist routing mapping
    specialist_routes = {
        "logs": "logs",
        "deployments": "deployments",
        "metrics": "metrics",
        "runbook": "runbook",
        "root_cause": "root_cause"
    }

    # Conditional routing from supervisor and after each specialist execution
    workflow.add_conditional_edges("supervisor", route_next_specialist, specialist_routes)
    workflow.add_conditional_edges("logs", route_next_specialist, specialist_routes)
    workflow.add_conditional_edges("deployments", route_next_specialist, specialist_routes)
    workflow.add_conditional_edges("metrics", route_next_specialist, specialist_routes)
    workflow.add_conditional_edges("runbook", route_next_specialist, specialist_routes)

    # Evidence synthesis to verification
    workflow.add_edge("root_cause", "verification")

    # Conditional branch from verification: PASS/Terminal -> END; FAIL -> supervisor (adaptive loop)
    workflow.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "supervisor": "supervisor",
            "__end__": END
        }
    )

    return workflow.compile()


def create_initial_state(incident: Dict[str, Any], max_iterations: int = None) -> InvestigationState:
    """Helper to initialize the shared LangGraph investigation state."""
    max_iters = max_iterations if max_iterations is not None else settings.max_investigation_iterations
    return {
        "incident": incident,
        "investigation_plan": {},
        "current_agent": "supervisor",
        "executed_specialists": [],
        "collected_evidence": [],
        "hypotheses": [],
        "selected_hypothesis": None,
        "verification_result": None,
        "confidence": 0.0,
        "confidence_assessment": None,
        "recommended_action": None,
        "investigation_status": "RUNNING",
        "agent_history": [],
        "iteration_count": 0,
        "max_iterations": max_iters,
        "error_message": None
    }


def run_investigation(incident: Dict[str, Any], max_iterations: int = None) -> InvestigationState:
    """Executes the full LangGraph investigation workflow for an incident."""
    graph = create_investigation_graph()
    initial_state = create_initial_state(incident=incident, max_iterations=max_iterations)
    final_state = graph.invoke(initial_state)
    return final_state
