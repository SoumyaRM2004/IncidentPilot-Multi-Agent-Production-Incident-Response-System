from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.db.database import SessionLocal
from app.db.models import Metric


def get_service_metrics(service: str, metric_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent metrics for a service, optionally filtered by metric name."""
    db = SessionLocal()
    try:
        q = db.query(Metric).filter(Metric.service == service)
        if metric_name:
            q = q.filter(Metric.metric_name == metric_name)
        metrics = q.order_by(Metric.timestamp.desc()).limit(20).all()

        return [
            {
                "evidence_id": f"METRIC-{m.id}",
                "source": "service_metrics",
                "service": m.service,
                "metric_name": m.metric_name,
                "value": m.value,
                "timestamp": m.timestamp.isoformat(),
                "finding": f"Metric {m.metric_name} = {m.value} for {m.service} at {m.timestamp.isoformat()}."
            }
            for m in metrics
        ]
    finally:
        db.close()


def get_metric_window(service: str, metric_name: str, minutes: int = 60) -> List[Dict[str, Any]]:
    """Retrieve metric timeseries data within a specified time window."""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(minutes=minutes)
        metrics = (
            db.query(Metric)
            .filter(Metric.service == service, Metric.metric_name == metric_name, Metric.timestamp >= since)
            .order_by(Metric.timestamp.asc())
            .all()
        )

        return [
            {
                "evidence_id": f"METRIC-{m.id}",
                "source": "service_metrics",
                "service": m.service,
                "metric_name": m.metric_name,
                "value": m.value,
                "timestamp": m.timestamp.isoformat(),
                "finding": f"Window metric {m.metric_name} = {m.value} at {m.timestamp.isoformat()}."
            }
            for m in metrics
        ]
    finally:
        db.close()
