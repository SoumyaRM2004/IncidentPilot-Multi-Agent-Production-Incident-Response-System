from typing import TypedDict, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class EvidenceItem(BaseModel):
    """Standardized evidence representation with strict provenance."""
    evidence_id: str = Field(..., description="Unique immutable evidence identifier, e.g. LOG-101, METRIC-1, DEP-101, RUNBOOK-01")
    source_type: Literal["log", "deployment", "metric", "runbook", "analytics"] = Field(..., description="Category of the telemetry source")
    source: str = Field(..., description="Origin name (e.g. application_logs, service_metrics, operational_runbook)")
    service: str = Field(..., description="Target service the evidence pertains to")
    finding: str = Field(..., description="Concise diagnostic summary extracted from telemetry")
    timestamp: Optional[str] = Field(None, description="ISO-8601 UTC timestamp of occurrence")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Raw structured payload or reference metadata")

    model_config = ConfigDict(from_attributes=True)


class InvestigationPlanModel(BaseModel):
    """Structured output from Supervisor Agent."""
    focus: str = Field(..., description="Primary diagnostic focus of the investigation")
    required_agents: List[str] = Field(default_factory=list, description="Specialist agents to run: logs, deployments, metrics, runbook")
    strategy: str = Field(..., description="Diagnostic strategy and objective")
    log_query: Optional[str] = Field(None, description="Specific keyword or error pattern to search in logs")
    metric_names: Optional[List[str]] = Field(None, description="Target metrics to inspect")
    window_minutes: int = Field(default=60, description="Time window in minutes to inspect")


class HypothesisItem(BaseModel):
    """Candidate root cause hypothesis."""
    id: str = Field(..., description="Hypothesis ID, e.g. HYP-1")
    title: str = Field(..., description="Hypothesis title")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score bounded between 0.0 and 1.0")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of supporting evidence")
    contradictory_evidence_ids: List[str] = Field(default_factory=list, description="IDs of contradictory evidence")
    rationale: Optional[str] = Field(None, description="Causal reasoning for this hypothesis")


class RecommendedAction(BaseModel):
    """Remediation proposal gated by human approval."""
    action: str = Field(..., description="Recommended remediation action")
    target_service: str = Field(..., description="Service to apply remediation to")
    human_approval_required: bool = True
    approval_status: str = "PENDING_APPROVAL"
    estimated_risk: str = "LOW"
    rationale: str = Field(..., description="Operational justification for recommended action")


class RootCauseOutput(BaseModel):
    """Structured output from Root Cause Analyst Agent."""
    hypotheses: List[HypothesisItem] = Field(..., description="Ranked plausible candidate hypotheses")
    selected_root_cause: str = Field(..., description="Selected primary root cause title")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence score")
    supporting_evidence_ids: List[str] = Field(..., description="Existing evidence IDs backing the selected root cause")
    contradictory_evidence_ids: List[str] = Field(default_factory=list, description="Existing evidence IDs contradicting the hypothesis")
    reasoning_summary: str = Field(..., description="Causal explanation linking evidence to the root cause")
    recommended_action: RecommendedAction


class VerificationEvaluation(BaseModel):
    """Structured output from Verification Agent semantic audit."""
    verified: bool = Field(..., description="Whether the hypothesis is empirically verified")
    confidence_acceptable: bool = Field(..., description="Whether the assigned confidence matches the evidence strength")
    evidence_sufficient: bool = Field(..., description="Whether evidence sufficiency criteria are met")
    contradictions_found: bool = Field(..., description="Whether unaddressed contradictory evidence was detected")
    explanation: str = Field(..., description="Clear explanation of the verification verdict")


# Aliases for backward compatibility
Hypothesis = HypothesisItem
VerificationResult = VerificationEvaluation


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
