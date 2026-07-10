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
    CreditContract,
    Event,
    Group,
    ItemPile,
    Needs,
    Position,
    Structure,
    Tile,
    TradeOffer,
    WorldConfig,
    WorldState,
)
from agent_world.maps import build_standard_tiles, find_specialist_spawn, specialist_profile
from agent_world.rules import (
    BASE_WAIT_ENERGY_RECOVERY,
    CONSUMABLE_EFFECTS,
    DIRECTIONS,
    COMMUNICATION_ACTION_TYPES,
    RECIPES,
    RESOURCE_VALUES,
    RESOURCE_WEIGHTS,
    REST_STRUCTURE_ENERGY_BONUS,
    REST_STRUCTURE_TYPES,
    STORAGE_STRUCTURE_TYPES,
    STRUCTURE_CAPACITIES,
    STRUCTURE_TYPES,
    TERRAIN_RULES,
    FREE_ACTION_TYPES,
    GROUP_ADMIN_ACTION_TYPES,
    STRUCTURE_OPERATIONS,
    TOOL_ENERGY_DISCOUNT,
    TOOL_MAX_DURABILITY,
    TOOL_PRODUCTIVITY_BONUS,
    WORK_ACTIONS,
    WORKSHOP_CRAFTING_ENERGY_DISCOUNT,
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
        tiles = build_standard_tiles(config)
        state = WorldState(config=config, tick=0, tiles=tiles)
        engine = cls(state)
        for index, name in enumerate(agent_names or []):
            engine.spawn_agent(name=name, agent_id=f"agent-{index + 1}")
        engine.log_event("world_created", message="World initialized", scope="public")
        return engine

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
        spawn_index = len(self.state.agents)
        agent = Agent(
            id=agent_id,
            name=name,
            position=position,
            carry_capacity=self.state.config.default_carry_capacity,
            needs=self._starting_needs(),
            skills={
                "foraging": 1,
                "woodcraft": 1,
                "mining": 1,
                "farming": 1,
                "fishing": 1,
                "crafting": 1,
            },
        )
        agent.inventory.update({"food": 1, "water": 2})
        if self.state.config.geography_mode == "dispersed":
            self._apply_specialist_profile(agent, spawn_index)
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

    def _apply_specialist_profile(self, agent: Agent, offset: int) -> None:
        profile = specialist_profile(offset)
        specialty_skill = str(profile["skill"])
        agent.specialty = str(profile["specialty"])
        agent.skills[specialty_skill] = 4
        agent.aptitudes = {skill: 0.8 for skill in agent.skills}
        agent.aptitudes[specialty_skill] = 1.75
        agent.need_multipliers = {
            str(name): float(multiplier)
            for name, multiplier in dict(profile.get("need_multipliers", {})).items()
        }
        agent.inventory.update(dict(profile.get("endowment", {})))

    def _starting_needs(self) -> Needs:
        return Needs(
            food=min(self.state.config.food_reserve_start, self.state.config.food_reserve_max),
            water=min(self.state.config.water_reserve_start, self.state.config.water_reserve_max),
            energy=min(self.state.config.energy_reserve_start, self.state.config.energy_reserve_max),
        )

    def _clamp_needs(self, agent: Agent) -> None:
        agent.needs.food = max(0, min(self.state.config.food_reserve_max, agent.needs.food))
        agent.needs.water = max(0, min(self.state.config.water_reserve_max, agent.needs.water))
        agent.needs.energy = max(0, min(self.state.config.energy_reserve_max, agent.needs.energy))

    def _resource_regen_capacity(self, base_quantity: int) -> int:
        multiplier = self.state.config.resource_base_multiplier
        if base_quantity <= 0 or multiplier <= 0:
            return 0
        return max(1, int(round(base_quantity * multiplier))) * 2

    def _find_spawn_position(self, offset: int) -> Position:
        if self.state.config.geography_mode == "dispersed":
            return find_specialist_spawn(
                self.state.tiles,
                self.state.config,
                offset,
                occupied={agent.position for agent in self.state.agents.values() if agent.alive},
            )
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
        self._reset_structure_capacity()
        for agent_id in self._actor_order():
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
            spare_ap = self._process_decision(agent, decision)
            self.state.capacity_samples.append(
                {"spare_ap": max(0, spare_ap), "energy": max(0, agent.needs.energy)}
            )
        self._accumulate_build_readiness()
        self._apply_survival()
        self._apply_food_spoilage()
        self._regenerate_resources()
        # Offers remain actionable for the entire tick in which they are visible.
        self._expire_trades()
        self._settle_due_contracts()
        self._apply_structure_upkeep()
        self.state.tick += 1
        return self.state.events[before:]

    def _actor_order(self) -> list[str]:
        """Rotate resolution priority every tick while remaining seed-reproducible."""

        ordered = sorted(agent_id for agent_id, agent in self.state.agents.items() if agent.alive)
        if len(ordered) <= 1:
            return ordered
        direction = 1 if self.state.config.seed % 2 else -1
        offset = (self.state.tick * direction) % len(ordered)
        return ordered[offset:] + ordered[:offset]

    def _process_decision(self, agent: Agent, decision: AgentDecision) -> int:
        action_points = self.state.config.action_points_per_tick
        for message in decision.messages:
            action_points = self._handle_message(agent, message, action_points)
        if not decision.actions:
            decision.actions = [{"type": "wait"}]
        for action in decision.actions:
            if action_points <= 0 and not self._is_free_action(action):
                self._invalid(agent, action, "No action points remain this tick.")
                break
            action_points = self._dispatch_action(agent, action, action_points)
        return action_points

    def _is_free_action(self, action: dict[str, Any]) -> bool:
        action_type = str(action.get("type", "")).strip()
        return action_type in FREE_ACTION_TYPES and self._coordination_action_cost(action_type) == 0

    def _coordination_action_cost(self, action_type: str) -> int:
        if action_type in COMMUNICATION_ACTION_TYPES:
            return self.state.config.communication_cost()
        if action_type in GROUP_ADMIN_ACTION_TYPES:
            return self.state.config.group_admin_cost()
        return 0

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
            "offer_contract": self._action_offer_contract,
            "accept_contract": self._action_accept_contract,
            "repay_contract": self._action_repay_contract,
            "gift": self._action_gift,
            "claim_tile": self._action_claim_tile,
            "contest_claim": self._action_contest_claim,
            "build": self._action_build,
            "contribute": self._action_contribute,
            "set_access_fee": self._action_set_access_fee,
            "claim_dividend": self._action_claim_dividend,
            "maintain_structure": self._action_maintain_structure,
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
        coordination_cost = self._coordination_action_cost(action_type)
        if action_points < coordination_cost:
            self._invalid(agent, action, f"{action_type} requires {coordination_cost} action points in this treatment.")
            return 0
        return handler(agent, action, action_points - coordination_cost)

    def _action_wait(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        rest_gain = BASE_WAIT_ENERGY_RECOVERY
        rest_structures = self._agent_structure_types(agent) & REST_STRUCTURE_TYPES
        if "house" in rest_structures:
            rest_gain += REST_STRUCTURE_ENERGY_BONUS["house"]
        elif "shelter" in rest_structures:
            rest_gain += REST_STRUCTURE_ENERGY_BONUS["shelter"]
        agent.needs.energy = min(self.state.config.energy_reserve_max, agent.needs.energy + rest_gain)
        self.log_event(
            "wait",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} waited.",
            data={"energy_recovered": rest_gain, "rest_structures": sorted(rest_structures)},
        )
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
        skill_name = str(rule["skill"])
        tool_name = self._equipped_work_tool(agent)
        skill_yield_bonus, skill_energy_discount = self._skill_modifiers(agent, skill_name)
        tool_yield_bonus = TOOL_PRODUCTIVITY_BONUS.get(tool_name or "", 0)
        tool_energy_discount = TOOL_ENERGY_DISCOUNT.get(tool_name or "", 0)
        energy = max(1, int(rule["energy"]) - skill_energy_discount - tool_energy_discount)
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
        source_position = agent.position
        source_tile = tile
        source_kind = "tile"
        source_structure: Structure | None = None
        productive_structure: Structure | None = None
        if action_type == "fish":
            resource = "food"
            water_source = self._nearby_water_source(agent.position, resource)
            if water_source is None:
                self._invalid(agent, action, "Fishing requires fishable food in current or adjacent water.")
                return action_points - cost
            source_position, source_tile = water_source
            source_kind = "open_water"
        elif action_type == "gather" and resource == "water" and tile.resources.get("water", 0) <= 0:
            well = self._accessible_structure_on_tile(agent, "well")
            if well is not None:
                source_kind = "well"
                source_structure = well
                productive_structure = well
            else:
                water_source = self._nearby_water_source(agent.position, "water")
                if water_source is None:
                    self._invalid(agent, action, "No water is available on this tile, from an accessible well, or adjacent water.")
                    self._notify_denied_structure_access(agent, "well")
                    return action_points - cost
                source_position, source_tile = water_source
                source_kind = "open_water"
        elif action_type == "gather" and resource == "water":
            source_kind = "open_water" if tile.terrain == "water" else "tile"
        elif action_type == "gather" and resource == "food":
            completed_farms = [
                self.state.structures[structure_id]
                for structure_id in tile.structure_ids
                if self.state.structures[structure_id].type == "farm_plot"
                and self.state.structures[structure_id].is_complete
            ]
            if completed_farms:
                productive_structure = self._accessible_structure_on_tile(agent, "farm_plot")
                if productive_structure is None:
                    self._invalid(agent, action, "Food on this improved tile requires access to its farm plot.")
                    return action_points - cost
        elif action_type == "harvest":
            productive_structure = self._accessible_structure_on_tile(agent, "farm_plot")
            if productive_structure is None:
                self._invalid(agent, action, "Harvesting requires an accessible farm plot on this tile.")
                return action_points - cost
        if (
            self.state.config.economy_mode == "commerce"
            and source_position == agent.position
            and tile.claimed_by
            and not self._controls_owner(agent, tile.claimed_by)
            and not self._has_access_grant(agent, tile.access)
            and productive_structure is None
        ):
            self._invalid(agent, action, "Resource extraction on this claimed tile requires access.")
            return action_points - cost
        if source_kind != "well" and source_tile.resources.get(resource, 0) <= 0:
            if source_position == agent.position:
                self._invalid(agent, action, f"No {resource} is available on this tile.")
            else:
                self._invalid(agent, action, f"No {resource} is available from adjacent water.")
            return action_points - cost
        max_quantity = int(rule.get("max_quantity", 2))
        requested = self._bounded_quantity(action.get("quantity"), default=1, maximum=max_quantity)
        quantity = requested + skill_yield_bonus + tool_yield_bonus
        if source_kind != "well":
            quantity = min(quantity, source_tile.resources[resource])
        quantity = min(quantity, self._carry_room(agent, resource))
        if quantity <= 0:
            if source_kind == "well":
                self._invalid(agent, action, "No water is available on this tile or adjacent water.")
            else:
                self._invalid(agent, action, f"No {resource} is available.")
            return action_points - cost
        if quantity < requested:
            self._invalid(agent, action, "Not enough source material or carrying capacity for the requested quantity.")
            return action_points - cost
        if productive_structure is not None and not self._use_productive_structure(agent, productive_structure, action):
            return action_points - cost
        depletes_source = not (
            action_type == "gather"
            and resource == "water"
            and source_kind in {"open_water", "well"}
        )
        if depletes_source:
            source_tile.resources[resource] -= quantity
        agent.inventory[resource] += quantity
        agent.needs.energy = max(0, agent.needs.energy - energy)
        self._improve_skill(agent, skill_name)
        tool_durability = self._wear_equipped_tool(agent, tool_name)
        improved_land = (
            resource == "food"
            and source_position == agent.position
            and self._accessible_structure_on_tile(agent, "farm_plot") is not None
        )
        source_note = " from improved land" if improved_land else ""
        if resource == "water" and source_kind == "well":
            source_note = " from a well"
        data = {
            "resource": resource,
            "quantity": quantity,
            "source_position": asdict(source_position),
            "improved_land": improved_land,
            "skill_yield_bonus": skill_yield_bonus,
            "tool_yield_bonus": tool_yield_bonus,
            "energy_cost": energy,
        }
        if tool_name is not None:
            data["tool"] = tool_name
            data["tool_durability"] = tool_durability
        if source_structure is not None:
            data["source"] = source_kind
            data["structure_id"] = source_structure.id
        self.log_event(
            action_type,
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} produced {quantity} {resource}{source_note}.",
            data=data,
        )
        return action_points - cost

    def _action_farm(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        cost = 2
        tool_name = self._equipped_work_tool(agent)
        skill_yield_bonus, skill_energy_discount = self._skill_modifiers(agent, "farming")
        tool_yield_bonus = TOOL_PRODUCTIVITY_BONUS.get(tool_name or "", 0)
        energy = max(1, 5 - skill_energy_discount - TOOL_ENERGY_DISCOUNT.get(tool_name or "", 0))
        if action_points < cost:
            self._invalid(agent, action, "farm requires 2 action points.")
            return 0
        if agent.needs.energy < energy:
            self._invalid(agent, action, f"farm requires {energy} energy.")
            return action_points - cost
        tile = self.state.tile_at(agent.position)
        if tile.terrain not in {"plains", "forest"}:
            self._invalid(agent, action, "Farming requires plains or forest terrain.")
            return action_points - cost
        farm_plot = self._accessible_structure_on_tile(agent, "farm_plot")
        if farm_plot is None:
            self._invalid(agent, action, "Farming requires a farm plot on this tile.")
            return action_points - cost
        cap = self.state.config.farm_food_capacity
        room = max(0, cap - tile.resources["food"])
        if room <= 0:
            self._invalid(agent, action, "This farm plot is already at its finite food capacity.")
            return action_points - cost
        if not self._use_productive_structure(agent, farm_plot, action):
            return action_points - cost
        quantity_added = min(room, self.state.config.farm_food_added + skill_yield_bonus + tool_yield_bonus)
        tile.resources["food"] += quantity_added
        agent.needs.energy = max(0, agent.needs.energy - energy)
        self._improve_skill(agent, "farming")
        tool_durability = self._wear_equipped_tool(agent, tool_name)
        self.log_event(
            "farm",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} tended a farm plot.",
            data={
                "resource": "food",
                "quantity_added": quantity_added,
                "structure_id": farm_plot.id,
                "mode": "farm_plot",
                "skill_yield_bonus": skill_yield_bonus,
                "tool_yield_bonus": tool_yield_bonus,
                "energy_cost": energy,
                "tool": tool_name,
                "tool_durability": tool_durability,
            },
        )
        return action_points - cost

    def _action_craft(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        recipe_name = str(action.get("recipe", ""))
        recipe = RECIPES.get(recipe_name)
        if recipe is None:
            self._invalid(agent, action, f"Unknown recipe: {recipe_name}")
            return action_points - 1
        if recipe_name in STRUCTURE_TYPES:
            return self._action_build(agent, {"type": "build", "structure": recipe_name}, action_points)
        if action_points < recipe.action_points:
            self._invalid(agent, action, f"Crafting {recipe_name} requires {recipe.action_points} action points.")
            return 0
        workshop = self._accessible_structure_on_tile(agent, "workshop")
        if recipe.required_structure and (workshop is None or workshop.type != recipe.required_structure):
            self._invalid(agent, action, f"Crafting {recipe_name} requires an accessible {recipe.required_structure}.")
            return action_points - recipe.action_points
        if recipe.required_tool and (
            recipe.required_tool not in agent.equipped or agent.inventory.get(recipe.required_tool, 0) <= 0
        ):
            self._invalid(agent, action, f"Crafting {recipe_name} requires equipped {recipe.required_tool}.")
            return action_points - recipe.action_points
        _, skill_energy_discount = self._skill_modifiers(agent, "crafting")
        energy_cost = max(
            1,
            recipe.energy
            - (WORKSHOP_CRAFTING_ENERGY_DISCOUNT if workshop else 0)
            - skill_energy_discount,
        )
        if agent.needs.energy < energy_cost:
            self._invalid(agent, action, f"Crafting {recipe_name} requires {energy_cost} energy.")
            return action_points - recipe.action_points
        missing = self._missing(agent.inventory, recipe.inputs)
        if missing:
            self._invalid(agent, action, f"Missing inputs: {missing}")
            return action_points - recipe.action_points
        if not self._inventory_exchange_fits(agent, remove=recipe.inputs, add=recipe.outputs):
            self._invalid(agent, action, "Crafted outputs would exceed carrying capacity.")
            return action_points - recipe.action_points
        if workshop is not None and not self._use_productive_structure(agent, workshop, action):
            return action_points - recipe.action_points
        for item, qty in recipe.inputs.items():
            agent.inventory[item] -= qty
        for item, qty in recipe.outputs.items():
            agent.inventory[item] += qty
        agent.needs.energy = max(0, agent.needs.energy - energy_cost)
        self._improve_skill(agent, "crafting")
        self.log_event(
            "craft",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} crafted {recipe_name}.",
            data={
                "recipe": recipe_name,
                "outputs": dict(recipe.outputs),
                "energy_cost": energy_cost,
                "skill_energy_discount": skill_energy_discount,
                "structure_id": workshop.id if workshop else None,
            },
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
            maximum = self.state.config.reserve_max_for(need)
            setattr(agent.needs, need, min(maximum, getattr(agent.needs, need) + amount * quantity))
        self._clamp_needs(agent)
        self.log_event(
            "consume",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} consumed {quantity} {item}.",
            data={"item": item, "quantity": quantity, "reserves": agent.needs.as_dict()},
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
        if item in TOOL_MAX_DURABILITY:
            agent.equipment_durability.setdefault(item, TOOL_MAX_DURABILITY[item])
        self.log_event(
            "equip",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} equipped {item}.",
            data={"item": item, "durability": agent.equipment_durability.get(item)},
            scope="private",
            recipients={agent.id},
        )
        return action_points - 1

    def _action_store(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        structure = self._get_structure(str(action.get("structure_id", "")))
        if structure is None or structure.position != agent.position:
            self._invalid(agent, action, "Structure is not on this tile.")
            return action_points - 1
        if structure.type not in STORAGE_STRUCTURE_TYPES:
            self._invalid(agent, action, "Only storage, house, or workshop structures can store inventory.")
            return action_points - 1
        if not structure.is_complete:
            self._invalid(agent, action, "Structure is still under construction.")
            return action_points - 1
        if self.state.config.economy_mode == "commerce" and not structure.active:
            self._invalid(agent, action, "Structure is inactive until upkeep is supplied.")
            return action_points - 1
        if not self._can_access_structure(agent, structure):
            self._invalid(agent, action, "No access to this storage.")
            self._notify_denied_structure_access(agent, structure.type, structure)
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
        if structure.type not in STORAGE_STRUCTURE_TYPES:
            self._invalid(agent, action, "Only storage, house, or workshop structures can retrieve inventory.")
            return action_points - 1
        if not structure.is_complete:
            self._invalid(agent, action, "Structure is still under construction.")
            return action_points - 1
        if self.state.config.economy_mode == "commerce" and not structure.active:
            self._invalid(agent, action, "Structure is inactive until upkeep is supplied.")
            return action_points - 1
        if not self._can_access_structure(agent, structure):
            self._invalid(agent, action, "No access to this storage.")
            self._notify_denied_structure_access(agent, structure.type, structure)
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
        return action_points

    def _action_whisper(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target_id = str(action.get("to", ""))
        target = self.state.agents.get(target_id)
        if target is None or not target.alive:
            self._invalid(agent, action, "Whisper target does not exist or is not alive.")
            return action_points
        if agent.position.distance_to(target.position) > 1:
            self._invalid(agent, action, "Whisper target must be adjacent or on the same tile.")
            return action_points
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
        return action_points

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
        return action_points

    def _action_offer_trade(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target_id = str(action.get("to") or "any").strip()
        public_offer = target_id in {"", "any", "public", "*"}
        target = None if public_offer else self.state.agents.get(target_id)
        if not public_offer:
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
        lots = self._bounded_quantity(
            action.get("lots"),
            default=1,
            maximum=20 if self.state.config.economy_mode == "commerce" else 1,
        )
        lots = max(1, lots)
        escrow = Counter({item: quantity * lots for item, quantity in give.items()})
        if self._missing(agent.inventory, escrow):
            self._invalid(agent, action, "Offerer does not currently hold the offered goods.")
            return action_points - 1
        for item, qty in escrow.items():
            agent.inventory[item] -= qty
        trade_id = f"trade-{self.state.next_trade_id}"
        self.state.next_trade_id += 1
        expires_in = self._bounded_quantity(action.get("expires_in"), default=5, maximum=50)
        requested_scope = str(action.get("scope", "")).strip().lower()
        market_scope = "global" if public_offer and self.state.config.economy_mode == "commerce" else "local"
        if requested_scope == "global" and public_offer and self.state.config.economy_mode == "commerce":
            market_scope = "global"
        offer = TradeOffer(
            id=trade_id,
            from_agent=agent.id,
            to_agent="any" if public_offer else target.id,
            give=give,
            receive=receive,
            created_tick=self.state.tick,
            expires_tick=self.state.tick + expires_in,
            market_scope=market_scope,
            lots_total=lots,
            lots_remaining=lots,
        )
        self.state.trades[trade_id] = offer
        self.log_event(
            "offer_trade",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} posted a public trade offer." if public_offer else f"{agent.name} offered a trade to {target.name}.",
            data={"trade": offer.summary()},
            scope="public" if market_scope == "global" else "local",
            recipients=set() if public_offer else {target.id},
        )
        return action_points - 1

    def _action_accept_trade(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        trade = self.state.trades.get(str(action.get("trade_id", "")))
        if trade is None or trade.status != "open":
            self._invalid(agent, action, "Trade is not open.")
            return action_points
        if trade.from_agent == agent.id:
            self._invalid(agent, action, "Agent cannot accept their own trade offer.")
            return action_points
        if trade.to_agent not in {"any", agent.id}:
            self._invalid(agent, action, "Only the trade recipient can accept this offer.")
            return action_points
        offerer = self.state.agents.get(trade.from_agent)
        if offerer is None or not offerer.alive:
            self._invalid(agent, action, "Trade offerer is unavailable.")
            return action_points
        if trade.market_scope != "global" and agent.position.distance_to(offerer.position) > self.state.config.visible_radius:
            self._invalid(agent, action, "Trade offerer is now outside visibility radius.")
            return action_points
        if trade.escrow_released:
            trade.status = "failed"
            self._invalid(agent, action, "Trade escrow is no longer available.")
            return action_points
        if self._missing(agent.inventory, trade.receive):
            self._invalid(agent, action, "Recipient lacks requested goods.")
            return action_points
        if not self._can_carry_after_exchange(agent, remove=trade.receive, add=trade.give):
            self._invalid(agent, action, "Recipient carrying capacity would be exceeded.")
            return action_points
        if not self._can_carry_after_exchange(offerer, remove=Counter(), add=trade.receive):
            self._invalid(agent, action, "Offerer carrying capacity would be exceeded.")
            return action_points
        for item, qty in trade.give.items():
            agent.inventory[item] += qty
        for item, qty in trade.receive.items():
            agent.inventory[item] -= qty
            offerer.inventory[item] += qty
        trade.lots_remaining -= 1
        trade.accepted_count += 1
        trade.status = "accepted" if trade.lots_remaining <= 0 else "open"
        trade.accepted_by = agent.id
        trade.escrow_released = trade.lots_remaining <= 0
        offerer.relationships[agent.id] = offerer.relationships.get(agent.id, 0) + 1
        agent.relationships[offerer.id] = agent.relationships.get(offerer.id, 0) + 1
        transaction = {
            "tick": self.state.tick,
            "trade_id": trade.id,
            "seller_id": offerer.id,
            "buyer_id": agent.id,
            "give": dict(trade.give),
            "receive": dict(trade.receive),
            "value": self._trade_value(trade),
            "market_scope": trade.market_scope,
            "lot_number": trade.accepted_count,
        }
        self.state.market_history.append(transaction)
        self.log_event(
            "accept_trade",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} accepted lot {trade.accepted_count} of {trade.id}.",
            data={"trade": trade.summary(), "value": self._trade_value(trade), "transaction": transaction},
            recipients={offerer.id},
        )
        return action_points

    def _action_reject_trade(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        trade = self.state.trades.get(str(action.get("trade_id", "")))
        if trade is None or trade.status != "open":
            self._invalid(agent, action, "Trade is not open.")
            return action_points
        if trade.to_agent == "any" and trade.from_agent == agent.id:
            pass
        elif trade.to_agent != agent.id:
            self._invalid(agent, action, "Only the trade recipient can reject this offer.")
            return action_points
        self._return_trade_escrow(trade)
        trade.status = "rejected"
        self.log_event(
            "reject_trade",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} rejected {trade.id}.",
            data={"trade": trade.summary()},
            recipients={trade.from_agent},
        )
        return action_points

    def _action_offer_contract(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        if self.state.config.economy_mode != "commerce":
            self._invalid(agent, action, "Credit contracts are enabled by the commerce treatment.")
            return action_points - 1
        borrower = self.state.agents.get(str(action.get("to", "")))
        if borrower is None or not borrower.alive or borrower.id == agent.id:
            self._invalid(agent, action, "Contract borrower must be another living agent.")
            return action_points - 1
        if agent.position.distance_to(borrower.position) > self.state.config.visible_radius:
            self._invalid(agent, action, "Contract borrower is outside visibility radius.")
            return action_points - 1
        advance = self._counter_from_mapping(action.get("advance", {}))
        repayment = self._counter_from_mapping(action.get("repayment", {}))
        collateral = self._counter_from_mapping(action.get("collateral", {}))
        if not advance or not repayment:
            self._invalid(agent, action, "A credit contract requires both an advance and repayment.")
            return action_points - 1
        if self._missing(agent.inventory, advance):
            self._invalid(agent, action, "Lender lacks the proposed advance.")
            return action_points - 1
        for item, quantity in advance.items():
            agent.inventory[item] -= quantity
        contract_id = f"contract-{self.state.next_contract_id}"
        self.state.next_contract_id += 1
        due_in = self._bounded_quantity(action.get("due_in"), default=5, maximum=100)
        due_in = max(1, due_in)
        expires_in = max(1, self._bounded_quantity(action.get("expires_in"), default=5, maximum=50))
        contract = CreditContract(
            id=contract_id,
            lender_id=agent.id,
            borrower_id=borrower.id,
            advance=advance,
            repayment=repayment,
            collateral=collateral,
            created_tick=self.state.tick,
            due_in=due_in,
            offer_expires_tick=self.state.tick + expires_in,
        )
        self.state.contracts[contract.id] = contract
        self.log_event(
            "create_contract",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} offered secured credit to {borrower.name}.",
            data={"contract": contract.summary()},
            scope="private",
            recipients={agent.id, borrower.id},
        )
        return action_points - 1

    def _action_accept_contract(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        contract = self.state.contracts.get(str(action.get("contract_id", "")))
        if contract is None or contract.status != "offered":
            self._invalid(agent, action, "Contract is not open.")
            return action_points
        if contract.borrower_id != agent.id:
            self._invalid(agent, action, "Only the named borrower can accept this contract.")
            return action_points
        lender = self.state.agents.get(contract.lender_id)
        if lender is None or not lender.alive:
            self._invalid(agent, action, "Contract lender is unavailable.")
            return action_points
        if self._missing(agent.inventory, contract.collateral):
            self._invalid(agent, action, "Borrower lacks the required collateral.")
            return action_points
        if not self._can_carry_after_exchange(agent, remove=contract.collateral, add=contract.advance):
            self._invalid(agent, action, "Advance would exceed borrower carrying capacity.")
            return action_points
        for item, quantity in contract.collateral.items():
            agent.inventory[item] -= quantity
        agent.inventory.update(contract.advance)
        contract.status = "active"
        contract.advance_released = True
        contract.due_tick = self.state.tick + contract.due_in
        self.log_event(
            "accept_contract",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} accepted {contract.id}; repayment is due at tick {contract.due_tick}.",
            data={"contract": contract.summary()},
            scope="private",
            recipients={contract.lender_id, contract.borrower_id},
        )
        return action_points

    def _action_repay_contract(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        contract = self.state.contracts.get(str(action.get("contract_id", "")))
        if contract is None or contract.status != "active":
            self._invalid(agent, action, "Contract is not active.")
            return action_points
        if contract.borrower_id != agent.id:
            self._invalid(agent, action, "Only the borrower can repay this contract.")
            return action_points
        if self._missing(agent.inventory, contract.repayment):
            self._invalid(agent, action, "Borrower lacks the full repayment.")
            return action_points
        self._fulfill_contract(contract, voluntary=True)
        return action_points

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
        owner_id = self._owner_for_action(agent, action)
        if owner_id is None:
            self._invalid(agent, action, "Agent is not a member of that group.")
            return action_points - 1
        if tile.claimed_by and tile.claimed_by != owner_id and not self._controls_owner(agent, tile.claimed_by):
            self._invalid(agent, action, f"Tile already claimed by {tile.claimed_by}.")
            return action_points - 1
        tile.claimed_by = owner_id
        self.log_event(
            "claim_tile",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} claimed this tile for {owner_id}.",
            data={"x": agent.position.x, "y": agent.position.y, "owner_id": owner_id},
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
        owner_id = self._owner_for_action(agent, action)
        if owner_id is None:
            self._invalid(agent, action, "Agent is not a member of that group.")
            return action_points - 1
        if structure_type not in STRUCTURE_TYPES or recipe is None:
            self._invalid(agent, action, "Can only build farm_plot, storage, shelter, house, workshop, or well.")
            return action_points - 1
        if action_points < recipe.action_points:
            self._invalid(agent, action, f"Building {structure_type} requires {recipe.action_points} action points.")
            return 0
        if agent.needs.energy < recipe.energy:
            self._invalid(agent, action, f"Building {structure_type} requires {recipe.energy} energy.")
            return action_points - recipe.action_points
        tile = self.state.tile_at(agent.position)
        if recipe.required_terrain and tile.terrain not in recipe.required_terrain:
            self._invalid(agent, action, f"Building {structure_type} requires terrain: {', '.join(recipe.required_terrain)}.")
            return action_points - recipe.action_points
        if structure_type == "farm_plot" and any(self.state.structures[sid].type == "farm_plot" for sid in tile.structure_ids):
            self._invalid(agent, action, "This tile already has a farm plot.")
            return action_points - recipe.action_points
        if structure_type == "well" and any(self.state.structures[sid].type == "well" for sid in tile.structure_ids):
            self._invalid(agent, action, "This tile already has a well.")
            return action_points - recipe.action_points
        if any(
            self.state.structures[sid].type == structure_type and not self.state.structures[sid].is_complete
            for sid in tile.structure_ids
        ):
            self._invalid(agent, action, f"A {structure_type} is already under construction here; contribute to it instead.")
            return action_points - recipe.action_points
        if tile.claimed_by and not self._controls_owner(agent, tile.claimed_by) and not self._has_access_grant(agent, tile.access):
            self._invalid(agent, action, "Cannot build on another agent's claimed tile without access.")
            return action_points - recipe.action_points
        structure_id = f"structure-{self.state.next_structure_id}"
        self.state.next_structure_id += 1
        operations = STRUCTURE_OPERATIONS.get(structure_type, {}) if self.state.config.economy_mode == "commerce" else {}
        uses_per_tick = int(operations.get("uses_per_tick", 0))
        structure = Structure(
            id=structure_id,
            type=structure_type,
            position=agent.position,
            owner_id=owner_id,
            capacity=STRUCTURE_CAPACITIES[structure_type],
            status="under_construction",
            remaining_inputs=Counter(recipe.inputs),
            uses_per_tick=uses_per_tick,
            uses_remaining=uses_per_tick,
            upkeep=Counter(dict(operations.get("upkeep", {}))),
            upkeep_interval=int(operations.get("upkeep_interval", 0)),
            last_upkeep_tick=self.state.tick,
        )
        self.state.structures[structure.id] = structure
        tile.structure_ids.append(structure.id)
        if tile.claimed_by is None:
            tile.claimed_by = owner_id
        agent.needs.energy = max(0, agent.needs.energy - recipe.energy)
        deposited = self._deposit_to_site(agent, structure, {item: agent.inventory.get(item, 0) for item in recipe.inputs})
        completed = self._finalize_site_if_ready(structure)
        if completed:
            self.log_event(
                "build",
                actor_id=agent.id,
                position=agent.position,
                message=f"{agent.name} built {structure_type}.",
                data={"structure": structure.public_summary(), "contributed": deposited},
            )
        else:
            self.log_event(
                "build_started",
                actor_id=agent.id,
                position=agent.position,
                message=f"{agent.name} started building {structure_type} (needs {dict(structure.remaining_inputs)}).",
                data={"structure": structure.public_summary(), "contributed": deposited},
            )
        return action_points - recipe.action_points

    def _action_contribute(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        structure = self._resolve_construction_site(agent, action)
        if structure is None:
            self._invalid(agent, action, "No matching structure is under construction on this tile.")
            return action_points - 1
        offered = self._contribution_items(action)
        if not offered:
            self._invalid(agent, action, 'Specify items to contribute, e.g. {"type":"contribute","structure":"house","items":{"wood":2}}.')
            return action_points - 1
        deposited = self._deposit_to_site(agent, structure, offered)
        if not deposited:
            self._invalid(agent, action, "Nothing contributed: you lack those materials or the structure does not need them.")
            return action_points - 1
        self.log_event(
            "contribute",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} contributed {deposited} to {structure.type} (still needs {dict(structure.remaining_inputs)}).",
            data={"structure_id": structure.id, "contributed": deposited, "remaining_inputs": dict(structure.remaining_inputs)},
        )
        if self._finalize_site_if_ready(structure):
            self.log_event(
                "build",
                actor_id=agent.id,
                position=agent.position,
                message=f"{agent.name} completed {structure.type} (built by {len(structure.contributors)} agent(s)).",
                data={"structure": structure.public_summary()},
            )
        return action_points - 1

    def _action_set_access_fee(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        if self.state.config.economy_mode != "commerce":
            self._invalid(agent, action, "Access fees are enabled by the commerce treatment.")
            return action_points
        structure = self._get_structure(str(action.get("structure_id", "")))
        if structure is None or structure.position != agent.position or not structure.is_complete:
            self._invalid(agent, action, "A completed structure on the current tile is required.")
            return action_points
        if not self._controls_owner(agent, structure.owner_id):
            self._invalid(agent, action, "Only the structure owner can set its access fee.")
            return action_points
        structure.access_fee = self._counter_from_mapping(action.get("fee", {}))
        if "public" in action:
            structure.public_access = self._as_bool(action.get("public"))
        self.log_event(
            "set_access_fee",
            actor_id=agent.id,
            position=structure.position,
            message=f"{agent.name} set {structure.id}'s public access policy.",
            data={
                "structure_id": structure.id,
                "public_access": structure.public_access,
                "fee": dict(structure.access_fee),
            },
            scope="public",
        )
        return action_points

    def _action_claim_dividend(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        structure = self._get_structure(str(action.get("structure_id", "")))
        if structure is None:
            self._invalid(agent, action, "Unknown structure.")
            return action_points
        credits = structure.dividend_credits.get(agent.id, Counter())
        item = str(action.get("item", ""))
        available = credits.get(item, 0)
        quantity = self._bounded_quantity(action.get("quantity"), default=available, maximum=available)
        quantity = min(quantity, self._carry_room(agent, item))
        if not item or quantity <= 0:
            self._invalid(agent, action, "No claimable dividend of that item or insufficient carrying capacity.")
            return action_points
        credits[item] -= quantity
        structure.treasury[item] -= quantity
        agent.inventory[item] += quantity
        self.log_event(
            "claim_dividend",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} claimed {quantity} {item} from {structure.id}.",
            data={"structure_id": structure.id, "item": item, "quantity": quantity},
            scope="private",
            recipients={agent.id},
        )
        return action_points

    def _action_maintain_structure(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        if self.state.config.economy_mode != "commerce":
            self._invalid(agent, action, "Structure upkeep is enabled by the commerce treatment.")
            return action_points - 1
        structure = self._get_structure(str(action.get("structure_id", "")))
        if structure is None or structure.position != agent.position or not structure.is_complete:
            self._invalid(agent, action, "A completed structure on the current tile is required.")
            return action_points - 1
        if not (self._controls_owner(agent, structure.owner_id) or agent.id in structure.contributors):
            self._invalid(agent, action, "Only owners or contributors can maintain this structure.")
            return action_points - 1
        offered = self._counter_from_mapping(action.get("items", {}))
        if not offered or self._missing(agent.inventory, offered):
            self._invalid(agent, action, "Maintenance requires carried upkeep materials.")
            return action_points - 1
        for item, quantity in offered.items():
            agent.inventory[item] -= quantity
            structure.upkeep_reserve[item] += quantity
        reactivated = False
        if not structure.active and not self._missing(structure.upkeep_reserve, structure.upkeep):
            for item, quantity in structure.upkeep.items():
                structure.upkeep_reserve[item] -= quantity
            structure.active = True
            structure.last_upkeep_tick = self.state.tick
            reactivated = True
        self.log_event(
            "maintain_structure",
            actor_id=agent.id,
            position=structure.position,
            message=f"{agent.name} supplied upkeep to {structure.id}.",
            data={"structure_id": structure.id, "items": dict(offered), "reactivated": reactivated},
        )
        return action_points - 1

    def _deposit_to_site(self, agent: Agent, structure: Structure, offered: dict[str, int]) -> dict[str, int]:
        """Move materials from an agent's inventory into a construction site, capped by what it still needs."""
        deposited: dict[str, int] = {}
        for item, qty in offered.items():
            need = structure.remaining_inputs.get(item, 0)
            have = agent.inventory.get(item, 0)
            amount = min(int(qty), need, have)
            if amount > 0:
                agent.inventory[item] -= amount
                structure.remaining_inputs[item] -= amount
                if structure.remaining_inputs[item] <= 0:
                    del structure.remaining_inputs[item]
                deposited[item] = amount
        if deposited:
            structure.contributors.add(agent.id)
            structure.contribution_units[agent.id] += sum(
                RESOURCE_VALUES.get(item, 1) * quantity for item, quantity in deposited.items()
            )
        return deposited

    def _finalize_site_if_ready(self, structure: Structure) -> bool:
        if not structure.is_complete and not any(qty > 0 for qty in structure.remaining_inputs.values()):
            structure.status = "complete"
            structure.remaining_inputs = Counter()
            return True
        return False

    def _resolve_construction_site(self, agent: Agent, action: dict[str, Any]) -> Structure | None:
        structure_id = str(action.get("structure_id", "")).strip()
        if structure_id:
            structure = self.state.structures.get(structure_id)
            if structure is not None and structure.position == agent.position and not structure.is_complete:
                return structure
            return None
        wanted_type = str(action.get("structure", "")).strip()
        for sid in self.state.tile_at(agent.position).structure_ids:
            structure = self.state.structures[sid]
            if not structure.is_complete and (not wanted_type or structure.type == wanted_type):
                return structure
        return None

    def _contribution_items(self, action: dict[str, Any]) -> dict[str, int]:
        items = action.get("items")
        parsed: dict[str, int] = {}
        if isinstance(items, dict):
            for key, value in items.items():
                try:
                    count = int(value)
                except (TypeError, ValueError):
                    continue
                if count > 0:
                    parsed[str(key)] = count
            return parsed
        item = action.get("item")
        if item:
            parsed[str(item)] = self._bounded_quantity(action.get("quantity"), default=1, maximum=1_000_000)
        return parsed

    def _action_grant_access(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target = str(action.get("target", ""))
        subject = str(action.get("subject", "tile"))
        if not self._access_target_exists(target):
            self._invalid(agent, action, "Target agent or group does not exist.")
            return action_points
        changed = self._set_access(agent, subject, target, grant=True)
        if not changed:
            self._invalid(agent, action, "Agent does not control that subject.")
            return action_points
        self.log_event(
            "grant_access",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} granted access to {target}.",
            data={"target": target, "subject": subject},
        )
        return action_points

    def _action_revoke_access(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        target = str(action.get("target", ""))
        subject = str(action.get("subject", "tile"))
        if not self._access_target_exists(target):
            self._invalid(agent, action, "Target agent or group does not exist.")
            return action_points
        changed = self._set_access(agent, subject, target, grant=False)
        if not changed:
            self._invalid(agent, action, "Agent does not control that subject.")
            return action_points
        self.log_event(
            "revoke_access",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} revoked access from {target}.",
            data={"target": target, "subject": subject},
        )
        return action_points

    def _action_create_group(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        name = str(action.get("name", "")).strip()[:80]
        if not name:
            self._invalid(agent, action, "Group name is required.")
            return action_points
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
        return action_points

    def _action_invite_member(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        target = self.state.agents.get(str(action.get("target", "")))
        if group is None:
            self._invalid(agent, action, "Unknown group.")
            return action_points
        if agent.id not in group.members:
            self._invalid(agent, action, "Only group members can invite.")
            return action_points
        if target is None:
            self._invalid(agent, action, "Target agent does not exist.")
            return action_points
        group.invited.add(target.id)
        self.log_event(
            "invite_member",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name} invited {target.name} to {group.name}.",
            data={"group_id": group.id, "target": target.id},
            recipients={target.id},
        )
        return action_points

    def _action_join_group(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        if group is None:
            self._invalid(agent, action, "Unknown group.")
            return action_points
        if agent.id not in group.invited and agent.id != group.founder_id:
            self._invalid(agent, action, "Agent has not been invited to this group.")
            return action_points
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
        return action_points

    def _action_leave_group(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        if group is None or agent.id not in group.members:
            self._invalid(agent, action, "Agent is not a member of this group.")
            return action_points
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
        return action_points

    def _action_publish_rule(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        group = self.state.groups.get(str(action.get("group_id", "")))
        text = str(action.get("text", "")).strip()[:1000]
        if group is None:
            self._invalid(agent, action, "Unknown group.")
            return action_points
        if agent.id not in group.members:
            self._invalid(agent, action, "Only group members can publish rules.")
            return action_points
        if not text:
            self._invalid(agent, action, "Rule text is required.")
            return action_points
        group.rules.append(text)
        self.log_event(
            "publish_rule",
            actor_id=agent.id,
            position=agent.position,
            message=text,
            data={"group_id": group.id},
            scope="public",
        )
        return action_points

    def _action_record_agreement(self, agent: Agent, action: dict[str, Any], action_points: int) -> int:
        text = str(action.get("text", "")).strip()[:1000]
        group = self.state.groups.get(str(action.get("group_id", "")))
        if action.get("group_id") and group is None:
            self._invalid(agent, action, "Unknown group.")
            return action_points
        if group is not None and agent.id not in group.members:
            self._invalid(agent, action, "Only group members can record group agreements.")
            return action_points
        parties = [str(p) for p in action.get("parties", []) if str(p) in self.state.agents]
        if agent.id not in parties:
            parties.append(agent.id)
        if not text:
            self._invalid(agent, action, "Agreement text is required.")
            return action_points
        agreement = {
            "tick": self.state.tick,
            "text": text,
            "parties": sorted(set(parties)),
            "recorded_by": agent.id,
        }
        if group is not None:
            group.agreements.append(agreement)
        self.log_event(
            "record_agreement",
            actor_id=agent.id,
            position=agent.position,
            message=text,
            data={"agreement": agreement, "group_id": group.id if group is not None else None},
            scope="public",
            recipients=set(parties),
        )
        return action_points

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
            shelter_bonus = bool(self._agent_structure_types(agent) & REST_STRUCTURE_TYPES)
            food_decay = int(round(self.state.config.survival_food_decay * agent.need_multipliers.get("food", 1.0)))
            water_decay = int(round(self.state.config.survival_water_decay * agent.need_multipliers.get("water", 1.0)))
            energy_decay = int(round(self.state.config.survival_energy_decay * agent.need_multipliers.get("energy", 1.0)))
            agent.needs.food -= food_decay
            agent.needs.water -= water_decay
            agent.needs.energy -= 0 if shelter_bonus else energy_decay
            damage = 0
            if agent.needs.food <= 0:
                damage += 3
            if agent.needs.water <= 0:
                damage += 5
            if agent.needs.energy <= 0:
                damage += self.state.config.exhaustion_damage
            self._clamp_needs(agent)
            if damage:
                agent.health = max(0, agent.health - damage)
                self.log_event(
                    "survival_damage",
                    actor_id=agent.id,
                    position=agent.position,
                    message=f"{agent.name} suffered survival damage.",
                    data={"damage": damage, "health": agent.health, "reserves": agent.needs.as_dict()},
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
                    data={"reserves": agent.needs.as_dict()},
                    scope="public",
                )

    def _apply_food_spoilage(self) -> None:
        interval = self.state.config.carried_food_spoil_interval
        if interval <= 0 or self.state.tick <= 0 or self.state.tick % interval != 0:
            return
        quantity = self.state.config.carried_food_spoil_quantity
        if quantity <= 0:
            return
        for agent in self.state.agents.values():
            if not agent.alive or agent.inventory.get("food", 0) <= 0:
                continue
            lost = min(quantity, agent.inventory["food"])
            agent.inventory["food"] -= lost
            self.log_event(
                "food_spoilage",
                actor_id=agent.id,
                position=agent.position,
                message=f"{agent.name} lost {lost} carried food to spoilage.",
                data={
                    "item": "food",
                    "quantity": lost,
                    "protected_storage_types": sorted(STORAGE_STRUCTURE_TYPES),
                    "remaining_food": agent.inventory.get("food", 0),
                },
                scope="private",
                recipients={agent.id},
            )

    def _regenerate_resources(self) -> None:
        for row in self.state.tiles:
            for tile in row:
                rule = TERRAIN_RULES[tile.terrain]
                for resource in rule.regen:
                    maximum = self._resource_regen_capacity(rule.base_resources.get(resource, 0))
                    if maximum <= 0 or tile.resources[resource] >= maximum:
                        continue
                    if self.rng.random() < min(1.0, self.state.config.regen_rate_for(tile.terrain, resource)):
                        tile.resources[resource] += 1
                if any(
                    self.state.structures[sid].type == "farm_plot"
                    and self.state.structures[sid].is_complete
                    and (
                        self.state.config.economy_mode != "commerce"
                        or self.state.structures[sid].active
                    )
                    for sid in tile.structure_ids
                ):
                    tile.resources["food"] = min(
                        self.state.config.farm_food_capacity,
                        tile.resources["food"] + self.state.config.farm_passive_food_growth,
                    )

    def _expire_trades(self) -> None:
        for trade in self.state.trades.values():
            if trade.status == "open" and trade.expires_tick <= self.state.tick:
                self._return_trade_escrow(trade)
                trade.status = "expired"
                self.log_event(
                    "expire_trade",
                    actor_id=trade.from_agent,
                    message=f"{trade.id} expired.",
                    data={"trade": trade.summary()},
                    recipients=self._trade_private_recipients(trade),
                    scope="private",
                )

    def _reset_structure_capacity(self) -> None:
        if self.state.config.economy_mode != "commerce":
            return
        for structure in self.state.structures.values():
            structure.uses_remaining = structure.uses_per_tick

    def _apply_structure_upkeep(self) -> None:
        if self.state.config.economy_mode != "commerce":
            return
        for structure in self.state.structures.values():
            if not structure.is_complete or structure.upkeep_interval <= 0:
                continue
            if self.state.tick - structure.last_upkeep_tick < structure.upkeep_interval:
                continue
            structure.last_upkeep_tick = self.state.tick
            if not self._missing(structure.upkeep_reserve, structure.upkeep):
                for item, quantity in structure.upkeep.items():
                    structure.upkeep_reserve[item] -= quantity
                structure.active = True
                self.log_event(
                    "structure_upkeep_paid",
                    actor_id=structure.owner_id if structure.owner_id in self.state.agents else None,
                    position=structure.position,
                    message=f"{structure.id} consumed its upkeep reserve.",
                    data={"structure_id": structure.id, "upkeep": dict(structure.upkeep)},
                )
                continue
            structure.active = False
            structure.durability = max(0, structure.durability - 10)
            self.log_event(
                "structure_upkeep_missed",
                actor_id=structure.owner_id if structure.owner_id in self.state.agents else None,
                position=structure.position,
                message=f"{structure.id} became inactive after missing upkeep.",
                data={
                    "structure_id": structure.id,
                    "required": dict(structure.upkeep),
                    "reserve": dict(structure.upkeep_reserve),
                    "durability": structure.durability,
                },
                scope="public",
            )

    def _settle_due_contracts(self) -> None:
        for contract in self.state.contracts.values():
            if contract.status == "offered" and contract.offer_expires_tick <= self.state.tick:
                contract.status = "expired"
                lender = self.state.agents.get(contract.lender_id)
                borrower = self.state.agents.get(contract.borrower_id)
                position = (
                    lender.position
                    if lender is not None
                    else borrower.position
                    if borrower is not None
                    else Position(self.state.config.width // 2, self.state.config.height // 2)
                )
                self._deliver_owned_items(contract.lender_id, contract.advance, position)
                self.log_event(
                    "expire_contract",
                    actor_id=contract.lender_id,
                    position=position,
                    message=f"{contract.id} expired and returned its advance.",
                    data={"contract": contract.summary()},
                    scope="private",
                    recipients={contract.lender_id, contract.borrower_id},
                )
                continue
            if contract.status != "active" or contract.due_tick is None or contract.due_tick > self.state.tick:
                continue
            borrower = self.state.agents.get(contract.borrower_id)
            if borrower is not None and not self._missing(borrower.inventory, contract.repayment):
                self._fulfill_contract(contract, voluntary=False)
                continue
            contract.status = "defaulted"
            contract.collateral_released = True
            lender = self.state.agents.get(contract.lender_id)
            delivery_position = (
                lender.position
                if lender is not None
                else borrower.position
                if borrower is not None
                else Position(self.state.config.width // 2, self.state.config.height // 2)
            )
            self._deliver_owned_items(contract.lender_id, contract.collateral, delivery_position)
            if borrower is not None:
                borrower.reputation -= 5
            self.log_event(
                "default_contract",
                actor_id=contract.borrower_id,
                position=borrower.position if borrower else None,
                message=f"{contract.id} defaulted; collateral transferred to the lender.",
                data={"contract": contract.summary(), "collateral_forfeited": dict(contract.collateral)},
                scope="public",
            )

    def _fulfill_contract(self, contract: CreditContract, voluntary: bool) -> None:
        borrower = self.state.agents[contract.borrower_id]
        lender = self.state.agents.get(contract.lender_id)
        for item, quantity in contract.repayment.items():
            borrower.inventory[item] -= quantity
        lender_position = lender.position if lender is not None else borrower.position
        self._deliver_owned_items(contract.lender_id, contract.repayment, lender_position)
        self._deliver_owned_items(contract.borrower_id, contract.collateral, borrower.position)
        contract.status = "fulfilled"
        contract.collateral_released = True
        borrower.reputation += 2
        self.log_event(
            "fulfill_contract",
            actor_id=borrower.id,
            position=borrower.position,
            message=f"{borrower.name} repaid {contract.id}.",
            data={"contract": contract.summary(), "voluntary": voluntary},
            scope="public",
        )

    def _deliver_owned_items(self, agent_id: str, items: Counter[str], position: Position) -> None:
        agent = self.state.agents.get(agent_id)
        for item, quantity in items.items():
            if quantity <= 0:
                continue
            if agent is not None and agent.alive and agent.can_carry(item, quantity):
                agent.inventory[item] += quantity
            else:
                self._create_item_pile(item, quantity, position, owner_id=agent_id)

    def _return_trade_escrow(self, trade: TradeOffer) -> None:
        if trade.escrow_released:
            return
        offerer = self.state.agents.get(trade.from_agent)
        if offerer is not None:
            offerer.inventory.update(
                {item: quantity * trade.lots_remaining for item, quantity in trade.give.items()}
            )
        trade.lots_remaining = 0
        trade.escrow_released = True

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

    def _agent_structure_types(self, agent: Agent) -> set[str]:
        tile = self.state.tile_at(agent.position)
        return {
            self.state.structures[sid].type
            for sid in tile.structure_ids
            if self.state.structures[sid].is_complete
            and (
                self.state.config.economy_mode != "commerce"
                or (
                    self.state.structures[sid].active
                    and self._can_access_structure(agent, self.state.structures[sid])
                )
            )
        }

    def _accessible_structure_on_tile(self, agent: Agent, structure_type: str) -> Structure | None:
        tile = self.state.tile_at(agent.position)
        for structure_id in tile.structure_ids:
            structure = self.state.structures[structure_id]
            if structure.type == structure_type and structure.is_complete and self._can_access_structure(agent, structure):
                return structure
        return None

    def _notify_denied_structure_access(self, agent: Agent, structure_type: str, structure: Structure | None = None) -> None:
        """Tell a structure's owner that someone standing at it was refused access.

        Owners often promise access in speech without executing grant_access; this makes
        the mismatch observable to them (like seeing a stranger turned away at your door),
        without granting anything automatically.
        """
        if structure is None:
            tile = self.state.tile_at(agent.position)
            for structure_id in tile.structure_ids:
                candidate = self.state.structures[structure_id]
                if candidate.type == structure_type and candidate.is_complete and not self._can_access_structure(agent, candidate):
                    structure = candidate
                    break
        if structure is None:
            return
        owner_agents = {structure.owner_id} if structure.owner_id in self.state.agents else set(
            self.state.groups[structure.owner_id].members
        ) if structure.owner_id in self.state.groups else set()
        if not owner_agents:
            return
        self.log_event(
            "access_denied",
            actor_id=agent.id,
            position=structure.position,
            message=f"{agent.name} was denied access to your {structure.type} ({structure.id}).",
            data={"structure_id": structure.id, "denied_agent": agent.id},
            scope="private",
            recipients=owner_agents | {agent.id},
        )

    def _get_structure(self, structure_id: str) -> Structure | None:
        return self.state.structures.get(structure_id)

    def _can_access_structure(self, agent: Agent, structure: Structure) -> bool:
        return (
            self._controls_owner(agent, structure.owner_id)
            or self._has_access_grant(agent, structure.access)
            or (self.state.config.economy_mode == "commerce" and structure.public_access)
        )

    def _use_productive_structure(
        self,
        agent: Agent,
        structure: Structure,
        action: dict[str, Any],
    ) -> bool:
        if self.state.config.economy_mode != "commerce":
            return True
        if not structure.active:
            self._invalid(agent, action, f"{structure.id} is inactive until upkeep is supplied.")
            return False
        if structure.uses_per_tick > 0 and structure.uses_remaining <= 0:
            self._invalid(agent, action, f"{structure.id} has reached its productive capacity this tick.")
            return False
        fee = structure.access_fee if not self._controls_owner(agent, structure.owner_id) else Counter()
        if fee and self._missing(agent.inventory, fee):
            self._invalid(agent, action, f"Using {structure.id} requires fee {dict(fee)}.")
            return False
        if fee:
            for item, quantity in fee.items():
                agent.inventory[item] -= quantity
                structure.treasury[item] += quantity
                self._credit_structure_revenue(structure, item, quantity)
            self.log_event(
                "pay_access_fee",
                actor_id=agent.id,
                position=structure.position,
                message=f"{agent.name} paid to use {structure.id}.",
                data={"structure_id": structure.id, "fee": dict(fee)},
                recipients=set(structure.contributors),
            )
        if structure.uses_per_tick > 0:
            structure.uses_remaining -= 1
        structure.total_uses += 1
        return True

    def _credit_structure_revenue(self, structure: Structure, item: str, quantity: int) -> None:
        units = Counter({agent_id: value for agent_id, value in structure.contribution_units.items() if value > 0})
        if not units:
            if structure.owner_id in self.state.agents:
                units[structure.owner_id] = 1
            elif structure.owner_id in self.state.groups:
                units.update({agent_id: 1 for agent_id in self.state.groups[structure.owner_id].members})
        total_units = sum(units.values())
        if total_units <= 0:
            return
        allocations = {agent_id: quantity * value // total_units for agent_id, value in units.items()}
        remainder = quantity - sum(allocations.values())
        ranked = sorted(
            units,
            key=lambda agent_id: (
                -(quantity * units[agent_id] % total_units),
                (sorted(units).index(agent_id) - structure.total_uses) % len(units),
            ),
        )
        for agent_id in ranked[:remainder]:
            allocations[agent_id] += 1
        for agent_id, amount in allocations.items():
            if amount <= 0:
                continue
            credits = structure.dividend_credits.setdefault(agent_id, Counter())
            credits[item] += amount

    def _has_access_grant(self, agent: Agent, access: set[str]) -> bool:
        return agent.id in access or bool(agent.groups.intersection(access))

    def _controls_owner(self, agent: Agent, owner_id: str | None) -> bool:
        return owner_id == agent.id or (owner_id is not None and owner_id in agent.groups)

    def _owner_for_action(self, agent: Agent, action: dict[str, Any]) -> str | None:
        group_id = str(action.get("group_id", "")).strip()
        if not group_id:
            return agent.id
        if group_id not in self.state.groups or agent.id not in self.state.groups[group_id].members:
            return None
        return group_id

    def _access_target_exists(self, target: str) -> bool:
        return target in self.state.agents or target in self.state.groups

    def _set_access(self, agent: Agent, subject: str, target: str, grant: bool) -> bool:
        if subject == "tile":
            tile = self.state.tile_at(agent.position)
            if not self._controls_owner(agent, tile.claimed_by):
                return False
            if grant:
                tile.access.add(target)
            else:
                tile.access.discard(target)
            return True
        structure = self.state.structures.get(subject)
        if structure is None or not self._controls_owner(agent, structure.owner_id):
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

    def _nearby_water_source(self, position: Position, resource: str) -> tuple[Position, Tile] | None:
        positions = [position]
        for dx, dy in DIRECTIONS.values():
            positions.append(position.shifted(dx, dy))
        for pos in positions:
            if not self.in_bounds(pos):
                continue
            tile = self.state.tile_at(pos)
            if tile.terrain == "water" and tile.resources.get(resource, 0) > 0:
                return pos, tile
        return None

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

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _carry_room(self, agent: Agent, item: str) -> int:
        weight = max(1, RESOURCE_WEIGHTS.get(item, 1))
        return max(0, (agent.carry_capacity - agent.inventory_weight()) // weight)

    def _skill_modifiers(self, agent: Agent, skill: str) -> tuple[int, int]:
        level = max(1, agent.skills.get(skill, 1))
        yield_interval = max(1, self.state.config.skill_yield_interval)
        energy_interval = max(1, self.state.config.skill_energy_interval)
        cap = max(0, self.state.config.skill_bonus_cap)
        return (
            min(cap, max(0, level - 1) // yield_interval),
            min(cap, max(0, level - 1) // energy_interval),
        )

    def _equipped_work_tool(self, agent: Agent) -> str | None:
        for item in ("advanced_tool", "tool"):
            if item in agent.equipped and agent.inventory.get(item, 0) > 0:
                agent.equipment_durability.setdefault(item, TOOL_MAX_DURABILITY[item])
                return item
        return None

    def _wear_equipped_tool(self, agent: Agent, item: str | None) -> int | None:
        if item is None:
            return None
        remaining = agent.equipment_durability.get(item, TOOL_MAX_DURABILITY[item]) - 1
        if remaining > 0:
            agent.equipment_durability[item] = remaining
            return remaining
        agent.inventory[item] -= 1
        if agent.inventory[item] > 0:
            agent.equipment_durability[item] = TOOL_MAX_DURABILITY[item]
            remaining = TOOL_MAX_DURABILITY[item]
        else:
            agent.equipped.discard(item)
            agent.equipment_durability.pop(item, None)
            remaining = 0
        self.log_event(
            "tool_broken",
            actor_id=agent.id,
            position=agent.position,
            message=f"{agent.name}'s {item} broke after productive use.",
            data={"item": item, "remaining_items": agent.inventory.get(item, 0)},
            scope="private",
            recipients={agent.id},
        )
        return remaining

    def _inventory_exchange_fits(
        self,
        agent: Agent,
        remove: Counter[str] | dict[str, int],
        add: Counter[str] | dict[str, int],
    ) -> bool:
        return self._can_carry_after_exchange(agent, remove=remove, add=add)

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

    def _accumulate_build_readiness(self) -> None:
        """Record which structure types any living agent was ever materials-ready to build."""
        for info in self._build_readiness()["by_agent"].values():
            self.state.build_ready_ever.update(info["buildable"])

    def _improve_skill(self, agent: Agent, skill: str) -> None:
        progress = agent.skill_progress.get(skill, 0.0) + agent.aptitudes.get(skill, 1.0)
        gained = int(progress)
        agent.skill_progress[skill] = progress - gained
        if gained > 0:
            agent.skills[skill] = agent.skills.get(skill, 0) + gained

    def _trade_value(self, trade: TradeOffer) -> dict[str, int]:
        return {
            "give": sum(RESOURCE_VALUES.get(item, 1) * qty for item, qty in trade.give.items()),
            "receive": sum(RESOURCE_VALUES.get(item, 1) * qty for item, qty in trade.receive.items()),
        }

    def _trade_private_recipients(self, trade: TradeOffer) -> set[str]:
        recipients = {trade.from_agent}
        if trade.to_agent != "any":
            recipients.add(trade.to_agent)
        if trade.accepted_by is not None:
            recipients.add(trade.accepted_by)
        return recipients

    def in_bounds(self, position: Position) -> bool:
        return 0 <= position.x < self.state.config.width and 0 <= position.y < self.state.config.height

    def export_events_jsonl(self) -> str:
        return "\n".join(json.dumps(event.to_dict(), sort_keys=True) for event in self.state.events)

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick": self.state.tick,
            "config": asdict(self.state.config),
            "tiles": self._tile_snapshots(),
            "agents": {agent_id: self._agent_snapshot(agent) for agent_id, agent in self.state.agents.items()},
            "item_piles": {pid: pile.public_summary() | {"position": asdict(pile.position)} for pid, pile in self.state.item_piles.items()},
            "structures": {sid: structure.public_summary(include_inventory=True) for sid, structure in self.state.structures.items()},
            "trades": {tid: trade.summary() for tid, trade in self.state.trades.items()},
            "contracts": {cid: contract.summary() for cid, contract in self.state.contracts.items()},
            "market_history": list(self.state.market_history),
            "groups": {gid: group.summary() for gid, group in self.state.groups.items()},
            "diagnostics": {
                "build_readiness": self._build_readiness(),
                "build_ready_ever": sorted(self.state.build_ready_ever),
            },
        }

    def _tile_snapshots(self) -> list[list[dict[str, Any]]]:
        rows: list[list[dict[str, Any]]] = []
        for y, row in enumerate(self.state.tiles):
            tile_row: list[dict[str, Any]] = []
            for x, tile in enumerate(row):
                data = tile.public_summary(include_private=True)
                data["x"] = x
                data["y"] = y
                tile_row.append(data)
            rows.append(tile_row)
        return rows

    def _agent_snapshot(self, agent: Agent) -> dict[str, Any]:
        data = agent.public_summary()
        data.update(
            {
                "inventory": dict(agent.inventory),
                "reserves": agent.needs.as_dict(),
                "needs": agent.needs.as_dict(),
                "skills": dict(agent.skills),
                "relationships": dict(agent.relationships),
                "memory": list(agent.memory),
                "equipped": sorted(agent.equipped),
                "equipment_durability": dict(agent.equipment_durability),
                "specialty": agent.specialty,
                "aptitudes": dict(agent.aptitudes),
                "need_multipliers": dict(agent.need_multipliers),
                "carry_weight": agent.inventory_weight(),
                "carry_capacity": agent.carry_capacity,
            }
        )
        return data

    def _build_readiness(self) -> dict[str, Any]:
        by_agent: dict[str, Any] = {}
        ready_counts: Counter[str] = Counter()
        for agent in self.state.agents.values():
            if not agent.alive:
                continue
            tile = self.state.tile_at(agent.position)
            buildable: list[str] = []
            blockers: dict[str, Any] = {}
            for structure_type in sorted(STRUCTURE_TYPES):
                recipe = RECIPES[structure_type]
                missing = self._missing(agent.inventory, recipe.inputs)
                terrain_ok = not recipe.required_terrain or tile.terrain in recipe.required_terrain
                energy_ok = agent.needs.energy >= recipe.energy
                claim_ok = not tile.claimed_by or self._controls_owner(agent, tile.claimed_by) or self._has_access_grant(agent, tile.access)
                duplicate_ok = not (
                    structure_type in {"farm_plot", "well"}
                    and any(self.state.structures[sid].type == structure_type for sid in tile.structure_ids)
                )
                if not missing and terrain_ok and energy_ok and claim_ok and duplicate_ok:
                    buildable.append(structure_type)
                    ready_counts[structure_type] += 1
                else:
                    blockers[structure_type] = {
                        "missing": missing,
                        "terrain_ok": terrain_ok,
                        "energy_ok": energy_ok,
                        "claim_ok": claim_ok,
                        "duplicate_ok": duplicate_ok,
                    }
            by_agent[agent.id] = {
                "buildable": buildable,
                "blockers": blockers,
            }
        return {
            "ready_counts": dict(sorted(ready_counts.items())),
            "by_agent": by_agent,
        }
