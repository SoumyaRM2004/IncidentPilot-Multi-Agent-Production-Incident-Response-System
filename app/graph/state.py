from typing import TypedDict, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


ALLOWED_AGENTS = {"logs", "deployments", "metrics", "runbook"}


class EvidenceItem(BaseModel):
    """Canonical evidence representation with strict provenance."""
    evidence_id: str = Field(..., description="Unique immutable evidence identifier, e.g. LOG-101, METRIC-1, DEP-101, RUNBOOK-01")
    source_type: Literal["log", "deployment", "metric", "runbook", "analytics"] = Field(..., description="Category of the telemetry source")
    source: str = Field(..., description="Origin name (e.g. application_logs, service_metrics, operational_runbook)")
    service: str = Field(..., description="Target service the evidence pertains to")
    timestamp: Optional[str] = Field(None, description="ISO-8601 UTC timestamp of occurrence")
    finding: str = Field(..., description="Concise diagnostic summary extracted from telemetry")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Raw structured payload or reference metadata")

    model_config = ConfigDict(from_attributes=True)


class InvestigationPlanModel(BaseModel):
    """Structured output from Supervisor Agent validated against allowed agents."""
    focus: str = Field(..., description="Primary diagnostic focus of the investigation")
    required_agents: List[str] = Field(default_factory=list, description="Specialist agents to run: logs, deployments, metrics, runbook")
    strategy: str = Field(..., description="Diagnostic strategy and objective")
    log_query: Optional[str] = Field(None, description="Specific keyword or error pattern to search in logs")
    metric_names: Optional[List[str]] = Field(None, description="Target metrics to inspect")
    window_minutes: int = Field(default=60, ge=1, le=1440, description="Time window in minutes to inspect")

    @model_validator(mode="before")
    @classmethod
    def unwrap_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Handle nested wrappers like {"investigation_plan": ...} or {"plan": ...}
        inner = data.get("investigation_plan") or data.get("plan")
        extracted: Dict[str, Any] = {}

        if isinstance(inner, dict):
            extracted = dict(inner)
            # Preserve remaining top-level fields
            for k, v in data.items():
                if k not in ("investigation_plan", "plan") and k not in extracted and v is not None:
                    extracted[k] = v
        elif isinstance(inner, list):
            # If investigation_plan is a list of steps/agents: e.g. [{"agent": "logs", ...}, ...]
            agents: List[str] = []
            f_parts: List[str] = []
            s_parts: List[str] = []
            log_query = data.get("log_query")
            metric_names = list(data.get("metric_names") or [])
            window_minutes = data.get("window_minutes")

            for item in inner:
                if isinstance(item, dict):
                    for ak in ("agent", "required_agents", "specialist", "name"):
                        val = item.get(ak)
                        if isinstance(val, str) and val.lower().strip() in ALLOWED_AGENTS:
                            clean_agent = val.lower().strip()
                            if clean_agent not in agents:
                                agents.append(clean_agent)
                        elif isinstance(val, list):
                            for a in val:
                                if isinstance(a, str) and a.lower().strip() in ALLOWED_AGENTS:
                                    clean_agent = a.lower().strip()
                                    if clean_agent not in agents:
                                        agents.append(clean_agent)
                    for fk in ("focus", "title", "objective", "target"):
                        if item.get(fk) and str(item[fk]) not in f_parts:
                            f_parts.append(str(item[fk]))
                    for sk in ("strategy", "action", "reason", "description"):
                        if item.get(sk) and str(item[sk]) not in s_parts:
                            s_parts.append(str(item[sk]))
                    if not log_query and item.get("log_query"):
                        log_query = item.get("log_query")
                    if item.get("metric_names"):
                        m_val = item.get("metric_names")
                        if isinstance(m_val, list):
                            metric_names.extend([m for m in m_val if m not in metric_names])
                        elif isinstance(m_val, str) and m_val not in metric_names:
                            metric_names.append(m_val)
                    if not window_minutes and item.get("window_minutes"):
                        window_minutes = item.get("window_minutes")

            extracted = {
                "required_agents": agents or data.get("required_agents", []),
                "focus": data.get("focus") or ("; ".join(f_parts) if f_parts else "Investigate incident symptoms"),
                "strategy": data.get("strategy") or ("; ".join(s_parts) if s_parts else "Execute diagnostic queries"),
            }
            if log_query:
                extracted["log_query"] = log_query
            if metric_names:
                extracted["metric_names"] = metric_names
            if window_minutes:
                extracted["window_minutes"] = window_minutes

            for k, v in data.items():
                if k not in ("investigation_plan", "plan") and k not in extracted and v is not None:
                    extracted[k] = v
        else:
            extracted = dict(data)

        # Normalize common aliases on extracted dict
        if not extracted.get("focus"):
            extracted["focus"] = extracted.get("title") or extracted.get("objective") or extracted.get("description") or "Investigate incident symptoms"

        if not extracted.get("strategy"):
            extracted["strategy"] = extracted.get("description") or extracted.get("action") or extracted.get("reason") or "Execute diagnostic queries"

        if not extracted.get("required_agents"):
            if "agents" in extracted:
                extracted["required_agents"] = extracted["agents"]
            elif "agent" in extracted:
                val = extracted["agent"]
                extracted["required_agents"] = [val] if isinstance(val, str) else val

        return extracted

    @field_validator("required_agents")
    @classmethod
    def sanitize_required_agents(cls, v: List[str]) -> List[str]:
        sanitized = []
        for agent in v:
            clean = agent.lower().strip()
            if clean in ALLOWED_AGENTS and clean not in sanitized:
                sanitized.append(clean)
        return sanitized


