"""Dataclasses for Agent World state."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from agent_world.rules import RESOURCE_WEIGHTS


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
    action_points_per_tick: int = 3
    max_memory: int = 50
    recent_event_limit: int = 20
    default_carry_capacity: int = 24
    storage_capacity: int = 120
    survival_food_decay: int = 1
    survival_water_decay: int = 2
    survival_energy_decay: int = 1


@dataclass
class Needs:
    food: int = 80
    water: int = 80
    energy: int = 80

    def as_dict(self) -> dict[str, int]:
        return {"food": self.food, "water": self.water, "energy": self.energy}

    def clamp(self) -> None:
        self.food = max(0, min(100, self.food))
        self.water = max(0, min(100, self.water))
        self.energy = max(0, min(100, self.energy))


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
    carry_capacity: int = 24

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
        }


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

    def inventory_weight(self) -> int:
        return sum(RESOURCE_WEIGHTS.get(item, 1) * qty for item, qty in self.inventory.items())

    def public_summary(self, include_inventory: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "owner_id": self.owner_id,
            "durability": self.durability,
        }
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

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
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
    agreements: list[str] = field(default_factory=list)

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
            actions=[a for a in actions if isinstance(a, dict)],
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

    def tile_at(self, position: Position) -> Tile:
        return self.tiles[position.y][position.x]
