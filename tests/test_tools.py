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


def test_search_logs_query_parameter():
    """query parameter must actually filter log messages by substring."""
    matching_logs = search_logs(service="payment-service", query="QueuePool", level="ERROR")
    assert len(matching_logs) >= 1
    assert "QueuePool" in matching_logs[0]["message"]

    non_matching = search_logs(service="payment-service", query="NonexistentSubstringXYZ123")
    assert len(non_matching) == 0


def test_get_error_frequency():
    freq = get_error_frequency(service="payment-service", minutes=60)
    assert freq["service"] == "payment-service"
    assert freq["error_count"] >= 2
    assert freq["evidence_id"].startswith("FREQ-")


def test_get_service_logs():
    logs = get_service_logs(service="order-service", limit=5)
    assert len(logs) > 0
    assert logs[0]["service"] == "order-service"


def test_get_service_logs_window_filtering():
    """get_service_logs must respect window_minutes parameter."""
    wide_logs = get_service_logs(service="order-service", window_minutes=600, limit=5)
    assert len(wide_logs) > 0

    narrow_logs = get_service_logs(service="order-service", window_minutes=0, limit=5)
    assert len(narrow_logs) == 0


def test_deployments_tools():
    deps = get_recent_deployments(service="order-service", limit=5)
    assert len(deps) >= 2
    dep_id = deps[0]["evidence_id"]
    assert dep_id.startswith("DEP-")

    details = get_deployment_details(dep_id)
    assert details is not None
    assert details["version"] == deps[0]["version"]


def test_deployments_window_filtering():
    """window_minutes parameter must filter out deployments outside the time range."""
    # Seeded deployments are within the last 180 minutes
    wide_deps = get_recent_deployments(service="order-service", window_minutes=600)
    assert len(wide_deps) >= 1

    # An extremely small window (0 minutes) should return zero deployments
    zero_deps = get_recent_deployments(service="order-service", window_minutes=0)
    assert len(zero_deps) == 0


def test_metrics_tools():
    metrics = get_service_metrics(service="auth-service")
    assert len(metrics) >= 4
    for m in metrics:
        assert m["evidence_id"].startswith("METRIC-")
        assert "finding" in m

    mem_metrics = get_service_metrics(service="auth-service", metric_name="memory_utilization_percent")
    assert len(mem_metrics) >= 1
    assert mem_metrics[0]["value"] > 90.0


def test_metrics_window_filtering():
    """window_minutes parameter must filter metrics outside the time window."""
    # Window of 600 minutes should capture seeded metrics
    wide_metrics = get_service_metrics(service="auth-service", metric_name="memory_utilization_percent", window_minutes=600)
    assert len(wide_metrics) >= 1

    # Window of 0 minutes should filter out all historical metrics
    narrow_metrics = get_service_metrics(service="auth-service", metric_name="memory_utilization_percent", window_minutes=0)
    assert len(narrow_metrics) == 0
