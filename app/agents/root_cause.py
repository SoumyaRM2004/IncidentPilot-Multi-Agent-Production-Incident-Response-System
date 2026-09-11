import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.graph.state import InvestigationState, RootCauseOutput, ConfidenceAssessment
from app.agents.llm import call_groq_json, get_groq_client

logger = logging.getLogger(__name__)


def run_root_cause_agent(state: InvestigationState) -> InvestigationState:
    """Root Cause Analyst Agent: Evaluates collected evidence, formulates candidate hypotheses,

    and performs evidence-grounded causal reasoning without benchmark hardcoding.
    """
    incident = state["incident"]
    service = incident.get("service", "")
    evidence_list = state.get("collected_evidence", [])
    iteration = state.get("iteration_count", 0)

    # Compile structured evidence catalog with IDs for LLM reasoning
    evidence_catalog = [
        {
            "id": e["evidence_id"],
            "source_type": e.get("source_type", "unknown"),
            "source": e.get("source", "unknown"),
            "timestamp": e.get("timestamp"),
            "finding": e.get("finding")
        }
        for e in evidence_list
    ]

    client = get_groq_client()
    analysis_dict = None

    if client and evidence_list:
        try:
            system_prompt = (
                "You are the Principal Incident Response Root Cause Analyst in IncidentPilot.\n"
                "Your objective is to evaluate empirical telemetry evidence and operational runbooks to identify the primary root cause.\n"
                "STRICT REQUIREMENTS:\n"
                "1. Formulate 2 to 3 distinct candidate hypotheses based on evidence.\n"
                "2. supporting_evidence_ids MUST cite the actual evidence IDs backing your conclusion.\n"
                "3. If contradictory evidence exists, cite it in contradictory_evidence_ids.\n"
                "4. Assign an evidence quality score based on corroboration (0.0 to 1.0).\n"
                "5. Propose a non-destructive remediation action with human approval required.\n"
                "6. If evidence is insufficient, set selected_root_cause to 'Inconclusive: Insufficient Evidence' and confidence < 0.5."
            )
            user_prompt = (
                f"Incident Context:\n"
                f"Title: {incident.get('title')}\n"
                f"Service: {service}\n"
                f"Description: {incident.get('description')}\n\n"
                f"Evidence Catalog ({len(evidence_catalog)} items):\n"
                f"{json.dumps(evidence_catalog, indent=2)}"
            )
            analysis_dict = call_groq_json(system_prompt, user_prompt, schema_model=RootCauseOutput)
        except Exception as e:
            logger.warning(f"Groq root-cause inference failed or schema invalid: {e}. Using evidence-driven synthesis.")
            analysis_dict = None

    if not analysis_dict:
        # Generic, evidence-driven causal synthesis without benchmark-specific keywords
        analysis_dict = _synthesize_from_evidence(incident, evidence_list)

    # CRITICAL: Preserve raw supporting evidence IDs so Layer 1 verification can detect hallucinations!
    # Do NOT silently filter out fabricated IDs here!
    raw_supporting_ids = analysis_dict.get("supporting_evidence_ids", [])
    raw_contradictory_ids = analysis_dict.get("contradictory_evidence_ids", [])

    is_inconclusive = "inconclusive" in analysis_dict.get("selected_root_cause", "").lower()

    # Compute explicit, explainable evidence quality score and rationale factors
    confidence_assessment = _assess_evidence_quality(
        supporting_ids=raw_supporting_ids,
        contradictory_ids=raw_contradictory_ids,
        evidence_list=evidence_list,
        is_inconclusive=is_inconclusive
    )

    selected_hyp = {
        "selected_root_cause": analysis_dict.get("selected_root_cause", "Inconclusive diagnosis"),
        "confidence": confidence_assessment["score"],
        "supporting_evidence_ids": raw_supporting_ids,  # CANONICAL PRESERVED for Verification Layer 1
        "contradictory_evidence_ids": raw_contradictory_ids,
        "reasoning_summary": analysis_dict.get("reasoning_summary", "Synthesized from telemetry findings."),
        "confidence_rationale": confidence_assessment["factors"]
    }

    raw_hypotheses = analysis_dict.get("hypotheses", [])
    formatted_hypotheses = []
    for h in raw_hypotheses:
        formatted_hypotheses.append({
            "id": h.get("id", "HYP-1"),
            "title": h.get("title", ""),
            "confidence": round(min(max(float(h.get("confidence", 0.5)), 0.0), 1.0), 2),
            "supporting_evidence_ids": h.get("supporting_evidence_ids", []),
            "contradictory_evidence_ids": h.get("contradictory_evidence_ids", []),
            "rationale": h.get("rationale")
        })

    rec_raw = analysis_dict.get("recommended_action", {})
    recommended_action = {
        "action": rec_raw.get("action", f"Conduct manual investigation of {service}"),
        "target_service": rec_raw.get("target_service", service),
        "human_approval_required": True,
        "approval_status": "PENDING_APPROVAL",
        "estimated_risk": rec_raw.get("estimated_risk", "LOW"),
        "rationale": rec_raw.get("rationale", selected_hyp["reasoning_summary"])
    }

    state["hypotheses"] = formatted_hypotheses
    state["selected_hypothesis"] = selected_hyp
    state["confidence"] = confidence_assessment["score"]
    state["confidence_assessment"] = confidence_assessment
    state["recommended_action"] = recommended_action
    state["current_agent"] = "root_cause"

    state["agent_history"].append({
        "agent_key": "root_cause",
        "agent": "Root Cause Analyst Agent",
        "status": "EXECUTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": "Evaluated evidence catalog and synthesized causal hypothesis",
        "findings": f"Selected root cause: '{selected_hyp['selected_root_cause']}' (Evidence Quality: {confidence_assessment['level']} - {confidence_assessment['score']}) citing {len(raw_supporting_ids)} evidence items.",
        "evidence_used": raw_supporting_ids
    })

    return state


