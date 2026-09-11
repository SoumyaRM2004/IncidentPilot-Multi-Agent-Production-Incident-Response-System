from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from app.db.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    service = Column(String(128), nullable=False, index=True)
    severity = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(32), default="OPEN", nullable=False)

    investigations = relationship("Investigation", back_populates="incident")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String(64), primary_key=True, index=True)
    service = Column(String(128), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    deployed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    environment = Column(String(64), default="production", nullable=False)


class Log(Base):
    __tablename__ = "logs"

    id = Column(String(64), primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    service = Column(String(128), nullable=False, index=True)
    level = Column(String(32), nullable=False, index=True)
    message = Column(Text, nullable=False)
    trace_id = Column(String(64), nullable=False, index=True)


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    service = Column(String(128), nullable=False, index=True)
    metric_name = Column(String(128), nullable=False, index=True)
    value = Column(Float, nullable=False)


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(String(64), primary_key=True, index=True)
    incident_id = Column(String(64), ForeignKey("incidents.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="RUNNING", nullable=False)
    final_confidence = Column(Float, nullable=True)
    report = Column(Text, nullable=True)

    incident = relationship("Incident", back_populates="investigations")
