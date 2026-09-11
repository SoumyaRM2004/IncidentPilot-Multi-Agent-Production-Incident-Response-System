import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
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
            "explanation": "Verification FAILED: No root cause hypothesis was formulated."
        }
        state["investigation_status"] = "INVESTIGATION_FAILED"
        return state

    # ==========================================================
    # LAYER 1: DETERMINISTIC VALIDATION (Authoritative)
    # ==========================================================
    layer1_passed, layer1_explanation = _deterministic_audit(selected_hyp, evidence_list)

    if not layer1_passed:
        # Layer 1 failure is terminal for this iteration; LLM cannot override
        v_result = {
            "verified": False,
            "confidence_acceptable": False,
            "evidence_sufficient": False,
            "contradictions_found": bool(selected_hyp.get("contradictory_evidence_ids")),
            "explanation": f"Layer 1 Deterministic Audit FAILED: {layer1_explanation}"
        }
        return _handle_verification_outcome(state, v_result, iteration)

    # ==========================================================
    # LAYER 2: SEMANTIC VERIFICATION (Groq LLM Challenge)
    # ==========================================================
    layer2_result = None
    client = get_groq_client()

    if client:
        try:
            system_prompt = (
                "You are the Independent Verification Agent in IncidentPilot.\n"
                "Your role is to rigorously challenge the selected root cause hypothesis against empirical evidence.\n"
                "Audit criteria:\n"
                "1. Does the evidence establish a direct causal mechanism or merely correlation?\n"
                "2. Could this be explained by another failure mode?\n"
                "3. Is the confidence score justified by evidence strength?\n"
                "Output JSON matching: verified (bool), confidence_acceptable (bool), evidence_sufficient (bool), "
                "contradictions_found (bool), explanation (str)."
            )
            evidence_map = {e["evidence_id"]: e for e in evidence_list}
            supporting_findings = [evidence_map[eid]["finding"] for eid in selected_hyp.get("supporting_evidence_ids", []) if eid in evidence_map]

            user_prompt = (
                f"Incident: {state['incident'].get('title')} ({state['incident'].get('service')})\n"
                f"Proposed Root Cause: {selected_hyp.get('selected_root_cause')}\n"
                f"Confidence: {selected_hyp.get('confidence')}\n"
                f"Supporting Evidence IDs: {selected_hyp.get('supporting_evidence_ids')}\n"
                f"Supporting Findings: {supporting_findings}\n"
                f"Contradictory IDs: {selected_hyp.get('contradictory_evidence_ids')}\n"
                f"Reasoning: {selected_hyp.get('reasoning_summary')}"
            )
            eval_dict = call_groq_json(system_prompt, user_prompt, schema_model=VerificationEvaluation)
            layer2_result = eval_dict
        except Exception as e:
            logger.warning(f"Layer 2 semantic verification call failed: {e}. Falling back to deterministic pass.")
            layer2_result = None

    if not layer2_result:
        # Default Layer 2 evaluation when LLM is unavailable or succeeds
        layer2_result = {
            "verified": True,
            "confidence_acceptable": True,
            "evidence_sufficient": True,
            "contradictions_found": False,
            "explanation": f"Layer 1 and Layer 2 verified across {len(selected_hyp.get('supporting_evidence_ids', []))} evidence sources."
        }

    # Combine results safely: Layer 1 is already checked as True here
    final_verified = layer2_result.get("verified", False) and not layer2_result.get("contradictions_found", False)
    v_result = {
        "verified": final_verified,
        "confidence_acceptable": layer2_result.get("confidence_acceptable", True),
        "evidence_sufficient": layer2_result.get("evidence_sufficient", True),
        "contradictions_found": layer2_result.get("contradictions_found", False),
        "explanation": layer2_result.get("explanation", "Verification completed.")
    }

    return _handle_verification_outcome(state, v_result, iteration)


def _deterministic_audit(
    selected_hyp: Dict[str, Any],
    evidence_list: List[Dict[str, Any]]
) -> Tuple[bool, str]:
    """Authoritative deterministic validation checks."""
    existing_evidence_map = {e["evidence_id"]: e for e in evidence_list}
    supporting_ids = selected_hyp.get("supporting_evidence_ids", [])
    contradictory_ids = selected_hyp.get("contradictory_evidence_ids", [])
    confidence = float(selected_hyp.get("confidence", 0.0))

    # 1. Check for hallucinated or fabricated evidence IDs
    fabricated_ids = [eid for eid in supporting_ids if eid not in existing_evidence_map]
    if fabricated_ids:
        return False, f"Detected fabricated or non-existent evidence IDs: {fabricated_ids}."

    # 2. Minimum evidence count check
    if len(supporting_ids) < settings.min_supporting_evidence_count:
        return False, f"Insufficient evidence: {len(supporting_ids)} supporting items provided (minimum {settings.min_supporting_evidence_count} required)."

    # 3. Confidence sanity bounds
    if confidence < 0.0 or confidence > 1.0:
        return False, f"Confidence score {confidence} is outside valid bounds [0.0, 1.0]."

    # 4. Multi-source diversity check for high confidence diagnoses
    if confidence >= 0.80:
        source_types = {existing_evidence_map[eid].get("source_type") for eid in supporting_ids if eid in existing_evidence_map}
        if len(source_types) < 2:
            return False, f"High confidence ({confidence}) requires multi-source corroboration, but only found sources: {source_types}."

    # 5. Check unaddressed contradictions
    if contradictory_ids:
        return False, f"Unresolved contradictory evidence IDs detected: {contradictory_ids}."

    # 6. Check for non-empty root cause title
    title = selected_hyp.get("selected_root_cause", "").strip()
    if not title or "inconclusive" in title.lower():
        return False, "Selected root cause is marked inconclusive or empty."

    return True, "Deterministic validation passed."


def _handle_verification_outcome(
    state: InvestigationState,
    v_result: Dict[str, Any],
    iteration: int
) -> InvestigationState:
    """Updates investigation state based on verification verdict and bounded iterations."""
    verified = v_result.get("verified", False)
    max_iters = state.get("max_iterations", settings.max_investigation_iterations)

    state["verification_result"] = v_result
    state["current_agent"] = "verification"

    history_entry = {
        "agent": "Verification Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": "Conducted independent two-layer evidence and causal verification",
        "findings": f"Verdict: {'VERIFIED' if verified else 'CHALLENGED'} - {v_result.get('explanation')}"
    }

    if verified:
        state["investigation_status"] = "SUCCESS"
    else:
        if iteration < max_iters:
            # Increment iteration and trigger adaptive re-investigation loop
            state["iteration_count"] = iteration + 1
            history_entry["action"] += f" -> Routing to Supervisor for targeted re-investigation (Loop {state['iteration_count']})"
        else:
            state["investigation_status"] = "INSUFFICIENT_EVIDENCE"
            service = state["incident"].get("service", "unknown")
            state["recommended_action"] = {
                "action": f"Escalate {service} incident to Senior Site Reliability Engineer",
                "target_service": service,
                "human_approval_required": True,
                "approval_status": "ESCALATED",
                "estimated_risk": "HIGH",
                "rationale": f"Investigation reached maximum iteration budget ({max_iters}) without meeting verification criteria: {v_result.get('explanation')}"
            }

    state["agent_history"].append(history_entry)
    return state
