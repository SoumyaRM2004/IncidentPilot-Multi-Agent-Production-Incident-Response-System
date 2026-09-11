import json
import os
import sys
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import init_db
from app.db.seed import seed_database
from app.graph.workflow import run_investigation


def evaluate_system():
    print("=" * 80)
    print("IncidentPilot Multi-Agent Production Incident Response Evaluation")
    print("=" * 80)

    # 1. Initialize environment
    init_db()
    seed_database()

    eval_file = os.path.join(os.path.dirname(__file__), "incidents.json")
    with open(eval_file, "r", encoding="utf-8") as f:
        benchmarks = json.load(f)

    total_incidents = len(benchmarks)
    correct_root_causes = 0
    total_cited_evidence = 0
    grounded_cited_evidence = 0
    hallucinated_evidence = 0
    correct_verifications = 0
    verification_rejections = 0
    total_iterations = 0

    results_table = []

    for item in benchmarks:
        inc_id = item["id"]
        category = item.get("category", "standard")
        service = item["service"]
        expected_v = item.get("expected_verification", True)
        print(f"\nEvaluating [{inc_id}] ({category}) {service}...")

        incident_payload = {
            "id": inc_id,
            "service": service,
            "title": item["title"],
            "description": item["description"],
            "severity": "HIGH",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Run multi-agent LangGraph workflow
        state = run_investigation(incident_payload)

        selected_hyp = state.get("selected_hypothesis") or {}
        root_cause_str = (selected_hyp.get("selected_root_cause", "") + " " + selected_hyp.get("reasoning_summary", "")).lower()
        supporting_ids = selected_hyp.get("supporting_evidence_ids", [])
        collected_map = {e["evidence_id"]: e for e in state.get("collected_evidence", [])}
        v_res = state.get("verification_result") or {}
        actual_v = v_res.get("verified", False)
        iterations = state.get("iteration_count", 1)
        total_iterations += iterations

        if not actual_v:
            verification_rejections += 1

        # 1. Root Cause Accuracy Check
        keywords = item.get("expected_root_cause_keywords", [])
        if not expected_v:
            # For insufficient evidence cases, success means correctly recognizing lack of evidence
            rc_matched = (
                state.get("investigation_status") in ("INSUFFICIENT_EVIDENCE", "INVESTIGATION_FAILED") or
                any(kw.lower() in root_cause_str for kw in keywords)
            )
        else:
            rc_matched = any(kw.lower() in root_cause_str for kw in keywords)

        if rc_matched:
            correct_root_causes += 1

        # 2. Evidence Grounding & Hallucination Check
        item_cited = len(supporting_ids)
        total_cited_evidence += item_cited
        item_grounded = sum(1 for eid in supporting_ids if eid in collected_map)
        item_hallucinated = item_cited - item_grounded
        grounded_cited_evidence += item_grounded
        hallucinated_evidence += item_hallucinated

        # 3. Verification Accuracy Check
        v_matched = (expected_v == actual_v)
        if v_matched:
            correct_verifications += 1

        results_table.append({
            "Incident ID": inc_id,
            "Category": category,
            "Service": service,
            "Root Cause": selected_hyp.get("selected_root_cause", "None")[:32] + "...",
            "RC Match": "PASS" if rc_matched else "FAIL",
            "Evidence Grounding": f"{item_grounded}/{item_cited}",
            "Verified": "PASS" if v_matched else "FAIL",
            "Iterations": str(iterations),
            "Confidence": f"{int(state.get('confidence', 0) * 100)}%"
        })

    rc_accuracy = (correct_root_causes / total_incidents) * 100
    evidence_grounding_rate = (grounded_cited_evidence / total_cited_evidence * 100) if total_cited_evidence > 0 else 100.0
    hallucination_rate = (hallucinated_evidence / total_cited_evidence * 100) if total_cited_evidence > 0 else 0.0
    verification_accuracy = (correct_verifications / total_incidents) * 100
    verification_rejection_rate = (verification_rejections / total_incidents) * 100
    avg_iterations = total_iterations / total_incidents

    print("\n" + "=" * 80)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    header = f"{'ID':<9} | {'Category':<14} | {'Service':<18} | {'RC':<4} | {'Evidence':<8} | {'Verif':<5} | {'Iters':<5} | {'Conf':<5}"
    print(header)
    print("-" * 80)
    for r in results_table:
        print(f"{r['Incident ID']:<9} | {r['Category']:<14} | {r['Service']:<18} | {r['RC Match']:<4} | {r['Evidence Grounding']:<8} | {r['Verified']:<5} | {r['Iterations']:<5} | {r['Confidence']:<5}")

    print("=" * 80)
    print("KEY METRICS:")
    print(f"1. Root Cause Accuracy:         {rc_accuracy:.1f}% ({correct_root_causes}/{total_incidents})")
    print(f"2. Evidence Grounding Rate:       {evidence_grounding_rate:.1f}% ({grounded_cited_evidence}/{total_cited_evidence} citations grounded in telemetry)")
    print(f"3. Hallucination Rate:           {hallucination_rate:.1f}% ({hallucinated_evidence}/{total_cited_evidence} fabricated citation IDs)")
    print(f"4. Verification Accuracy:        {verification_accuracy:.1f}% ({correct_verifications}/{total_incidents} correctly judged)")
    print(f"5. Verification Rejection Rate:  {verification_rejection_rate:.1f}% ({verification_rejections}/{total_incidents} flagged or rejected)")
    print(f"6. Avg Iterations to Converge:   {avg_iterations:.2f}")
    print("=" * 80)

    # Assert evaluation criteria
    assert rc_accuracy >= 80.0, f"Root cause accuracy below threshold: {rc_accuracy}%"
    assert evidence_grounding_rate == 100.0, f"Unverified/ungrounded evidence detected: {evidence_grounding_rate}%"
    assert hallucination_rate == 0.0, f"Hallucinated evidence citations detected: {hallucination_rate}%"
    assert verification_accuracy >= 80.0, f"Verification accuracy below threshold: {verification_accuracy}%"

    print("ALL EVALUATION BENCHMARKS PASSED SUCCESSFULLY.")
    return {
        "root_cause_accuracy": rc_accuracy,
        "evidence_grounding_rate": evidence_grounding_rate,
        "hallucination_rate": hallucination_rate,
        "verification_accuracy": verification_accuracy,
        "verification_rejection_rate": verification_rejection_rate,
        "avg_iterations": avg_iterations,
        "total_incidents": total_incidents
    }


if __name__ == "__main__":
    evaluate_system()
