# Cortex

Two AI models check each other's work so you don't have to.

Cortex is a Python SDK that runs one AI model as the **worker** and another as the **overseer**. The worker writes code. The overseer stress-tests it. They debate until the output passes your rules. If an agent fails, Cortex shuts it down and spawns a new one with memory of what went wrong.

You define the plan. You approve it. You set the rules. Then you walk away. Cortex handles the execution — you handle the decisions that matter.

---

## Limitations

While Cortex significantly reduces the need for human oversight, it has important limitations. Complex business logic, regulatory compliance decisions, and context requiring deep domain expertise still need human judgment. The models may miss subtle requirements or make assumptions about user intent. Edge cases in specialized domains might require manual intervention. Always review outputs for critical applications and consider Cortex as a powerful assistant, not a replacement for human decision-making.

---

## Error Handling

Cortex includes comprehensive error handling across multiple layers:

- **Model failures**: Automatic retries with exponential backoff
- **API timeouts**: Graceful degradation and fallback strategies  
- **Rule violations**: Immediate task rejection with detailed feedback
- **Agent corruption**: Complete agent termination and fresh spawning
- **Plan interruptions**: State preservation and recovery mechanisms
- **Network issues**: Queue-based task management with persistence

All errors are logged with full context. Failed agents are replaced automatically with corrective memory to prevent recurring issues.

---

## Performance Trade-offs

The dual-model architecture prioritizes reliability over speed:

**Processing Time**: 2-3x slower than single-model systems due to overseer review and potential debate rounds. Simple tasks may feel over-engineered.

**Cost**: Higher API costs from running two models per task. Budget 1.5-2x typical usage costs.

**Latency**: Additional network round-trips for model communication add 500ms-2s per interaction.

**Accuracy**: Significantly fewer errors and higher-quality outputs offset the performance costs for production use cases.

Consider single-model solutions for simple, non-critical tasks where speed matters more than accuracy.

---

## Real-world Use Cases

**Software Development**
- Automated code reviews and refactoring
- Test generation with comprehensive coverage
- API documentation that stays current with code changes
- Legacy code modernization with safety checks

**DevOps & Infrastructure**  
- CI/CD pipeline generation and maintenance
- Infrastructure as code with security validation
- Automated deployment scripts with rollback safety
- Configuration management across environments

**Content & Documentation**
- Technical documentation that maintains accuracy
- Code comment generation and maintenance  
- Architecture decision records with peer review
- API specification generation from existing code

**Research & Analysis**
- Data pipeline validation and testing
- Automated code quality assessments
- Security vulnerability scanning and remediation
- Performance optimization with benchmarking

---

## How it works

```
You: "Build auth, write tests, deploy to staging"
     ↓ approve
Claude (worker): writes the code
GPT (overseer): "no input validation, XSS risk"
Claude: fixes it
GPT: "PASS"
     ↓ next task

Agent fails 3 times? Cortex kills it.
Spawns a new agent with memory: "don't do what the last one did."
Plan keeps moving. You're at the gym.
```

---

## Quick Start

```bash
pip install -r requirements.txt
```

Start the dashboard:

```bash
uvicorn supervisor.main:app --reload --port 8000
streamlit run dashboard/app.py
```

Open http://localhost:8501. Create an account. The dashboard walks you through adding your API keys — you'll need one from [Anthropic](https://console.anthropic.com) and one from [OpenAI](https://platform.openai.com). Keys are stored locally on your machine and never leave it.

Each user gets their own private workspace — tasks, rules, uploads, and results are isolated per account.

---

## Usage

### Single Task

```python
from cortex import Cortex
from cortex.adapters.anthropic import AnthropicAdapter
from cortex.adapters.openai import OpenAIAdapter

cortex = Cortex(
    worker=AnthropicAdapter(model="claude-sonnet-4-20250514"),
    overseer=OpenAIAdapter(model="gpt-4o"),
    rules_path="cortex.yaml",
)

result = cortex.run("Write a function that validates email addresses")
print(result["output"])
```

### Full Plan

```python
result = cortex.run_plan(
    tasks=[
        "Build auth flow with JWT tokens",
        "Write unit tests for auth",
        "Deploy to staging",
    ],
    status_path="plan_status.json",
)
```

`plan_status.json` updates in real time. Open it on your phone.

---

## Rules

Define your rules in `cortex.yaml`. The overseer enforces them.

```yaml
rules:
  - "never add features that weren't explicitly requested"
  - "prefer the simplest solution"
  - "flag any security vulnerability before shipping"
  - "keep responses under 50 lines unless the task requires more"

risk_threshold: 100
max_blocked_attempts: 3
max_rounds: 3
```

These are your rules. The overseer's job is to make sure the worker follows them. Every time.

---

## Self-healing Agents

Other systems shut down agents permanently. Cortex doesn't.

When an agent fails, Cortex:

1. Records what went wrong
2. Shuts down the agent
3. Spawns a new one
4. Injects memory: "v1 was killed for attempting external data export. Don't repeat this."
5. The new agent continues the plan

No human intervention. The plan keeps moving.

---

## Vault

API keys are stored at `~/.cortex/vault.json` with `600` permissions. They never enter git, logs, or conversation.

```bash
python -m cortex vault set ANTHROPIC_API_KEY
python -m cortex vault list
python -m cortex vault delete OLD_KEY
```

Adapters check the vault automatically. No `.env` files needed.

---

## Dashboard

Real-time monitoring at `http://localhost:8501`.

```bash
uvicorn supervisor.main:app --reload --port 8000
streamlit run dashboard/app.py
```

Shows:

- **Plan progress** — which tasks are done, which are running, which are next
- **Add tasks** — add to the plan from the dashboard (or your phone)
- **Event feed** — every action, decision, and trace
- **Agent status** — risk, blocked attempts, self-heal history

Mobile-friendly. Single column. Check between sets.

---

## Architecture

```
cortex/
  engine/core.py     — dual-model loop + self-healing + plan runner
  engine/rules.py    — YAML rule parser
  adapters/          — model adapters (Anthropic, OpenAI)
  vault.py           — secure local key storage
  cli.py             — vault management CLI

supervisor/          — runtime policy engine (from Sentra)
  main.py            — FastAPI endpoints
  risk.py            — risk scoring + threshold logic
  rules.py           — deterministic policy rules
  storage.py         — state + audit logs

dashboard/app.py     — Streamlit monitoring UI
cortex.yaml          — your rules
```

---

## Why Two Models

One model checking itself has blind spots. Two different architectures catch each other's weaknesses.

Claude writes clean code but sometimes overcomplicates. GPT catches that.
GPT sometimes misses edge cases. Claude catches that.

Your rules guide what they focus on. The debate is the quality gate.

---

## What Makes This Different

| | Cortex | Guardrails AI | CrewAI |
|---|---|---|---|
| Cross-model adversarial review | Yes | No | No |
| User-defined rules | YAML | Python validators | No |
| Self-healing agents | Yes | No | No |
| Plan execution | Yes | No | Yes |
| Mobile monitoring | Yes | No | No |

---

## License

MIT