from app.tools.logs import search_logs, get_error_frequency, get_service_logs
from app.tools.deployments import get_recent_deployments, get_deployment_details
from app.tools.metrics import get_service_metrics, get_metric_window


def test_search_logs_filtering():
    logs = search_logs(service="payment-service", level="ERROR")
    assert len(logs) >= 2
    for l in logs:
        assert l["service"] == "payment-service"
        assert l["level"] == "ERROR"
        assert l["evidence_id"].startswith("LOG-")
        assert "finding" in l


def test_get_error_frequency():
    freq = get_error_frequency(service="payment-service", minutes=60)
    assert freq["service"] == "payment-service"
    assert freq["error_count"] >= 2
    assert freq["evidence_id"].startswith("FREQ-")


def test_get_service_logs():
    logs = get_service_logs(service="order-service", limit=5)
    assert len(logs) > 0
    assert logs[0]["service"] == "order-service"


def test_deployments_tools():
    deps = get_recent_deployments(service="order-service", limit=5)
    assert len(deps) >= 2
    dep_id = deps[0]["evidence_id"]
    assert dep_id.startswith("DEP-")

    details = get_deployment_details(dep_id)
    assert details is not None
    assert details["version"] == deps[0]["version"]


def test_metrics_tools():
    metrics = get_service_metrics(service="auth-service")
    assert len(metrics) >= 4
    for m in metrics:
        assert m["evidence_id"].startswith("METRIC-")
        assert "finding" in m

    mem_metrics = get_service_metrics(service="auth-service", metric_name="memory_utilization_percent")
    assert len(mem_metrics) >= 1
    assert mem_metrics[0]["value"] > 90.0
