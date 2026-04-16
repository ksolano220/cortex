"""
Cortex Daemon — runs your approved plan in the background.

Usage:
    python -m cortex start     # start the daemon
    python -m cortex stop      # stop it
    python -m cortex status    # check what it's doing
"""

import json
import os
import re
import sys
import signal
import time
from pathlib import Path
from datetime import datetime

from cortex.vault import Vault
from cortex.engine.core import Cortex
from cortex.engine.rules import RuleSet
from cortex.adapters.anthropic import AnthropicAdapter
from cortex.adapters.openai import OpenAIAdapter

PROJECT_DIR = Path.home() / "cortex"
PLAN_PATH = PROJECT_DIR / "plan_status.json"
RULES_PATH = PROJECT_DIR / "cortex.yaml"
PID_PATH = Path.home() / ".cortex" / "daemon.pid"
LOG_PATH = Path.home() / ".cortex" / "daemon.log"


def _log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _notify(msg):
    """Send a desktop notification. Works on macOS, falls back to log."""
    _log(f"NOTIFICATION: {msg}")
    try:
        import subprocess
        import platform
        if platform.system() == "Darwin":
            subprocess.run([
                "osascript", "-e",
                f'display notification "{msg}" with title "Cortex"'
            ], timeout=5)
        elif platform.system() == "Linux":
            subprocess.run(["notify-send", "Cortex", msg], timeout=5)
    except Exception:
        pass


def _read_plan():
    if not PLAN_PATH.exists():
        return None
    with open(PLAN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_plan(plan):
    with open(PLAN_PATH, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)


def _save_pid():
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))


def _clear_pid():
    if PID_PATH.exists():
        PID_PATH.unlink()


def _get_pid():
    if not PID_PATH.exists():
        return None
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, 0)  # check if process exists
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        _clear_pid()
        return None


