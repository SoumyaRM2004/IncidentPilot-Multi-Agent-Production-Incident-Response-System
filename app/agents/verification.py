import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from app.graph.state import InvestigationState, VerificationEvaluation
from app.agents.llm import call_groq_json, get_groq_client
from app.config import settings

logger = logging.getLogger(__name__)


def run_verification_agent(state: InvestigationState) -> InvestigationState:
    """Verification Agent: Independent two-layer verification.

    Layer 1: Deterministic validation (authoritative, cannot be overridden by LLM).
    Layer 2: Semantic verification (challenges causality, alternative explanations, confidence justification).
    """
    selected_hyp = state.get("selected_hypothesis")
    evidence_list = state.get("collected_evidence", [])
    iteration = state.get("iteration_count", 0)

    if not selected_hyp:
        state["verification_result"] = {
            "verified": False,
            "confidence_acceptable": False,
            "evidence_sufficient": False,
            "contradictions_found": False,
            "challenge_category": "INSUFFICIENT_EVIDENCE",
            "missing_evidence_types": ["log", "metric", "deployment"],
            "weak_evidence_types": [],
            "requested_agent_types": ["logs", "metrics"],
            "alternative_hypotheses": [],
            "suggested_time_window": 120,
            "explanation": "Verification FAILED: No root cause hypothesis was formulated."
        }
        state["investigation_status"] = "INVESTIGATION_FAILED"
        return state

    # ==========================================================
    # LAYER 1: DETERMINISTIC VALIDATION (Authoritative)
    # ==========================================================
    layer1_passed, category, layer1_explanation, missing_types, requested_agents = _deterministic_audit(selected_hyp, evidence_list)

    if not layer1_passed:
        # Layer 1 failure is authoritative and terminal for this pass
        v_result = {
            "verified": False,
            "confidence_acceptable": False,
            "evidence_sufficient": category not in ("INSUFFICIENT_EVIDENCE", "FABRICATED_EVIDENCE_ID"),
            "contradictions_found": category == "UNRESOLVED_CONTRADICTION",
            "challenge_category": category,
            "missing_evidence_types": missing_types,
            "weak_evidence_types": [],
            "requested_agent_types": requested_agents,
            "alternative_hypotheses": [],
            "suggested_time_window": 120,
            "explanation": f"Layer 1 Deterministic Audit FAILED [{category}]: {layer1_explanation}"
        }
        return _handle_verification_outcome(state, v_result, iteration)

    # ==========================================================
    # LAYER 2: SEMANTIC VERIFICATION (Groq LLM Challenge)
    # ==========================================================
    client = get_groq_client()

    if client:
        try:
            system_prompt = (
                "You are the Independent Verification Agent in IncidentPilot.\n"
                "Your role is to rigorously challenge the selected root cause hypothesis against empirical evidence.\n"
                "Audit criteria:\n"
                "1. Does the evidence establish a direct causal mechanism or merely correlation?\n"
                "2. Could this be explained by another failure mode?\n"
                "3. Is the evidence quality score justified by empirical corroboration?\n"
                "Output JSON matching the VerificationEvaluation schema."
            )
            evidence_map = {e["evidence_id"]: e for e in evidence_list}
            supporting_findings = [
                evidence_map[eid]["finding"]
                for eid in selected_hyp.get("supporting_evidence_ids", [])
                if eid in evidence_map
            ]

            user_prompt = (
                f"Incident: {state['incident'].get('title')} ({state['incident'].get('service')})\n"
                f"Proposed Root Cause: {selected_hyp.get('selected_root_cause')}\n"
                f"Confidence Score: {selected_hyp.get('confidence')}\n"
                f"Supporting Evidence IDs: {selected_hyp.get('supporting_evidence_ids')}\n"
                f"Supporting Findings: {supporting_findings}\n"
                f"Contradictory IDs: {selected_hyp.get('contradictory_evidence_ids')}\n"
                f"Reasoning: {selected_hyp.get('reasoning_summary')}"
            )
            eval_dict = call_groq_json(system_prompt, user_prompt, schema_model=VerificationEvaluation)

            sem_verified = eval_dict.get("verified", False) and not eval_dict.get("contradictions_found", False)
            v_result = {
                "verified": sem_verified,
                "confidence_acceptable": eval_dict.get("confidence_acceptable", True),
                "evidence_sufficient": eval_dict.get("evidence_sufficient", True),
                "contradictions_found": eval_dict.get("contradictions_found", False),
                "challenge_category": None if sem_verified else "SEMANTIC_CHALLENGE",
                "missing_evidence_types": eval_dict.get("missing_evidence_types", []),
                "weak_evidence_types": eval_dict.get("weak_evidence_types", []),
                "requested_agent_types": eval_dict.get("requested_agent_types", []),
                "alternative_hypotheses": eval_dict.get("alternative_hypotheses", []),
                "suggested_time_window": eval_dict.get("suggested_time_window"),
                "explanation": eval_dict.get("explanation", "Semantic verification completed.")
            }
        except Exception as e:
            logger.warning(f"Layer 2 semantic verification call failed: {e}.")
            # CRITICAL: If Layer 2 fails or is unavailable, NEVER default to verified=True!
            v_result = {
                "verified": False,
                "confidence_acceptable": False,
                "evidence_sufficient": True,
                "contradictions_found": False,
                "challenge_category": "VERIFICATION_UNAVAILABLE",
                "missing_evidence_types": [],
                "weak_evidence_types": [],
                "requested_agent_types": [],
                "alternative_hypotheses": [],
                "suggested_time_window": None,
                "explanation": "Layer 2 unavailable; deterministic Layer 1 passed but semantic verification could not be completed."
            }
    else:
        # Client is not configured/available: Record explicit VERIFICATION_UNAVAILABLE
        v_result = {
            "verified": False,
            "confidence_acceptable": False,
            "evidence_sufficient": True,
            "contradictions_found": False,
            "challenge_category": "VERIFICATION_UNAVAILABLE",
            "missing_evidence_types": [],
            "weak_evidence_types": [],
            "requested_agent_types": [],
            "alternative_hypotheses": [],
            "suggested_time_window": None,
            "explanation": "Layer 2 unavailable; deterministic Layer 1 passed but semantic verification could not be completed."
        }

    return _handle_verification_outcome(state, v_result, iteration)


