from unittest.mock import patch
from app.graph.workflow import create_initial_state
from app.agents.supervisor import run_supervisor_agent, ALLOWED_AGENTS
from app.agents.logs import run_log_agent
from app.agents.deployments import run_deployment_agent
from app.agents.metrics import run_metrics_agent
from app.agents.runbook import run_runbook_agent
from app.agents.root_cause import run_root_cause_agent
from app.agents.verification import run_verification_agent, _deterministic_audit


def test_supervisor_agent_allowlist_validation():
    """Supervisor plan must strictly filter out any invalid agent names."""
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
    for agent_name in state["investigation_plan"]["required_agents"]:
        assert agent_name in ALLOWED_AGENTS
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


def test_root_cause_preserves_hallucinated_evidence_ids():
    """Root Cause Analyst must NOT silently discard hallucinated citations so Layer 1 can detect them."""
    incident = {"id": "INC-TEST", "service": "order-service", "title": "Crash", "description": "Crash"}
    state = create_initial_state(incident)
    state["collected_evidence"] = [
        {"evidence_id": "LOG-1", "source_type": "log", "source": "logs", "service": "order-service", "finding": "Real error"}
    ]

    # Mock analysis_dict returning a hallucinated ID
    mock_output = {
        "selected_root_cause": "Hypothetical error",
        "confidence": 0.85,
        "supporting_evidence_ids": ["LOG-1", "LOG-FABRICATED-999"],
        "contradictory_evidence_ids": [],
        "reasoning_summary": "Test rationale",
        "hypotheses": [],
        "recommended_action": {"action": "Fix it", "target_service": "order-service"}
    }
    with patch("app.agents.root_cause._synthesize_from_evidence", return_value=mock_output):
        state = run_root_cause_agent(state)

    # Must preserve the fabricated citation
    assert "LOG-FABRICATED-999" in state["selected_hypothesis"]["supporting_evidence_ids"]

    # Layer 1 must catch and fail verification on the fabricated citation
    v_state = run_verification_agent(state)
    assert v_state["verification_result"]["verified"] is False
    assert v_state["verification_result"]["challenge_category"] == "FABRICATED_EVIDENCE_ID"


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
    assert state["verification_result"]["challenge_category"] == "FABRICATED_EVIDENCE_ID"
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
    passed, category, reason, _, _ = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert category == "INSUFFICIENT_EVIDENCE"
    assert "insufficient evidence" in reason.lower()


def test_two_logs_alone_do_not_count_as_two_independent_source_types():
    """Two logs alone are from a single domain and must NOT pass source diversity."""
    selected_hyp = {
        "selected_root_cause": "Single Domain Logs Cause",
        "confidence": 0.75,
        "supporting_evidence_ids": ["LOG-1", "LOG-2"],
        "contradictory_evidence_ids": []
    }
    evidence_list = [
        {"evidence_id": "LOG-1", "source_type": "log"},
        {"evidence_id": "LOG-2", "source_type": "log"}
    ]
    passed, category, reason, missing, requested = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert category == "LOW_SOURCE_DIVERSITY"
    assert "independent empirical source types" in reason.lower()
    assert "metric" in missing or "deployment" in missing


def test_log_and_metric_satisfies_source_diversity():
    """One log plus one metric represents two distinct empirical domains and satisfies diversity."""
    selected_hyp = {
        "selected_root_cause": "Multi Domain Empirical Cause",
        "confidence": 0.85,
        "supporting_evidence_ids": ["LOG-1", "METRIC-1"],
        "contradictory_evidence_ids": []
    }
    evidence_list = [
        {"evidence_id": "LOG-1", "source_type": "log"},
        {"evidence_id": "METRIC-1", "source_type": "metric"}
    ]
    passed, category, reason, _, _ = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is True
    assert category == "VALIDATED"


def test_verification_agent_rejects_unresolved_contradictions():
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
    passed, category, reason, _, _ = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert category == "UNRESOLVED_CONTRADICTION"
    assert "contradictory evidence" in reason.lower()