def run_daemon():
    """Main daemon loop — execute the approved plan."""
    _save_pid()
    _log("Cortex daemon started")

    def shutdown(sig, frame):
        _log("Cortex daemon stopped")
        _clear_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Load keys
    Vault().load_into_env()

    # Check for API keys
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _log("ERROR: No ANTHROPIC_API_KEY in vault")
        _clear_pid()
        return
    if not os.environ.get("OPENAI_API_KEY"):
        _log("ERROR: No OPENAI_API_KEY in vault")
        _clear_pid()
        return

    # Load rules
    if RULES_PATH.exists():
        rules = RuleSet.from_file(str(RULES_PATH))
        _log(f"Loaded {len(rules.rules)} rules from cortex.yaml")
    else:
        rules = RuleSet()
        _log("No cortex.yaml found, using defaults")

    # Set up models
    worker = AnthropicAdapter(model="claude-sonnet-4-20250514")
    overseer = OpenAIAdapter(model="gpt-4o")

    _log(f"Worker: {worker.provider_name()}/{worker.model_name()}")
    _log(f"Overseer: {overseer.provider_name()}/{overseer.model_name()}")

    # Read plan
    plan = _read_plan()
    if not plan or not plan.get("tasks"):
        _log("No plan found. Waiting for tasks...")
        # Poll for a plan
        while True:
            time.sleep(5)
            plan = _read_plan()
            if plan and plan.get("tasks"):
                pending = [t for t in plan["tasks"] if t.get("status") == "pending"]
                if pending:
                    _log(f"Plan found with {len(pending)} pending tasks")
                    break

    # Execute pending tasks
    cortex = Cortex(
        worker=worker,
        overseer=overseer,
        rules=rules,
    )

    tasks = plan.get("tasks", [])
    total = len(tasks)

    for i, task_entry in enumerate(tasks):
        if task_entry.get("status") in ("complete", "failed"):
            _log(f"Skipping task {i+1}/{total} (already {task_entry['status']})")
            continue

        task_text = task_entry.get("task", "")

        # Read any referenced files and inject content
        file_refs = re.findall(r'uploads/[\w\-\.]+', task_text)
        for ref in file_refs:
            file_path = PROJECT_DIR / ref
            if file_path.exists():
                try:
                    if file_path.suffix.lower() == ".pdf":
                        from PyPDF2 import PdfReader
                        reader = PdfReader(str(file_path))
                        text = "\n".join(page.extract_text() or "" for page in reader.pages)
                        task_text += f"\n\n--- Content of {ref} ---\n{text}\n--- End of file ---"
                        _log(f"Read PDF: {ref} ({len(text)} chars)")
                    else:
                        text = file_path.read_text(encoding="utf-8", errors="ignore")
                        task_text += f"\n\n--- Content of {ref} ---\n{text}\n--- End of file ---"
                        _log(f"Read file: {ref} ({len(text)} chars)")
                except Exception as e:
                    _log(f"Failed to read {ref}: {e}")

        # Fetch any URLs mentioned in the task
        from cortex.web import extract_urls, fetch_url
        urls = extract_urls(task_text)
        for url in urls[:5]:  # max 5 URLs per task
            try:
                content = fetch_url(url)
                if content and not content.startswith("[Error"):
                    task_text += f"\n\n--- Content from {url} ---\n{content[:3000]}\n--- End ---"
                    _log(f"Fetched URL: {url} ({len(content)} chars)")
                else:
                    _log(f"Failed to fetch: {url}")
            except Exception as e:
                _log(f"Error fetching {url}: {e}")

        _log(f"Starting task {i+1}/{total}: {task_text[:80]}")

        plan["tasks"][i]["status"] = "in_progress"
        plan["current_task"] = task_text[:80]
        _write_plan(plan)

        # Execute with crash recovery — retry up to 2 times on unexpected errors
        result = None
        for attempt in range(3):
            try:
                result = cortex.run(task_text, max_respawns=2)
                break
            except Exception as e:
                _log(f"Task {i+1}/{total} crashed (attempt {attempt+1}/3): {e}")
                if attempt == 2:
                    _log(f"Task {i+1}/{total} CRASHED after 3 attempts")
                    result = {"passed": False, "output": f"Error: {e}", "agent": "crashed", "attempts": 0, "rounds": 0}
                else:
                    time.sleep(5)

        if result["passed"]:
            plan["tasks"][i]["status"] = "complete"
            plan["tasks"][i]["result"] = "passed"
            plan["tasks"][i]["agent"] = result["agent"]
            plan["completed"] = sum(1 for t in plan["tasks"] if t["status"] == "complete")
            _log(f"Task {i+1}/{total} PASSED (agent {result['agent']}, {result['rounds']} rounds)")

            output_dir = PROJECT_DIR / "output"
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / f"task_{i+1}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result["output"])
            _log(f"Output saved to {output_file}")
        else:
            plan["tasks"][i]["status"] = "failed"
            plan["tasks"][i]["result"] = "failed after max respawns"
            plan["failed"] = sum(1 for t in plan["tasks"] if t["status"] == "failed")
            _log(f"Task {i+1}/{total} FAILED after {result['attempts']} attempts")
            _notify(f"Task {i+1} failed: {task_entry.get('task', '')[:50]}")

        plan["current_task"] = None
        _write_plan(plan)

    plan["finished"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_plan(plan)

    completed = sum(1 for t in plan["tasks"] if t["status"] == "complete")
    failed = sum(1 for t in plan["tasks"] if t["status"] == "failed")
    _log(f"Plan complete: {completed}/{total} passed, {failed} failed")

    _notify(f"Cortex plan complete: {completed}/{total} passed, {failed} failed")
    _clear_pid()


def start():
    pid = _get_pid()
    if pid:
        print(f"Cortex daemon already running (pid {pid})")
        return

    # Fork to background
    if os.fork() > 0:
        print("Cortex daemon started. Check status with: python -m cortex status")
        return

    # Child process
    os.setsid()
    run_daemon()


def stop():
    pid = _get_pid()
    if not pid:
        print("Cortex daemon is not running.")
        return
    os.kill(pid, signal.SIGTERM)
    print("Cortex daemon stopped.")


def status():
    pid = _get_pid()
    if not pid:
        print("Cortex daemon is not running.")
    else:
        print(f"Cortex daemon is running (pid {pid})")

    plan = _read_plan()
    if plan and plan.get("tasks"):
        total = len(plan["tasks"])
        completed = sum(1 for t in plan["tasks"] if t["status"] == "complete")
        failed = sum(1 for t in plan["tasks"] if t["status"] == "failed")
        in_progress = sum(1 for t in plan["tasks"] if t["status"] == "in_progress")
        pending = sum(1 for t in plan["tasks"] if t["status"] == "pending")

        print(f"\nPlan: {completed}/{total} complete, {failed} failed, {in_progress} running, {pending} pending")
        for i, t in enumerate(plan["tasks"], 1):
            icon = {"complete": "+", "failed": "x", "in_progress": ">", "pending": " "}.get(t["status"], " ")
            name = t["task"][:60] + "..." if len(t["task"]) > 60 else t["task"]
            print(f"  [{icon}] {name}")
    else:
        print("\nNo plan loaded.")

    if LOG_PATH.exists():
        print(f"\nRecent log:")
        lines = LOG_PATH.read_text().strip().split("\n")
        for line in lines[-5:]:
            print(f"  {line}")
