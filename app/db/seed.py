import os
import json
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal, init_db
from app.db.models import Incident, Deployment, Log, Metric

SEED_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "seed_data.json")


def seed_database(seed_file_path: str = SEED_FILE):
    """Seed database from clean JSON data with dynamic UTC timestamps."""
    init_db()
    db = SessionLocal()
    try:
        # Clear existing data idempotently
        db.query(Metric).delete()
        db.query(Log).delete()
        db.query(Deployment).delete()
        db.query(Incident).delete()
        db.commit()

        if not os.path.exists(seed_file_path):
            raise FileNotFoundError(f"Seed data file not found at: {seed_file_path}")

        with open(seed_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = datetime.now(timezone.utc)

        # 1. Incidents
        incidents = [
            Incident(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                service=item["service"],
                severity=item["severity"],
                created_at=now - timedelta(minutes=item.get("offset_minutes", 30)),
                status="OPEN"
            )
            for item in data.get("incidents", [])
        ]
        db.add_all(incidents)

        # 2. Deployments
        deployments = [
            Deployment(
                id=item["id"],
                service=item["service"],
                version=item["version"],
                deployed_at=now - timedelta(minutes=item.get("offset_minutes", 60)),
                environment=item.get("environment", "production")
            )
            for item in data.get("deployments", [])
        ]
        db.add_all(deployments)

        # 3. Logs
        logs = [
            Log(
                id=item["id"],
                service=item["service"],
                level=item["level"],
                message=item["message"],
                trace_id=item["trace_id"],
                timestamp=now - timedelta(minutes=item.get("offset_minutes", 30))
            )
            for item in data.get("logs", [])
        ]
        db.add_all(logs)

        # 4. Metrics
        metrics = [
            Metric(
                service=item["service"],
                metric_name=item["metric_name"],
                value=item["value"],
                timestamp=now - timedelta(minutes=item.get("offset_minutes", 30))
            )
            for item in data.get("metrics", [])
        ]
        db.add_all(metrics)

        db.commit()
        print(f"Successfully seeded database: {len(incidents)} incidents, {len(deployments)} deployments, {len(logs)} logs, {len(metrics)} metrics.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
