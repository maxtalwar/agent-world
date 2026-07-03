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
    "water": 2,
    "food": 1,
    "fiber": 1,
    "wood": 2,
    "stone": 3,
    "ore": 4,
    "tool": 2,
}

CONSUMABLE_EFFECTS: dict[str, dict[str, int]] = {
    "food": {"food": 5, "energy": 4},
    "water": {"water": 10},
}

BASE_WAIT_ENERGY_RECOVERY = 6
REST_STRUCTURE_ENERGY_BONUS = {
    "shelter": 4,
    "house": 8,
}
FARM_PLOT_FARM_FOOD_ADDED = 5
FARM_PLOT_FOOD_CAPACITY = 24
FARM_PLOT_PASSIVE_FOOD_GROWTH = 2
WORKSHOP_CRAFTING_ENERGY_DISCOUNT = 2

MECHANICS_SUMMARY: dict[str, object] = {
    "resources": {
        "water": "Consumed to restore thirst need. Gathered from adjacent open water, accessible wells, or from the current tile if water is present.",
        "food": "Consumed to restore hunger and a small amount of energy. Gathered, harvested, fished, or produced on improved land.",
        "fiber": "Crafting/building material. Gathered from tiles where fiber is present.",
        "wood": "Crafting/building/repair material. Produced with chop on tiles where wood is present.",
        "stone": "Crafting/building material. Produced with mine on tiles where stone is present.",
        "ore": "High-value raw material. Produced with mine on tiles where ore is present.",
        "tool": "Crafted from wood, stone, and fiber. Can be equipped.",
    },
    "action_notes": {
        "gather": "Produces food or fiber from the current tile. Water can be gathered from adjacent open water or accessible wells without standing on water.",
        "chop": "Produces wood from local wood resources.",
        "mine": "Produces stone or ore from local mountain-style resources.",
        "harvest": "Collects food from improved land such as a farm plot.",
        "consume": "Uses carried food or water to restore body needs.",
        "farm": "Tends an existing farm plot.",
        "fish": "Produces food from current or adjacent water if fishable food is present there.",
        "build": "Starts (or instantly finishes) a farm_plot, storage, shelter, house, workshop, or well on the current tile. Materials you are carrying are placed into the site immediately; if it still needs more, it stays under construction until enough is contributed. Heavier structures need more material than one agent can carry at once, so they must be funded across several trips or by several agents.",
        "contribute": "Adds carried materials to an under-construction structure on the current tile. Any agent standing on the tile may contribute. The structure finishes and its effects turn on only once every required material has been supplied.",
        "store": "Moves carried goods into accessible storage, house, or workshop space on the current tile.",
        "retrieve": "Moves goods from accessible storage, house, or workshop space into inventory.",
        "offer_trade": "Creates a direct trade offer to a visible agent, or a local public offer if target is any. Offered goods are held until accepted, rejected, or expired.",
        "grant_access": "Allows another agent or a group to use a claimed tile or owned structure.",
        "groups": "Groups can hold members, rules, access grants, claimed land, and owned structures for shared infrastructure.",
    },
    "structures": {
        "farm_plot": "Persistent improved land on plains/forest. It can support more reliable food production than wild foraging.",
        "storage": "Holds inventory on a tile, reducing agent carrying pressure and protecting stored food from spoilage. Owner can grant/revoke access.",
        "shelter": "Simple rest structure. Improves waiting energy recovery and prevents passive energy decay while on its tile.",
        "house": "Better rest and small private/shared storage. Helps agents remain near a settlement site.",
        "workshop": "Shared work site and material cache. Makes crafting cheaper and is the base for later production chains.",
        "well": "Local water infrastructure. Helps a settled site access water without living beside open water.",
    },
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
        base_resources={"food": 1, "fiber": 2},
        regen={"food": 0.01, "fiber": 0.03},
    ),
    "forest": TerrainRule(
        passable=True,
        move_cost=2,
        max_occupants=3,
        base_resources={"wood": 7, "food": 1, "fiber": 1},
        regen={"wood": 0.14, "food": 0.02, "fiber": 0.03},
    ),
    "mountain": TerrainRule(
        passable=True,
        move_cost=3,
        max_occupants=2,
        base_resources={"stone": 7, "ore": 2},
        regen={"stone": 0.04, "ore": 0.01},
    ),
    "water": TerrainRule(
        passable=False,
        move_cost=2,
        max_occupants=0,
        base_resources={"water": 12, "food": 1},
        regen={"water": 0.7, "food": 0.02},
    ),
}


