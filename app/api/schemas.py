from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class IncidentCreate(BaseModel):
    title: str = Field(..., description="Short incident summary")
    description: str = Field(..., description="Detailed symptom description")
    service: str = Field(..., description="Target service name")
    severity: str = Field(default="HIGH", description="Severity level: CRITICAL, HIGH, MEDIUM, LOW")


class IncidentResponse(BaseModel):
    id: str
    title: str
    description: str
    service: str
    severity: str
    created_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class ApprovalDecisionRequest(BaseModel):
    operator: str = Field(..., description="Name or ID of on-call operator making the decision")
    decision: Literal["APPROVED", "REJECTED"] = Field(..., description="Operator decision: APPROVED or REJECTED")
    notes: Optional[str] = Field(None, description="Optional operator justification notes")


class InvestigationResponse(BaseModel):
    id: str
    incident_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    final_confidence: Optional[float] = None
    approval_status: str = "PENDING_APPROVAL"
    approved_at: Optional[datetime] = None
    operator_decision: Optional[str] = None
    operator_notes: Optional[str] = None
    report: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