def _deterministic_audit(
    selected_hyp: Dict[str, Any],
    evidence_list: List[Dict[str, Any]]
) -> Tuple[bool, str, str, List[str], List[str]]:
    """Authoritative deterministic validation checks.

    Returns:
        (passed, category, explanation, missing_evidence_types, requested_agents)
    """
    existing_evidence_map = {e["evidence_id"]: e for e in evidence_list}
    supporting_ids = selected_hyp.get("supporting_evidence_ids", [])
    contradictory_ids = selected_hyp.get("contradictory_evidence_ids", [])
    confidence = float(selected_hyp.get("confidence", 0.0))

    # 1. Hallucinated / Fabricated evidence IDs check
    fabricated_ids = [eid for eid in supporting_ids if eid not in existing_evidence_map]
    if fabricated_ids:
        return (
            False,
            "FABRICATED_EVIDENCE_ID",
            f"Detected fabricated or non-existent evidence IDs: {fabricated_ids}.",
            ["log", "metric", "deployment"],
            ["logs", "metrics", "deployments"]
        )

    # 2. Minimum evidence count check
    if len(supporting_ids) < settings.min_supporting_evidence_count:
        return (
            False,
            "INSUFFICIENT_EVIDENCE",
            f"Insufficient evidence: {len(supporting_ids)} supporting items provided (minimum {settings.min_supporting_evidence_count} required).",
            ["log", "metric"],
            ["logs", "metrics"]
        )

    # 3. Confidence sanity bounds
    if confidence < 0.0 or confidence > 1.0:
        return (
            False,
            "UNCALIBRATED_CONFIDENCE",
            f"Confidence score {confidence} is outside valid bounds [0.0, 1.0].",
            [],
            []
        )

    # 4. Source diversity check: At least two independent empirical source types required
    # Runbook is operational guidance, NOT an independent empirical source
    supporting_items = [existing_evidence_map[eid] for eid in supporting_ids if eid in existing_evidence_map]
    has_logs = any(item.get("source_type") in ("log", "analytics") for item in supporting_items)
    has_metrics = any(item.get("source_type") == "metric" for item in supporting_items)
    has_deployments = any(item.get("source_type") == "deployment" for item in supporting_items)

    empirical_domain_count = sum([has_logs, has_metrics, has_deployments])

    if empirical_domain_count < 2:
        missing = []
        requested = []
        if not has_metrics:
            missing.append("metric")
            requested.append("metrics")
        if not has_deployments:
            missing.append("deployment")
            requested.append("deployments")
        if not has_logs:
            missing.append("log")
            requested.append("logs")

        return (
            False,
            "LOW_SOURCE_DIVERSITY",
            f"Verification requires at least two independent empirical source types (logs, metrics, deployments), but only found {empirical_domain_count}. Runbook guidance is operational and cannot serve as independent empirical proof.",
            missing,
            requested
        )

    # 5. Check unaddressed contradictions
    if contradictory_ids:
        return (
            False,
            "UNRESOLVED_CONTRADICTION",
            f"Unresolved contradictory evidence IDs detected: {contradictory_ids}.",
            [],
            []
        )

    # 6. Check for non-empty root cause title
    title = selected_hyp.get("selected_root_cause", "").strip()
    if not title or "inconclusive" in title.lower():
        return (
            False,
            "INSUFFICIENT_EVIDENCE",
            "Selected root cause is marked inconclusive or empty.",
            ["log", "metric"],
            ["logs", "metrics"]
        )

    return True, "VALIDATED", "Deterministic validation passed.", [], []


