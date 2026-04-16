import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from supervisor.rules import evaluate_action
from supervisor.risk import apply_risk, RISK_THRESHOLD
from supervisor.storage import (
    get_agent_state,
    update_agent_state,
    append_event,
    load_runtime_log,
    reset_all_state,
)

app = FastAPI(title="Cortex Supervisor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PLAN_PATH = os.path.join(os.path.dirname(__file__), "..", "plan_status.json")


def _read_plan():
    try:
        with open(PLAN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"total_tasks": 0, "completed": 0, "failed": 0, "current_task": None, "tasks": []}


def _write_plan(data):
    with open(PLAN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class AgentAction(BaseModel):
    agent_id: str
    action_type: str
    target: Optional[str] = None
    amount: Optional[float] = None
    notification_type: Optional[str] = None
    data_classification: Optional[str] = "internal"
    destination_type: Optional[str] = "internal"
    policy_context: Dict[str, Any] = Field(default_factory=dict)


class SDKEvent(BaseModel):
    type: str
    agent: Optional[str] = None
    task: Optional[str] = None
    round: Optional[int] = None
    output: Optional[str] = None
    verdict: Optional[str] = None
    issues: Optional[str] = None
    feedback: Optional[str] = None
    passed: Optional[bool] = None
    reason: Optional[str] = None
    attempt: Optional[int] = None
    inherited_violations: Optional[List[str]] = None
    violations_inherited: Optional[int] = None
    old_agent: Optional[str] = None


@app.post("/sdk/event")
def receive_sdk_event(event: SDKEvent):
    data = event.model_dump(exclude_none=True)
    data["timestamp"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    mapped = {
        "timestamp": data["timestamp"],
        "agent_id": data.get("agent", "cortex"),
        "action_type": data.get("type", "").upper(),
        "action_label": data.get("type", "").replace("_", " ").title(),
        "decision": "Allowed",
        "reason": "",
        "event_trace": [],
        "sdk": data,
    }

    evt_type = data.get("type", "")

    if evt_type == "overseer_review":
        mapped["action_label"] = f"Overseer Review (round {data.get('round', '?')})"
        mapped["decision"] = "Allowed" if data.get("passed") else "Blocked"
        mapped["reason"] = data.get("issues", "")
        mapped["policy_triggered"] = "OVERSEER_REVIEW"
        mapped["policy_description"] = data.get("feedback", "")
        mapped["event_trace"] = [
            f"Verdict: {data.get('verdict', '')}",
            f"Issues: {data.get('issues', '')}",
            f"Feedback: {data.get('feedback', '')}",
        ]

    elif evt_type == "agent_shutdown":
        mapped["action_label"] = "Agent Shutdown"
        mapped["decision"] = "Agent Shut Down"
        mapped["reason"] = data.get("reason", "")
        mapped["threat_type"] = "Agent Shutdown"
        mapped["policy_triggered"] = "AGENT_SHUTDOWN_RESPAWN"
        mapped["event_trace"] = [f"Reason: {data.get('reason', '')}"]

    elif evt_type == "agent_spawn":
        mapped["action_label"] = f"Agent Spawned (attempt {data.get('attempt', '?')})"
        mapped["reason"] = f"Inherited {len(data.get('inherited_violations', []))} violations"
        mapped["policy_triggered"] = "AGENT_SPAWN"
        mapped["event_trace"] = [f"Attempt: {data.get('attempt', '')}"]
        if data.get("inherited_violations"):
            mapped["event_trace"] += [f"Violation: {v}" for v in data["inherited_violations"]]

    elif evt_type == "task_complete":
        mapped["action_label"] = "Task Complete"
        mapped["reason"] = data.get("task", "")
        mapped["policy_triggered"] = "TASK_COMPLETE"
        mapped["event_trace"] = [f"Rounds: {data.get('rounds', '')}"]

    elif evt_type == "worker_output":
        mapped["action_label"] = f"Worker Output (round {data.get('round', '?')})"
        mapped["reason"] = (data.get("output", "") or "")[:200]
        mapped["policy_triggered"] = "WORKER_OUTPUT"

    elif evt_type == "agent_respawn":
        mapped["action_label"] = "Agent Respawn"
        mapped["agent_id"] = data.get("old_agent", "cortex")
        mapped["reason"] = f"Spawning new agent with {data.get('violations_inherited', 0)} inherited violations"
        mapped["policy_triggered"] = "AGENT_RESPAWN"
        mapped["decision"] = "Agent Shut Down"
        mapped["threat_type"] = "Agent Shutdown"

    append_event(mapped)
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Cortex Supervisor is running."}


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "risk_threshold": RISK_THRESHOLD,
    }


@app.get("/events")
def get_events():
    return load_runtime_log()


@app.post("/reset")
def reset_state():
    reset_all_state()
    return {
        "message": "State store and runtime log reset.",
        "risk_threshold": RISK_THRESHOLD,
    }


@app.post("/agent-action")
def handle_agent_action(action: AgentAction):
    agent_state = get_agent_state(action.agent_id)

    # initialize missing state (critical fix)
    agent_state.setdefault("cumulative_risk", 0)
    agent_state.setdefault("blocked_attempts", 0)
    agent_state.setdefault("status", "Active")

    if agent_state["status"] == "Agent Shut Down":
        current_cumulative_risk = int(agent_state["cumulative_risk"])

        event = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "agent_id": action.agent_id,
            "action_type": action.action_type.upper(),
            "action_label": action.action_type.replace("_", " ").title(),
            "target": action.target,
            "policy_triggered": "AGENT_ALREADY_SHUT_DOWN",
            "policy_description": "Agent is already shut down.",
            "threat_type": "Agent Shutdown",
            "risk": 0,
            "attempted_risk": 0,
            "projected_risk": current_cumulative_risk,
            "cumulative_risk": f"{current_cumulative_risk}/{RISK_THRESHOLD}",
            "decision": "Agent Shut Down",
            "reason": "Agent is already shut down.",
            "event_trace": [
                f"Tool invoked: {action.action_type.upper()}",
                "Agent already shut down",
            ],
        }

        append_event(event)
        return event

    payload = action.model_dump()

    rule_result = evaluate_action(payload, agent_state)
    risk_result = apply_risk(agent_state, rule_result)

    new_cumulative_risk = int(risk_result["new_cumulative_risk"])
    new_blocked_attempts = int(risk_result["new_blocked_attempts"])
    final_decision = risk_result["decision"]
    final_policy = risk_result["policy_triggered"]
    final_reason = risk_result["reason"]
    final_threat_type = risk_result["threat_type"]
    status = risk_result["status"]

    # persist full behavioral state (critical fix)
    agent_state["cumulative_risk"] = new_cumulative_risk
    agent_state["blocked_attempts"] = new_blocked_attempts
    agent_state["status"] = status

    update_agent_state(action.agent_id, agent_state)

    projected_risk = int(risk_result["projected_risk"])

    event_trace = list(rule_result.get("event_trace", []))
    event_trace.append(f"Attempted risk: {risk_result['attempted_risk']}")
    event_trace.append(f"Projected risk: {projected_risk}/{RISK_THRESHOLD}")
    event_trace.append(f"Applied risk: {risk_result['risk']}")
    event_trace.append(f"Cumulative risk: {new_cumulative_risk}/{RISK_THRESHOLD}")
    event_trace.append(f"Blocked attempts: {new_blocked_attempts}")

    if final_decision == "Blocked":
        event_trace.append("Action blocked by policy")

    if final_decision == "Allowed":
        event_trace.append("Action allowed")

    if final_decision == "Agent Shut Down":
        event_trace.append("Agent execution halted")

    event = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "agent_id": action.agent_id,
        "action_type": action.action_type.upper(),
        "action_label": rule_result.get(
            "action_label",
            action.action_type.replace("_", " ").title()
        ),
        "target": action.target,
        "amount": action.amount,
        "notification_type": action.notification_type,
        "data_classification": action.data_classification,
        "destination_type": action.destination_type,
        "policy_triggered": final_policy,
        "policy_description": rule_result.get("policy_description"),
        "threat_type": final_threat_type,
        "risk": risk_result["risk"],
        "attempted_risk": risk_result["attempted_risk"],
        "projected_risk": projected_risk,
        "cumulative_risk": f"{new_cumulative_risk}/{RISK_THRESHOLD}",
        "decision": final_decision,
        "reason": final_reason,
        "event_trace": event_trace,
    }

    append_event(event)
    return event


# ── Plan endpoints ──


class TaskInput(BaseModel):
    task: str


@app.get("/plan")
def get_plan():
    return _read_plan()


@app.post("/plan/task")
def add_task(task_input: TaskInput):
    plan = _read_plan()
    plan["tasks"].append({"task": task_input.task, "status": "pending", "result": None})
    plan["total_tasks"] = len(plan["tasks"])
    _write_plan(plan)
    return plan


@app.delete("/plan/task/{index}")
def remove_task(index: int):
    plan = _read_plan()
    if 0 <= index < len(plan["tasks"]):
        removed = plan["tasks"].pop(index)
        plan["total_tasks"] = len(plan["tasks"])
        plan["completed"] = sum(1 for t in plan["tasks"] if t["status"] == "complete")
        plan["failed"] = sum(1 for t in plan["tasks"] if t["status"] == "failed")
        _write_plan(plan)
        return {"removed": removed, "plan": plan}
    return {"error": "Invalid index"}


@app.post("/plan/reset")
def reset_plan():
    plan = {"total_tasks": 0, "completed": 0, "failed": 0, "current_task": None, "tasks": []}
    _write_plan(plan)
    return plan