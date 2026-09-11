from app.graph.workflow import create_initial_state
from app.agents.supervisor import run_supervisor_agent
from app.agents.logs import run_log_agent
from app.agents.deployments import run_deployment_agent
from app.agents.metrics import run_metrics_agent
from app.agents.runbook import run_runbook_agent
from app.agents.root_cause import run_root_cause_agent
from app.agents.verification import run_verification_agent


def test_supervisor_agent_planning():
    incident = {
        "id": "INC-001",
        "title": "Database pool exhaustion",
        "description": "Payment timeouts",
        "service": "payment-service",
        "severity": "CRITICAL"
    }
    state = create_initial_state(incident)
    state = run_supervisor_agent(state)

    assert state["investigation_plan"] is not None
    assert "required_agents" in state["investigation_plan"]
    assert len(state["agent_history"]) == 1
    assert state["agent_history"][0]["agent"] == "Supervisor Agent"


def test_investigation_agents_evidence_collection():
    incident = {
        "id": "INC-001",
        "title": "Database pool exhaustion",
        "description": "Payment timeouts",
        "service": "payment-service",
        "severity": "CRITICAL"
    }
    state = create_initial_state(incident)
    state = run_supervisor_agent(state)
    state = run_log_agent(state)
    state = run_deployment_agent(state)
    state = run_metrics_agent(state)
    state = run_runbook_agent(state)

    assert len(state["collected_evidence"]) >= 4
    sources = {e["source"] for e in state["collected_evidence"]}
    assert "application_logs" in sources or "log_analytics" in sources
    assert "service_metrics" in sources
    assert "operational_runbook" in sources


def test_verification_agent_catches_fabricated_evidence():
    incident = {"id": "INC-TEST", "service": "test-service", "title": "Test", "description": "Test"}
    state = create_initial_state(incident)

    # Simulate root cause analyst hallucinating non-existent evidence IDs
    state["selected_hypothesis"] = {
        "selected_root_cause": "Fabricated Root Cause",
        "confidence": 0.95,
        "supporting_evidence_ids": ["FAKE-LOG-999", "FAKE-METRIC-999"],
        "contradictory_evidence_ids": [],
        "reasoning_summary": "Fabricated reasoning."
    }
    state["collected_evidence"] = [
        {"evidence_id": "REAL-1", "source": "logs", "finding": "ok", "service": "test-service"}
    ]

    state = run_verification_agent(state)
    assert state["verification_result"]["verified"] is False
    assert "unverified or fabricated" in state["verification_result"]["explanation"].lower() or "insufficient" in state["verification_result"]["explanation"].lower()
