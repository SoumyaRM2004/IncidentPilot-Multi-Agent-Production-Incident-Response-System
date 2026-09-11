from datetime import datetime
from app.db.models import Incident, Deployment, Log, Metric, Investigation


def test_incident_models(db_session):
    incidents = db_session.query(Incident).all()
    assert len(incidents) >= 5
    first = incidents[0]
    assert first.id.startswith("INC-")
    assert first.service != ""
    assert first.severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def test_deployment_models(db_session):
    deps = db_session.query(Deployment).all()
    assert len(deps) >= 5
    first = deps[0]
    assert first.id.startswith("DEP-")
    assert first.version != ""
    assert first.environment == "production"


def test_log_models(db_session):
    logs = db_session.query(Log).all()
    assert len(logs) >= 15
    for l in logs[:5]:
        assert l.id.startswith("LOG-")
        assert l.level in ["ERROR", "WARN", "INFO"]
        assert l.trace_id != ""


def test_metric_models(db_session):
    metrics = db_session.query(Metric).all()
    assert len(metrics) >= 15
    for m in metrics[:5]:
        assert m.metric_name != ""
        assert isinstance(m.value, float)
