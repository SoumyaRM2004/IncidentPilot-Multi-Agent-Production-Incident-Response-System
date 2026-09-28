from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.db.models import Metric
from app.utils import normalize_timestamp

# Backward compatibility — agents import this name from here
_normalize_timestamp = normalize_timestamp


def get_service_metrics(
    service: str,
    metric_name: Optional[str] = None,
    window_minutes: Optional[int] = None,
    end_time: Optional[Union[datetime, str]] = None,
    start_time: Optional[Union[datetime, str]] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Retrieve recent metrics for a service, filtered by metric name and time window."""
    db = SessionLocal()
    try:
        q = db.query(Metric).filter(Metric.service == service)
        if metric_name:
            q = q.filter(Metric.metric_name == metric_name)

        end_dt = normalize_timestamp(end_time)
        start_dt = normalize_timestamp(start_time)

        if start_dt is not None and end_dt is not None:
            q = q.filter(Metric.timestamp >= start_dt, Metric.timestamp <= end_dt)
        elif start_dt is not None:
            q = q.filter(Metric.timestamp >= start_dt)
        elif window_minutes is not None:
            if end_dt is None:
                end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(minutes=window_minutes)
            q = q.filter(Metric.timestamp >= start_dt, Metric.timestamp <= end_dt)
        elif end_dt is not None:
            q = q.filter(Metric.timestamp <= end_dt)

        metrics = q.order_by(Metric.timestamp.desc()).limit(limit).all()

        return [
            {
                "evidence_id": f"METRIC-{m.id}",
                "source_type": "metric",
                "source": "service_metrics",
                "service": m.service,
                "metric_name": m.metric_name,
                "value": m.value,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "finding": f"Metric {m.metric_name} = {m.value} recorded for {m.service} at {m.timestamp.isoformat() if m.timestamp else 'unknown'}.",
                "details": {
                    "metric_id": m.id,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None
                }
            }
            for m in metrics
        ]
    finally:
        db.close()


def get_metric_window(
    service: str,
    metric_name: str,
    minutes: int = 60,
    end_time: Optional[Union[datetime, str]] = None,
    start_time: Optional[Union[datetime, str]] = None
) -> List[Dict[str, Any]]:
    """Retrieve metric timeseries data within a specified time window."""
    db = SessionLocal()
    try:
        end_dt = normalize_timestamp(end_time) or datetime.now(timezone.utc)
        start_dt = normalize_timestamp(start_time) or (end_dt - timedelta(minutes=minutes))
        metrics = (
            db.query(Metric)
            .filter(Metric.service == service, Metric.metric_name == metric_name, Metric.timestamp >= start_dt, Metric.timestamp <= end_dt)
            .order_by(Metric.timestamp.asc())
            .all()
        )

        return [
            {
                "evidence_id": f"METRIC-{m.id}",
                "source_type": "metric",
                "source": "service_metrics",
                "service": m.service,
                "metric_name": m.metric_name,
                "value": m.value,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "finding": f"Window metric {m.metric_name} = {m.value} at {m.timestamp.isoformat() if m.timestamp else 'unknown'}.",
                "details": {
                    "metric_id": m.id,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None
                }
            }
            for m in metrics
        ]
    finally:
        db.close()
