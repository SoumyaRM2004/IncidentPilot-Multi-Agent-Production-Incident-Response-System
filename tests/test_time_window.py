import pytest
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.db.models import Log, Metric
from app.tools.logs import search_logs, get_error_frequency, get_service_logs
from app.tools.metrics import get_service_metrics, get_metric_window
from app.agents.logs import run_log_agent
from app.agents.metrics import run_metrics_agent
from app.graph.workflow import create_initial_state


@pytest.fixture
def historical_telemetry(db_session):
    """Inserts historical telemetry anchored to a fixed incident time in the past."""
    # Incident reported_at: 2026-01-15 10:00:00 UTC
    reported_at = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    service = "test-order-service"

    # 1. In-window log (15 min before reported_at)
    log_in_window = Log(
        id="LOG-TEST-IN",
        service=service,
        level="ERROR",
        message="Critical database connection timeout in checkout worker",
        trace_id="tr-test-001",
        timestamp=reported_at - timedelta(minutes=15)
    )
    # 2. After incident log (15 min after reported_at) -> must be excluded
    log_after = Log(
        id="LOG-TEST-AFTER",
        service=service,
        level="ERROR",
        message="Late error after incident closure",
        trace_id="tr-test-002",
        timestamp=reported_at + timedelta(minutes=15)
    )
    # 3. Before window log (90 min before reported_at) -> must be excluded for window_minutes=60
    log_before = Log(
        id="LOG-TEST-BEFORE",
        service=service,
        level="ERROR",
        message="Ancient error well before investigation window",
        trace_id="tr-test-003",
        timestamp=reported_at - timedelta(minutes=90)
    )

    # 4. In-window metric (10 min before reported_at)
    metric_in_window = Metric(
        service=service,
        metric_name="http_error_rate_percent",
        value=42.5,
        timestamp=reported_at - timedelta(minutes=10)
    )
    # 5. After incident metric (10 min after reported_at) -> must be excluded
    metric_after = Metric(
        service=service,
        metric_name="http_error_rate_percent",
        value=12.0,
        timestamp=reported_at + timedelta(minutes=10)
    )
    # 6. Before window metric (90 min before reported_at) -> must be excluded
    metric_before = Metric(
        service=service,
        metric_name="http_error_rate_percent",
        value=5.0,
        timestamp=reported_at - timedelta(minutes=90)
    )

    db_session.add_all([log_in_window, log_after, log_before, metric_in_window, metric_after, metric_before])
    db_session.commit()

    try:
        yield {
            "service": service,
            "reported_at": reported_at,
            "reported_at_iso": reported_at.isoformat(),
            "log_in_id": log_in_window.id,
            "log_after_id": log_after.id,
            "log_before_id": log_before.id,
            "metric_in_id": f"METRIC-{metric_in_window.id}",
            "metric_after_id": f"METRIC-{metric_after.id}",
            "metric_before_id": f"METRIC-{metric_before.id}"
        }
    finally:
        db_session.query(Log).filter(Log.service == service).delete()
        db_session.query(Metric).filter(Metric.service == service).delete()
        db_session.commit()


def test_1_delayed_investigation_retrieves_historical_logs(historical_telemetry):
    """TEST 1: Delayed investigation retrieves historical logs when anchored to incident reported_at.

    Calling with end_time returns the historical log; omitting end_time (wall-clock) misses it.
    """
    svc = historical_telemetry["service"]
    end_time = historical_telemetry["reported_at_iso"]

    # Anchored to incident reported_at: retrieves historical log
    anchored_logs = search_logs(service=svc, window_minutes=60, end_time=end_time)
    log_ids = [l["evidence_id"] for l in anchored_logs]
    assert historical_telemetry["log_in_id"] in log_ids

    # Unanchored (wall-clock now): misses historical log because execution happens months later
    wallclock_logs = search_logs(service=svc, window_minutes=60, end_time=None)
    wallclock_ids = [l["evidence_id"] for l in wallclock_logs]
    assert historical_telemetry["log_in_id"] not in wallclock_ids


def test_2_delayed_investigation_retrieves_historical_metrics(historical_telemetry):
    """TEST 2: Delayed investigation retrieves historical metrics when anchored to incident reported_at."""
    svc = historical_telemetry["service"]
    end_time = historical_telemetry["reported_at_iso"]

    # Anchored to incident reported_at: retrieves historical metric
    anchored_metrics = get_service_metrics(service=svc, window_minutes=60, end_time=end_time)
    metric_ids = [m["evidence_id"] for m in anchored_metrics]
    assert historical_telemetry["metric_in_id"] in metric_ids

    # Unanchored (wall-clock now): misses historical metric
    wallclock_metrics = get_service_metrics(service=svc, window_minutes=60, end_time=None)
    wallclock_ids = [m["evidence_id"] for m in wallclock_metrics]
    assert historical_telemetry["metric_in_id"] not in wallclock_ids

    # Also verify get_metric_window
    window_data = get_metric_window(service=svc, metric_name="http_error_rate_percent", minutes=60, end_time=end_time)
    window_ids = [m["evidence_id"] for m in window_data]
    assert historical_telemetry["metric_in_id"] in window_ids


