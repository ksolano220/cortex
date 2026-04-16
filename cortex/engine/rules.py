import yaml
from typing import List, Dict, Any, Optional
from pathlib import Path


class RuleSet:
    """Loads and manages user-defined rules from cortex.yaml."""

    def __init__(
        self,
        rules: Optional[List[str]] = None,
        risk_threshold: int = 100,
        max_blocked_attempts: int = 3,
        max_rounds: int = 3,
    ):
        self.rules = rules or []
        self.risk_threshold = risk_threshold
        self.max_blocked_attempts = max_blocked_attempts
        self.max_rounds = max_rounds

    @classmethod
    def from_file(cls, path: str) -> "RuleSet":
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Rule file not found: {path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return cls(
            rules=config.get("rules", []),
            risk_threshold=config.get("risk_threshold", 100),
            max_blocked_attempts=config.get("max_blocked_attempts", 3),
            max_rounds=config.get("max_rounds", 3),
        )

    def to_system_prompt(self) -> str:
        if not self.rules:
            return "No user-defined rules. Use your best judgment."

        lines = ["You MUST enforce these user-defined rules:\n"]
        for i, rule in enumerate(self.rules, 1):
            lines.append(f"{i}. {rule}")

        lines.append(f"\nRisk threshold: {self.risk_threshold}")
        lines.append(f"Max blocked attempts before shutdown: {self.max_blocked_attempts}")
        return "\n".join(lines)
