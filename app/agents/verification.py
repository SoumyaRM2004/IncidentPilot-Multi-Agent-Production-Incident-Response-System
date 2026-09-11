from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.agents.llm import call_groq_json, get_groq_client


def run_verification_agent(state: InvestigationState) -> InvestigationState:
    """Verification Agent: Rigorously audits root cause hypothesis against ground-truth evidence."""
    selected_hyp = state.get("selected_hypothesis")
    evidence_list = state.get("collected_evidence", [])
    iteration = state.get("iteration_count", 0)

    if not selected_hyp:
        v_result = {
            "verified": False,
            "confidence_acceptable": False,
            "evidence_sufficient": False,
            "contradictions_found": False,
            "explanation": "No root cause hypothesis was selected for verification."
        }
        state["verification_result"] = v_result
        state["investigation_status"] = "INVESTIGATION_FAILED"
        return state

    # 1. Audit Evidence Existence
    existing_evidence_map = {e["evidence_id"]: e for e in evidence_list}
    supporting_ids = selected_hyp.get("supporting_evidence_ids", [])
    contradictory_ids = selected_hyp.get("contradictory_evidence_ids", [])
    confidence = float(selected_hyp.get("confidence", 0.0))

    valid_supporting = [eid for eid in supporting_ids if eid in existing_evidence_map]
    fabricated_ids = [eid for eid in supporting_ids if eid not in existing_evidence_map]

    # Audit rules
    has_sufficient_evidence = len(valid_supporting) >= 2 and len(fabricated_ids) == 0
    has_contradictions = len(contradictory_ids) > 0
    is_confidence_acceptable = True

    if confidence >= 0.85 and len(valid_supporting) < 2:
        is_confidence_acceptable = False
    elif confidence > 1.0 or confidence < 0.0:
        is_confidence_acceptable = False

    # Perform LLM or deterministic verification reasoning
    client = get_groq_client()
    if client and has_sufficient_evidence:
        try:
            system_prompt = (
                "You are the Independent Verification Agent. Your mandate is to rigorously challenge "
                "the proposed root cause hypothesis against the collected evidence. "
                "Verify: (1) Does the evidence truly support the hypothesis? (2) Are there unexplained contradictions? "
                "Output JSON with: verified (bool), confidence_acceptable (bool), evidence_sufficient (bool), "
                "contradictions_found (bool), explanation (str)."
            )
            user_prompt = (
                f"Hypothesis: {selected_hyp.get('selected_root_cause')}\n"
                f"Confidence: {confidence}\n"
                f"Supporting Evidence IDs: {valid_supporting}\n"
                f"Evidence Findings: {[existing_evidence_map[eid]['finding'] for eid in valid_supporting]}\n"
                f"Contradictory IDs: {contradictory_ids}"
            )
            v_eval = call_groq_json(system_prompt, user_prompt)
            verified = bool(v_eval.get("verified", False))
            is_confidence_acceptable = bool(v_eval.get("confidence_acceptable", is_confidence_acceptable))
            has_sufficient_evidence = bool(v_eval.get("evidence_sufficient", has_sufficient_evidence))
            has_contradictions = bool(v_eval.get("contradictions_found", has_contradictions))
            explanation = v_eval.get("explanation", "LLM verification audit completed.")
        except Exception:
            verified = has_sufficient_evidence and is_confidence_acceptable and not has_contradictions
            explanation = _build_verification_explanation(has_sufficient_evidence, is_confidence_acceptable, has_contradictions, valid_supporting, fabricated_ids)
    else:
        verified = has_sufficient_evidence and is_confidence_acceptable and not has_contradictions
        explanation = _build_verification_explanation(has_sufficient_evidence, is_confidence_acceptable, has_contradictions, valid_supporting, fabricated_ids)

    verification_result = {
        "verified": verified,
        "confidence_acceptable": is_confidence_acceptable,
        "evidence_sufficient": has_sufficient_evidence,
        "contradictions_found": has_contradictions,
        "explanation": explanation
    }

    state["verification_result"] = verification_result
    state["current_agent"] = "verification"

    history_entry = {
        "agent": "Verification Agent",
        "timestamp": datetime.utcnow().isoformat(),
        "iteration": iteration,
        "action": "Challenged root cause hypothesis against empirical evidence catalog",
        "findings": f"Verdict: {'VERIFIED' if verified else 'FAILED'} - {explanation}"
    }

    if verified:
        state["investigation_status"] = "SUCCESS"
    else:
        max_iters = state.get("max_iterations", 2)
        if iteration < max_iters:
            # Increment iteration and trigger re-investigation loop
            state["iteration_count"] = iteration + 1
            history_entry["action"] += " -> Triggering Re-investigation Loop"
        else:
            state["investigation_status"] = "INSUFFICIENT_EVIDENCE"
            state["recommended_action"] = {
                "action": "Escalate to on-call Human Site Reliability Engineer",
                "target_service": state["incident"].get("service", "unknown"),
                "human_approval_required": True,
                "approval_status": "ESCALATED",
                "estimated_risk": "HIGH",
                "rationale": "Automated multi-agent investigation could not verify root cause with high confidence."
            }

    state["agent_history"].append(history_entry)
    return state


def _build_verification_explanation(
    sufficient: bool,
    conf_ok: bool,
    contradictions: bool,
    valid_ids: List[str],
    fabricated_ids: List[str]
) -> str:
    if fabricated_ids:
        return f"Verification FAILED: Detected unverified or fabricated evidence IDs: {fabricated_ids}."
    if not sufficient:
        return f"Verification FAILED: Insufficient supporting evidence ({len(valid_ids)} items found; minimum 2 required)."
    if not conf_ok:
        return "Verification FAILED: Confidence score is ungrounded or out of acceptable bounds."
    if contradictions:
        return "Verification FAILED: Unresolved contradictory evidence identified."
    return f"Hypothesis fully VERIFIED against {len(valid_ids)} verified evidence sources: {', '.join(valid_ids)}."
