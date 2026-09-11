from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    evidence_id: str
    source: str
    service: str
    finding: str
    timestamp: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class Hypothesis(BaseModel):
    id: str
    title: str
    description: str
    confidence: float
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradictory_evidence_ids: List[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    verified: bool
    confidence_acceptable: bool
    evidence_sufficient: bool
    contradictions_found: bool
    explanation: str


class RecommendedAction(BaseModel):
    action: str
    target_service: str
    human_approval_required: bool = True
    approval_status: str = "PENDING_APPROVAL"
    estimated_risk: str = "LOW"
    rationale: str


class InvestigationState(TypedDict):
    incident: Dict[str, Any]
    investigation_plan: Dict[str, Any]
    current_agent: str
    collected_evidence: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    selected_hypothesis: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    confidence: float
    recommended_action: Optional[Dict[str, Any]]
    investigation_status: str  # SUCCESS | INSUFFICIENT_EVIDENCE | INVESTIGATION_FAILED
    agent_history: List[Dict[str, Any]]
    iteration_count: int
    max_iterations: int
    error_message: Optional[str]
