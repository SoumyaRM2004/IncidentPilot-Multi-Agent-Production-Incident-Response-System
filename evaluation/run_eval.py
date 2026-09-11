import json
import os
import sys
from datetime import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import init_db
from app.db.seed import seed_database
from app.graph.workflow import run_investigation


def evaluate_system():
    print("=" * 60)
    print("IncidentPilot V1 Autonomous Incident Response Evaluation")
    print("=" * 60)

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
    correct_verifications = 0

    results_table = []

    for item in benchmarks:
        inc_id = item["id"]
        service = item["service"]
        print(f"\nEvaluating [{inc_id}] {service}...")

        incident_payload = {
            "id": inc_id,
            "service": service,
            "title": item["title"],
            "description": item["description"],
            "severity": "HIGH",
            "created_at": datetime.utcnow().isoformat()
        }

        # Run multi-agent LangGraph workflow
        state = run_investigation(incident_payload)

        selected_hyp = state.get("selected_hypothesis") or {}
        root_cause_str = (selected_hyp.get("selected_root_cause", "") + " " + selected_hyp.get("reasoning_summary", "")).lower()
        supporting_ids = selected_hyp.get("supporting_evidence_ids", [])
        collected_map = {e["evidence_id"]: e for e in state.get("collected_evidence", [])}
        v_res = state.get("verification_result") or {}

        # 1. Root Cause Accuracy Check
        keywords = item.get("expected_root_cause_keywords", [])
        rc_matched = any(kw.lower() in root_cause_str for kw in keywords)
        if rc_matched:
            correct_root_causes += 1

        # 2. Evidence Support Rate Check
        item_cited = len(supporting_ids)
        total_cited_evidence += item_cited
        item_grounded = sum(1 for eid in supporting_ids if eid in collected_map)
        grounded_cited_evidence += item_grounded

        # 3. Verification Accuracy Check
        expected_v = item.get("expected_verification", True)
        actual_v = v_res.get("verified", False)
        v_matched = (expected_v == actual_v)
        if v_matched:
            correct_verifications += 1

        results_table.append({
            "Incident ID": inc_id,
            "Service": service,
            "Root Cause": selected_hyp.get("selected_root_cause", "None")[:38] + "...",
            "RC Match": "PASS" if rc_matched else "FAIL",
            "Evidence Grounding": f"{item_grounded}/{item_cited}",
            "Verified": "PASS" if v_matched else "FAIL",
            "Confidence": f"{int(state.get('confidence', 0) * 100)}%"
        })

    rc_accuracy = (correct_root_causes / total_incidents) * 100
    evidence_support_rate = (grounded_cited_evidence / total_cited_evidence * 100) if total_cited_evidence > 0 else 0
    verification_accuracy = (correct_verifications / total_incidents) * 100

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 60)
    for r in results_table:
        print(f"[{r['Incident ID']}] {r['Service']:<22} | RC: {r['RC Match']} | Evidence: {r['Evidence Grounding']} | Verif: {r['Verified']} | Conf: {r['Confidence']}")

    print("-" * 60)
    print(f"1. Root Cause Accuracy:    {rc_accuracy:.1f}% ({correct_root_causes}/{total_incidents})")
    print(f"2. Evidence Support Rate:  {evidence_support_rate:.1f}% ({grounded_cited_evidence}/{total_cited_evidence} evidence citations valid)")
    print(f"3. Verification Accuracy:  {verification_accuracy:.1f}% ({correct_verifications}/{total_incidents})")
    print("=" * 60)

    # Assert evaluation criteria
    assert rc_accuracy >= 80.0, f"Root cause accuracy below threshold: {rc_accuracy}%"
    assert evidence_support_rate == 100.0, f"Unverified evidence detected: {evidence_support_rate}%"
    assert verification_accuracy >= 80.0, f"Verification accuracy below threshold: {verification_accuracy}%"

    print("ALL EVALUATION BENCHMARKS PASSED SUCCESSFULLY.")
    return {
        "root_cause_accuracy": rc_accuracy,
        "evidence_support_rate": evidence_support_rate,
        "verification_accuracy": verification_accuracy,
        "total_incidents": total_incidents
    }


if __name__ == "__main__":
    evaluate_system()
