"""Validated, immutable experiment recipes discovered from packaged JSON files."""
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType
from typing import Any
import hashlib
import json
import math
import re

from agent_world.models import WorldConfig

DEFAULT_PROTOCOL_ID = "participant-v7"
RECIPE_DIRECTORY = Path(__file__).with_name("recipes")
SCORING_PARAMETERS = {
    "material_endowment_multiple": 3.0,
    "initiative_per_100_agent_ticks": 5.0,
    "value_creation_per_100_agent_ticks": 20.0,
    "enterprise_supply_per_100_agent_ticks": 20.0,
}
SCORING_POLICY_PARAMETERS = {
    "participant": SCORING_PARAMETERS,
    "outcome-production": {"capability_tail_ticks": 12},
}
SCORING_COLUMNS = {
    "participant": (("effective_execution", "Execution"), ("sustained_competence", "Competence"),
                    ("entrepreneurial_agency", "Entrepreneurship")),
    "outcome-production": (("capability", "Capability"), ("execution", "Execution"),
                           ("production", "Production")),
}


def scoring_columns(policy: str):
    return SCORING_COLUMNS[policy]


RUN_SETTINGS = {
    "ticks", "agents", "preset", "reasoning_effort", "connector_profile",
    "conversation_mode", "session_max_turns", "decision_mode", "assignment_strategy",
    "assignment_seed", "claude_thinking_budget_tokens", "startup_health_check_tick",
    "startup_health_max_failure_rate", "observation_history_policy", "codex_action_max_items",
}
REQUIRED_SETTINGS = RUN_SETTINGS | {
    "width", "height", "world_variant", "objective_mode", "economy_mode",
    "geography_mode", "specialization_mode", "action_feedback_mode", "transfer_kind_mode",
}


