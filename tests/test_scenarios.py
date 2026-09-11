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
    assert "connection pool" in state["selected_hypothesis"]["selected_root_cause"].lower()
    assert state["confidence"] >= 0.85
    assert state["verification_result"]["verified"] is True
    assert len(state["selected_hypothesis"]["supporting_evidence_ids"]) >= 2
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
    assert "v2.4.1" in state["selected_hypothesis"]["selected_root_cause"].lower() or "release" in state["selected_hypothesis"]["selected_root_cause"].lower() or "deployment" in state["selected_hypothesis"]["selected_root_cause"].lower()
    assert state["verification_result"]["verified"] is True
    assert "rollback" in state["recommended_action"]["action"].lower()


def test_scenario_3_memory_leak(db_session):
    incident = {
        "id": "INC-003",
        "title": "Recurring container restarts and authentication failures in auth-service",
        "description": "Auth service pods restarting periodically. Memory utilization steadily climbs to 98% resulting in OOMKilled termination.",
        "service": "auth-service",
        "severity": "HIGH"
    }
    state = run_investigation(incident)
    assert state["investigation_status"] == "SUCCESS"
    assert "memory" in state["selected_hypothesis"]["selected_root_cause"].lower() or "oomkilled" in state["selected_hypothesis"]["selected_root_cause"].lower()
    assert state["verification_result"]["verified"] is True


def test_scenario_4_external_api_failure(db_session):
    incident = {
        "id": "INC-004",
        "title": "Outbound SMS and push notification delivery failure backlog",
        "description": "Notification dispatch queue backlog growing rapidly. External SMS gateway returning HTTP 504 timeouts.",
        "service": "notification-service",
        "severity": "MEDIUM"
    }
    state = run_investigation(incident)
    assert state["investigation_status"] == "SUCCESS"
    assert "gateway" in state["selected_hypothesis"]["selected_root_cause"].lower() or "sms" in state["selected_hypothesis"]["selected_root_cause"].lower() or "external" in state["selected_hypothesis"]["selected_root_cause"].lower()
    assert state["verification_result"]["verified"] is True


def test_scenario_5_network_latency(db_session):
    incident = {
        "id": "INC-005",
        "title": "Inter-service communication timeouts and packet degradation on user-service",
        "description": "Downstream calls to user-service experiencing heavy socket resets and 19% packet drop rates.",
        "service": "user-service",
        "severity": "HIGH"
    }
    state = run_investigation(incident)
    assert state["investigation_status"] == "SUCCESS"
    assert "network" in state["selected_hypothesis"]["selected_root_cause"].lower() or "packet" in state["selected_hypothesis"]["selected_root_cause"].lower()
    assert state["verification_result"]["verified"] is True