def _handle_verification_outcome(
    state: InvestigationState,
    v_result: Dict[str, Any],
    iteration: int
) -> InvestigationState:
    """Updates investigation state based on verification verdict and bounded iterations."""
    verified = v_result.get("verified", False)
    category = v_result.get("challenge_category")
    max_iters = state.get("max_iterations", settings.max_investigation_iterations)

    state["verification_result"] = v_result
    state["current_agent"] = "verification"

    if verified:
        verdict_str = "VERIFIED"
        state["investigation_status"] = "SUCCESS"
    elif category == "VERIFICATION_UNAVAILABLE":
        verdict_str = "VERIFICATION_UNAVAILABLE"
        state["investigation_status"] = "VERIFICATION_UNAVAILABLE"
    else:
        verdict_str = "CHALLENGED"

    history_entry = {
        "agent": "Verification Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": "Conducted independent two-layer evidence and causal verification",
        "findings": f"Verdict: {verdict_str} - {v_result.get('explanation')}"
    }

    if not verified:
        if iteration < max_iters and category != "VERIFICATION_UNAVAILABLE":
            # Increment iteration and trigger adaptive re-investigation loop
            state["iteration_count"] = iteration + 1
            state["investigation_status"] = "CHALLENGED"
            history_entry["action"] += f" -> Routing to Supervisor for targeted re-investigation (Loop {state['iteration_count']})"
        else:
            if state["investigation_status"] != "VERIFICATION_UNAVAILABLE":
                state["investigation_status"] = "INSUFFICIENT_EVIDENCE"
            service = state["incident"].get("service", "unknown")
            state["recommended_action"] = {
                "action": f"Escalate {service} incident to Senior Site Reliability Engineer",
                "target_service": service,
                "human_approval_required": True,
                "approval_status": "ESCALATED",
                "estimated_risk": "HIGH",
                "rationale": f"Investigation reached terminal condition ({category or 'limit'}): {v_result.get('explanation')}"
            }

    state["agent_history"].append(history_entry)
    return state
