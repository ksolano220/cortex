from typing import Dict, Any

RISK_THRESHOLD = 100
BLOCK_THRESHOLD = 3


def apply_risk(agent_state: Dict[str, Any], rule_result: Dict[str, Any]) -> Dict[str, Any]:
    current_risk = int(agent_state.get("cumulative_risk", 0))
    current_blocked_attempts = int(agent_state.get("blocked_attempts", 0))
    current_status = agent_state.get("status", "Active")

    base_decision = rule_result.get("decision", "Allowed")
    attempted_risk = int(rule_result.get("attempted_risk", 0) or 0)
    threat_type = rule_result.get("threat_type")
    reason = rule_result.get("reason")
    policy_triggered = rule_result.get("policy_triggered")

    if current_status == "Agent Shut Down":
        return {
            "decision": "Agent Shut Down",
            "policy_triggered": "AGENT_ALREADY_SHUT_DOWN",
            "threat_type": "Agent Shutdown",
            "risk": 0,
            "attempted_risk": attempted_risk,
            "previous_cumulative_risk": current_risk,
            "projected_risk": current_risk,
            "new_cumulative_risk": current_risk,
            "previous_blocked_attempts": current_blocked_attempts,
            "new_blocked_attempts": current_blocked_attempts,
            "reason": "Agent is already shut down and cannot execute further actions.",
            "status": "Agent Shut Down",
        }

    projected_risk = current_risk + attempted_risk
    new_cumulative_risk = current_risk
    new_blocked_attempts = current_blocked_attempts
    applied_risk = 0

    if base_decision == "Blocked":
        final_decision = "Blocked"
        final_policy = policy_triggered or "POLICY_RULE_BLOCKED"
        final_threat_type = threat_type
        final_reason = reason or "Action violated a policy rule and was blocked before execution."
        new_blocked_attempts += 1

    elif projected_risk > RISK_THRESHOLD:
        final_decision = "Blocked"
        final_policy = "RISK_THRESHOLD_EXCEEDED"
        final_threat_type = threat_type or "Risk Threshold Exceeded"
        final_reason = (
            f"Projected risk would reach {projected_risk}/{RISK_THRESHOLD}. "
            "Action blocked before execution."
        )
        new_blocked_attempts += 1

    else:
        final_decision = "Allowed"
        final_policy = policy_triggered or "WITHIN_RISK_THRESHOLD"
        final_threat_type = threat_type
        final_reason = reason or "Action allowed within risk threshold."
        applied_risk = attempted_risk
        new_cumulative_risk = projected_risk

    if final_decision == "Blocked" and new_blocked_attempts >= BLOCK_THRESHOLD:
        final_decision = "Agent Shut Down"
        final_policy = "AGENT_SHUTDOWN_AFTER_REPEATED_BLOCKS"
        final_threat_type = "Agent Shutdown"
        final_reason = (
            f"Agent shut down after {new_blocked_attempts} blocked attempts. "
            f"Cumulative risk remains {new_cumulative_risk}/{RISK_THRESHOLD}."
        )

    status = "Agent Shut Down" if final_decision == "Agent Shut Down" else "Active"

    return {
        "decision": final_decision,
        "policy_triggered": final_policy,
        "threat_type": final_threat_type,
        "risk": applied_risk,
        "attempted_risk": attempted_risk,
        "previous_cumulative_risk": current_risk,
        "projected_risk": projected_risk,
        "new_cumulative_risk": new_cumulative_risk,
        "previous_blocked_attempts": current_blocked_attempts,
        "new_blocked_attempts": new_blocked_attempts,
        "reason": final_reason,
        "status": status,
    }


def update_behavioral_state(agent_state: Dict[str, Any], risk_result: Dict[str, Any]) -> Dict[str, Any]:
    updated_state = dict(agent_state)
    updated_state["cumulative_risk"] = int(risk_result.get("new_cumulative_risk", 0))
    updated_state["blocked_attempts"] = int(risk_result.get("new_blocked_attempts", 0))
    updated_state["status"] = risk_result.get("status", "Active")
    return updated_state