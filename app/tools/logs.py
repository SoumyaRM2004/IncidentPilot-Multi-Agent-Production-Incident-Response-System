from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from app.db.database import SessionLocal
from app.db.models import Log


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


def search_logs(
    service: str,
    query: Optional[str] = None,
    level: Optional[str] = None,
    window_minutes: Optional[int] = None,
    end_time: Optional[Union[datetime, str]] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Search application logs by service, query substring, log level, and time window."""
    db = SessionLocal()
    try:
        q = db.query(Log).filter(Log.service == service)
        if level:
            q = q.filter(Log.level == level.upper())
        if query:
            q = q.filter(Log.message.ilike(f"%{query}%"))

        end_dt = _normalize_timestamp(end_time)
        if window_minutes is not None:
            if end_dt is None:
                end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(minutes=window_minutes)
            q = q.filter(Log.timestamp >= start_dt, Log.timestamp <= end_dt)
        elif end_dt is not None:
            q = q.filter(Log.timestamp <= end_dt)

        results = q.order_by(Log.timestamp.desc()).limit(limit).all()

        return [
            {
                "evidence_id": log.id,
                "source_type": "log",
                "source": "application_logs",
                "service": log.service,
                "level": log.level,
                "message": log.message,
                "trace_id": log.trace_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "finding": f"[{log.level}] {log.message}",
                "details": {
                    "level": log.level,
                    "message": log.message,
                    "trace_id": log.trace_id
                }
            }
            for log in results
        ]
    finally:
        db.close()


def get_error_frequency(
    service: str,
    minutes: int = 60,
    end_time: Optional[Union[datetime, str]] = None
) -> Dict[str, Any]:
    """Calculate the frequency of error-level logs for a service in a time window."""
    db = SessionLocal()
    try:
        end_dt = _normalize_timestamp(end_time) or datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(minutes=minutes)
        error_count = (
            db.query(func.count(Log.id))
            .filter(Log.service == service, Log.level == "ERROR", Log.timestamp >= start_dt, Log.timestamp <= end_dt)
            .scalar()
            or 0
        )
        warn_count = (
            db.query(func.count(Log.id))
            .filter(Log.service == service, Log.level == "WARN", Log.timestamp >= start_dt, Log.timestamp <= end_dt)
            .scalar()
            or 0
        )
        total_count = (
            db.query(func.count(Log.id))
            .filter(Log.service == service, Log.timestamp >= start_dt, Log.timestamp <= end_dt)
            .scalar()
            or 0
        )

        return {
            "evidence_id": f"FREQ-{service}-{minutes}m",
            "source_type": "analytics",
            "source": "log_analytics",
            "service": service,
            "window_minutes": minutes,
            "error_count": error_count,
            "warn_count": warn_count,
            "total_count": total_count,
            "timestamp": end_dt.isoformat(),
            "finding": f"Service {service} produced {error_count} ERRORs and {warn_count} WARNs out of {total_count} total logs in the past {minutes}m.",
            "details": {
                "window_minutes": minutes,
                "error_count": error_count,
                "warn_count": warn_count,
                "total_count": total_count
            }
        }
    finally:
        db.close()


def get_service_logs(
    service: str,
    window_minutes: Optional[int] = None,
    end_time: Optional[Union[datetime, str]] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Retrieve recent chronological logs for a specific service within an optional time window."""
    return search_logs(service=service, window_minutes=window_minutes, end_time=end_time, limit=limit)
