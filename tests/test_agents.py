from app.graph.workflow import create_initial_state
from app.agents.supervisor import run_supervisor_agent
from app.agents.logs import run_log_agent
from app.agents.deployments import run_deployment_agent
from app.agents.metrics import run_metrics_agent
from app.agents.runbook import run_runbook_agent
from app.agents.root_cause import run_root_cause_agent
from app.agents.verification import run_verification_agent, _deterministic_audit


def test_supervisor_agent_planning():
    incident = {
        "id": "INC-001",
        "title": "Payment database connection timeouts",
        "description": "Payment timeouts observed on checkout gateway",
        "service": "payment-service",
        "severity": "CRITICAL"
    }
    state = create_initial_state(incident)
    state = run_supervisor_agent(state)

    assert state["investigation_plan"] is not None
    assert "required_agents" in state["investigation_plan"]
    # Verify allowlist enforcement
    for agent_name in state["investigation_plan"]["required_agents"]:
        assert agent_name in {"logs", "deployments", "metrics", "runbook"}
    assert len(state["agent_history"]) == 1
    assert state["agent_history"][0]["agent"] == "Supervisor Agent"


def test_investigation_agents_evidence_collection():
    incident = {
        "id": "INC-001",
        "title": "Payment database connection timeouts",
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

    assert len(state["collected_evidence"]) >= 3
    source_types = {e.get("source_type") for e in state["collected_evidence"]}
    assert "log" in source_types or "analytics" in source_types
    assert "metric" in source_types
    assert "runbook" in source_types


def test_verification_agent_catches_fabricated_evidence():
    """Layer 1 deterministic check must reject any hallucinated evidence ID."""
    incident = {"id": "INC-TEST", "service": "test-service", "title": "Test", "description": "Test"}
    state = create_initial_state(incident)

    state["selected_hypothesis"] = {
        "selected_root_cause": "Fabricated Root Cause",
        "confidence": 0.85,
        "supporting_evidence_ids": ["FAKE-LOG-999", "FAKE-METRIC-999"],
        "contradictory_evidence_ids": [],
        "reasoning_summary": "Fabricated reasoning."
    }
    state["collected_evidence"] = [
        {"evidence_id": "LOG-REAL-1", "source_type": "log", "source": "logs", "finding": "ok", "service": "test-service"}
    ]

    state = run_verification_agent(state)
    assert state["verification_result"]["verified"] is False
    assert "fabricated or non-existent" in state["verification_result"]["explanation"].lower()


def test_verification_agent_rejects_insufficient_evidence():
    """Layer 1 must reject hypotheses with fewer than minimum required evidence items."""
    selected_hyp = {
        "selected_root_cause": "Unproven Cause",
        "confidence": 0.60,
        "supporting_evidence_ids": ["LOG-1"],
        "contradictory_evidence_ids": []
    }
    evidence_list = [{"evidence_id": "LOG-1", "source_type": "log"}]
    passed, reason = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert "insufficient evidence" in reason.lower()


def test_verification_agent_rejects_uncalibrated_high_confidence():
    """Layer 1 must reject confidence >= 0.80 if evidence comes from only 1 source type."""
    selected_hyp = {
        "selected_root_cause": "Overconfident Single Source Cause",
        "confidence": 0.90,
        "supporting_evidence_ids": ["LOG-1", "LOG-2"],
        "contradictory_evidence_ids": []
    }
    evidence_list = [
        {"evidence_id": "LOG-1", "source_type": "log"},
        {"evidence_id": "LOG-2", "source_type": "log"}
    ]
    passed, reason = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert "multi-source corroboration" in reason.lower()


def test_verification_agent_rejects_contradictions():
    """Layer 1 must reject hypotheses that have unaddressed contradictory evidence."""
    selected_hyp = {
        "selected_root_cause": "Contradicted Cause",
        "confidence": 0.60,
        "supporting_evidence_ids": ["LOG-1", "METRIC-1"],
        "contradictory_evidence_ids": ["METRIC-2"]
    }
    evidence_list = [
        {"evidence_id": "LOG-1", "source_type": "log"},
        {"evidence_id": "METRIC-1", "source_type": "metric"},
        {"evidence_id": "METRIC-2", "source_type": "metric"}
    ]
    passed, reason = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert "contradictory evidence" in reason.lower()
