from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.db.models import Metric


def _normalize_timestamp(ts: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """Safely normalizes an ISO-8601 string or datetime to timezone-aware UTC datetime."""
    if ts is None:
        return None
    if isinstance(ts, str):
        iso_str = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(iso_str)
    elif isinstance(ts, datetime):
        dt = ts
    else:
        raise ValueError(f"Unsupported timestamp type: {type(ts)}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_service_metrics(
    service: str,
    metric_name: Optional[str] = None,
    window_minutes: Optional[int] = None,
    end_time: Optional[Union[datetime, str]] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Retrieve recent metrics for a service, filtered by metric name and time window."""
    db = SessionLocal()
    try:
        q = db.query(Metric).filter(Metric.service == service)
        if metric_name:
            q = q.filter(Metric.metric_name == metric_name)

        end_dt = _normalize_timestamp(end_time)
        if window_minutes is not None:
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
    end_time: Optional[Union[datetime, str]] = None
) -> List[Dict[str, Any]]:
    """Retrieve metric timeseries data within a specified time window."""
    db = SessionLocal()
    try:
        end_dt = _normalize_timestamp(end_time) or datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(minutes=minutes)
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