def _assess_evidence_quality(
    supporting_ids: List[str],
    contradictory_ids: List[str],
    evidence_list: List[Dict[str, Any]],
    is_inconclusive: bool = False
) -> Dict[str, Any]:
    """Computes a heuristic, explainable evidence quality score and rationale factors.

    Evaluates: item count, independent empirical source diversity, operational runbook guidance, and contradictions.
    This is a heuristic indicator of evidence completeness and corroboration, NOT a calibrated statistical probability.
    """
    factors = []
    evidence_map = {e["evidence_id"]: e for e in evidence_list}

    # If the hypothesis is explicitly inconclusive
    if is_inconclusive:
        factors.append("Automated causal inference is inconclusive; score reflects conservative unverified baseline.")
        factors.append(f"{len(supporting_ids)} telemetry items referenced as observational context.")
        return {
            "score": 0.20,
            "level": "LOW",
            "factors": factors
        }

    # Detect if any cited IDs are fabricated
    fabricated = [eid for eid in supporting_ids if eid not in evidence_map]
    if fabricated:
        factors.append(f"Contains non-existent or fabricated evidence citations: {fabricated}")
        return {
            "score": 0.15,
            "level": "LOW",
            "factors": factors
        }

    if not supporting_ids:
        factors.append("Zero supporting evidence items cited.")
        return {
            "score": 0.20,
            "level": "LOW",
            "factors": factors
        }

    supporting_items = [evidence_map[eid] for eid in supporting_ids if eid in evidence_map]

    # Map supporting items to independent empirical domains:
    # 'log' and 'analytics' map to the single empirical domain 'log'
    empirical_domains = set()
    for item in supporting_items:
        st = item.get("source_type")
        if st in ("log", "analytics"):
            empirical_domains.add("log")
        elif st == "metric":
            empirical_domains.add("metric")
        elif st == "deployment":
            empirical_domains.add("deployment")
        # 'runbook' is operational context and does NOT count as an empirical domain

    has_runbook = any(item.get("source_type") == "runbook" for item in supporting_items)

    score = 0.50
    factors.append(f"{len(supporting_ids)} supporting evidence items cited.")

    # Empirical source diversity
    if len(empirical_domains) >= 2:
        score += 0.25
        factors.append(f"Corroborated across {len(empirical_domains)} independent empirical source domains: {sorted(list(empirical_domains))}.")
    elif len(empirical_domains) == 1:
        score = min(score, 0.40)
        factors.append(f"Restricted to single empirical domain ({list(empirical_domains)[0]}); lacks multi-source empirical corroboration.")
    else:
        score = min(score, 0.20)
        factors.append("No empirical telemetry backing (only runbook or external references).")

    # Runbook alignment (operational guidance only, not independent proof)
    if has_runbook:
        score += 0.05
        factors.append("Operational runbook provides documented procedure (operational guidance).")

    # Contradictions
    if contradictory_ids:
        score = max(score - 0.25, 0.15)
        factors.append(f"Unresolved contradictory telemetry detected: {contradictory_ids}.")
    else:
        factors.append("No contradictory telemetry detected.")

    final_score = round(min(max(score, 0.10), 0.95), 2)
    level = "HIGH" if final_score >= 0.80 else ("MODERATE" if final_score >= 0.50 else "LOW")

    return {
        "score": final_score,
        "level": level,
        "factors": factors
    }


