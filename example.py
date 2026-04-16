"""
Cortex — approve a plan and walk away.

Claude executes. GPT supervises. Agents self-heal.
Check plan_status.json from your phone.
"""

from cortex import Cortex
from cortex.adapters.anthropic import AnthropicAdapter
from cortex.adapters.openai import OpenAIAdapter

worker = AnthropicAdapter(model="claude-sonnet-4-20250514")
overseer = OpenAIAdapter(model="gpt-4o")

cortex = Cortex(
    worker=worker,
    overseer=overseer,
    rules_path="cortex.yaml",
)

# Define your plan
plan = [
    "Write a Python function that validates email addresses with proper regex",
    "Write unit tests for the email validator covering edge cases",
    "Write a Flask endpoint that accepts POST /validate with a JSON body",
]

# Approve and walk away
result = cortex.run_plan(
    tasks=plan,
    max_respawns_per_task=3,
    status_path="plan_status.json",  # poll this from your phone
)

# Summary
print(f"\nPlan complete.")
print(f"Tasks passed: {result['plan']['completed']}/{result['plan']['total_tasks']}")
print(f"Tasks failed: {result['plan']['failed']}")
print(f"Agent generations: {len(result['memory']['generations']) + 1}")

if result["memory"]["violations"]:
    print(f"\nSelf-healed from {len(result['memory']['violations'])} shutdowns:")
    for v in result["memory"]["violations"]:
        print(f"  - {v}")