def test_layer2_unavailable_never_produces_verified():
    """When Layer 2 LLM is unavailable, verification must produce VERIFICATION_UNAVAILABLE, never verified=True."""
    incident = {"id": "INC-TEST", "service": "test-service", "title": "Test", "description": "Test"}
    state = create_initial_state(incident)
    state["selected_hypothesis"] = {
        "selected_root_cause": "Valid Sound Cause",
        "confidence": 0.85,
        "supporting_evidence_ids": ["LOG-1", "METRIC-1"],
        "contradictory_evidence_ids": [],
        "reasoning_summary": "Solid multi-domain correlation."
    }
    state["collected_evidence"] = [
        {"evidence_id": "LOG-1", "source_type": "log", "source": "logs", "finding": "err", "service": "test-service"},
        {"evidence_id": "METRIC-1", "source_type": "metric", "source": "metrics", "finding": "sat", "service": "test-service"}
    ]

    with patch("app.agents.verification.get_groq_client", return_value=None):
        state = run_verification_agent(state)

    assert state["verification_result"]["verified"] is False
    assert state["verification_result"]["challenge_category"] == "VERIFICATION_UNAVAILABLE"
    assert "Layer 2 unavailable" in state["verification_result"]["explanation"]


def test_layer2_rejection_produces_challenged():
    """When Layer 2 semantic evaluation challenges causality, status must be CHALLENGED and verified=False."""
    incident = {"id": "INC-TEST", "service": "test-service", "title": "Test", "description": "Test"}
    state = create_initial_state(incident)
    state["selected_hypothesis"] = {
        "selected_root_cause": "Correlated but not causal",
        "confidence": 0.85,
        "supporting_evidence_ids": ["LOG-1", "METRIC-1"],
        "contradictory_evidence_ids": [],
        "reasoning_summary": "Correlation only."
    }
    state["collected_evidence"] = [
        {"evidence_id": "LOG-1", "source_type": "log", "source": "logs", "finding": "err", "service": "test-service"},
        {"evidence_id": "METRIC-1", "source_type": "metric", "source": "metrics", "finding": "sat", "service": "test-service"}
    ]

    mock_layer2 = {
        "verified": False,
        "confidence_acceptable": False,
        "evidence_sufficient": True,
        "contradictions_found": False,
        "missing_evidence_types": ["deployment"],
        "requested_agent_types": ["deployments"],
        "explanation": "Correlation observed but deployment changeset is required to establish causality."
    }

    with patch("app.agents.verification.get_groq_client", return_value=True):
        with patch("app.agents.verification.call_groq_json", return_value=mock_layer2):
            state = run_verification_agent(state)

    assert state["verification_result"]["verified"] is False
    assert state["verification_result"]["challenge_category"] == "SEMANTIC_CHALLENGE"


def test_reinvestigation_consumes_structured_verification_feedback():
    """Supervisor must consume structured verification fields rather than parsing free-form strings."""
    incident = {"id": "INC-TEST", "service": "order-service", "title": "Spike", "description": "Spike"}
    state = create_initial_state(incident)
    state["iteration_count"] = 1
    state["verification_result"] = {
        "verified": False,
        "challenge_category": "LOW_SOURCE_DIVERSITY",
        "missing_evidence_types": ["deployment"],
        "requested_agent_types": ["deployments"],
        "suggested_time_window": 180,
        "explanation": "Free-form explanation text that does not contain trigger keywords."
    }

    state = run_supervisor_agent(state)
    plan = state["investigation_plan"]
    assert "deployments" in plan["required_agents"]
    assert plan["window_minutes"] == 180


def test_runbook_does_not_count_as_empirical_proof():
    """Runbook guidance is operational context and must NOT count as an empirical domain."""
    selected_hyp = {
        "selected_root_cause": "Hypothetical Cause",
        "confidence": 0.65,
        "supporting_evidence_ids": ["LOG-1", "RUNBOOK-1"],
        "contradictory_evidence_ids": []
    }
    evidence_list = [
        {"evidence_id": "LOG-1", "source_type": "log"},
        {"evidence_id": "RUNBOOK-1", "source_type": "runbook"}
    ]
    passed, category, reason, missing, requested = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert category == "LOW_SOURCE_DIVERSITY"
    assert "runbook guidance is operational context" in reason.lower()
    assert "metric" in missing or "deployment" in missing


def test_log_plus_analytics_is_not_two_independent_domains():
    """Log-derived analytics and raw logs belong to the same empirical domain ('log') and fail diversity."""
    selected_hyp = {
        "selected_root_cause": "Hypothetical Cause",
        "confidence": 0.65,
        "supporting_evidence_ids": ["LOG-1", "FREQ-ANALYTICS-1"],
        "contradictory_evidence_ids": []
    }
    evidence_list = [
        {"evidence_id": "LOG-1", "source_type": "log"},
        {"evidence_id": "FREQ-ANALYTICS-1", "source_type": "analytics"}
    ]
    passed, category, reason, missing, requested = _deterministic_audit(selected_hyp, evidence_list)
    assert passed is False
    assert category == "LOW_SOURCE_DIVERSITY"
    assert "log-derived analytics does not constitute a separate empirical domain" in reason.lower()