class ConfidenceAssessment(BaseModel):
    """Explainable evidence quality score and rationale factors."""
    score: float = Field(..., ge=0.0, le=1.0, description="Heuristic evidence quality score")
    level: Literal["LOW", "MODERATE", "HIGH"] = Field(..., description="Qualitative confidence band")
    factors: List[str] = Field(default_factory=list, description="Specific empirical factors determining the score")


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
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evidence quality score")
    supporting_evidence_ids: List[str] = Field(..., description="Evidence IDs backing the selected root cause")
    contradictory_evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs contradicting the hypothesis")
    reasoning_summary: str = Field(..., description="Causal explanation linking evidence to the root cause")
    recommended_action: RecommendedAction


class VerificationEvaluation(BaseModel):
    """Structured output from Verification Agent semantic audit with actionable feedback."""
    verified: bool = Field(..., description="Whether the hypothesis is empirically verified")
    confidence_acceptable: bool = Field(..., description="Whether the assigned confidence matches evidence strength")
    evidence_sufficient: bool = Field(..., description="Whether evidence sufficiency criteria are met")
    contradictions_found: bool = Field(..., description="Whether unaddressed contradictory evidence was detected")
    challenge_category: Optional[str] = Field(None, description="Category of challenge: FABRICATED_EVIDENCE_ID, INSUFFICIENT_EVIDENCE, LOW_SOURCE_DIVERSITY, UNRESOLVED_CONTRADICTION, UNCALIBRATED_CONFIDENCE, SEMANTIC_CHALLENGE, VERIFICATION_UNAVAILABLE")
    missing_evidence_types: List[str] = Field(default_factory=list, description="Types of missing evidence required: log, metric, deployment, runbook")
    weak_evidence_types: List[str] = Field(default_factory=list, description="Evidence types that provided weak signal")
    requested_agent_types: List[str] = Field(default_factory=list, description="Specialist agents requested for re-investigation")
    alternative_hypotheses: List[str] = Field(default_factory=list, description="Plausible alternative explanations to explore")
    suggested_time_window: Optional[int] = Field(None, description="Suggested time window expansion in minutes")
    explanation: str = Field(..., description="Detailed explanation of the verification verdict")


# Aliases for backward compatibility
Hypothesis = HypothesisItem
VerificationResult = VerificationEvaluation


class InvestigationState(TypedDict):
    incident: Dict[str, Any]
    investigation_plan: Dict[str, Any]
    current_agent: str
    executed_specialists: List[str]  # Tracks specialists executed in the current iteration
    collected_evidence: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    selected_hypothesis: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    confidence: float
    confidence_assessment: Optional[Dict[str, Any]]
    recommended_action: Optional[Dict[str, Any]]
    investigation_status: str  # SUCCESS | INSUFFICIENT_EVIDENCE | INVESTIGATION_FAILED | VERIFICATION_UNAVAILABLE | RUNNING
    agent_history: List[Dict[str, Any]]
    iteration_count: int
    max_iterations: int
    error_message: Optional[str]
