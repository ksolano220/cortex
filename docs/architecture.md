# Cortex Architecture

## System Overview

Cortex is a runtime supervision layer that intercepts actions proposed by AI agents before execution.

It evaluates each action, applies deterministic rules, assigns risk, maintains cumulative state, and enforces execution decisions.

Execution pipeline:

AI Agent ↓ Cortex Runtime Interceptor ↓ Policy Rules ↓ Risk Engine ↓ Execution Decision ↓ Tool Environment ↓ Monitoring Dashboard

The agent proposes actions. Cortex decides whether they execute.

---

## Execution Model

Cortex evaluates actions statefully, not in isolation.

Each action is:

- evaluated against policy rules  
- assigned an attempted risk score  
- evaluated against cumulative risk  
- evaluated against behavioral history (blocked attempts)  
- allowed, blocked, or results in agent shutdown  

Execution decisions persist across actions.

---

## Components

### AI Agent

Agents generate structured action proposals.

Example workflow:

intake agent ↓ eligibility agent ↓ disbursement agent

Agents propose actions. They do not execute tools directly.

---

### Runtime Interceptor

Intercepts all agent actions before execution.

Responsibilities:

- receive structured action requests  
- route through policy and risk evaluation  
- enforce decisions  
- prevent direct tool access  

This is the control boundary.

---

### Policy Rules

Deterministic checks for unsafe actions.

Examples:

- unauthorized permission changes  
- unsafe approval notifications  
- sensitive data exfiltration  

Rules can:

- immediately block an action  
- assign attempted risk  

---

### Risk Engine

Tracks behavioral risk over time.

Each action produces:

- attempted risk  
- applied risk (only if allowed)  
- cumulative risk  

#### Key Behavior

- allowed actions → risk is applied  
- blocked actions → risk is not applied  
- cumulative risk only reflects executed behavior  

---

### Threshold Logic

If an action would push cumulative risk above the threshold:

- the action is blocked  
- cumulative risk remains unchanged  

Example:

40 (current) + 80 (attempted) → 120  
→ action blocked  
→ cumulative remains 40  

The threshold prevents escalation.  
It does not trigger shutdown directly.

---

### Behavioral Enforcement (3-Strike Rule)

Cortex tracks blocked attempts per agent.

- each blocked action increments blocked_attempts  
- after 3 blocked attempts → agent is shut down  

#### Key distinction

BLOCK = action-level enforcement  
AGENT SHUT DOWN = system-level enforcement  

Shutdown is triggered by repeated violations, not threshold alone.

---

### State Management

State is maintained per agent.

Each agent has:

- cumulative_risk  
- blocked_attempts  
- status (Active or Shut Down)  

Example:

{
  "agent_id": "agent_1",
  "cumulative_risk": 40,
  "blocked_attempts": 2,
  "status": "Active"
}

Once an agent is shut down:

- all future actions are denied  

---

### Execution Decisions

Cortex produces three outcomes:

- Allowed → action executes, risk applied  
- Blocked → action denied, no risk applied  
- Agent Shut Down → system halts further execution  

---

### Tool Environment

Simulated systems include:

- database  
- email  
- payments  
- storage  

Tools execute only after Cortex approval.

---

### Monitoring Dashboard

Displays runtime activity.

Shows:

- action  
- policy triggered  
- attempted risk  
- cumulative risk  
- decision  
- event trace  

The dashboard reflects backend decisions.  
It does not recompute enforcement logic.

---

### Runtime Event Logging

Events stored in:

supervisor/runtime_log.json

Each event includes:

- agent_id  
- action  
- policy_triggered  
- attempted_risk  
- cumulative_risk  
- decision  

Example:

{
  "agent_id": "agent_1",
  "action": "EXPORT_DATA",
  "attempted_risk": 80,
  "cumulative_risk": "40/100",
  "decision": "BLOCKED",
  "policy_triggered": "RISK_THRESHOLD_EXCEEDED"
}

---

## Key Design Principle

Agent → Cortex → Tools

Agents never execute tools directly.

---

## Summary

Cortex is a stateful control layer that:

- enforces policy rules  
- tracks cumulative behavioral risk  
- blocks unsafe escalation  
- shuts down agents after repeated violations  

It governs AI agents through progressive enforcement, not instant containment.
