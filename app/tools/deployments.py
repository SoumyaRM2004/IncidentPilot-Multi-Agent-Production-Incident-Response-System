from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.db.models import Deployment


def get_recent_deployments(
    service: str,
    limit: int = 5,
    window_minutes: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieve recent deployments for a specific service with optional time window."""
    db = SessionLocal()
    try:
        q = db.query(Deployment).filter(Deployment.service == service)
        if window_minutes:
            since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            q = q.filter(Deployment.deployed_at >= since)

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
