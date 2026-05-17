"""Deterministic world engine for Agent World."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
import random
from typing import Any, Iterable

from agent_world.models import (
    Agent,
    AgentDecision,
    Event,
    Group,
    ItemPile,
    Position,
    Structure,
    Tile,
    TradeOffer,
    WorldConfig,
    WorldState,
)
from agent_world.rules import (
    CONSUMABLE_EFFECTS,
    DIRECTIONS,
    RECIPES,
    RESOURCE_VALUES,
    RESOURCE_WEIGHTS,
    TERRAIN_RULES,
    WORK_ACTIONS,
)


class WorldEngine:
    """Source-of-truth simulation engine.

    Agents can propose actions, but this engine validates resources, position,
    ownership, carrying capacity, action points, and survival changes.
    """

    def __init__(self, state: WorldState):
        self.state = state
        self.rng = random.Random(state.config.seed)

    @classmethod
    def create(
        cls,
        config: WorldConfig | None = None,
        agent_names: Iterable[str] | None = None,
    ) -> "WorldEngine":
        config = config or WorldConfig()
        rng = random.Random(config.seed)
        tiles = cls._generate_tiles(config, rng)
        state = WorldState(config=config, tick=0, tiles=tiles)
        engine = cls(state)
        for index, name in enumerate(agent_names or []):
            engine.spawn_agent(name=name, agent_id=f"agent-{index + 1}")
        engine.log_event("world_created", message="World initialized", scope="public")
        return engine

    @staticmethod
    def _generate_tiles(config: WorldConfig, rng: random.Random) -> list[list[Tile]]:
        tiles: list[list[Tile]] = []
        center_x = config.width // 2
        center_y = config.height // 2
        for y in range(config.height):
            row: list[Tile] = []
            for x in range(config.width):
                distance_from_center = abs(x - center_x) + abs(y - center_y)
                roll = rng.random()
                if distance_from_center <= 2:
                    terrain = "plains"
                elif roll < 0.11:
                    terrain = "water"
                elif roll < 0.34:
                    terrain = "forest"
                elif roll < 0.48:
                    terrain = "mountain"
                else:
                    terrain = "plains"
                resources = Counter(TERRAIN_RULES[terrain].base_resources)
                row.append(Tile(terrain=terrain, resources=resources))
            tiles.append(row)
        return tiles

    def spawn_agent(
        self,
        name: str,
        agent_id: str | None = None,
        position: Position | None = None,
    ) -> Agent:
        agent_id = agent_id or f"agent-{len(self.state.agents) + 1}"
        if agent_id in self.state.agents:
            raise ValueError(f"Agent id already exists: {agent_id}")
        position = position or self._find_spawn_position(len(self.state.agents))
        agent = Agent(
            id=agent_id,
            name=name,
            position=position,
            carry_capacity=self.state.config.default_carry_capacity,
            skills={
                "foraging": 1,
                "woodcraft": 1,
                "mining": 1,
                "farming": 1,
                "fishing": 1,
                "crafting": 1,
            },
        )
        agent.inventory.update({"food": 2, "water": 2})
        self.state.agents[agent.id] = agent
        self.log_event(
            "agent_spawned",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} entered the world.",
            data={"agent": agent.public_summary()},
            scope="public",
        )
        return agent

    def _find_spawn_position(self, offset: int) -> Position:
        candidates: list[Position] = []
        center = Position(self.state.config.width // 2, self.state.config.height // 2)
        for radius in range(max(self.state.config.width, self.state.config.height)):
            for y in range(self.state.config.height):
                for x in range(self.state.config.width):
                    pos = Position(x, y)
                    if center.distance_to(pos) == radius and self._can_occupy(pos):
                        candidates.append(pos)
            if candidates:
                return candidates[offset % len(candidates)]
        raise RuntimeError("No valid spawn position found")

    def log_event(
        self,
        event_type: str,
        actor_id: str | None = None,
        position: Position | None = None,
        message: str = "",
        data: dict[str, Any] | None = None,
        scope: str = "local",
        recipients: Iterable[str] | None = None,
    ) -> Event:
        event = Event(
            tick=self.state.tick,
            type=event_type,
            actor_id=actor_id,
            position=position,
            message=message,
            data=data or {},
            scope=scope,
            recipients=set(recipients or []),
        )
        self.state.events.append(event)
        return event

    def tick(self, decisions: dict[str, AgentDecision | dict[str, Any]]) -> list[Event]:
        before = len(self.state.events)
        self._expire_trades()
        for agent_id in sorted(self.state.agents):
            agent = self.state.agents[agent_id]
            if not agent.alive:
                continue
            decision = AgentDecision.from_json_like(decisions.get(agent_id, AgentDecision(actions=[{"type": "wait"}])))
            self._remember(agent, decision.memory_updates)
            self.log_event(
                "agent_response",
                actor_id=agent.id,
                position=agent.position,
                message=decision.intent,
                data={
                    "intent": decision.intent,
                    "actions": decision.actions,
                    "messages": decision.messages,
                    "memory_updates": decision.memory_updates,
                },
                scope="private",
                recipients={agent.id},
            )
            self._process_decision(agent, decision)
        self._apply_survival()
        self._regenerate_resources()
        self.state.tick += 1
        return self.state.events[before:]

    def _process_decision(self, agent: Agent, decision: AgentDecision) -> None:
        action_points = self.state.config.action_points_per_tick
        for message in decision.messages:
            if action_points <= 0:
                break
            action_points = self._handle_message(agent, message, action_points)
        if not decision.actions:
            decision.actions = [{"type": "wait"}]
        for action in decision.actions:
            if action_points <= 0:
                self._invalid(agent, action, "No action points remain this tick.")
                break
            action_points = self._dispatch_action(agent, action, action_points)

    def _dispatch_action(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        action_type = str(action.get("type", "")).strip()
        handlers = {
            "wait": self._action_wait,
            "move": self._action_move,
            "inspect": self._action_inspect,
            "gather": self._action_work,
            "chop": self._action_work,
            "mine": self._action_work,
            "harvest": self._action_work,
            "fish": self._action_work,
            "farm": self._action_farm,
            "craft": self._action_craft,
            "repair": self._action_repair,
            "pick_up": self._action_pick_up,
            "drop": self._action_drop,
            "claim_item": self._action_claim_item,
            "consume": self._action_consume,
            "equip": self._action_equip,
            "store": self._action_store,
            "retrieve": self._action_retrieve,
            "say": self._action_say,
            "whisper": self._action_whisper,
            "broadcast": self._action_broadcast,
            "offer_trade": self._action_offer_trade,
            "accept_trade": self._action_accept_trade,
            "reject_trade": self._action_reject_trade,
            "gift": self._action_gift,
            "claim_tile": self._action_claim_tile,
            "contest_claim": self._action_contest_claim,
            "build": self._action_build,
            "grant_access": self._action_grant_access,
            "revoke_access": self._action_revoke_access,
            "create_group": self._action_create_group,
            "invite_member": self._action_invite_member,
            "join_group": self._action_join_group,
            "leave_group": self._action_leave_group,
            "publish_rule": self._action_publish_rule,
            "record_agreement": self._action_record_agreement,
        }
        handler = handlers.get(action_type)
        if handler is None:
            self._invalid(agent, action, f"Unknown action type: {action_type}")
            return action_points - 1
        return handler(agent, action, action_points)

    def _action_wait(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        rest_gain = 6
        if self._agent_in_structure(agent, "shelter"):
            rest_gain += 4
        agent.needs.energy = min(100, agent.needs.energy + rest_gain)
        self.log_event("wait", actor_id=agent.id, position=agent.position, message=f"{agent.name} waited.")
        return action_points - 1

    def _action_move(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        direction = str(action.get("direction", ""))
        if direction not in DIRECTIONS:
            self._invalid(agent, action, "Move requires direction north, south, east, or west.")
            return action_points - 1
        dx, dy = DIRECTIONS[direction]
        destination = agent.position.shifted(dx, dy)
        if not self.in_bounds(destination):
            self._invalid(agent, action, "Destination is outside world bounds.")
            return action_points - 1
        terrain = self.state.tile_at(destination).terrain
        cost = TERRAIN_RULES[terrain].move_cost
        if action_points < cost:
            self._invalid(agent, action, f"Moving into {terrain} requires {cost} action points.")
            return 0
        if not self._can_occupy(destination):
            self._invalid(agent, action, "Destination occupancy limit is full or terrain is impassable.")
            return action_points - cost
        if agent.needs.energy < cost:
            self._invalid(agent, action, "Not enough energy to move.")
            return action_points - cost
        old = agent.position
        agent.position = destination
        agent.needs.energy = max(0, agent.needs.energy - cost)
        self.log_event(
            "move",
            actor_id=agent.id,
            position=destination,
            message=f"{agent.name} moved {direction}.",
            data={"from": asdict(old), "to": asdict(destination), "terrain": terrain},
        )
        return action_points - cost

    def _action_inspect(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target = self._target_position(action, default=agent.position)
        if not self.in_bounds(target):
            self._invalid(agent, action, "Cannot inspect outside world bounds.")
            return action_points - 1
        if agent.position.distance_to(target) > self.state.config.visible_radius:
            self._invalid(agent, action, "Cannot inspect beyond visibility radius.")
            return action_points - 1
        tile = self.state.tile_at(target)
        self.log_event(
            "inspect",
            actor_id=agent.id,
            position=target,
            message=f"{agent.name} inspected ({target.x}, {target.y}).",
            data={"tile": tile.public_summary(include_private=tile.claimed_by == agent.id)},
            scope="private",
            recipients={agent.id},
        )
        return action_points - 1

    def _action_work(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        action_type = str(action.get("type"))
        rule = WORK_ACTIONS[action_type]
        cost = int(rule["action_points"])
        energy = int(rule["energy"])
        if action_points < cost:
            self._invalid(agent, action, f"{action_type} requires {cost} action points.")
            return 0
        if agent.needs.energy < energy:
            self._invalid(agent, action, f"{action_type} requires {energy} energy.")
            return action_points - cost
        tile = self.state.tile_at(agent.position)
        resource = str(action.get("resource") or self._first_available(tile.resources, rule["resources"]))
        allowed = set(rule["resources"])
        if resource not in allowed:
            self._invalid(agent, action, f"{action_type} cannot produce {resource}.")
            return action_points - cost
        if action_type == "fish" and not self._near_terrain(agent.position, "water"):
            self._invalid(agent, action, "Fishing requires being on or adjacent to water.")
            return action_points - cost
        if tile.resources.get(resource, 0) <= 0:
            self._invalid(agent, action, f"No {resource} is available on this tile.")
            return action_points - cost
        quantity = self._bounded_quantity(action.get("quantity"), default=1, maximum=2)
        quantity = min(quantity, tile.resources[resource])
        if not agent.can_carry(resource, quantity):
            self._invalid(agent, action, "Carrying capacity would be exceeded.")
            return action_points - cost
        tile.resources[resource] -= quantity
        agent.inventory[resource] += quantity
        agent.needs.energy = max(0, agent.needs.energy - energy)
        self._improve_skill(agent, str(rule["skill"]))
        self.log_event(
            action_type,
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} produced {quantity} {resource}.",
            data={"resource": resource, "quantity": quantity},
        )
        return action_points - cost

    def _action_farm(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        cost = 2
        energy = 6
        if action_points < cost:
            self._invalid(agent, action, "farm requires 2 action points.")
            return 0
        if agent.needs.energy < energy:
            self._invalid(agent, action, "farm requires 6 energy.")
            return action_points - cost
        tile = self.state.tile_at(agent.position)
        if tile.terrain not in {"plains", "forest"}:
            self._invalid(agent, action, "Farming requires plains or forest terrain.")
            return action_points - cost
        tile.resources["food"] += 2
        agent.needs.energy = max(0, agent.needs.energy - energy)
        self._improve_skill(agent, "farming")
        self.log_event(
            "farm",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} tended food-producing land.",
            data={"resource": "food", "quantity_added": 2},
        )
        return action_points - cost

    def _action_craft(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        recipe_name = str(action.get("recipe", ""))
        recipe = RECIPES.get(recipe_name)
        if recipe is None:
            self._invalid(agent, action, f"Unknown recipe: {recipe_name}")
            return action_points - 1
        if recipe_name in {"storage", "shelter"}:
            return self._action_build(agent, {"type": "build", "structure": recipe_name}, action_points)
        if action_points < recipe.action_points:
            self._invalid(agent, action, f"Crafting {recipe_name} requires {recipe.action_points} action points.")
            return 0
        if agent.needs.energy < recipe.energy:
            self._invalid(agent, action, f"Crafting {recipe_name} requires {recipe.energy} energy.")
            return action_points - recipe.action_points
        missing = self._missing(agent.inventory, recipe.inputs)
        if missing:
            self._invalid(agent, action, f"Missing inputs: {missing}")
            return action_points - recipe.action_points
        for item, qty in recipe.inputs.items():
            agent.inventory[item] -= qty
        for item, qty in recipe.outputs.items():
            agent.inventory[item] += qty
        agent.needs.energy = max(0, agent.needs.energy - recipe.energy)
        self._improve_skill(agent, "crafting")
        self.log_event(
            "craft",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} crafted {recipe_name}.",
            data={"recipe": recipe_name, "outputs": dict(recipe.outputs)},
        )
        return action_points - recipe.action_points

    def _action_repair(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        structure = self._get_structure(str(action.get("structure_id", "")))
        if structure is None:
            self._invalid(agent, action, "Unknown structure.")
            return action_points - 1
        if not self._can_access_structure(agent, structure):
            self._invalid(agent, action, "No access to repair this structure.")
            return action_points - 1
        if agent.inventory.get("wood", 0) < 1:
            self._invalid(agent, action, "Repair requires 1 wood.")
            return action_points - 1
        agent.inventory["wood"] -= 1
        structure.durability = min(100, structure.durability + 20)
        self.log_event(
            "repair",
            actor_id=agent.id,
            position=structure.position,
            message=f"{agent.name} repaired {structure.id}.",
            data={"structure_id": structure.id, "durability": structure.durability},
        )
        return action_points - 1

    def _action_pick_up(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        pile = self._find_pile_on_tile(agent.position, action)
        if pile is None:
            self._invalid(agent, action, "No matching item pile on this tile.")
            return action_points - 1
        quantity = self._bounded_quantity(action.get("quantity"), default=pile.quantity, maximum=pile.quantity)
        if not agent.can_carry(pile.item, quantity):
            self._invalid(agent, action, "Carrying capacity would be exceeded.")
            return action_points - 1
        agent.inventory[pile.item] += quantity
        pile.quantity -= quantity
        tile = self.state.tile_at(agent.position)
        if pile.owner_id and pile.owner_id != agent.id:
            agent.reputation -= 1
            self.log_event(
                "claimed_item_taken",
                actor_id=agent.id,
                position=agent.position,
                message=f"{agent.name} picked up claimed {pile.item}.",
                data={"pile_id": pile.id, "owner_id": pile.owner_id, "item": pile.item, "quantity": quantity},
            )
        else:
            self.log_event(
                "pick_up",
                actor_id=agent.id,
                position=agent.position,
                message=f"{agent.name} picked up {quantity} {pile.item}.",
                data={"pile_id": pile.id, "item": pile.item, "quantity": quantity},
            )
        if pile.quantity <= 0:
            tile.item_pile_ids.remove(pile.id)
            del self.state.item_piles[pile.id]
        return action_points - 1

    def _action_drop(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        item = str(action.get("item", ""))
        if agent.inventory.get(item, 0) <= 0:
            self._invalid(agent, action, f"No {item} in inventory.")
            return action_points - 1
        quantity = self._bounded_quantity(action.get("quantity"), default=1, maximum=agent.inventory[item])
        agent.inventory[item] -= quantity
        pile = self._create_item_pile(item, quantity, agent.position, owner_id=agent.id)
        self.log_event(
            "drop",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} dropped {quantity} {item}.",
            data={"pile_id": pile.id, "item": item, "quantity": quantity, "owner_id": agent.id},
        )
        return action_points - 1

    def _action_claim_item(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        pile = self.state.item_piles.get(str(action.get("pile_id", "")))
        if pile is None or pile.position != agent.position:
            self._invalid(agent, action, "Item pile is not on this tile.")
            return action_points - 1
        if pile.owner_id and pile.owner_id != agent.id:
            self._invalid(agent, action, "Item pile is already claimed by another agent.")
            return action_points - 1
        pile.owner_id = agent.id
        self.log_event(
            "claim_item",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} claimed {pile.id}.",
            data={"pile_id": pile.id},
        )
        return action_points - 1

    def _action_consume(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        item = str(action.get("item", "food"))
        if item not in CONSUMABLE_EFFECTS:
            self._invalid(agent, action, f"{item} is not consumable.")
            return action_points - 1
        quantity = self._bounded_quantity(action.get("quantity"), default=1, maximum=agent.inventory.get(item, 0))
        if quantity <= 0:
            self._invalid(agent, action, f"No {item} available to consume.")
            return action_points - 1
        agent.inventory[item] -= quantity
        for need, amount in CONSUMABLE_EFFECTS[item].items():
            setattr(agent.needs, need, min(100, getattr(agent.needs, need) + amount * quantity))
        agent.needs.clamp()
        self.log_event(
            "consume",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} consumed {quantity} {item}.",
            data={"item": item, "quantity": quantity, "needs": agent.needs.as_dict()},
            scope="private",
            recipients={agent.id},
        )
        return action_points - 1

    def _action_equip(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        item = str(action.get("item", ""))
        if agent.inventory.get(item, 0) <= 0:
            self._invalid(agent, action, f"No {item} available to equip.")
            return action_points - 1
        agent.equipped.add(item)
        self.log_event(
            "equip",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} equipped {item}.",
            data={"item": item},
            scope="private",
            recipients={agent.id},
        )
        return action_points - 1

    def _action_store(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        structure = self._get_structure(str(action.get("structure_id", "")))
        if structure is None or structure.position != agent.position:
            self._invalid(agent, action, "Structure is not on this tile.")
            return action_points - 1
        if structure.type != "storage":
            self._invalid(agent, action, "Only storage structures can store inventory.")
            return action_points - 1
        if not self._can_access_structure(agent, structure):
            self._invalid(agent, action, "No access to this storage.")
            return action_points - 1
        item = str(action.get("item", ""))
        quantity = self._bounded_quantity(action.get("quantity"), default=1, maximum=agent.inventory.get(item, 0))
        if quantity <= 0:
            self._invalid(agent, action, f"No {item} available to store.")
            return action_points - 1
        added_weight = RESOURCE_WEIGHTS.get(item, 1) * quantity
        if structure.inventory_weight() + added_weight > structure.capacity:
            self._invalid(agent, action, "Storage capacity would be exceeded.")
            return action_points - 1
        agent.inventory[item] -= quantity
        structure.inventory[item] += quantity
        self.log_event(
            "store",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} stored {quantity} {item}.",
            data={"structure_id": structure.id, "item": item, "quantity": quantity},
        )
        return action_points - 1

    def _action_retrieve(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        structure = self._get_structure(str(action.get("structure_id", "")))
        if structure is None or structure.position != agent.position:
            self._invalid(agent, action, "Structure is not on this tile.")
            return action_points - 1
        if structure.type != "storage":
            self._invalid(agent, action, "Only storage structures can retrieve inventory.")
            return action_points - 1
        if not self._can_access_structure(agent, structure):
            self._invalid(agent, action, "No access to this storage.")
            return action_points - 1
        item = str(action.get("item", ""))
        quantity = self._bounded_quantity(action.get("quantity"), default=1, maximum=structure.inventory.get(item, 0))
        if quantity <= 0:
            self._invalid(agent, action, f"No {item} available in storage.")
            return action_points - 1
        if not agent.can_carry(item, quantity):
            self._invalid(agent, action, "Carrying capacity would be exceeded.")
            return action_points - 1
        structure.inventory[item] -= quantity
        agent.inventory[item] += quantity
        self.log_event(
            "retrieve",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} retrieved {quantity} {item}.",
            data={"structure_id": structure.id, "item": item, "quantity": quantity},
        )
        return action_points - 1

    def _handle_message(self, agent: Agent, message: dict[str, Any], action_points: int) -> int:
        mode = str(message.get("mode", "say"))
        action = {"type": mode, "text": message.get("text", ""), "to": message.get("to")}
        if mode not in {"say", "whisper", "broadcast"}:
            action["type"] = "say"
        return self._dispatch_action(agent, action, action_points)

    def _action_say(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        text = str(action.get("text", ""))[:1000]
        target = action.get("to")
        recipients = {str(target)} if target else set()
        self.log_event(
            "say",
            actor_id=agent.id,
            position=agent.position,
            message=text,
            data={"to": target},
            scope="local",
            recipients=recipients,
        )
        return action_points - 1

    def _action_whisper(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target_id = str(action.get("to", ""))
        target = self.state.agents.get(target_id)
        if target is None or not target.alive:
            self._invalid(agent, action, "Whisper target does not exist or is not alive.")
            return action_points - 1
        if agent.position.distance_to(target.position) > 1:
            self._invalid(agent, action, "Whisper target must be adjacent or on the same tile.")
            return action_points - 1
        text = str(action.get("text", ""))[:1000]
        self.log_event(
            "whisper",
            actor_id=agent.id,
            position=agent.position,
            message=text,
            scope="private",
            recipients={agent.id, target.id},
            data={"to": target.id},
        )
        return action_points - 1

    def _action_broadcast(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        text = str(action.get("text", ""))[:1000]
        self.log_event(
            "broadcast",
            actor_id=agent.id,
            position=agent.position,
            message=text,
            data={"radius": self.state.config.visible_radius * 2},
            scope="public",
        )
        return action_points - 1

    def _action_offer_trade(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target_id = str(action.get("to", ""))
        target = self.state.agents.get(target_id)
        if target is None or not target.alive:
            self._invalid(agent, action, "Trade target does not exist or is not alive.")
            return action_points - 1
        if agent.position.distance_to(target.position) > self.state.config.visible_radius:
            self._invalid(agent, action, "Trade target is outside visibility radius.")
            return action_points - 1
        give = self._counter_from_mapping(action.get("give", {}))
        receive = self._counter_from_mapping(action.get("receive", {}))
        if not give and not receive:
            self._invalid(agent, action, "Trade offer must include give or receive items.")
            return action_points - 1
        if self._missing(agent.inventory, give):
            self._invalid(agent, action, "Offerer does not currently hold the offered goods.")
            return action_points - 1
        trade_id = f"trade-{self.state.next_trade_id}"
        self.state.next_trade_id += 1
        expires_in = self._bounded_quantity(action.get("expires_in"), default=5, maximum=50)
        offer = TradeOffer(
            id=trade_id,
            from_agent=agent.id,
            to_agent=target.id,
            give=give,
            receive=receive,
            created_tick=self.state.tick,
            expires_tick=self.state.tick + expires_in,
        )
        self.state.trades[trade_id] = offer
        self.log_event(
            "offer_trade",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} offered a trade to {target.name}.",
            data={"trade": offer.summary()},
            recipients={target.id},
        )
        return action_points - 1

    def _action_accept_trade(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        trade = self.state.trades.get(str(action.get("trade_id", "")))
        if trade is None or trade.status != "open":
            self._invalid(agent, action, "Trade is not open.")
            return action_points - 1
        if trade.to_agent != agent.id:
            self._invalid(agent, action, "Only the trade recipient can accept this offer.")
            return action_points - 1
        offerer = self.state.agents.get(trade.from_agent)
        if offerer is None or not offerer.alive:
            self._invalid(agent, action, "Trade offerer is unavailable.")
            return action_points - 1
        if agent.position.distance_to(offerer.position) > self.state.config.visible_radius:
            self._invalid(agent, action, "Trade offerer is now outside visibility radius.")
            return action_points - 1
        if self._missing(offerer.inventory, trade.give):
            trade.status = "failed"
            self._invalid(agent, action, "Offerer no longer has offered goods.")
            return action_points - 1
        if self._missing(agent.inventory, trade.receive):
            self._invalid(agent, action, "Recipient lacks requested goods.")
            return action_points - 1
        if not self._can_carry_after_exchange(agent, remove=trade.receive, add=trade.give):
            self._invalid(agent, action, "Recipient carrying capacity would be exceeded.")
            return action_points - 1
        if not self._can_carry_after_exchange(offerer, remove=trade.give, add=trade.receive):
            self._invalid(agent, action, "Offerer carrying capacity would be exceeded.")
            return action_points - 1
        for item, qty in trade.give.items():
            offerer.inventory[item] -= qty
            agent.inventory[item] += qty
        for item, qty in trade.receive.items():
            agent.inventory[item] -= qty
            offerer.inventory[item] += qty
        trade.status = "accepted"
        offerer.relationships[agent.id] = offerer.relationships.get(agent.id, 0) + 1
        agent.relationships[offerer.id] = agent.relationships.get(offerer.id, 0) + 1
        self.log_event(
            "accept_trade",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} accepted {trade.id}.",
            data={"trade": trade.summary(), "value": self._trade_value(trade)},
            recipients={offerer.id},
        )
        return action_points - 1

    def _action_reject_trade(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        trade = self.state.trades.get(str(action.get("trade_id", "")))
        if trade is None or trade.status != "open":
            self._invalid(agent, action, "Trade is not open.")
            return action_points - 1
        if trade.to_agent != agent.id:
            self._invalid(agent, action, "Only the trade recipient can reject this offer.")
            return action_points - 1
        trade.status = "rejected"
        self.log_event(
            "reject_trade",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} rejected {trade.id}.",
            data={"trade": trade.summary()},
            recipients={trade.from_agent},
        )
        return action_points - 1

    def _action_gift(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target = self.state.agents.get(str(action.get("to", "")))
        if target is None or not target.alive:
            self._invalid(agent, action, "Gift target does not exist or is not alive.")
            return action_points - 1
        if agent.position.distance_to(target.position) > 1:
            self._invalid(agent, action, "Gift target must be adjacent or on the same tile.")
            return action_points - 1
        items = self._counter_from_mapping(action.get("items", {}))
        if not items:
            self._invalid(agent, action, "Gift requires items.")
            return action_points - 1
        if self._missing(agent.inventory, items):
            self._invalid(agent, action, "Agent lacks gifted items.")
            return action_points - 1
        if not self._can_carry_after_exchange(target, remove=Counter(), add=items):
            self._invalid(agent, action, "Target carrying capacity would be exceeded.")
            return action_points - 1
        for item, qty in items.items():
            agent.inventory[item] -= qty
            target.inventory[item] += qty
        target.relationships[agent.id] = target.relationships.get(agent.id, 0) + 1
        self.log_event(
            "gift",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} gifted items to {target.name}.",
            data={"to": target.id, "items": dict(items)},
            recipients={target.id},
        )
        return action_points - 1

    def _action_claim_tile(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        tile = self.state.tile_at(agent.position)
        if tile.claimed_by and tile.claimed_by != agent.id:
            self._invalid(agent, action, f"Tile already claimed by {tile.claimed_by}.")
            return action_points - 1
        tile.claimed_by = agent.id
        self.log_event(
            "claim_tile",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} claimed this tile.",
            data={"x": agent.position.x, "y": agent.position.y},
        )
        return action_points - 1

    def _action_contest_claim(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target = self._target_position(action, default=agent.position)
        if not self.in_bounds(target):
            self._invalid(agent, action, "Cannot contest outside world bounds.")
            return action_points - 1
        tile = self.state.tile_at(target)
        if not tile.claimed_by:
            self._invalid(agent, action, "Target tile is not claimed.")
            return action_points - 1
        self.log_event(
            "contest_claim",
            actor_id=agent.id,
            position=target,
            message=f"{agent.name} contested a tile claim.",
            data={"claimed_by": tile.claimed_by, "reason": str(action.get("reason", ""))[:500]},
        )
        return action_points - 1

    def _action_build(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        structure_type = str(action.get("structure", ""))
        recipe = RECIPES.get(structure_type)
        if structure_type not in {"storage", "shelter"} or recipe is None:
            self._invalid(agent, action, "Can only build storage or shelter.")
            return action_points - 1
        if action_points < recipe.action_points:
            self._invalid(agent, action, f"Building {structure_type} requires {recipe.action_points} action points.")
            return 0
        if agent.needs.energy < recipe.energy:
            self._invalid(agent, action, f"Building {structure_type} requires {recipe.energy} energy.")
            return action_points - recipe.action_points
        tile = self.state.tile_at(agent.position)
        if tile.claimed_by and tile.claimed_by != agent.id and agent.id not in tile.access:
            self._invalid(agent, action, "Cannot build on another agent's claimed tile without access.")
            return action_points - recipe.action_points
        missing = self._missing(agent.inventory, recipe.inputs)
        if missing:
            self._invalid(agent, action, f"Missing inputs: {missing}")
            return action_points - recipe.action_points
        for item, qty in recipe.inputs.items():
            agent.inventory[item] -= qty
        structure_id = f"structure-{self.state.next_structure_id}"
        self.state.next_structure_id += 1
        structure = Structure(
            id=structure_id,
            type=structure_type,
            position=agent.position,
            owner_id=agent.id,
            capacity=self.state.config.storage_capacity,
        )
        self.state.structures[structure.id] = structure
        tile.structure_ids.append(structure.id)
        if tile.claimed_by is None:
            tile.claimed_by = agent.id
        agent.needs.energy = max(0, agent.needs.energy - recipe.energy)
        self.log_event(
            "build",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} built {structure_type}.",
            data={"structure": structure.public_summary()},
        )
        return action_points - recipe.action_points

    def _action_grant_access(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target = str(action.get("target", ""))
        subject = str(action.get("subject", "tile"))
        if target not in self.state.agents:
            self._invalid(agent, action, "Target agent does not exist.")
            return action_points - 1
        changed = self._set_access(agent, subject, target, grant=True)
        if not changed:
            self._invalid(agent, action, "Agent does not control that subject.")
            return action_points - 1
        self.log_event(
            "grant_access",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} granted access to {target}.",
            data={"target": target, "subject": subject},
        )
        return action_points - 1

    def _action_revoke_access(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target = str(action.get("target", ""))
        subject = str(action.get("subject", "tile"))
        changed = self._set_access(agent, subject, target, grant=False)
        if not changed:
            self._invalid(agent, action, "Agent does not control that subject.")
            return action_points - 1
        self.log_event(
            "revoke_access",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} revoked access from {target}.",
            data={"target": target, "subject": subject},
        )
        return action_points - 1

    def _action_create_group(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        name = str(action.get("name", "")).strip()[:80]
        if not name:
            self._invalid(agent, action, "Group name is required.")
            return action_points - 1
        group_id = f"group-{self.state.next_group_id}"
        self.state.next_group_id += 1
        group = Group(id=group_id, name=name, founder_id=agent.id, members={agent.id})
        self.state.groups[group.id] = group
        agent.groups.add(group.id)
        self.log_event(
            "create_group",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} created group {name}.",
            data={"group": group.summary()},
            scope="public",
        )
        return action_points - 1

    def _action_invite_member(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        target = self.state.agents.get(str(action.get("target", "")))
        if group is None:
            self._invalid(agent, action, "Unknown group.")
            return action_points - 1
        if agent.id not in group.members:
            self._invalid(agent, action, "Only group members can invite.")
            return action_points - 1
        if target is None:
            self._invalid(agent, action, "Target agent does not exist.")
            return action_points - 1
        group.invited.add(target.id)
        self.log_event(
            "invite_member",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} invited {target.name} to {group.name}.",
            data={"group_id": group.id, "target": target.id},
            recipients={target.id},
        )
        return action_points - 1

    def _action_join_group(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        if group is None:
            self._invalid(agent, action, "Unknown group.")
            return action_points - 1
        if agent.id not in group.invited and agent.id != group.founder_id:
            self._invalid(agent, action, "Agent has not been invited to this group.")
            return action_points - 1
        group.members.add(agent.id)
        group.invited.discard(agent.id)
        agent.groups.add(group.id)
        self.log_event(
            "join_group",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} joined {group.name}.",
            data={"group": group.summary()},
            scope="public",
        )
        return action_points - 1

    def _action_leave_group(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        if group is None or agent.id not in group.members:
            self._invalid(agent, action, "Agent is not a member of this group.")
            return action_points - 1
        group.members.remove(agent.id)
        agent.groups.discard(group.id)
        self.log_event(
            "leave_group",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} left {group.name}.",
            data={"group": group.summary()},
            scope="public",
        )
        return action_points - 1

    def _action_publish_rule(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        text = str(action.get("text", "")).strip()[:1000]
        if group is None:
            self._invalid(agent, action, "Unknown group.")
            return action_points - 1
        if agent.id not in group.members:
            self._invalid(agent, action, "Only group members can publish rules.")
            return action_points - 1
        if not text:
            self._invalid(agent, action, "Rule text is required.")
            return action_points - 1
        group.rules.append(text)
        self.log_event(
            "publish_rule",
            actor_id=agent.id,
            position=agent.position,
            message=text,
            data={"group_id": group.id},
            scope="public",
        )
        return action_points - 1

    def _action_record_agreement(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        text = str(action.get("text", "")).strip()[:1000]
        parties = [str(p) for p in action.get("parties", []) if str(p) in self.state.agents]
        if agent.id not in parties:
            parties.append(agent.id)
        if not text:
            self._invalid(agent, action, "Agreement text is required.")
            return action_points - 1
        self.log_event(
            "record_agreement",
            actor_id=agent.id,
            position=agent.position,
            message=text,
            data={"parties": sorted(set(parties))},
            scope="public",
            recipients=set(parties),
        )
        return action_points - 1

    def _invalid(self, agent: Agent, action: dict[str, Any], reason: str) -> None:
        self.log_event(
            "invalid_action",
            actor_id=agent.id,
            position=agent.position,
            message=reason,
            data={"action": action},
            scope="private",
            recipients={agent.id},
        )

    def _apply_survival(self) -> None:
        for agent in self.state.agents.values():
            if not agent.alive:
                continue
            shelter_bonus = self._agent_in_structure(agent, "shelter")
            agent.needs.food -= self.state.config.survival_food_decay
            agent.needs.water -= self.state.config.survival_water_decay
            agent.needs.energy -= 0 if shelter_bonus else self.state.config.survival_energy_decay
            damage = 0
            if agent.needs.food <= 0:
                damage += 3
            if agent.needs.water <= 0:
                damage += 5
            if agent.needs.energy <= 0:
                damage += 1
            agent.needs.clamp()
            if damage:
                agent.health = max(0, agent.health - damage)
                self.log_event(
                    "survival_damage",
                    actor_id=agent.id,
                    position=agent.position,
                    message=f"{agent.name} suffered survival damage.",
                    data={"damage": damage, "health": agent.health, "needs": agent.needs.as_dict()},
                    scope="private",
                    recipients={agent.id},
                )
            if agent.health <= 0:
                agent.alive = False
                self.log_event(
                    "death",
                    actor_id=agent.id,
                    position=agent.position,
                    message=f"{agent.name} died.",
                    data={"needs": agent.needs.as_dict()},
                    scope="public",
                )

    def _regenerate_resources(self) -> None:
        for row in self.state.tiles:
            for tile in row:
                rule = TERRAIN_RULES[tile.terrain]
                for resource, rate in rule.regen.items():
                    maximum = rule.base_resources.get(resource, 0) * 2
                    if maximum <= 0 or tile.resources[resource] >= maximum:
                        continue
                    if self.rng.random() < rate:
                        tile.resources[resource] += 1

    def _expire_trades(self) -> None:
        for trade in self.state.trades.values():
            if trade.status == "open" and trade.expires_tick <= self.state.tick:
                trade.status = "expired"
                self.log_event(
                    "expire_trade",
                    actor_id=trade.from_agent,
                    message=f"{trade.id} expired.",
                    data={"trade": trade.summary()},
                    recipients={trade.from_agent, trade.to_agent},
                    scope="private",
                )

    def _remember(self, agent: Agent, memory_updates: list[str]) -> None:
        for memory in memory_updates:
            text = memory.strip()
            if text:
                agent.memory.append(f"tick {self.state.tick}: {text}")
        if len(agent.memory) > self.state.config.max_memory:
            agent.memory = agent.memory[-self.state.config.max_memory :]

    def _create_item_pile(self, item: str, quantity: int, position: Position, owner_id: str | None = None) -> ItemPile:
        pile_id = f"item-{self.state.next_item_id}"
        self.state.next_item_id += 1
        pile = ItemPile(id=pile_id, item=item, quantity=quantity, position=position, owner_id=owner_id)
        self.state.item_piles[pile.id] = pile
        self.state.tile_at(position).item_pile_ids.append(pile.id)
        return pile

    def _find_pile_on_tile(self, position: Position, action: dict[str, Any]) -> ItemPile | None:
        tile = self.state.tile_at(position)
        pile_id = action.get("pile_id")
        if pile_id:
            pile = self.state.item_piles.get(str(pile_id))
            if pile and pile.id in tile.item_pile_ids:
                return pile
            return None
        item = action.get("item")
        for candidate_id in tile.item_pile_ids:
            pile = self.state.item_piles[candidate_id]
            if item is None or pile.item == item:
                return pile
        return None

    def _can_occupy(self, position: Position) -> bool:
        if not self.in_bounds(position):
            return False
        tile = self.state.tile_at(position)
        rule = TERRAIN_RULES[tile.terrain]
        if not rule.passable:
            return False
        occupants = sum(1 for agent in self.state.agents.values() if agent.alive and agent.position == position)
        return occupants < rule.max_occupants

    def _agent_in_structure(self, agent: Agent, structure_type: str) -> bool:
        tile = self.state.tile_at(agent.position)
        return any(self.state.structures[sid].type == structure_type for sid in tile.structure_ids)

    def _get_structure(self, structure_id: str) -> Structure | None:
        return self.state.structures.get(structure_id)

    def _can_access_structure(self, agent: Agent, structure: Structure) -> bool:
        return structure.owner_id == agent.id or agent.id in structure.access

    def _set_access(self, agent: Agent, subject: str, target: str, grant: bool) -> bool:
        if subject == "tile":
            tile = self.state.tile_at(agent.position)
            if tile.claimed_by != agent.id:
                return False
            if grant:
                tile.access.add(target)
            else:
                tile.access.discard(target)
            return True
        structure = self.state.structures.get(subject)
        if structure is None or structure.owner_id != agent.id:
            return False
        if grant:
            structure.access.add(target)
        else:
            structure.access.discard(target)
        return True

    def _near_terrain(self, position: Position, terrain: str) -> bool:
        positions = [position]
        for dx, dy in DIRECTIONS.values():
            positions.append(position.shifted(dx, dy))
        return any(self.in_bounds(pos) and self.state.tile_at(pos).terrain == terrain for pos in positions)

    def _target_position(self, action: dict[str, Any], default: Position) -> Position:
        try:
            return Position(int(action.get("x", default.x)), int(action.get("y", default.y)))
        except (TypeError, ValueError):
            return default

    def _first_available(self, resources: Counter[str], allowed: object) -> str:
        for resource in sorted(allowed):
            if resources.get(resource, 0) > 0:
                return resource
        return sorted(allowed)[0]

    def _bounded_quantity(self, value: Any, default: int, maximum: int) -> int:
        try:
            quantity = int(value)
        except (TypeError, ValueError):
            quantity = default
        return max(0, min(quantity, maximum))

    def _counter_from_mapping(self, value: Any) -> Counter[str]:
        counter: Counter[str] = Counter()
        if not isinstance(value, dict):
            return counter
        for item, qty in value.items():
            try:
                parsed = int(qty)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                counter[str(item)] += parsed
        return counter

    def _can_carry_after_exchange(
        self,
        agent: Agent,
        remove: Counter[str] | dict[str, int],
        add: Counter[str] | dict[str, int],
    ) -> bool:
        projected = Counter(agent.inventory)
        for item, qty in remove.items():
            projected[item] -= qty
        for item, qty in add.items():
            projected[item] += qty
        weight = sum(RESOURCE_WEIGHTS.get(item, 1) * max(0, qty) for item, qty in projected.items())
        return weight <= agent.carry_capacity

    def _missing(self, inventory: Counter[str], required: Counter[str] | dict[str, int]) -> dict[str, int]:
        missing: dict[str, int] = {}
        for item, qty in required.items():
            if inventory.get(item, 0) < qty:
                missing[item] = qty - inventory.get(item, 0)
        return missing

    def _improve_skill(self, agent: Agent, skill: str) -> None:
        agent.skills[skill] = agent.skills.get(skill, 0) + 1

    def _trade_value(self, trade: TradeOffer) -> dict[str, int]:
        return {
            "give": sum(RESOURCE_VALUES.get(item, 1) * qty for item, qty in trade.give.items()),
            "receive": sum(RESOURCE_VALUES.get(item, 1) * qty for item, qty in trade.receive.items()),
        }

    def in_bounds(self, position: Position) -> bool:
        return 0 <= position.x < self.state.config.width and 0 <= position.y < self.state.config.height

    def export_events_jsonl(self) -> str:
        return "\n".join(json.dumps(event.to_dict(), sort_keys=True) for event in self.state.events)

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.state.tick,
            "config": asdict(self.state.config),
            "agents": {agent_id: self._agent_snapshot(agent) for agent_id, agent in self.state.agents.items()},
            "structures": {sid: structure.public_summary(include_inventory=True) for sid, structure in self.state.structures.items()},
            "trades": {tid: trade.summary() for tid, trade in self.state.trades.items()},
            "groups": {gid: group.summary() for gid, group in self.state.groups.items()},
        }

    def _agent_snapshot(self, agent: Agent) -> dict[str, Any]:
        data = agent.public_summary()
        data.update(
            {
                "inventory": dict(agent.inventory),
                "needs": agent.needs.as_dict(),
                "skills": dict(agent.skills),
                "relationships": dict(agent.relationships),
                "memory": list(agent.memory),
                "equipped": sorted(agent.equipped),
                "carry_weight": agent.inventory_weight(),
                "carry_capacity": agent.carry_capacity,
            }
        )
        return data
