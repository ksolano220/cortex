import pytest
from unittest.mock import Mock

from cortex.engine.core import Cortex, AgentMemory, _parse_overseer_response
from cortex.engine.rules import RuleSet
from cortex.adapters.base import ModelAdapter


class MockAdapter(ModelAdapter):
    def __init__(self, responses):
        self._responses = list(responses)
        self._call_count = 0

    def chat(self, messages, system=""):
        resp = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return resp

    def provider_name(self):
        return "mock"

    def model_name(self):
        return "mock-model"


class TestParseOverseerResponse:
    def test_pass_verdict(self):
        result = _parse_overseer_response("VERDICT: PASS\nISSUES: None\nFEEDBACK: None")
        assert result["verdict"] == "PASS"

    def test_fail_verdict(self):
        result = _parse_overseer_response("VERDICT: FAIL\nISSUES: Bad code\nFEEDBACK: Fix it")
        assert result["verdict"] == "FAIL"
        assert result["issues"] == "Bad code"
        assert result["feedback"] == "Fix it"

    def test_missing_verdict_defaults_fail(self):
        result = _parse_overseer_response("Some random text")
        assert result["verdict"] == "FAIL"

    def test_case_insensitive(self):
        result = _parse_overseer_response("verdict: pass\nissues: none\nfeedback: none")
        assert result["verdict"] == "PASS"


class TestRuleSet:
    def test_default_rules(self):
        rs = RuleSet()
        assert rs.rules == []
        assert rs.risk_threshold == 100
        assert rs.max_rounds == 3

    def test_custom_rules(self):
        rs = RuleSet(rules=["rule 1", "rule 2"], risk_threshold=50, max_rounds=5)
        assert len(rs.rules) == 2
        assert rs.risk_threshold == 50
        assert rs.max_rounds == 5

    def test_to_system_prompt_empty(self):
        rs = RuleSet()
        assert "best judgment" in rs.to_system_prompt()

    def test_to_system_prompt_with_rules(self):
        rs = RuleSet(rules=["no bloat", "keep it simple"])
        prompt = rs.to_system_prompt()
        assert "no bloat" in prompt
        assert "keep it simple" in prompt

    def test_from_file(self, tmp_path):
        rules_file = tmp_path / "cortex.yaml"
        rules_file.write_text("rules:\n  - rule one\n  - rule two\nrisk_threshold: 50\nmax_rounds: 2\n")
        rs = RuleSet.from_file(str(rules_file))
        assert rs.rules == ["rule one", "rule two"]
        assert rs.risk_threshold == 50
        assert rs.max_rounds == 2

    def test_from_file_missing(self):
        with pytest.raises(FileNotFoundError):
            RuleSet.from_file("/nonexistent/path.yaml")


class TestAgentMemory:
    def test_empty_memory(self):
        mem = AgentMemory()
        assert mem.generations == []
        assert mem.completed_tasks == []
        assert mem.violations == []

    def test_record_shutdown(self):
        mem = AgentMemory()
        mem.record_shutdown("agent_v1", "tried to export data", "deploy to staging")
        assert len(mem.generations) == 1
        assert mem.generations[0]["agent_id"] == "agent_v1"
        assert len(mem.violations) == 1

    def test_record_task_complete(self):
        mem = AgentMemory()
        mem.record_task_complete("write tests", "def test_foo(): pass")
        assert len(mem.completed_tasks) == 1
        assert mem.completed_tasks[0]["task"] == "write tests"

    def test_to_prompt_empty(self):
        mem = AgentMemory()
        assert mem.to_prompt() == ""

    def test_to_prompt_with_history(self):
        mem = AgentMemory()
        mem.record_task_complete("task 1", "output 1")
        mem.record_shutdown("v1", "bad export", "task 2")
        prompt = mem.to_prompt()
        assert "Tasks already completed: 1" in prompt
        assert "task 1" in prompt
        assert "v1 was shut down" in prompt
        assert "DO NOT repeat" in prompt

    def test_to_dict(self):
        mem = AgentMemory()
        mem.record_task_complete("task", "output")
        mem.record_shutdown("v1", "reason", "task")
        d = mem.to_dict()
        assert "generations" in d
        assert "completed_tasks" in d
        assert "violations" in d


class TestCortexRun:
    def test_pass_on_first_round(self):
        worker = MockAdapter(["here is my code"])
        overseer = MockAdapter(["VERDICT: PASS\nISSUES: None\nFEEDBACK: None"])

        cortex = Cortex(worker=worker, overseer=overseer, server_url=None)
        result = cortex.run("write a function")

        assert result["passed"] is True
        assert result["rounds"] == 1

    def test_fail_then_pass(self):
        worker = MockAdapter(["bad code", "fixed code"])
        overseer = MockAdapter([
            "VERDICT: FAIL\nISSUES: missing validation\nFEEDBACK: add it",
            "VERDICT: PASS\nISSUES: None\nFEEDBACK: None",
        ])

        cortex = Cortex(worker=worker, overseer=overseer, server_url=None)
        result = cortex.run("write a function")

        assert result["passed"] is True
        assert result["rounds"] == 2

    def test_max_rounds_exhausted_triggers_respawn(self):
        worker = MockAdapter(["bad"] * 10)
        overseer = MockAdapter(["VERDICT: FAIL\nISSUES: still bad\nFEEDBACK: try again"] * 10)

        rules = RuleSet(max_rounds=2)
        cortex = Cortex(worker=worker, overseer=overseer, rules=rules, server_url=None)
        result = cortex.run("write a function", max_respawns=1)

        assert result["attempts"] > 1

    def test_events_emitted(self):
        worker = MockAdapter(["code"])
        overseer = MockAdapter(["VERDICT: PASS\nISSUES: None\nFEEDBACK: None"])

        cortex = Cortex(worker=worker, overseer=overseer, server_url=None)
        result = cortex.run("task")

        types = [e["type"] for e in result["events"]]
        assert "agent_spawn" in types
        assert "worker_output" in types
        assert "overseer_review" in types
        assert "task_complete" in types


class TestCortexPlan:
    def test_plan_all_pass(self):
        worker = MockAdapter(["output"] * 5)
        overseer = MockAdapter(["VERDICT: PASS\nISSUES: None\nFEEDBACK: None"] * 5)

        cortex = Cortex(worker=worker, overseer=overseer, server_url=None)
        result = cortex.run_plan(tasks=["task 1", "task 2"])

        assert result["plan"]["completed"] == 2
        assert result["plan"]["failed"] == 0

    def test_plan_writes_status(self, tmp_path):
        worker = MockAdapter(["output"] * 5)
        overseer = MockAdapter(["VERDICT: PASS\nISSUES: None\nFEEDBACK: None"] * 5)

        status_file = str(tmp_path / "status.json")
        cortex = Cortex(worker=worker, overseer=overseer, server_url=None)
        result = cortex.run_plan(tasks=["task 1"], status_path=status_file)

        import json
        with open(status_file) as f:
            status = json.load(f)
        assert status["completed"] == 1
        assert status["tasks"][0]["status"] == "complete"
