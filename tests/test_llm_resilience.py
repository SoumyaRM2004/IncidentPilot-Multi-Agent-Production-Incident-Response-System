import pytest
from unittest.mock import patch, MagicMock
from groq import RateLimitError
from app.graph.state import InvestigationPlanModel
from app.graph.workflow import create_initial_state, run_investigation
from app.agents.llm import (
    call_groq_json,
    is_rate_limited,
    get_rate_limit_reason,
    set_rate_limited,
    reset_rate_limit_state,
    LLMRateLimitError,
)
from app.agents.supervisor import run_supervisor_agent
from app.agents.root_cause import run_root_cause_agent
from app.agents.verification import run_verification_agent, _deterministic_audit


# ==============================================================================
# 1. SUPERVISOR RESPONSE WRAPPER / SCHEMA MISMATCH REGRESSION TESTS
# ==============================================================================

def test_supervisor_schema_handles_list_wrapper_mismatch():
    """Exact regression test: Groq output shaped like {'investigation_plan': [...]}

    must be parsed into canonical InvestigationPlanModel with required focus & strategy.
    """
    # The exact observed Groq response format:
    raw_groq_response = {
        "investigation_plan": [
            {
                "agent": "logs",
                "focus": "Investigate database connection timeout errors",
                "strategy": "Query logs for QueuePool limit and acquisition failures"
            },
            {
                "agent": "metrics",
                "focus": "Analyze connection pool saturation",
                "strategy": "Inspect db_connection_pool_utilization and active connections"
            }
        ]
    }

    model = InvestigationPlanModel.model_validate(raw_groq_response)
    assert "logs" in model.required_agents
    assert "metrics" in model.required_agents
    assert "database connection timeout" in model.focus.lower()
    assert "query logs" in model.strategy.lower()
    assert model.window_minutes == 60


def test_supervisor_schema_handles_dict_wrapper_mismatch():
    """Groq output wrapped in {'investigation_plan': {...}} must unwrap correctly."""
    raw_groq_response = {
        "investigation_plan": {
            "focus": "Investigate transaction latency surge",
            "strategy": "Examine service metrics and error frequency",
            "required_agents": ["logs", "metrics"],
            "log_query": "TimeoutError",
            "metric_names": ["p99_latency_ms"],
            "window_minutes": 90
        }
    }

    model = InvestigationPlanModel.model_validate(raw_groq_response)
    assert model.focus == "Investigate transaction latency surge"
    assert model.strategy == "Examine service metrics and error frequency"
    assert model.required_agents == ["logs", "metrics"]
    assert model.log_query == "TimeoutError"
    assert model.metric_names == ["p99_latency_ms"]
    assert model.window_minutes == 90


def test_supervisor_agent_end_to_end_with_wrapped_llm_response():
    """run_supervisor_agent successfully parses wrapped LLM response without falling back."""
    wrapped_response = {
        "investigation_plan": [
            {
                "agent": "logs",
                "focus": "Investigate payment failures",
                "strategy": "Inspect error logs"
            }
        ]
    }
    incident = {
        "id": "INC-001",
        "title": "Payment failures",
        "description": "Payment timeouts",
        "service": "payment-service"
    }
    state = create_initial_state(incident)

    with patch("app.agents.supervisor.get_groq_client", return_value=True), \
         patch("app.agents.supervisor.call_groq_json", return_value=InvestigationPlanModel.model_validate(wrapped_response).model_dump()):
        state = run_supervisor_agent(state)

    plan = state["investigation_plan"]
    assert "logs" in plan["required_agents"]
    assert "Investigate payment failures" in plan["focus"]
    assert "Inspect error logs" in plan["strategy"]


# ==============================================================================
# 2. HTTP 429 RATE-LIMIT HANDLING & CIRCUIT-BREAKER REGRESSION TESTS
# ==============================================================================

def test_429_rate_limit_detection_and_circuit_breaker():
    """HTTP 429 triggers LLMRateLimitError, latches rate-limited state,

    and fails-fast on subsequent calls without touching Groq client.
    """
    reset_rate_limit_state()
    assert not is_rate_limited()

    # Create mock Groq client whose chat completion raises a 429 RateLimitError
    mock_client = MagicMock()
    # Simulate groq.RateLimitError response
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    rate_limit_exc = RateLimitError(
        message="Rate limit reached for model `openai/gpt-oss-120b` on tokens per day (TPD): Limit 200000",
        response=mock_resp,
        body={"error": {"message": "Rate limit reached", "code": "rate_limit_exceeded"}}
    )
    mock_client.chat.completions.create.side_effect = rate_limit_exc

    with patch("app.agents.llm.get_groq_client", return_value=mock_client):
        with pytest.raises(LLMRateLimitError) as exc_info:
            call_groq_json("system prompt", "user prompt")

        assert "429" in str(exc_info.value)
        assert is_rate_limited()
        assert "Rate limit reached" in get_rate_limit_reason()

        # Subsequent call MUST fail-fast immediately via circuit-breaker
        # and MUST NOT call mock_client.chat.completions.create again!
        initial_call_count = mock_client.chat.completions.create.call_count
        with pytest.raises(LLMRateLimitError) as exc_info2:
            call_groq_json("second system prompt", "second user prompt")

        assert is_rate_limited()
        assert mock_client.chat.completions.create.call_count == initial_call_count  # Zero retries!


