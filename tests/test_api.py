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


def test_investigate_incident_endpoint(api_client):
    # Test investigation against seeded incident INC-001
    resp = api_client.post("/incidents/INC-001/investigate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["final_confidence"] is not None
    assert data["report"] is not None
    assert data["report"]["selected_hypothesis"] is not None
    assert data["report"]["human_approval_required"] is True

    # Test retrieving investigation by ID
    inv_id = data["id"]
    get_inv = api_client.get(f"/investigations/{inv_id}")
    assert get_inv.status_code == 200
    inv_data = get_inv.json()
    assert inv_data["id"] == inv_id
    assert inv_data["status"] == "SUCCESS"
