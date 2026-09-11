from datetime import datetime, timezone
from typing import Dict, Any, List
from app.graph.state import InvestigationState, InvestigationPlanModel
from app.agents.llm import call_groq_json, get_groq_client
from app.config import settings

ALLOWED_AGENTS = {"logs", "deployments", "metrics", "runbook"}


def run_supervisor_agent(state: InvestigationState) -> InvestigationState:
    """Supervisor Agent: Evaluates incident context, creates structured investigation plan, and adapts upon verification challenge."""
    incident = state["incident"]
    service = incident.get("service", "unknown")
    title = incident.get("title", "")
    description = incident.get("description", "")
    iteration = state.get("iteration_count", 0)

    history_entry = {
        "agent": "Supervisor Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
    }

    # Adaptive re-investigation if triggered by verification challenge
    if iteration > 0 and state.get("verification_result"):
        v_res = state["verification_result"]
        explanation = v_res.get("explanation", "").lower()

        # Adapt plan based on specific verification critique
        selected_agents = ["logs", "metrics", "runbook"]
        window_minutes = 120  # Expand temporal window
        metric_names = None
        log_query = None

        if "deployment" in explanation or "release" in explanation:
            selected_agents = ["deployments", "logs"]
            window_minutes = 180
        elif "metric" in explanation or "saturation" in explanation:
            selected_agents = ["metrics", "logs"]
            metric_names = ["db_connection_pool_utilization", "memory_utilization_percent", "http_error_rate_percent", "p99_latency_ms"]
        elif "insufficient" in explanation:
            selected_agents = ["logs", "deployments", "metrics", "runbook"]
            window_minutes = 180

        plan = {
            "focus": f"Targeted re-investigation ({service}) addressing verification challenge: {v_res.get('explanation')}",
            "required_agents": [a for a in selected_agents if a in ALLOWED_AGENTS],
            "strategy": f"Expand time window to {window_minutes}m and query deeper telemetry to resolve verification gaps.",
            "log_query": log_query,
            "metric_names": metric_names,
            "window_minutes": window_minutes
        }

        history_entry["action"] = f"Created adaptive re-investigation plan (Iteration {iteration})"
        history_entry["findings"] = f"Targeting agents: {', '.join(plan['required_agents'])} with window {window_minutes}m based on challenge: '{v_res.get('explanation')}'."

    else:
        # Initial planning phase
        client = get_groq_client()
        plan_dict = None

        if client:
            try:
                system_prompt = (
                    "You are the Lead SRE Investigation Supervisor in IncidentPilot. "
                    "Analyze the incident symptoms and produce a focused investigation plan. "
                    "Select specialist agents strictly from: ['logs', 'deployments', 'metrics', 'runbook']. "
                    "Provide specific log query keywords and metric names to inspect."
                )
                user_prompt = (
                    f"Incident Title: {title}\n"
                    f"Affected Service: {service}\n"
                    f"Description: {description}"
                )
                plan_dict = call_groq_json(system_prompt, user_prompt, schema_model=InvestigationPlanModel)
            except Exception:
                plan_dict = None

        if not plan_dict:
            # Deterministic, symptom-aware initial plan without benchmark keyword hardcoding
            plan_dict = _create_initial_plan(service, title, description)

        # Enforce agent allowlist validation
        valid_agents = [a for a in plan_dict.get("required_agents", []) if a in ALLOWED_AGENTS]
        if not valid_agents:
            valid_agents = ["logs", "deployments", "metrics", "runbook"]

        plan = {
            "focus": plan_dict.get("focus", f"Triage incident on {service}"),
            "required_agents": valid_agents,
            "strategy": plan_dict.get("strategy", "Correlate error logs, recent deployments, metrics, and runbooks."),
            "log_query": plan_dict.get("log_query"),
            "metric_names": plan_dict.get("metric_names"),
            "window_minutes": plan_dict.get("window_minutes", 60)
        }

        history_entry["action"] = "Formulated initial multi-agent investigation plan"
        history_entry["findings"] = f"Strategy: {plan['strategy']}. Delegating to: {', '.join(plan['required_agents'])}."

    state["investigation_plan"] = plan
    state["current_agent"] = "supervisor"
    state["agent_history"].append(history_entry)
    return state


def _create_initial_plan(service: str, title: str, description: str) -> Dict[str, Any]:
    """Generates a structured investigation plan tailored to incident symptoms."""
    text = f"{title} {description}".lower()
    selected_agents = ["logs", "metrics", "runbook"]

    # Include deployments if release, update, deploy, or change is hinted
    if any(k in text for k in ["deploy", "release", "version", "update", "rolled", "commit", "crash", "outage", "spike"]):
        selected_agents.append("deployments")

    return {
        "focus": f"Investigate service anomalies and degradation on {service}",
        "required_agents": selected_agents,
        "strategy": f"Retrieve error logs, telemetry metrics, deployment correlation, and runbooks for {service}.",
        "window_minutes": 60
    }
