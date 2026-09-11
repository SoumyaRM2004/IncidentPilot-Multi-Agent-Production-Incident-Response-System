import os
import ast
from unittest.mock import patch


def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "IncidentPilot" in data["service"]


def test_list_incidents_endpoint(api_client):
    response = api_client.get("/incidents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5


def test_create_and_get_incident(api_client):
    payload = {
        "title": "API Gateway 502 Bad Gateway Spike",
        "description": "Gateway returning 502 during peak traffic window.",
        "service": "api-gateway",
        "severity": "HIGH"
    }
    create_resp = api_client.post("/incidents", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["id"].startswith("INC-")
    assert created["service"] == "api-gateway"

    get_resp = api_client.get(f"/incidents/{created['id']}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["id"] == created["id"]
    assert fetched["title"] == payload["title"]


def test_investigate_and_approve_lifecycle(api_client, mock_layer2_verified):
    # 1. Trigger investigation against INC-001
    resp = api_client.post("/incidents/INC-001/investigate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["approval_status"] == "PENDING_APPROVAL"
    inv_id = data["id"]

    # 2. Check incident status is ROOT_CAUSE_IDENTIFIED (NEVER RESOLVED)
    inc_resp = api_client.get("/incidents/INC-001")
    assert inc_resp.status_code == 200
    inc_data = inc_resp.json()
    assert inc_data["status"] == "ROOT_CAUSE_IDENTIFIED"
    assert inc_data["status"] != "RESOLVED"

    # 3. Retrieve investigation details
    get_inv = api_client.get(f"/investigations/{inv_id}")
    assert get_inv.status_code == 200
    inv_data = get_inv.json()
    assert inv_data["id"] == inv_id

    # 4. Submit operator approval
    approval_payload = {
        "operator": "lead-sre-alex",
        "decision": "APPROVED",
        "notes": "Verified telemetry corroboration and approved pool scaling."
    }
    appr_resp = api_client.post(f"/investigations/{inv_id}/approve", json=approval_payload)
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()
    assert appr_data["approval_status"] == "APPROVED"
    assert appr_data["operator_decision"] == "APPROVED"
    assert appr_data["approved_at"] is not None
    assert "lead-sre-alex" in appr_data["operator_notes"]

    # 5. Invalid transition: cannot approve again
    duplicate_resp = api_client.post(f"/investigations/{inv_id}/approve", json=approval_payload)
    assert duplicate_resp.status_code == 400
    assert "already approved" in duplicate_resp.json()["detail"].lower()

    # 6. Invalid transition: cannot reject an already approved investigation
    rej_resp = api_client.post(f"/investigations/{inv_id}/reject", json=approval_payload)
    assert rej_resp.status_code == 400
    assert "cannot reject" in rej_resp.json()["detail"].lower()


def test_investigate_and_reject_lifecycle(api_client):
    # Trigger investigation on INC-002
    resp = api_client.post("/incidents/INC-002/investigate")
    assert resp.status_code == 200
    inv_id = resp.json()["id"]

    # Reject / escalate
    reject_payload = {
        "operator": "oncall-dev-sam",
        "decision": "REJECTED",
        "notes": "Escalating to database administrator."
    }
    rej_resp = api_client.post(f"/investigations/{inv_id}/reject", json=reject_payload)
    assert rej_resp.status_code == 200
    rej_data = rej_resp.json()
    assert rej_data["approval_status"] == "REJECTED"
    assert rej_data["operator_decision"] == "REJECTED"

    # Cannot reject again
    dup_rej = api_client.post(f"/investigations/{inv_id}/reject", json=reject_payload)
    assert dup_rej.status_code == 400
    assert "already rejected" in dup_rej.json()["detail"].lower()


def test_api_error_handling_does_not_leak_internals(api_client):
    """API must catch internal exceptions and return a sanitized generic 500 error."""
    with patch("app.api.routes.run_investigation", side_effect=RuntimeError("CRITICAL_INTERNAL_DB_SECRET_KEY_12345")):
        resp = api_client.post("/incidents/INC-003/investigate")
        assert resp.status_code == 500
        detail = resp.json().get("detail", "")
        assert "CRITICAL_INTERNAL_DB_SECRET_KEY" not in detail
        assert detail == "Investigation failed during multi-agent orchestration."


def test_frontend_has_no_internal_db_or_workflow_imports():
    """Frontend must act strictly as an HTTP client with no backend DB or graph imports."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.py")
    with open(frontend_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="app.py")

    disallowed = {"app.db", "app.graph", "app.agents", "app.tools", "sqlalchemy", "SessionLocal"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for d in disallowed:
                    assert not alias.name.startswith(d), f"Frontend improperly imports backend module: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for d in disallowed:
                    assert not node.module.startswith(d), f"Frontend improperly imports from backend module: {node.module}"
