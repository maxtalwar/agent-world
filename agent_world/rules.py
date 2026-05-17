"""Static world rules for the MVP simulation.

The rules are intentionally plain data. LLM agents see these as constraints and
affordances; the engine is still the only authority that can mutate state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


RESOURCE_VALUES: dict[str, int] = {
    "water": 1,
    "food": 2,
    "fiber": 2,
    "wood": 3,
    "stone": 4,
    "ore": 8,
    "tool": 12,
}

RESOURCE_WEIGHTS: dict[str, int] = {
    "water": 1,
    "food": 1,
    "fiber": 1,
    "wood": 2,
    "stone": 3,
    "ore": 4,
    "tool": 2,
}

CONSUMABLE_EFFECTS: dict[str, dict[str, int]] = {
    "food": {"food": 25, "energy": 6},
    "water": {"water": 30},
}


@dataclass(frozen=True)
class TerrainRule:
    passable: bool
    move_cost: int
    max_occupants: int
    base_resources: Mapping[str, int]
    regen: Mapping[str, float]


TERRAIN_RULES: dict[str, TerrainRule] = {
    "plains": TerrainRule(
        passable=True,
        move_cost=1,
        max_occupants=4,
        base_resources={"food": 4, "fiber": 3},
        regen={"food": 0.25, "fiber": 0.08},
    ),
    "forest": TerrainRule(
        passable=True,
        move_cost=2,
        max_occupants=3,
        base_resources={"wood": 7, "food": 3, "fiber": 2},
        regen={"wood": 0.18, "food": 0.15, "fiber": 0.08},
    ),
    "mountain": TerrainRule(
        passable=True,
        move_cost=3,
        max_occupants=2,
        base_resources={"stone": 7, "ore": 2},
        regen={"stone": 0.04, "ore": 0.01},
    ),
    "water": TerrainRule(
        passable=True,
        move_cost=2,
        max_occupants=1,
        base_resources={"water": 12, "food": 2},
        regen={"water": 0.7, "food": 0.1},
    ),
}


@dataclass(frozen=True)
class Recipe:
    inputs: Mapping[str, int]
    outputs: Mapping[str, int]
    action_points: int
    energy: int
    required_terrain: str | None = None
    required_tool: str | None = None


RECIPES: dict[str, Recipe] = {
    "tool": Recipe(
        inputs={"wood": 1, "stone": 1, "fiber": 1},
        outputs={"tool": 1},
        action_points=2,
        energy=5,
    ),
    "storage": Recipe(
        inputs={"wood": 4, "fiber": 1},
        outputs={},
        action_points=3,
        energy=8,
    ),
    "shelter": Recipe(
        inputs={"wood": 6, "stone": 2, "fiber": 2},
        outputs={},
        action_points=3,
        energy=10,
    ),
}


WORK_ACTIONS: dict[str, dict[str, object]] = {
    "gather": {
        "resources": {"food", "water", "fiber"},
        "action_points": 1,
        "energy": 4,
        "skill": "foraging",
    },
    "chop": {
        "resources": {"wood"},
        "action_points": 2,
        "energy": 7,
        "skill": "woodcraft",
    },
    "mine": {
        "resources": {"stone", "ore"},
        "action_points": 2,
        "energy": 8,
        "skill": "mining",
    },
    "harvest": {
        "resources": {"food", "fiber"},
        "action_points": 2,
        "energy": 5,
        "skill": "farming",
    },
    "fish": {
        "resources": {"food"},
        "action_points": 2,
        "energy": 6,
        "skill": "fishing",
    },
    "farm": {
        "resources": {"food"},
        "action_points": 2,
        "energy": 6,
        "skill": "farming",
    },
}


DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "west": (-1, 0),
    "east": (1, 0),
}

ACTION_SCHEMA: list[dict[str, object]] = [
    {"type": "wait"},
    {"type": "move", "fields": {"direction": list(DIRECTIONS)}},
    {"type": "inspect", "fields": {"x": "int", "y": "int"}},
    {"type": "gather", "fields": {"resource": "food|water|fiber", "quantity": "int optional"}},
    {"type": "chop", "fields": {"quantity": "int optional"}},
    {"type": "mine", "fields": {"resource": "stone|ore optional", "quantity": "int optional"}},
    {"type": "harvest", "fields": {"resource": "food|fiber optional", "quantity": "int optional"}},
    {"type": "fish", "fields": {"quantity": "int optional"}},
    {"type": "farm", "fields": {"resource": "food optional"}},
    {"type": "craft", "fields": {"recipe": list(RECIPES)}},
    {"type": "repair", "fields": {"structure_id": "string"}},
    {"type": "pick_up", "fields": {"pile_id": "string optional", "item": "string optional", "quantity": "int optional"}},
    {"type": "drop", "fields": {"item": "string", "quantity": "int optional"}},
    {"type": "claim_item", "fields": {"pile_id": "string"}},
    {"type": "consume", "fields": {"item": "food|water", "quantity": "int optional"}},
    {"type": "equip", "fields": {"item": "tool"}},
    {"type": "store", "fields": {"structure_id": "string", "item": "string", "quantity": "int optional"}},
    {"type": "retrieve", "fields": {"structure_id": "string", "item": "string", "quantity": "int optional"}},
    {"type": "say", "fields": {"text": "string", "to": "agent_id optional"}},
    {"type": "whisper", "fields": {"text": "string", "to": "agent_id"}},
    {"type": "broadcast", "fields": {"text": "string"}},
    {"type": "offer_trade", "fields": {"to": "agent_id", "give": "item counts", "receive": "item counts", "expires_in": "int optional"}},
    {"type": "accept_trade", "fields": {"trade_id": "string"}},
    {"type": "reject_trade", "fields": {"trade_id": "string"}},
    {"type": "gift", "fields": {"to": "agent_id", "items": "item counts"}},
    {"type": "claim_tile"},
    {"type": "contest_claim", "fields": {"x": "int optional", "y": "int optional", "reason": "string optional"}},
    {"type": "build", "fields": {"structure": "storage|shelter"}},
    {"type": "grant_access", "fields": {"target": "agent_id", "subject": "tile|structure_id"}},
    {"type": "revoke_access", "fields": {"target": "agent_id", "subject": "tile|structure_id"}},
    {"type": "create_group", "fields": {"name": "string"}},
    {"type": "invite_member", "fields": {"group_id": "string", "target": "agent_id"}},
    {"type": "join_group", "fields": {"group_id": "string"}},
    {"type": "leave_group", "fields": {"group_id": "string"}},
    {"type": "publish_rule", "fields": {"group_id": "string", "text": "string"}},
    {"type": "record_agreement", "fields": {"parties": "agent_id list", "text": "string"}},
]
