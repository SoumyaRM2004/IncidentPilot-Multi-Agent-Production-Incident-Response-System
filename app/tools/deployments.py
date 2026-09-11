from typing import List, Dict, Any, Optional
from app.db.database import SessionLocal
from app.db.models import Deployment


def get_recent_deployments(service: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve recent deployments for a specific service."""
    db = SessionLocal()
    try:
        deployments = (
            db.query(Deployment)
            .filter(Deployment.service == service)
            .order_by(Deployment.deployed_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "evidence_id": dep.id,
                "source": "deployment_records",
                "service": dep.service,
                "version": dep.version,
                "deployed_at": dep.deployed_at.isoformat(),
                "environment": dep.environment,
                "finding": f"Deployment {dep.id}: version {dep.version} deployed to {dep.environment} at {dep.deployed_at.isoformat()}."
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
            "source": "deployment_records",
            "service": dep.service,
            "version": dep.version,
            "deployed_at": dep.deployed_at.isoformat(),
            "environment": dep.environment,
            "finding": f"Deployment {dep.id} ({dep.service} {dep.version}) deployed at {dep.deployed_at.isoformat()}."
        }
    finally:
        db.close()
