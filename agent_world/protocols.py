"""Versioned experiment recipes; certification is an explicit opt-in layer."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
import hashlib
import json

DEFAULT_PROTOCOL_ID = "participant-v7"


@dataclass(frozen=True)
class ParticipantRecipe:
    id: str
    reasoning_effort: str
    transfer_accounting: str
    scoring_revision: int = 1

    @property
    def suite_id(self) -> str:
        return "agent-world-" + self.id

    def defaults(self) -> dict[str, Any]:
        return {
            "ticks": 50, "agents": 10, "preset": "frontier-generalists",
            "world_variant": "frontier", "objective_mode": "neutral",
            "economy_mode": "organic", "geography_mode": "dispersed",
            "specialization_mode": "generalists", "reasoning_effort": self.reasoning_effort,
            "connector_profile": "connector-v3", "conversation_mode": "fresh-conversation",
            "session_max_turns": 10, "decision_mode": "raw", "action_feedback_mode": "baseline",
            "assignment_strategy": "ordered", "assignment_seed": 0, "width": 16, "height": 16,
            "claude_thinking_budget_tokens": 2048,
            "startup_health_check_tick": 5, "startup_health_max_failure_rate": 0.2,
            "transfer_kind_mode": "external" if self.transfer_accounting == "frozen_classifier" else "self_declared",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "suite_id": self.suite_id,
                "scoring_revision": self.scoring_revision,
                "transfer_accounting": self.transfer_accounting, "defaults": self.defaults()}

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


RECIPES = MappingProxyType({
    "participant-v6": ParticipantRecipe("participant-v6", "medium", "frozen_classifier", scoring_revision=2),
    "participant-v7": ParticipantRecipe("participant-v7", "low", "self_declared"),
})


def get_recipe(protocol_id: str | None = None) -> ParticipantRecipe:
    selected = protocol_id or DEFAULT_PROTOCOL_ID
    try:
        return RECIPES[selected]
    except (KeyError, TypeError):
        raise ValueError(f"Unsupported recipe {selected!r}; choose from {', '.join(RECIPES)}") from None
