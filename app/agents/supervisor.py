from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import InvestigationState
from app.agents.llm import call_groq_json, get_groq_client


def run_supervisor_agent(state: InvestigationState) -> InvestigationState:
    """Supervisor Agent: Creates investigation plan and coordinates specialized agents."""
    incident = state["incident"]
    service = incident.get("service", "unknown")
    title = incident.get("title", "")
    description = incident.get("description", "")
    iteration = state.get("iteration_count", 0)

    history_entry = {
        "agent": "Supervisor Agent",
        "timestamp": datetime.utcnow().isoformat(),
        "iteration": iteration,
    }

    # If this is a re-investigation loop triggered by verification failure
    if iteration > 0 and state.get("verification_result"):
        v_res = state["verification_result"]
        plan = {
            "focus": f"Targeted re-investigation for {service} after verification challenge: {v_res.get('explanation', '')}",
            "required_agents": ["logs", "metrics", "runbook"],
            "strategy": "Expand query parameters, inspect metric trends, and search for alternative operational root causes.",
            "status": "RE_INVESTIGATING"
        }
        history_entry["action"] = "Formulated re-investigation plan addressing verification gaps."
        history_entry["findings"] = plan["focus"]
    else:
        # Initial planning: Attempt Groq inference if available, otherwise use deterministic domain logic
        client = get_groq_client()
        if client:
            try:
                system_prompt = (
                    "You are the IncidentPilot Lead Investigation Supervisor. Given a production incident, "
                    "produce a concise investigation plan identifying required agent investigations "
                    "(logs, deployments, metrics, runbook) and priority diagnostic objectives."
                )
                user_prompt = f"Incident Title: {title}\nService: {service}\nDescription: {description}"
                llm_plan = call_groq_json(system_prompt, user_prompt)
                plan = {
                    "focus": llm_plan.get("focus", f"Comprehensive triage of {service}"),
                    "required_agents": llm_plan.get("required_agents", ["logs", "deployments", "metrics", "runbook"]),
                    "strategy": llm_plan.get("strategy", "Gather log errors, deployment timestamps, metric thresholds, and runbooks."),
                    "status": "PLANNED"
                }
            except Exception:
                plan = _default_plan(service, title)
        else:
            plan = _default_plan(service, title)

        history_entry["action"] = "Created initial multi-agent investigation plan."
        history_entry["findings"] = f"Strategy: {plan['strategy']}. Delegating to agents: {', '.join(plan['required_agents'])}."

    state["investigation_plan"] = plan
    state["current_agent"] = "supervisor"
    state["agent_history"].append(history_entry)
    return state


def _default_plan(service: str, title: str) -> Dict[str, Any]:
    return {
        "focus": f"Triage incident on {service}: {title}",
        "required_agents": ["logs", "deployments", "metrics", "runbook"],
        "strategy": f"Correlate {service} error logs, recent deployments, timeseries metrics, and operational runbooks.",
        "status": "PLANNED"
    }