@dataclass(frozen=True)
class Recipe:
    inputs: Mapping[str, int]
    outputs: Mapping[str, int]
    action_points: int
    energy: int
    required_terrain: tuple[str, ...] = ()
    required_tool: str | None = None


RECIPES: dict[str, Recipe] = {
    "tool": Recipe(
        inputs={"wood": 1, "stone": 1, "fiber": 1},
        outputs={"tool": 1},
        action_points=2,
        energy=5,
    ),
    "farm_plot": Recipe(
        inputs={"fiber": 1},
        outputs={},
        action_points=1,
        energy=3,
        required_terrain=("plains", "forest"),
    ),
    "storage": Recipe(
        inputs={"wood": 2, "fiber": 1},
        outputs={},
        action_points=2,
        energy=5,
    ),
    "shelter": Recipe(
        inputs={"wood": 6, "stone": 1, "fiber": 2},
        outputs={},
        action_points=3,
        energy=10,
    ),
    "house": Recipe(
        inputs={"wood": 10, "stone": 3, "fiber": 3},
        outputs={},
        action_points=3,
        energy=14,
        required_terrain=("plains", "forest"),
    ),
    "workshop": Recipe(
        inputs={"wood": 5, "stone": 2, "fiber": 1},
        outputs={},
        action_points=3,
        energy=10,
        required_terrain=("plains", "forest"),
    ),
    "well": Recipe(
        inputs={"wood": 2, "fiber": 1},
        outputs={},
        action_points=2,
        energy=6,
        required_terrain=("plains", "forest"),
    ),
}

