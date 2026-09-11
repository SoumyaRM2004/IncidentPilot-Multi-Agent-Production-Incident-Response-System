from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from app.db.database import SessionLocal
from app.db.models import Log


def search_logs(
    service: str,
    query: Optional[str] = None,
    level: Optional[str] = None,
    window_minutes: Optional[int] = None,
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
        if window_minutes is not None:
            since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            q = q.filter(Log.timestamp >= since)

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


def get_error_frequency(service: str, minutes: int = 60) -> Dict[str, Any]:
    """Calculate the frequency of error-level logs for a service in a time window."""
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        error_count = (
            db.query(func.count(Log.id))
            .filter(Log.service == service, Log.level == "ERROR", Log.timestamp >= since)
            .scalar()
            or 0
        )
        warn_count = (
            db.query(func.count(Log.id))
            .filter(Log.service == service, Log.level == "WARN", Log.timestamp >= since)
            .scalar()
            or 0
        )
        total_count = (
            db.query(func.count(Log.id))
            .filter(Log.service == service, Log.timestamp >= since)
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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


def get_service_logs(service: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve recent chronological logs for a specific service."""
    return search_logs(service=service, limit=limit)