def _synthesize_from_evidence(
    incident: Dict[str, Any],
    evidence_list: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Conservative fallback when semantic Root Cause LLM inference is unavailable.

    Summarizes observed telemetry and preserves evidence IDs, but produces an explicitly
    inconclusive hypothesis rather than inventing an unsupported causal diagnosis.
    """
    service = incident.get("service", "service")
    collected_ids = [e["evidence_id"] for e in evidence_list]

    # Summarize observed telemetry without fabricating causal claims
    logs = [e for e in evidence_list if e.get("source_type") in ("log", "analytics")]
    metrics = [e for e in evidence_list if e.get("source_type") == "metric"]
    deployments = [e for e in evidence_list if e.get("source_type") == "deployment"]
    runbooks = [e for e in evidence_list if e.get("source_type") == "runbook"]

    telemetry_signals = []
    if logs:
        telemetry_signals.append(f"{len(logs)} log events")
    if metrics:
        telemetry_signals.append(f"{len(metrics)} metric samples")
    if deployments:
        telemetry_signals.append(f"{len(deployments)} deployment records")
    if runbooks:
        telemetry_signals.append(f"{len(runbooks)} runbook references")

    signals_desc = ", ".join(telemetry_signals) if telemetry_signals else "no telemetry collected"

    reasoning = (
        f"Telemetry was collected ({signals_desc}), but automated causal inference could not be completed "
        f"because the semantic root-cause analysis component was unavailable. "
        f"Manual investigation is required to establish causality."
    )

    return {
        "selected_root_cause": "Inconclusive: automated causal inference unavailable",
        "confidence": 0.20,
        "supporting_evidence_ids": collected_ids,
        "contradictory_evidence_ids": [],
        "reasoning_summary": reasoning,
        "hypotheses": [
            {
                "id": "HYP-INCONCLUSIVE",
                "title": "Inconclusive: automated causal inference unavailable",
                "confidence": 0.20,
                "supporting_evidence_ids": collected_ids,
                "contradictory_evidence_ids": [],
                "rationale": reasoning
            }
        ],
        "recommended_action": {
            "action": f"Escalate {service} incident to on-call engineer for manual telemetry triage",
            "target_service": service,
            "human_approval_required": True,
            "approval_status": "PENDING_APPROVAL",
            "estimated_risk": "LOW",
            "rationale": "Automated causal diagnosis is inconclusive; requires human operator triage."
        }
    }