def test_3_end_boundary_is_respected(historical_telemetry):
    """TEST 3: Telemetry occurring strictly after incident reported_at must NOT be returned."""
    svc = historical_telemetry["service"]
    end_time = historical_telemetry["reported_at_iso"]

    # Logs after reported_at must not be returned
    logs = search_logs(service=svc, window_minutes=60, end_time=end_time)
    log_ids = [l["evidence_id"] for l in logs]
    assert historical_telemetry["log_after_id"] not in log_ids

    # Metrics after reported_at must not be returned
    metrics = get_service_metrics(service=svc, window_minutes=60, end_time=end_time)
    metric_ids = [m["evidence_id"] for m in metrics]
    assert historical_telemetry["metric_after_id"] not in metric_ids

    # Frequency analysis must not count events after reported_at
    freq = get_error_frequency(service=svc, minutes=60, end_time=end_time)
    # Only 1 in-window ERROR log exists
    assert freq["error_count"] == 1


def test_4_lower_boundary_is_respected(historical_telemetry):
    """TEST 4: Telemetry older than reported_at - window_minutes must NOT be returned."""
    svc = historical_telemetry["service"]
    end_time = historical_telemetry["reported_at_iso"]

    # Logs older than (reported_at - 60m) must not be returned
    logs = search_logs(service=svc, window_minutes=60, end_time=end_time)
    log_ids = [l["evidence_id"] for l in logs]
    assert historical_telemetry["log_before_id"] not in log_ids

    # Metrics older than (reported_at - 60m) must not be returned
    metrics = get_service_metrics(service=svc, window_minutes=60, end_time=end_time)
    metric_ids = [m["evidence_id"] for m in metrics]
    assert historical_telemetry["metric_before_id"] not in metric_ids


def test_5_agent_propagation(historical_telemetry):
    """TEST 5: run_log_agent and run_metrics_agent pass incident reported_at into the telemetry tools."""
    svc = historical_telemetry["service"]
    reported_at = historical_telemetry["reported_at_iso"]

    incident = {
        "id": "INC-TEST-HIST",
        "service": svc,
        "title": "Historical order service degradation",
        "description": "Historical checkout failures",
        "severity": "HIGH",
        "reported_at": reported_at
    }
    state = create_initial_state(incident)
    state["investigation_plan"] = {
        "focus": "Diagnostic investigation",
        "required_agents": ["logs", "metrics"],
        "strategy": "Historical telemetry analysis",
        "window_minutes": 60
    }

    # Run log agent
    state = run_log_agent(state)
    collected_ids = [e["evidence_id"] for e in state["collected_evidence"]]
    assert historical_telemetry["log_in_id"] in collected_ids
    assert historical_telemetry["log_after_id"] not in collected_ids
    assert historical_telemetry["log_before_id"] not in collected_ids

    # Run metrics agent
    state = run_metrics_agent(state)
    collected_ids = [e["evidence_id"] for e in state["collected_evidence"]]
    assert historical_telemetry["metric_in_id"] in collected_ids
    assert historical_telemetry["metric_after_id"] not in collected_ids
    assert historical_telemetry["metric_before_id"] not in collected_ids


def test_6_execution_timestamp_remains_current(historical_telemetry):
    """TEST 6: Execution timestamp in agent_history must record current UTC time, NOT incident reported_at."""
    svc = historical_telemetry["service"]
    reported_at = historical_telemetry["reported_at_iso"]

    incident = {
        "id": "INC-TEST-HIST",
        "service": svc,
        "title": "Historical outage",
        "description": "Historical crash",
        "severity": "HIGH",
        "reported_at": reported_at
    }
    state = create_initial_state(incident)
    state["investigation_plan"] = {
        "focus": "Diagnostic investigation",
        "required_agents": ["logs", "metrics"],
        "strategy": "Execution time audit",
        "window_minutes": 60
    }

    before_run = datetime.now(timezone.utc)
    state = run_log_agent(state)
    state = run_metrics_agent(state)
    after_run = datetime.now(timezone.utc)

    assert len(state["agent_history"]) == 2
    for entry in state["agent_history"]:
        entry_ts = datetime.fromisoformat(entry["timestamp"])
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.replace(tzinfo=timezone.utc)

        # Execution time MUST be around right now, NOT in January 2026
        assert before_run - timedelta(seconds=5) <= entry_ts <= after_run + timedelta(seconds=5)
        # Explicitly verify it is NOT the incident reported_at
        assert abs((entry_ts - historical_telemetry["reported_at"]).total_seconds()) > 86400


def test_7_backward_compatibility_when_end_time_omitted(historical_telemetry):
    """TEST 7: When end_time is omitted, tools preserve relative-to-now behavior without crashing."""
    # Test logs
    logs = search_logs(service=historical_telemetry["service"], window_minutes=60)
    assert isinstance(logs, list)

    service_logs = get_service_logs(service=historical_telemetry["service"], window_minutes=60)
    assert isinstance(service_logs, list)

    freq = get_error_frequency(service=historical_telemetry["service"], minutes=60)
    assert isinstance(freq, dict)
    assert "error_count" in freq

    # Test metrics
    metrics = get_service_metrics(service=historical_telemetry["service"], window_minutes=60)
    assert isinstance(metrics, list)

    metric_window = get_metric_window(service=historical_telemetry["service"], metric_name="http_error_rate_percent", minutes=60)
    assert isinstance(metric_window, list)