STRUCTURE_TYPES = {"farm_plot", "storage", "shelter", "house", "workshop", "well"}
STORAGE_STRUCTURE_TYPES = {"storage", "house", "workshop"}
REST_STRUCTURE_TYPES = {"shelter", "house"}
FREE_ACTION_TYPES = {
    "say",
    "whisper",
    "broadcast",
    "grant_access",
    "revoke_access",
    "create_group",
    "invite_member",
    "join_group",
    "leave_group",
    "publish_rule",
    "record_agreement",
}
STRUCTURE_CAPACITIES = {
    "farm_plot": 0,
    "storage": 120,
    "shelter": 20,
    "house": 60,
    "workshop": 80,
    "well": 0,
}
WORK_ACTIONS: dict[str, dict[str, object]] = {
    "gather": {
        "resources": {"food", "water", "fiber"},
        "action_points": 1,
        "energy": 3,
        "skill": "foraging",
        "max_quantity": 1,
    },
    "chop": {
        "resources": {"wood"},
        "action_points": 2,
        "energy": 5,
        "skill": "woodcraft",
    },
    "mine": {
        "resources": {"stone", "ore"},
        "action_points": 2,
        "energy": 6,
        "skill": "mining",
    },
    "harvest": {
        "resources": {"food"},
        "action_points": 2,
        "energy": 4,
        "skill": "farming",
        "max_quantity": 3,
    },
    "fish": {
        "resources": {"food"},
        "action_points": 2,
        "energy": 6,
        "skill": "fishing",
        "max_quantity": 1,
    },
    "farm": {
        "resources": {"food"},
        "action_points": 2,
        "energy": 5,
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
    {"type": "wait", "example": {"type": "wait"}},
    {
        "type": "move",
        "parameters": {"direction": list(DIRECTIONS)},
        "example": {"type": "move", "direction": "north"},
    },
    {
        "type": "inspect",
        "parameters": {"x": "int", "y": "int"},
        "example": {"type": "inspect", "x": 8, "y": 8},
    },
    {
        "type": "gather",
        "parameters": {"resource": "food|water|fiber", "quantity": "int optional"},
        "example": {"type": "gather", "resource": "food", "quantity": 1},
    },
    {"type": "chop", "parameters": {"quantity": "int optional"}, "example": {"type": "chop", "quantity": 1}},
    {
        "type": "mine",
        "parameters": {"resource": "stone|ore optional", "quantity": "int optional"},
        "example": {"type": "mine", "resource": "stone", "quantity": 1},
    },
    {
        "type": "harvest",
        "parameters": {"resource": "food|fiber optional", "quantity": "int optional"},
        "example": {"type": "harvest", "resource": "food", "quantity": 1},
    },
    {"type": "fish", "parameters": {"quantity": "int optional"}, "example": {"type": "fish", "quantity": 1}},
    {"type": "farm", "example": {"type": "farm"}},
    {"type": "craft", "parameters": {"recipe": list(RECIPES)}, "example": {"type": "craft", "recipe": "tool"}},
    {
        "type": "repair",
        "parameters": {"structure_id": "string"},
        "example": {"type": "repair", "structure_id": "structure-1"},
    },
    {
        "type": "pick_up",
        "parameters": {"pile_id": "string optional", "item": "string optional", "quantity": "int optional"},
        "example": {"type": "pick_up", "pile_id": "item-1", "quantity": 1},
    },
    {
        "type": "drop",
        "parameters": {"item": "string", "quantity": "int optional"},
        "example": {"type": "drop", "item": "food", "quantity": 1},
    },
    {
        "type": "claim_item",
        "parameters": {"pile_id": "string"},
        "example": {"type": "claim_item", "pile_id": "item-1"},
    },
    {
        "type": "consume",
        "parameters": {"item": "food|water", "quantity": "int optional"},
        "example": {"type": "consume", "item": "water", "quantity": 1},
    },
    {"type": "equip", "parameters": {"item": "tool"}, "example": {"type": "equip", "item": "tool"}},
    {
        "type": "store",
        "parameters": {"structure_id": "string", "item": "string", "quantity": "int optional"},
        "example": {"type": "store", "structure_id": "structure-1", "item": "food", "quantity": 1},
    },
    {
        "type": "retrieve",
        "parameters": {"structure_id": "string", "item": "string", "quantity": "int optional"},
        "example": {"type": "retrieve", "structure_id": "structure-1", "item": "food", "quantity": 1},
    },
    {
        "type": "say",
        "parameters": {"text": "string", "to": "agent_id optional"},
        "example": {"type": "say", "text": "Food is scarce here."},
    },
    {
        "type": "whisper",
        "parameters": {"text": "string", "to": "agent_id"},
        "example": {"type": "whisper", "to": "agent-2", "text": "I can share water."},
    },
    {
        "type": "broadcast",
        "parameters": {"text": "string"},
        "example": {"type": "broadcast", "text": "I found water near the lake."},
    },
    {
        "type": "offer_trade",
        "parameters": {"to": "agent_id|'any' optional", "give": "item counts", "receive": "item counts", "expires_in": "int optional"},
        "example": {"type": "offer_trade", "to": "any", "give": {"food": 1}, "receive": {"water": 1}},
    },
    {
        "type": "accept_trade",
        "parameters": {"trade_id": "string"},
        "example": {"type": "accept_trade", "trade_id": "trade-1"},
    },
    {
        "type": "reject_trade",
        "parameters": {"trade_id": "string"},
        "example": {"type": "reject_trade", "trade_id": "trade-1"},
    },
    {
        "type": "gift",
        "parameters": {"to": "agent_id", "items": "item counts"},
        "example": {"type": "gift", "to": "agent-2", "items": {"water": 1}},
    },
    {
        "type": "claim_tile",
        "parameters": {"group_id": "string optional"},
        "example": {"type": "claim_tile", "group_id": "group-1"},
    },
    {
        "type": "contest_claim",
        "parameters": {"x": "int optional", "y": "int optional", "reason": "string optional"},
        "example": {"type": "contest_claim", "x": 8, "y": 8, "reason": "shared access needed"},
    },
    {
        "type": "build",
        "parameters": {"structure": "farm_plot|storage|shelter|house|workshop|well", "group_id": "string optional"},
        "example": {"type": "build", "structure": "farm_plot"},
    },
    {
        "type": "contribute",
        "parameters": {"structure_id": "string optional", "structure": "structure type optional", "items": "item counts"},
        "example": {"type": "contribute", "structure": "house", "items": {"wood": 2}},
    },
    {
        "type": "grant_access",
        "parameters": {"target": "agent_id|group_id", "subject": "tile|structure_id"},
        "example": {"type": "grant_access", "target": "agent-2", "subject": "structure-1"},
    },
    {
        "type": "revoke_access",
        "parameters": {"target": "agent_id|group_id", "subject": "tile|structure_id"},
        "example": {"type": "revoke_access", "target": "agent-2", "subject": "structure-1"},
    },
    {"type": "create_group", "parameters": {"name": "string"}, "example": {"type": "create_group", "name": "Camp"}},
    {
        "type": "invite_member",
        "parameters": {"group_id": "string", "target": "agent_id"},
        "example": {"type": "invite_member", "group_id": "group-1", "target": "agent-2"},
    },
    {"type": "join_group", "parameters": {"group_id": "string"}, "example": {"type": "join_group", "group_id": "group-1"}},
    {"type": "leave_group", "parameters": {"group_id": "string"}, "example": {"type": "leave_group", "group_id": "group-1"}},
    {
        "type": "publish_rule",
        "parameters": {"group_id": "string", "text": "string"},
        "example": {"type": "publish_rule", "group_id": "group-1", "text": "Share stored water."},
    },
    {
        "type": "record_agreement",
        "parameters": {"parties": "agent_id list", "text": "string", "group_id": "string optional"},
        "example": {"type": "record_agreement", "group_id": "group-1", "parties": ["agent-1", "agent-2"], "text": "Share food from this tile."},
    },
]

_ACTION_COSTS: dict[str, dict[str, object]] = {
    "wait": {"action_points": 1, "energy": 0, "effect": "recovers energy"},
    "move": {"action_points": "destination terrain move_cost", "energy": "destination terrain move_cost"},
    "inspect": {"action_points": 1, "energy": 0},
    "gather": {"action_points": WORK_ACTIONS["gather"]["action_points"], "energy": WORK_ACTIONS["gather"]["energy"]},
    "chop": {"action_points": WORK_ACTIONS["chop"]["action_points"], "energy": WORK_ACTIONS["chop"]["energy"]},
    "mine": {"action_points": WORK_ACTIONS["mine"]["action_points"], "energy": WORK_ACTIONS["mine"]["energy"]},
    "harvest": {"action_points": WORK_ACTIONS["harvest"]["action_points"], "energy": WORK_ACTIONS["harvest"]["energy"]},
    "fish": {"action_points": WORK_ACTIONS["fish"]["action_points"], "energy": WORK_ACTIONS["fish"]["energy"]},
    "farm": {"action_points": WORK_ACTIONS["farm"]["action_points"], "energy": WORK_ACTIONS["farm"]["energy"]},
    "craft": {"action_points": "recipe action_points", "energy": "recipe energy"},
    "repair": {"action_points": 1, "energy": 0},
    "pick_up": {"action_points": 1, "energy": 0},
    "drop": {"action_points": 1, "energy": 0},
    "claim_item": {"action_points": 1, "energy": 0},
    "consume": {"action_points": 1, "energy": 0},
    "equip": {"action_points": 1, "energy": 0},
    "store": {"action_points": 1, "energy": 0},
    "retrieve": {"action_points": 1, "energy": 0},
    "say": {"action_points": 0, "energy": 0},
    "whisper": {"action_points": 0, "energy": 0},
    "broadcast": {"action_points": 0, "energy": 0},
    "offer_trade": {"action_points": 1, "energy": 0},
    "accept_trade": {"action_points": 1, "energy": 0},
    "reject_trade": {"action_points": 1, "energy": 0},
    "gift": {"action_points": 1, "energy": 0},
    "claim_tile": {"action_points": 1, "energy": 0},
    "contest_claim": {"action_points": 1, "energy": 0},
    "build": {"action_points": "recipe action_points", "energy": "recipe energy"},
    "contribute": {"action_points": 1, "energy": 0},
    "grant_access": {"action_points": 0, "energy": 0},
    "revoke_access": {"action_points": 0, "energy": 0},
    "create_group": {"action_points": 0, "energy": 0},
    "invite_member": {"action_points": 0, "energy": 0},
    "join_group": {"action_points": 0, "energy": 0},
    "leave_group": {"action_points": 0, "energy": 0},
    "publish_rule": {"action_points": 0, "energy": 0},
    "record_agreement": {"action_points": 0, "energy": 0},
}

for action in ACTION_SCHEMA:
    cost = _ACTION_COSTS.get(str(action["type"]))
    if cost is not None:
        action["cost"] = dict(cost)
