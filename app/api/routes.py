import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Incident, Investigation
from app.api.schemas import (
    IncidentCreate,
    IncidentResponse,
    InvestigationResponse,
    ApprovalDecisionRequest,
    HealthResponse,
)
from app.graph.workflow import run_investigation

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "IncidentPilot Autonomous Incident Response API",
        "timestamp": datetime.now(timezone.utc)
    }


@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED, tags=["Incidents"])
def create_incident(incident_in: IncidentCreate, db: Session = Depends(get_db)):
    """Create a new production incident."""
    incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
    incident = Incident(
        id=incident_id,
        title=incident_in.title,
        description=incident_in.description,
        service=incident_in.service,
        severity=incident_in.severity.upper(),
        created_at=datetime.now(timezone.utc),
        status="OPEN"
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/incidents", response_model=List[IncidentResponse], tags=["Incidents"])
def list_incidents(db: Session = Depends(get_db)):
    """List all incidents ordered by creation time."""
    return db.query(Incident).order_by(Incident.created_at.desc()).all()


@router.get("/incidents/{incident_id}", response_model=IncidentResponse, tags=["Incidents"])
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """Get details of a specific incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found."
        )
    return incident


@router.post("/incidents/{incident_id}/investigate", response_model=InvestigationResponse, tags=["Investigations"])
def start_investigation(incident_id: str, db: Session = Depends(get_db)):
    """Trigger the autonomous multi-agent LangGraph investigation for an incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found."
        )

    investigation_id = f"INV-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)

    inv_record = Investigation(
        id=investigation_id,
        incident_id=incident.id,
        started_at=now,
        status="RUNNING",
        approval_status="PENDING_APPROVAL"
    )
    incident.status = "INVESTIGATING"
    db.add(inv_record)
    db.commit()

    incident_dict = {
        "id": incident.id,
        "title": incident.title,
        "description": incident.description,
        "service": incident.service,
        "severity": incident.severity,
        "created_at": incident.created_at.isoformat() if incident.created_at else now.isoformat()
    }

    try:
        final_state = run_investigation(incident=incident_dict)
        completed_at = datetime.now(timezone.utc)

        inv_record.completed_at = completed_at
        inv_record.status = final_state.get("investigation_status", "INVESTIGATION_FAILED")
        inv_record.final_confidence = final_state.get("confidence")

        # Serialized structured investigation report
        report_data = {
            "incident_summary": {
                "id": incident.id,
                "title": incident.title,
                "service": incident.service,
                "severity": incident.severity
            },
            "investigation_plan": final_state.get("investigation_plan"),
            "evidence": final_state.get("collected_evidence", []),
            "hypotheses": final_state.get("hypotheses", []),
            "selected_hypothesis": final_state.get("selected_hypothesis"),
            "confidence": final_state.get("confidence"),
            "verification_result": final_state.get("verification_result"),
            "recommended_action": final_state.get("recommended_action"),
            "agent_history": final_state.get("agent_history", []),
            "iteration_count": final_state.get("iteration_count", 0),
            "human_approval_required": True,
            "approval_status": "PENDING_APPROVAL"
        }

        inv_record.report = json.dumps(report_data)
        incident.status = "RESOLVED" if inv_record.status == "SUCCESS" else "INVESTIGATION_FAILED"
        db.commit()
        db.refresh(inv_record)

        return _format_investigation_response(inv_record)

    except Exception as e:
        logger.exception(f"Investigation {investigation_id} failed during orchestration: {e}")
        inv_record.status = "INVESTIGATION_FAILED"
        inv_record.completed_at = datetime.now(timezone.utc)
        incident.status = "INVESTIGATION_FAILED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation failed during multi-agent orchestration: {str(e)}"
        )


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse, tags=["Investigations"])
def get_investigation(investigation_id: str, db: Session = Depends(get_db)):
    """Retrieve full investigation report, audit trail, and persistent approval status."""
    inv = db.query(Investigation).filter(Investigation.id == investigation_id).first()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    return _format_investigation_response(inv)


@router.post("/investigations/{investigation_id}/approve", response_model=InvestigationResponse, tags=["Approval"])
def approve_investigation(investigation_id: str, payload: ApprovalDecisionRequest, db: Session = Depends(get_db)):
    """Record persistent operator approval of proposed remediation."""
    inv = db.query(Investigation).filter(Investigation.id == investigation_id).first()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    now = datetime.now(timezone.utc)
    inv.approval_status = "APPROVED" if payload.decision == "APPROVED" else "REJECTED"
    inv.operator_decision = payload.decision
    inv.approved_at = now
    inv.operator_notes = f"Operator: {payload.operator}. Notes: {payload.notes or 'None'}"

    # Update embedded JSON report to reflect persistent approval
    if inv.report:
        try:
            report_dict = json.loads(inv.report)
            report_dict["approval_status"] = inv.approval_status
            report_dict["operator_decision"] = inv.operator_decision
            report_dict["approved_at"] = now.isoformat()
            report_dict["operator_notes"] = inv.operator_notes
            inv.report = json.dumps(report_dict)
        except Exception as e:
            logger.warning(f"Could not update embedded report JSON: {e}")

    db.commit()
    db.refresh(inv)
    return _format_investigation_response(inv)


@router.post("/investigations/{investigation_id}/reject", response_model=InvestigationResponse, tags=["Approval"])
def reject_investigation(investigation_id: str, payload: ApprovalDecisionRequest, db: Session = Depends(get_db)):
    """Record operator rejection or escalation of proposed remediation."""
    payload.decision = "REJECTED"
    return approve_investigation(investigation_id=investigation_id, payload=payload, db=db)


def _format_investigation_response(inv: Investigation) -> Dict[str, Any]:
    """Helper to deserialize report JSON and format response."""
    parsed_report = None
    if inv.report:
        try:
            parsed_report = json.loads(inv.report)
        except Exception:
            parsed_report = None

    return {
        "id": inv.id,
        "incident_id": inv.incident_id,
        "started_at": inv.started_at,
        "completed_at": inv.completed_at,
        "status": inv.status,
        "final_confidence": inv.final_confidence,
        "approval_status": inv.approval_status,
        "approved_at": inv.approved_at,
        "operator_decision": inv.operator_decision,
        "operator_notes": inv.operator_notes,
        "report": parsed_report
    }
