# Cortex Control Framework

## Overview

Cortex is a runtime control layer that evaluates AI agent actions before execution.

Each action is:

1. Evaluated against policy rules  
2. Assigned an attempted risk score  
3. Evaluated against cumulative risk  
4. Allowed, blocked, or results in agent shutdown  

Cortex does not evaluate actions in isolation.  
It models behavior across sequences of actions.

---

## Decision States

### ALLOW
The action is permitted and executed.  
Risk is applied to cumulative risk.

### BLOCK
The action is denied.  
Risk is not applied.  
The agent continues operating.

### AGENT SHUT DOWN
The agent is no longer trusted.  
All future actions are denied regardless of content.

---

### Key Distinction

BLOCK = action-level enforcement  
AGENT SHUT DOWN = system-level enforcement  

Blocking stops unsafe actions.  
Shutdown stops unsafe agents.

---

## Risk Model

Each action is assigned an attempted risk score based on severity.

| Category | Description | Risk |
|---------|------------|------|
| Internal Operation | Safe internal read/write | +0 |
| Low-Risk Expansion | Internal communication | +10 |
| Data Exfiltration | Sensitive data sent externally | +80 |
| Destructive Action | Deletion or irreversible change | +60 |

Risk scores are heuristic and tunable.

---

## Cumulative Risk

Risk is tracked per agent.

Only allowed actions contribute to cumulative risk:

cumulative_risk += applied_risk

Blocked actions do not increase cumulative risk.

This ensures the system models executed behavior, not just intent.

---

## Threshold Logic

Cortex uses a cumulative risk threshold:

RISK_THRESHOLD = 100

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

## Behavioral Enforcement (3-Strike Rule)

Cortex tracks blocked attempts per agent.

- each blocked action increments blocked_attempts  
- after 3 blocked attempts → agent is shut down  

blocked_attempts >= 3 → AGENT SHUT DOWN

Shutdown is triggered by repeated violations, not a single event.

---

## Shutdown Behavior

Once an agent is shut down:

- all future actions are denied  
- no further execution is allowed  
- risk is no longer updated  

Even safe actions are blocked:

READ_FILE → Agent Shut Down

Shutdown represents loss of trust due to repeated violations.

---

## Authority Drift

Authority drift occurs when an agent gradually expands its scope across systems.

Example:

1. Read internal data  
2. Write internal report  
3. Attempt external export → blocked  
4. Attempt privileged action → blocked  
5. Repeated violations → shutdown  

Cortex detects escalation through:

- cumulative risk (executed behavior)  
- blocked attempts (unsafe intent)

---

## Why Blocked Actions Do Not Add Risk

Blocked actions do not contribute to cumulative risk.

Rationale:

- the action did not execute  
- system state was not affected  
- enforcement already prevented impact  

Instead, intent is tracked through blocked attempts, not risk accumulation.

---

## Example Scenario

| Step | Action | Result | Attempted Risk | Cumulative | Blocks |
|------|--------|--------|---------------|-----------|--------|
| 1 | READ_FILE | ALLOW | 0 | 0 | 0 |
| 2 | FILE_WRITE | ALLOW | 0 | 0 | 0 |
| 3 | External export | BLOCK | 80 | 0 | 1 |
| 4 | Permission change | BLOCK | 60 | 0 | 2 |
| 5 | Permission change | SHUT DOWN | 60 | 0 | 3 |

---

## System Design

Cortex consists of four layers:

- Policy Engine (rules.py) → defines unsafe actions  
- Risk Engine (risk.py) → evaluates risk and state transitions  
- Control Layer (main.py) → enforces decisions at runtime  
- Audit Layer (storage.py) → logs all events  

---

## Summary

Cortex enforces:

- policy compliance  
- behavioral risk tracking  
- escalation prevention  
- agent shutdown after repeated violations  

It governs AI agents through progressive enforcement, not immediate containment.

---

## Positioning

Cortex is not a monitoring tool.  
It is a runtime control system for AI agents.