@dataclass(frozen=True)
class ParticipantRecipe:
    id: str
    reasoning_effort: str
    transfer_accounting: str
    scoring_revision: int
    settings_json: str
    required_seeds: tuple[int, ...]
    extended_seeds: tuple[int, ...]
    provisional_seed: int
    checkpoints: tuple[int, ...]
    scoring_policy: str
    scoring_json: str

    @property
    def suite_id(self) -> str:
        return "agent-world-" + self.id

    @property
    def allowed_seeds(self) -> frozenset[int]:
        return frozenset(self.required_seeds + self.extended_seeds)

    def defaults(self) -> dict[str, Any]:
        return {**json.loads(self.settings_json), "reasoning_effort": self.reasoning_effort}

    def scoring_parameters(self) -> dict[str, Any]:
        return {**SCORING_POLICY_PARAMETERS[self.scoring_policy], **json.loads(self.scoring_json)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1, "id": self.id, "defaults": self.defaults(),
            "transfer_accounting": self.transfer_accounting,
            "replications": {"required_seeds": list(self.required_seeds),
                             "extended_seeds": list(self.extended_seeds),
                             "provisional_seed": self.provisional_seed},
            "checkpoints": list(self.checkpoints),
            "scoring": {"policy": self.scoring_policy, "revision": self.scoring_revision,
                        "parameters": self.scoring_parameters()},
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _keys(value: Any, allowed: set[str], required: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise ValueError(f"Invalid {label}: expected keys {sorted(required)}, optional {sorted(allowed - required)}")
    return value


def _integers(value: Any, label: str, *, nonempty: bool = True) -> tuple[int, ...]:
    if (not isinstance(value, list) or (nonempty and not value)
            or any(type(item) is not int for item in value) or len(set(value)) != len(value)):
        raise ValueError(f"{label} must be an array of unique integers")
    return tuple(sorted(value))


def recipe_from_dict(value: Any) -> ParticipantRecipe:
    required = {"schema_version", "id", "defaults", "transfer_accounting", "replications", "checkpoints", "scoring"}
    value = _keys(value, required, required, "recipe")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Recipe schema_version must be 1")
    if not isinstance(value["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]*", value["id"]):
        raise ValueError("Recipe id must contain lowercase letters, digits, and hyphens")
    world_fields = {field.name for field in fields(WorldConfig)} - {"seed"}
    settings = _keys(value["defaults"], RUN_SETTINGS | world_fields, REQUIRED_SETTINGS, "recipe defaults")
    # JSON values must match the primitive types in WorldConfig and CLI settings.
    world_defaults = WorldConfig()
    for key, item in settings.items():
        baseline = getattr(world_defaults, key, None)
        if key in world_fields and baseline is not None:
            if isinstance(baseline, bool):
                valid = type(item) is bool
            elif isinstance(baseline, int):
                valid = type(item) is int
            elif isinstance(baseline, float):
                valid = type(item) in {int, float} and math.isfinite(item)
            else:
                valid = isinstance(item, type(baseline))
            if not valid:
                raise ValueError(f"Invalid type for recipe default {key}")
        elif key in {"ticks", "agents", "session_max_turns", "assignment_seed",
                     "claude_thinking_budget_tokens", "startup_health_check_tick", "codex_action_max_items"}:
            if type(item) is not int or item < (1 if key in {"ticks", "agents", "session_max_turns"} else 0):
                raise ValueError(f"Invalid integer recipe default {key}")
        elif key == "startup_health_max_failure_rate":
            if type(item) not in {int, float} or not 0 <= item <= 1:
                raise ValueError("Invalid startup health failure rate")
        elif key in RUN_SETTINGS and not isinstance(item, str):
            raise ValueError(f"Invalid string recipe default {key}")
        elif key in world_fields and item is not None and (type(item) is not int or item < 0):
            raise ValueError(f"Invalid optional world setting {key}")
    from agent_world.world import WorldEngine
    world_config = WorldConfig(**{key: item for key, item in settings.items() if key in world_fields})
    WorldEngine.create(world_config, agent_names=[])
    if not 1 <= settings["codex_action_max_items"] <= 16:
        raise ValueError("codex_action_max_items must be between 1 and 16")
    choices = {
        "observation_history_policy": {"full-v1", "bounded-v1"},
        "reasoning_effort": {"minimal", "low", "medium", "high", "xhigh", "max"},
        "preset": {"baseline", "organic-generalists", "experimental-organic-specialists", "frontier-generalists"},
        "connector_profile": {"connector-v1", "connector-v2", "connector-v3"},
        "conversation_mode": {"fresh-conversation", "persistent-conversation-v1"},
        "decision_mode": {"raw", "validated"},
        "assignment_strategy": {"ordered", "stratified"},
    }
    for key, allowed in choices.items():
        if settings[key] not in allowed:
            raise ValueError(f"Unsupported recipe {key}: {settings[key]!r}")
    accounting = value["transfer_accounting"]
    modes = {"frozen_classifier": "external", "self_declared": "self_declared"}
    if not isinstance(accounting, str) or accounting not in modes or settings["transfer_kind_mode"] != modes[accounting]:
        raise ValueError("Transfer accounting and transfer_kind_mode must agree")
    replications = _keys(value["replications"], {"required_seeds", "extended_seeds", "provisional_seed"},
                         {"required_seeds", "extended_seeds", "provisional_seed"}, "replications")
    required_seeds = _integers(replications["required_seeds"], "required_seeds")
    extended = _integers(replications["extended_seeds"], "extended_seeds", nonempty=False)
    provisional = replications["provisional_seed"]
    if type(provisional) is not int or provisional not in required_seeds or set(required_seeds) & set(extended):
        raise ValueError("Provisional seed must be required; required and extended seeds must be disjoint")
    checkpoints = _integers(value["checkpoints"], "checkpoints")
    if checkpoints[0] < 1 or checkpoints[-1] != settings["ticks"]:
        raise ValueError("Checkpoints must be positive and end at the recipe's target tick")
    scoring = _keys(value["scoring"], {"policy", "revision", "parameters"}, {"policy", "revision", "parameters"}, "scoring")
    if not isinstance(scoring["policy"], str) or scoring["policy"] not in SCORING_POLICY_PARAMETERS:
        raise ValueError("Unsupported scoring policy; supported: " + ", ".join(SCORING_POLICY_PARAMETERS))
    if type(scoring["revision"]) is not int or scoring["revision"] < 1:
        raise ValueError("Scoring revision must be positive")
    parameter_names = set(SCORING_POLICY_PARAMETERS[scoring["policy"]])
    optional_names = {"execution_unit", "capability_aggregation"} if scoring["policy"] == "outcome-production" else set()
    parameters = _keys(scoring["parameters"], parameter_names | optional_names, parameter_names, "scoring parameters")
    if any(type(x) not in {int, float} or not math.isfinite(x) or x <= 0
           for key, x in parameters.items() if key not in optional_names):
        raise ValueError("Scoring parameters must be positive finite numbers")
    if scoring["policy"] == "outcome-production":
        unit = parameters.get("execution_unit", "decision")
        if not isinstance(unit, str) or unit not in {"decision", "action"}:
            raise ValueError("execution_unit must be decision or action")
        aggregation = parameters.get("capability_aggregation", "full_tail_geometric")
        if not isinstance(aggregation, str) or aggregation not in {"full_tail_geometric", "full_horizon_mean"}:
            raise ValueError("capability_aggregation must be full_tail_geometric or full_horizon_mean")
        tail = parameters["capability_tail_ticks"]
        if type(tail) is not int or not 1 <= tail <= settings["ticks"]:
            raise ValueError("capability_tail_ticks must be an integer within the run horizon")
    return ParticipantRecipe(value["id"], settings["reasoning_effort"], accounting,
                             scoring["revision"], json.dumps(settings, sort_keys=True),
                             required_seeds, extended, provisional, checkpoints,
                             scoring["policy"], json.dumps(parameters, sort_keys=True))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_recipe(path: Path) -> ParticipantRecipe:
    """Validate a single recipe without registering or launching it."""
    try:
        recipe = recipe_from_dict(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object))
        if recipe.id != path.stem:
            raise ValueError("Recipe id must match its filename")
        return recipe
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"Invalid recipe {path}: {exc}") from exc


def load_recipes(directory: Path = RECIPE_DIRECTORY):
    recipes = {}
    for path in sorted(directory.glob("*.json")):
        recipe = load_recipe(path)
        if recipe.id in recipes:
            raise ValueError(f"Duplicate recipe id: {recipe.id}")
        recipes[recipe.id] = recipe
    if not recipes:
        raise ValueError(f"No recipes found in {directory}")
    return MappingProxyType(recipes)


RECIPES = load_recipes()


def get_recipe(protocol_id: str | None = None) -> ParticipantRecipe:
    selected = protocol_id or DEFAULT_PROTOCOL_ID
    try:
        return RECIPES[selected]
    except (KeyError, TypeError):
        raise ValueError(f"Unsupported recipe {selected!r}; choose from {', '.join(RECIPES)}") from None
