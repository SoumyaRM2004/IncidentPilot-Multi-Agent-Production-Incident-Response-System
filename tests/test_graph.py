from unittest.mock import patch
from app.graph.workflow import (
    create_investigation_graph,
    route_after_verification,
    route_next_specialist,
    create_initial_state
)


def test_graph_compilation():
    graph = create_investigation_graph()
    assert graph is not None


def test_route_next_specialist_ordering():
    state = create_initial_state({"id": "1", "service": "test-service"})
    state["investigation_plan"] = {"required_agents": ["logs", "metrics"]}
    state["executed_specialists"] = []

    # First specialist should be logs
    assert route_next_specialist(state) == "logs"

    # After logs executes, next should be metrics
    state["executed_specialists"].append("logs")
    assert route_next_specialist(state) == "metrics"

    # After metrics executes, next should be root_cause
    state["executed_specialists"].append("metrics")
    assert route_next_specialist(state) == "root_cause"


def test_supervisor_plan_strictly_controls_graph_execution(db_session):
    """When Supervisor selects ['logs', 'metrics'], deployment and runbook nodes MUST NOT execute."""
    incident = {
        "id": "INC-TEST-PLAN",
        "service": "payment-service",
        "title": "Database connection timeouts",
        "description": "SQL connection timeouts on payment checkout",
        "severity": "HIGH"
    }

    # Force supervisor to select strictly logs and metrics
    fixed_plan = {
        "focus": "Inspect logs and metrics only",
        "required_agents": ["logs", "metrics"],
        "strategy": "Targeted test execution",
        "window_minutes": 60
    }

    with patch("app.agents.supervisor._create_initial_plan", return_value=fixed_plan):
        with patch("app.agents.supervisor.get_groq_client", return_value=None):
            graph = create_investigation_graph()
            initial_state = create_initial_state(incident=incident)
            final_state = graph.invoke(initial_state)

    executed = final_state.get("executed_specialists", [])
    assert "logs" in executed
    assert "metrics" in executed
    assert "deployments" not in executed, "Deployments was executed despite not being in supervisor plan!"
    assert "runbook" not in executed, "Runbook was executed despite not being in supervisor plan!"

    # Verify agent_history only contains executed nodes
    agent_names = [h.get("agent") for h in final_state.get("agent_history", [])]
    assert "Log Investigation Agent" in agent_names
    assert "Metrics Investigation Agent" in agent_names
    assert "Deployment Investigation Agent" not in agent_names
    assert "Runbook / RAG Agent" not in agent_names


def test_route_after_verification_pass():
    state = create_initial_state({"id": "1", "service": "s"})
    state["verification_result"] = {"verified": True}
    state["investigation_status"] = "SUCCESS"

    next_node = route_after_verification(state)
    assert next_node == "__end__"


def test_route_after_verification_reinvestigate_loop():
    state = create_initial_state({"id": "1", "service": "s"}, max_iterations=2)
    state["verification_result"] = {"verified": False}
    state["investigation_status"] = "RUNNING"
    state["iteration_count"] = 1

    next_node = route_after_verification(state)
    assert next_node == "supervisor"


def test_route_after_verification_max_iteration_stop():
    state = create_initial_state({"id": "1", "service": "s"}, max_iterations=2)
    state["verification_result"] = {"verified": False}
    state["investigation_status"] = "INSUFFICIENT_EVIDENCE"
    state["iteration_count"] = 2

    next_node = route_after_verification(state)
    assert next_node == "__end__"


def test_workflow_enforces_strict_max_iteration_budget(db_session):
    """Workflow must terminate at max_iterations without exceeding iteration budget."""
    empty_incident = {
        "id": "INC-ITER-BOUND",
        "service": "ghost-service",
        "title": "Unprovable anomaly",
        "description": "No telemetry available."
    }
    with patch("app.agents.supervisor.get_groq_client", return_value=None), \
         patch("app.agents.root_cause.get_groq_client", return_value=None), \
         patch("app.agents.verification.get_groq_client", return_value=None):
        graph = create_investigation_graph()
        initial_state = create_initial_state(incident=empty_incident, max_iterations=2)
        final_state = graph.invoke(initial_state)

    # Invariant: Must terminate at exactly iteration 2 with INSUFFICIENT_EVIDENCE
    assert final_state["iteration_count"] == 2
    assert final_state["investigation_status"] == "INSUFFICIENT_EVIDENCE"
    assert final_state["verification_result"]["verified"] is False