# ==============================================================================
# 3. RCA REMAINS INCONCLUSIVE WHEN LLM IS UNAVAILABLE REGRESSION TESTS
# ==============================================================================

def test_root_cause_inconclusive_when_rate_limited():
    """When LLM is unavailable / rate-limited, Root Cause Analyst must:

    1. Never fabricate a root cause.
    2. Keep selected_root_cause explicitly inconclusive.
    3. Return zero supporting evidence IDs (supporting_evidence_ids == []).
    4. Keep confidence low (<= 0.20).
    5. Record rate-limit diagnostic reason in agent history.
    """
    set_rate_limited("Rate limit reached for model openai/gpt-oss-120b: TPD limit 200000")

    incident = {
        "id": "INC-001",
        "title": "Payment database connection timeouts",
        "description": "Connection pool acquisition timeout errors",
        "service": "payment-service"
    }
    state = create_initial_state(incident)
    state["collected_evidence"] = [
        {"evidence_id": "LOG-101", "source_type": "log", "source": "logs", "service": "payment-service", "finding": "QueuePool limit reached"},
        {"evidence_id": "METRIC-1", "source_type": "metric", "source": "service_metrics", "service": "payment-service", "finding": "Pool utilization 98%"}
    ]

    state = run_root_cause_agent(state)

    selected = state["selected_hypothesis"]
    assert selected is not None
    assert "inconclusive" in selected["selected_root_cause"].lower()
    # CRITICAL: zero supporting evidence IDs (never fabricated)
    assert selected["supporting_evidence_ids"] == []
    assert selected["confidence"] <= 0.20

    # Concise rate-limit reason recorded in history
    history_entry = [h for h in state["agent_history"] if h["agent_key"] == "root_cause"][-1]
    assert "rate-limited" in history_entry["findings"].lower()
    assert "tpd limit 200000" in history_entry["findings"].lower()


# ==============================================================================
# 4. DETERMINISTIC VERIFICATION REJECTS ZERO SUPPORTING EVIDENCE IDS
# ==============================================================================

def test_verification_rejects_zero_supporting_evidence_ids():
    """Verification Layer 1 must deterministically reject hypotheses with 0 supporting evidence items,

    regardless of LLM availability, without making any LLM call.
    """
    incident = {
        "id": "INC-001",
        "title": "Payment database connection timeouts",
        "description": "Timeouts",
        "service": "payment-service"
    }
    state = create_initial_state(incident)
    state["collected_evidence"] = [
        {"evidence_id": "LOG-101", "source_type": "log", "source": "logs", "service": "payment-service", "finding": "QueuePool limit reached"}
    ]
    # Inconclusive hypothesis with 0 supporting evidence items
    state["selected_hypothesis"] = {
        "selected_root_cause": "Inconclusive: automated causal inference unavailable",
        "confidence": 0.20,
        "supporting_evidence_ids": [],
        "contradictory_evidence_ids": [],
        "reasoning_summary": "Telemetry collected but inference unavailable."
    }

    # Verify deterministic audit directly
    passed, category, explanation, _, _ = _deterministic_audit(state["selected_hypothesis"], state["collected_evidence"])
    assert not passed
    assert category == "INSUFFICIENT_EVIDENCE"
    assert "0 supporting items provided" in explanation or "inconclusive" in explanation

    # Now verify run_verification_agent
    with patch("app.agents.verification.call_groq_json") as mock_groq:
        state = run_verification_agent(state)
        # Layer 1 failure must be authoritative: no Layer 2 Groq call attempted!
        mock_groq.assert_not_called()

    v_res = state["verification_result"]
    assert not v_res["verified"]
    assert v_res["challenge_category"] == "INSUFFICIENT_EVIDENCE"


def test_verification_does_not_loop_when_rate_limited():
    """When LLM is rate-limited, verification must NOT loop repeatedly inside the investigation."""
    set_rate_limited("TPD limit 200000 reached")

    incident = {
        "id": "INC-001",
        "title": "Payment database connection timeouts",
        "description": "Timeouts",
        "service": "payment-service"
    }
    state = create_initial_state(incident, max_iterations=2)
    state["iteration_count"] = 0
    state["collected_evidence"] = []
    state["selected_hypothesis"] = {
        "selected_root_cause": "Inconclusive: automated causal inference unavailable",
        "confidence": 0.20,
        "supporting_evidence_ids": [],
        "contradictory_evidence_ids": [],
        "reasoning_summary": "Inference unavailable."
    }

    state = run_verification_agent(state)

    # Must NOT increment iteration_count or route to Supervisor when rate-limited
    assert state["iteration_count"] == 0
    assert state["investigation_status"] == "INSUFFICIENT_EVIDENCE"
    assert state["recommended_action"]["approval_status"] == "ESCALATED"
