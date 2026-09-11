from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from app.db.database import SessionLocal
from app.db.models import Log


def search_logs(service: str, query: Optional[str] = None, level: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Search application logs by service, query substring, or log level."""
    db = SessionLocal()
    try:
        q = db.query(Log).filter(Log.service == service)
        if level:
            q = q.filter(Log.level == level.upper())
        if query:
            q = q.filter(Log.message.ilike(f"%{query}%"))
        results = q.order_by(Log.timestamp.desc()).limit(limit).all()

        return [
            {
                "evidence_id": log.id,
                "source": "application_logs",
                "service": log.service,
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message,
                "trace_id": log.trace_id,
                "finding": f"[{log.level}] {log.message}"
            }
            for log in results
        ]
    finally:
        db.close()


def get_error_frequency(service: str, minutes: int = 60) -> Dict[str, Any]:
    """Calculate the frequency of error-level logs for a service in a time window."""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(minutes=minutes)
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
            "source": "log_analytics",
            "service": service,
            "window_minutes": minutes,
            "error_count": error_count,
            "warn_count": warn_count,
            "total_count": total_count,
            "finding": f"Service {service} produced {error_count} ERRORs and {warn_count} WARNs in the past {minutes}m."
        }
    finally:
        db.close()


def get_service_logs(service: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve recent logs for a specific service."""
    return search_logs(service=service, limit=limit)
