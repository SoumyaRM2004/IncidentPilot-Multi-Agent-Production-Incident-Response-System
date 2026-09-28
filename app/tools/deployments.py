from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.db.models import Deployment
from app.utils import normalize_timestamp


def get_recent_deployments(
    service: str,
    limit: int = 5,
    window_minutes: Optional[int] = None,
    end_time: Optional[Union[datetime, str]] = None,
    start_time: Optional[Union[datetime, str]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve recent deployments for a specific service with optional time window."""
    db = SessionLocal()
    try:
        q = db.query(Deployment).filter(Deployment.service == service)

        end_dt = normalize_timestamp(end_time)
        start_dt = normalize_timestamp(start_time)

        if start_dt is not None and end_dt is not None:
            q = q.filter(Deployment.deployed_at >= start_dt, Deployment.deployed_at <= end_dt)
        elif start_dt is not None:
            q = q.filter(Deployment.deployed_at >= start_dt)
        elif window_minutes is not None:
            if end_dt is None:
                end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(minutes=window_minutes)
            q = q.filter(Deployment.deployed_at >= start_dt, Deployment.deployed_at <= end_dt)
        elif end_dt is not None:
            q = q.filter(Deployment.deployed_at <= end_dt)

        deployments = q.order_by(Deployment.deployed_at.desc()).limit(limit).all()

        return [
            {
                "evidence_id": dep.id,
                "source_type": "deployment",
                "source": "deployment_records",
                "service": dep.service,
                "version": dep.version,
                "environment": dep.environment,
                "timestamp": dep.deployed_at.isoformat() if dep.deployed_at else None,
                "finding": f"Deployment {dep.id}: version {dep.version} rolled out to {dep.environment} at {dep.deployed_at.isoformat() if dep.deployed_at else 'unknown'}.",
                "details": {
                    "version": dep.version,
                    "environment": dep.environment,
                    "deployed_at": dep.deployed_at.isoformat() if dep.deployed_at else None
                }
            }
            for dep in deployments
        ]
    finally:
        db.close()


def get_deployment_details(deployment_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full details for a specific deployment ID."""
    db = SessionLocal()
    try:
        dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
        if not dep:
            return None

        return {
            "evidence_id": dep.id,
            "source_type": "deployment",
            "source": "deployment_records",
            "service": dep.service,
            "version": dep.version,
            "environment": dep.environment,
            "timestamp": dep.deployed_at.isoformat() if dep.deployed_at else None,
            "finding": f"Deployment {dep.id} ({dep.service} {dep.version}) deployed at {dep.deployed_at.isoformat() if dep.deployed_at else 'unknown'}.",
            "details": {
                "version": dep.version,
                "environment": dep.environment,
                "deployed_at": dep.deployed_at.isoformat() if dep.deployed_at else None
            }
        }
    finally:
        db.close()
