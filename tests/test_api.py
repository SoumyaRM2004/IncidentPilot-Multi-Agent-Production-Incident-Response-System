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


def test_investigate_and_approve_lifecycle(api_client):
    # 1. Trigger investigation against INC-001
    resp = api_client.post("/incidents/INC-001/investigate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("SUCCESS", "INSUFFICIENT_EVIDENCE")
    assert data["approval_status"] == "PENDING_APPROVAL"
    inv_id = data["id"]

    # 2. Retrieve investigation details
    get_inv = api_client.get(f"/investigations/{inv_id}")
    assert get_inv.status_code == 200
    inv_data = get_inv.json()
    assert inv_data["id"] == inv_id

    # 3. Submit operator approval
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

    # 4. Verify persistence on GET
    verify_get = api_client.get(f"/investigations/{inv_id}").json()
    assert verify_get["approval_status"] == "APPROVED"
    assert verify_get["operator_decision"] == "APPROVED"


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