def test_root_cause_llm_unavailable_conservative_fallback():
    """When Groq LLM is unavailable, Root Cause Agent must use conservative fallback without inventing causes."""
    incident = {"id": "INC-TEST", "service": "payment-service", "title": "Database degradation", "description": "Timeouts"}
    state = create_initial_state(incident)
    state["collected_evidence"] = [
        {"evidence_id": "LOG-1", "source_type": "log", "source": "logs", "finding": "DB connection timeout", "service": "payment-service"},
        {"evidence_id": "METRIC-1", "source_type": "metric", "source": "metrics", "finding": "Pool saturation 99%", "service": "payment-service"}
    ]

    with patch("app.agents.root_cause.get_groq_client", return_value=None):
        state = run_root_cause_agent(state)

    selected = state["selected_hypothesis"]
    assert selected["selected_root_cause"] == "Inconclusive: automated causal inference unavailable"
    assert selected["confidence"] <= 0.30
    assert selected["supporting_evidence_ids"] == []
    assert "sanitized_supporting_evidence_ids" not in selected
    assert "payment-service degradation:" not in selected["selected_root_cause"]
    assert selected["recommended_action"]["estimated_risk"] == "LOW"
    assert "escalate" in selected["recommended_action"]["action"].lower()

    # Verification must run on the fallback and refuse to mark it verified
    v_state = run_verification_agent(state)
    assert v_state["verification_result"]["verified"] is False
    assert v_state["verification_result"]["challenge_category"] == "INSUFFICIENT_EVIDENCE"


def test_supervisor_fallback_conservative_signals():
    """Supervisor fallback must default to logs, metrics, runbook; crash/outage/spike alone must not trigger deployments."""
    # Scenario with symptom keywords alone
    symptom_incident = {
        "id": "INC-SYMPTOM",
        "service": "order-service",
        "title": "Severe latency spike and crash outage",
        "description": "System encountered high error spike resulting in outage and service crash."
    }
    state = create_initial_state(symptom_incident)
    with patch("app.agents.supervisor.get_groq_client", return_value=None):
        state = run_supervisor_agent(state)

    plan = state["investigation_plan"]
    assert "logs" in plan["required_agents"]
    assert "metrics" in plan["required_agents"]
    assert "runbook" in plan["required_agents"]
    assert "deployments" not in plan["required_agents"], "Symptom words ('crash', 'outage', 'spike') must NOT trigger deployment agent!"

    # Scenario with explicit deployment/release signal
    release_incident = {
        "id": "INC-RELEASE",
        "service": "order-service",
        "title": "Checkout failure following release v2.4.1",
        "description": "Errors observed immediately after deployment rollout commit."
    }
    rel_state = create_initial_state(release_incident)
    with patch("app.agents.supervisor.get_groq_client", return_value=None):
        rel_state = run_supervisor_agent(rel_state)

    rel_plan = rel_state["investigation_plan"]
    assert "deployments" in rel_plan["required_agents"]


def test_frontend_execution_trace_derivation():
    """UI execution trace must derive EXECUTED and SKIPPED states from machine-readable history."""
    sample_history = [
        {"agent_key": "supervisor", "agent": "Supervisor Agent", "status": "EXECUTED"},
        {"agent_key": "logs", "agent": "Log Investigation Agent", "status": "EXECUTED"},
        {"agent_key": "metrics", "agent": "Metrics Investigation Agent", "status": "EXECUTED"},
        {"agent_key": "root_cause", "agent": "Root Cause Analyst Agent", "status": "EXECUTED"},
        {"agent_key": "verification", "agent": "Verification Agent", "status": "EXECUTED"}
    ]

    executed_keys = {
        h.get("agent_key")
        for h in sample_history
        if h.get("agent_key") and h.get("status") == "EXECUTED"
    }

    assert "supervisor" in executed_keys
    assert "logs" in executed_keys
    assert "metrics" in executed_keys
    assert "root_cause" in executed_keys
    assert "verification" in executed_keys
    assert "deployments" not in executed_keys
    assert "runbook" not in executed_keys


