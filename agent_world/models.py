"""Dataclasses for Agent World state."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from agent_world.rules import RESOURCE_WEIGHTS

FOOD_RESERVE_MAX = 20
FOOD_RESERVE_START = 10
WATER_RESERVE_MAX = 20
WATER_RESERVE_START = 10
RESERVE_MAX = 30
RESERVE_START = 25
RESERVE_MAX_BY_NAME = {"food": FOOD_RESERVE_MAX, "water": WATER_RESERVE_MAX, "energy": RESERVE_MAX}


@dataclass(frozen=True, order=True)
class Position:
    x: int
    y: int

    def distance_to(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def shifted(self, dx: int, dy: int) -> "Position":
        return Position(self.x + dx, self.y + dy)


@dataclass
class WorldConfig:
    width: int = 16
    height: int = 16
    seed: int = 1
    visible_radius: int = 2
    action_points_per_tick: int = 4
    max_memory: int = 50
    recent_event_limit: int = 20
    default_carry_capacity: int = 10
    storage_capacity: int = 120
    food_reserve_start: int = FOOD_RESERVE_START
    food_reserve_max: int = FOOD_RESERVE_MAX
    water_reserve_start: int = WATER_RESERVE_START
    water_reserve_max: int = WATER_RESERVE_MAX
    energy_reserve_start: int = RESERVE_START
    energy_reserve_max: int = RESERVE_MAX
    survival_food_decay: int = 1
    survival_water_decay: int = 2
    survival_energy_decay: int = 1
    exhaustion_damage: int = 2
    carried_food_spoil_interval: int = 6
    carried_food_spoil_quantity: int = 1
    resource_base_multiplier: float = 1.0
    plains_food_regen: float = 0.01
    plains_fiber_regen: float = 0.03
    forest_wood_regen: float = 0.14
    forest_food_regen: float = 0.02
    forest_fiber_regen: float = 0.03
    mountain_stone_regen: float = 0.04
    mountain_ore_regen: float = 0.01
    water_water_regen: float = 0.7
    water_food_regen: float = 0.02
    wild_food_density: float = 0.35
    wild_fiber_density: float = 0.85
    starter_resource_radius: int = 1
    farm_food_added: int = 5
    farm_food_capacity: int = 24
    farm_passive_food_growth: int = 2

    def reserve_max_for(self, name: str) -> int:
        return {
            "food": self.food_reserve_max,
            "water": self.water_reserve_max,
            "energy": self.energy_reserve_max,
        }.get(name, self.energy_reserve_max)

    def regen_rate_for(self, terrain: str, resource: str) -> float:
        return {
            ("plains", "food"): self.plains_food_regen,
            ("plains", "fiber"): self.plains_fiber_regen,
            ("forest", "wood"): self.forest_wood_regen,
            ("forest", "food"): self.forest_food_regen,
            ("forest", "fiber"): self.forest_fiber_regen,
            ("mountain", "stone"): self.mountain_stone_regen,
            ("mountain", "ore"): self.mountain_ore_regen,
            ("water", "water"): self.water_water_regen,
            ("water", "food"): self.water_food_regen,
        }.get((terrain, resource), 0.0)


@dataclass
class Needs:
    food: int = FOOD_RESERVE_START
    water: int = WATER_RESERVE_START
    energy: int = RESERVE_START

    def as_dict(self) -> dict[str, int]:
        return {"food": self.food, "water": self.water, "energy": self.energy}

    def clamp(self) -> None:
        self.food = max(0, min(FOOD_RESERVE_MAX, self.food))
        self.water = max(0, min(WATER_RESERVE_MAX, self.water))
        self.energy = max(0, min(RESERVE_MAX, self.energy))


@dataclass
class Agent:
    id: str
    name: str
    position: Position
    inventory: Counter[str] = field(default_factory=Counter)
    needs: Needs = field(default_factory=Needs)
    skills: dict[str, int] = field(default_factory=dict)
    health: int = 100
    reputation: int = 0
    relationships: dict[str, int] = field(default_factory=dict)
    memory: list[str] = field(default_factory=list)
    equipped: set[str] = field(default_factory=set)
    groups: set[str] = field(default_factory=set)
    alive: bool = True
    carry_capacity: int = 10

    def inventory_weight(self) -> int:
        return sum(RESOURCE_WEIGHTS.get(item, 1) * qty for item, qty in self.inventory.items())

    def can_carry(self, item: str, quantity: int) -> bool:
        return self.inventory_weight() + RESOURCE_WEIGHTS.get(item, 1) * quantity <= self.carry_capacity

    def public_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "position": {"x": self.position.x, "y": self.position.y},
            "health": self.health,
            "alive": self.alive,
            "reputation": self.reputation,
            "groups": sorted(self.groups),
            "visible_carry": self.visible_carry_summary(),
            "visible_condition": self.visible_condition_summary(),
        }

    def visible_carry_summary(self) -> dict[str, Any]:
        weight = self.inventory_weight()
        if weight <= 0:
            load = "empty"
        elif weight >= self.carry_capacity:
            load = "full"
        elif weight >= self.carry_capacity * 0.75:
            load = "heavy"
        elif weight >= self.carry_capacity * 0.35:
            load = "some"
        else:
            load = "light"
        return {
            "load": load,
            "resource_types": sorted(item for item, quantity in self.inventory.items() if quantity > 0),
        }

    def visible_condition_summary(self) -> dict[str, str]:
        return {
            "health": _condition_band(self.health, maximum=100),
            "hunger": _reserve_condition_band(self.needs.food, FOOD_RESERVE_MAX),
            "thirst": _reserve_condition_band(self.needs.water, WATER_RESERVE_MAX),
            "energy": _reserve_condition_band(self.needs.energy, RESERVE_MAX),
        }


def _condition_band(value: int, maximum: int) -> str:
    ratio = value / maximum if maximum > 0 else 0
    if ratio <= 0:
        return "critical"
    if ratio <= 0.25:
        return "bad"
    if ratio <= 0.5:
        return "strained"
    if ratio < 1:
        return "reduced"
    return "ok"


def _reserve_condition_band(value: int, maximum: int) -> str:
    if value <= 0:
        return "critical"
    ratio = value / maximum if maximum > 0 else 0
    if ratio <= 0.25:
        return "low"
    if ratio <= 0.5:
        return "strained"
    return "ok"


@dataclass
class ItemPile:
    id: str
    item: str
    quantity: int
    position: Position
    owner_id: str | None = None

    def public_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "item": self.item,
            "quantity": self.quantity,
            "owner_id": self.owner_id,
        }


@dataclass
class Structure:
    id: str
    type: str
    position: Position
    owner_id: str
    inventory: Counter[str] = field(default_factory=Counter)
    access: set[str] = field(default_factory=set)
    durability: int = 100
    capacity: int = 120
    status: str = "complete"
    remaining_inputs: Counter[str] = field(default_factory=Counter)
    contributors: set[str] = field(default_factory=set)

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

    def inventory_weight(self) -> int:
        return sum(RESOURCE_WEIGHTS.get(item, 1) * qty for item, qty in self.inventory.items())

    def public_summary(self, include_inventory: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "position": {"x": self.position.x, "y": self.position.y},
            "owner_id": self.owner_id,
            "durability": self.durability,
            "capacity": self.capacity,
            "stored_weight": self.inventory_weight(),
            "status": self.status,
            "contributors": sorted(self.contributors),
        }
        if not self.is_complete:
            data["remaining_inputs"] = {item: qty for item, qty in self.remaining_inputs.items() if qty > 0}
        if include_inventory:
            data["inventory"] = dict(self.inventory)
        return data


@dataclass
class Tile:
    terrain: str
    resources: Counter[str] = field(default_factory=Counter)
    item_pile_ids: list[str] = field(default_factory=list)
    structure_ids: list[str] = field(default_factory=list)
    claimed_by: str | None = None
    access: set[str] = field(default_factory=set)

    def public_summary(self, include_private: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "terrain": self.terrain,
            "resources": dict(self.resources),
            "claimed_by": self.claimed_by,
            "structures": list(self.structure_ids),
            "item_piles": list(self.item_pile_ids),
        }
        if include_private:
            data["access"] = sorted(self.access)
        return data


@dataclass
class TradeOffer:
    id: str
    from_agent: str
    to_agent: str
    give: Counter[str]
    receive: Counter[str]
    created_tick: int
    expires_tick: int
    status: str = "open"
    accepted_by: str | None = None
    escrow_released: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "public": self.to_agent == "any",
            "accepted_by": self.accepted_by,
            "escrowed": not self.escrow_released,
            "give": dict(self.give),
            "receive": dict(self.receive),
            "created_tick": self.created_tick,
            "expires_tick": self.expires_tick,
            "status": self.status,
        }


@dataclass
class Group:
    id: str
    name: str
    founder_id: str
    members: set[str] = field(default_factory=set)
    invited: set[str] = field(default_factory=set)
    rules: list[str] = field(default_factory=list)
    agreements: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "founder_id": self.founder_id,
            "members": sorted(self.members),
            "invited": sorted(self.invited),
            "rules": list(self.rules),
            "agreements": list(self.agreements),
        }


@dataclass
class Event:
    tick: int
    type: str
    actor_id: str | None = None
    position: Position | None = None
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    scope: str = "local"
    recipients: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "type": self.type,
            "actor_id": self.actor_id,
            "position": None
            if self.position is None
            else {"x": self.position.x, "y": self.position.y},
            "message": self.message,
            "data": self.data,
            "scope": self.scope,
            "recipients": sorted(self.recipients),
        }


@dataclass
class AgentDecision:
    intent: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    memory_updates: list[str] = field(default_factory=list)

    @classmethod
    def from_json_like(cls, value: Any) -> "AgentDecision":
        if isinstance(value, AgentDecision):
            return value
        if not isinstance(value, dict):
            return cls(intent="Invalid response shape", actions=[{"type": "wait"}])
        actions = value.get("actions", [])
        messages = value.get("messages", [])
        memory_updates = value.get("memory_updates", [])
        if not isinstance(actions, list):
            actions = [{"type": "wait"}]
        if not isinstance(messages, list):
            messages = []
        if not isinstance(memory_updates, list):
            memory_updates = []
        return cls(
            intent=str(value.get("intent", ""))[:500],
            actions=[_normalize_action(a) for a in actions if isinstance(a, dict)],
            messages=[m for m in messages if isinstance(m, dict)],
            memory_updates=[str(m)[:500] for m in memory_updates],
        )


@dataclass
class WorldState:
    config: WorldConfig
    tick: int
    tiles: list[list[Tile]]
    agents: dict[str, Agent] = field(default_factory=dict)
    item_piles: dict[str, ItemPile] = field(default_factory=dict)
    structures: dict[str, Structure] = field(default_factory=dict)
    trades: dict[str, TradeOffer] = field(default_factory=dict)
    groups: dict[str, Group] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    next_item_id: int = 1
    next_structure_id: int = 1
    next_trade_id: int = 1
    next_group_id: int = 1
    build_ready_ever: set[str] = field(default_factory=set)
    capacity_samples: list[dict[str, int]] = field(default_factory=list)

    def tile_at(self, position: Position) -> Tile:
        return self.tiles[position.y][position.x]


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    """Accept the old fields-wrapper shape while preserving the flat action contract."""

    fields = action.get("fields")
    if not isinstance(fields, dict):
        return action
    normalized = {key: value for key, value in action.items() if key != "fields"}
    for key, value in fields.items():
        normalized.setdefault(str(key), value)
    return normalized
