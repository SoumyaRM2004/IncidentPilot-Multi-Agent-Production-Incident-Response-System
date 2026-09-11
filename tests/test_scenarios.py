from app.graph.workflow import run_investigation


def test_scenario_1_database_pool_exhaustion(db_session):
    incident = {
        "id": "INC-001",
        "title": "Elevated HTTP 500 errors and transaction timeouts on payment processing",
        "description": "Payment processing latency surged to 4.8s with recurring connection acquisition timeout errors.",
        "service": "payment-service",
        "severity": "CRITICAL"
    }
    state = run_investigation(incident)
    assert state["investigation_status"] == "SUCCESS"
    assert state["selected_hypothesis"] is not None
    assert len(state["selected_hypothesis"]["supporting_evidence_ids"]) >= 2
    assert state["confidence"] >= 0.70
    assert state["verification_result"]["verified"] is True
    assert state["recommended_action"]["human_approval_required"] is True


def test_scenario_2_bad_deployment(db_session):
    incident = {
        "id": "INC-002",
        "title": "Order checkout failures surging following release v2.4.1",
        "description": "Customers unable to complete order placement. HTTP 500 error rate spiked to 38% immediately following deployment.",
        "service": "order-service",
        "severity": "CRITICAL"
    }
    state = run_investigation(incident)
    assert state["investigation_status"] == "SUCCESS"
    assert state["verification_result"]["verified"] is True
    assert len(state["selected_hypothesis"]["supporting_evidence_ids"]) >= 2


def test_paraphrased_incident_no_keyword_dependency(db_session):
    """Test incident with completely rephrased symptoms to prove zero dependency on hardcoded strings."""
    paraphrased_incident = {
        "id": "INC-PARA-01",
        "title": "Severe throughput degradation on transaction ingress",
        "description": "Upstream microservices reporting persistent 500 status codes when submitting customer cart payments.",
        "service": "payment-service",
        "severity": "HIGH"
    }
    state = run_investigation(paraphrased_incident)
    assert state["investigation_status"] == "SUCCESS"
    assert state["verification_result"]["verified"] is True
    # Verify that all cited evidence exists in collected evidence
    collected_ids = {e["evidence_id"] for e in state["collected_evidence"]}
    for cited_id in state["selected_hypothesis"]["supporting_evidence_ids"]:
        assert cited_id in collected_ids


def test_insufficient_evidence_safely_terminates(db_session):
    """Test incident for a service with no telemetry. System must return INSUFFICIENT_EVIDENCE without hallucination."""
    empty_incident = {
        "id": "INC-EMPTY-01",
        "title": "Hypothetical issue on ghost service",
        "description": "Alert triggered without any telemetry.",
        "service": "ghost-nonexistent-service",
        "severity": "LOW"
    }
    state = run_investigation(empty_incident)
    # The investigation must conclude with INSUFFICIENT_EVIDENCE
    assert state["investigation_status"] in ("INSUFFICIENT_EVIDENCE", "INVESTIGATION_FAILED")
    assert state["verification_result"]["verified"] is False
    assert state["confidence"] <= 0.50
