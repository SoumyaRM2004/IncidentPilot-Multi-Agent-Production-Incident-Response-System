import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from app.graph.state import InvestigationState, InvestigationPlanModel, ALLOWED_AGENTS
from app.agents.llm import (
    call_groq_json,
    get_groq_client,
    is_rate_limited,
    get_rate_limit_reason,
    LLMRateLimitError
)

logger = logging.getLogger(__name__)


def run_supervisor_agent(state: InvestigationState) -> InvestigationState:
    """Supervisor Agent: Evaluates incident context, creates validated investigation plan,

    and adapts upon structured verification feedback without keyword parsing.
    """
    incident = state["incident"]
    service = incident.get("service", "unknown")
    title = incident.get("title", "")
    description = incident.get("description", "")
    iteration = state.get("iteration_count", 0)

    # Reset executed specialists for this iteration round
    state["executed_specialists"] = []

    history_entry = {
        "agent_key": "supervisor",
        "agent": "Supervisor Agent",
        "status": "EXECUTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
    }

    # Adaptive re-investigation using STRUCTURED verification feedback
    if iteration > 0 and state.get("verification_result"):
        v_res = state["verification_result"]
        category = v_res.get("challenge_category", "UNKNOWN")
        requested_agents = v_res.get("requested_agent_types") or []
        missing_evidence = v_res.get("missing_evidence_types") or []
        suggested_window = v_res.get("suggested_time_window") or 120

        # Map missing evidence types to agent names
        evidence_to_agent_map = {
            "log": "logs",
            "logs": "logs",
            "deployment": "deployments",
            "deployments": "deployments",
            "metric": "metrics",
            "metrics": "metrics",
            "runbook": "runbook"
        }

        selected_agents: List[str] = []

        if requested_agents:
            selected_agents = [a for a in requested_agents if a in ALLOWED_AGENTS]
        elif missing_evidence:
            for met in missing_evidence:
                mapped = evidence_to_agent_map.get(met.lower())
                if mapped and mapped in ALLOWED_AGENTS and mapped not in selected_agents:
                    selected_agents.append(mapped)

        if not selected_agents:
            if category in ("LOW_SOURCE_DIVERSITY", "INSUFFICIENT_EVIDENCE"):
                # Find which allowed agents have not yet contributed evidence
                existing_sources = {e.get("source_type") for e in state.get("collected_evidence", [])}
                unrepresented = []
                if "log" not in existing_sources:
                    unrepresented.append("logs")
                if "metric" not in existing_sources:
                    unrepresented.append("metrics")
                if "deployment" not in existing_sources:
                    unrepresented.append("deployments")
                selected_agents = unrepresented if unrepresented else ["logs", "metrics", "deployments"]
            else:
                selected_agents = ["logs", "metrics", "deployments"]

        # Validate through Pydantic model
        plan_model = InvestigationPlanModel(
            focus=f"Targeted re-investigation ({service}) addressing {category}",
            required_agents=selected_agents,
            strategy=f"Structured re-planning for challenge category '{category}'. Expanded window to {suggested_window}m.",
            window_minutes=suggested_window,
            metric_names=["db_connection_pool_utilization", "memory_utilization_percent", "http_error_rate_percent", "p99_latency_ms"] if "metrics" in selected_agents else None
        )
        plan = plan_model.model_dump()

        history_entry["action"] = f"Created adaptive re-investigation plan (Iteration {iteration})"
        history_entry["findings"] = (
            f"Structured challenge feedback '{category}'. "
            f"Targeting agents: {', '.join(plan['required_agents'])} with window {suggested_window}m."
        )

    else:
        # Initial planning phase
        client = get_groq_client()
        plan_dict = None

        if client:
            try:
                system_prompt = (
                    "You are the Lead SRE Investigation Supervisor in IncidentPilot.\n"
                    "Analyze the incident symptoms and produce a focused investigation plan.\n"
                    "Select specialist agents strictly from: ['logs', 'deployments', 'metrics', 'runbook'].\n"
                    "Output a JSON object matching this schema:\n"
                    "{\n"
                    '  "focus": "Primary diagnostic focus",\n'
                    '  "strategy": "Diagnostic strategy and objective",\n'
                    '  "required_agents": ["logs", "metrics"],\n'
                    '  "log_query": null,\n'
                    '  "metric_names": null,\n'
                    '  "window_minutes": 60\n'
                    "}\n"
                    "Do NOT nest the response inside an outer wrapper key."
                )
                user_prompt = (
                    f"Incident Title: {title}\n"
                    f"Affected Service: {service}\n"
                    f"Description: {description}"
                )
                plan_dict = call_groq_json(system_prompt, user_prompt, schema_model=InvestigationPlanModel)
            except LLMRateLimitError as rle:
                logger.warning(f"Supervisor planning skipped due to LLM rate limit: {rle}. Using conservative fallback.")
                plan_dict = None
            except Exception as e:
                logger.warning(f"Supervisor LLM planning failed: {e}. Using conservative fallback.")
                plan_dict = None

        if not plan_dict:
            plan_dict = _create_initial_plan(service, title, description)

        # Validate and sanitize through Pydantic
        plan_model = InvestigationPlanModel.model_validate(plan_dict)
        plan = plan_model.model_dump()

        if not plan["required_agents"]:
            plan["required_agents"] = ["logs", "metrics", "runbook"]

        history_entry["action"] = "Formulated initial multi-agent investigation plan"
        rate_note = f" [LLM rate-limited: {get_rate_limit_reason()}]" if is_rate_limited() else ""
        history_entry["findings"] = f"Strategy: {plan['strategy']}. Delegating to: {', '.join(plan['required_agents'])}.{rate_note}"

    state["investigation_plan"] = plan
    state["current_agent"] = "supervisor"
    state["agent_history"].append(history_entry)
    return state


def _create_initial_plan(service: str, title: str, description: str) -> Dict[str, Any]:
    """Conservative deterministic fallback plan when planning LLM is unavailable.

    Default plan investigates telemetry (logs, metrics) and operational context (runbook).
    Deployments are included only when there is an explicit signal in incident metadata
    that deployment or release context is relevant.
    """
    text = f"{title} {description}".lower()
    selected_agents = ["logs", "metrics", "runbook"]

    # Deployment analysis is added only when explicit release/deployment context is present
    deployment_signals = [
        "deployment", "deployed", "release", "released",
        "rollout", "rolled out", "version", "commit"
    ]
    if any(sig in text for sig in deployment_signals):
        selected_agents.append("deployments")

    return {
        "focus": f"Investigate service anomalies and degradation on {service}",
        "required_agents": selected_agents,
        "strategy": (
            "When the planning LLM is unavailable, IncidentPilot uses a conservative fallback plan "
            "prioritizing logs, metrics, and operational runbook guidance; deployment analysis is "
            "added only when explicit release/deployment context is present."
        ),
        "window_minutes": 60
    }
