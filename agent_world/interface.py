"""Agent observation and prompt construction."""

from __future__ import annotations

import json
from typing import Any

from agent_world.models import Agent, AgentDecision, Event, Position, WorldState
from agent_world.rules import ACTION_SCHEMA, RECIPES, TERRAIN_RULES


def build_observation(state: WorldState, agent_id: str) -> dict[str, Any]:
    agent = state.agents[agent_id]
    radius = state.config.visible_radius
    visible_positions = _visible_positions(agent.position, radius, state.config.width, state.config.height)
    local_tiles = []
    visible_agent_ids = set()
    for pos in visible_positions:
        tile = state.tile_at(pos)
        piles = [state.item_piles[pile_id].public_summary() for pile_id in tile.item_pile_ids]
        structures = [
            state.structures[structure_id].public_summary(
                include_inventory=_can_inspect_structure(agent, state.structures[structure_id])
            )
            for structure_id in tile.structure_ids
        ]
        agents_here = [
            other.public_summary()
            for other in state.agents.values()
            if other.alive and other.position == pos and other.id != agent.id
        ]
        visible_agent_ids.update(other["id"] for other in agents_here)
        local_tiles.append(
            {
                "x": pos.x,
                "y": pos.y,
                "terrain": tile.terrain,
                "move_cost": TERRAIN_RULES[tile.terrain].move_cost,
                "resources": dict(tile.resources),
                "claimed_by": tile.claimed_by,
                "access_granted": agent.id in tile.access,
                "item_piles": piles,
                "structures": structures,
                "agents": agents_here,
            }
        )
    open_trades = [
        trade.summary()
        for trade in state.trades.values()
        if trade.status == "open" and (trade.from_agent == agent.id or trade.to_agent == agent.id)
    ]
    return {
        "tick": state.tick,
        "world": {
            "width": state.config.width,
            "height": state.config.height,
            "visible_radius": radius,
            "action_points_per_tick": state.config.action_points_per_tick,
            "terrain_rules": {
                name: {
                    "passable": rule.passable,
                    "move_cost": rule.move_cost,
                    "max_occupants": rule.max_occupants,
                    "base_resources": dict(rule.base_resources),
                    "regen": dict(rule.regen),
                }
                for name, rule in TERRAIN_RULES.items()
            },
            "recipes": {
                name: {
                    "inputs": dict(recipe.inputs),
                    "outputs": dict(recipe.outputs),
                    "action_points": recipe.action_points,
                    "energy": recipe.energy,
                }
                for name, recipe in RECIPES.items()
            },
        },
        "self": {
            "id": agent.id,
            "name": agent.name,
            "position": {"x": agent.position.x, "y": agent.position.y},
            "health": agent.health,
            "alive": agent.alive,
            "needs": agent.needs.as_dict(),
            "inventory": dict(agent.inventory),
            "carry_weight": agent.inventory_weight(),
            "carry_capacity": agent.carry_capacity,
            "skills": dict(agent.skills),
            "equipped": sorted(agent.equipped),
            "groups": sorted(agent.groups),
            "relationships": dict(agent.relationships),
            "reputation": agent.reputation,
        },
        "local_map": local_tiles,
        "visible_agents": sorted(visible_agent_ids),
        "recent_events": [
            event.to_dict()
            for event in state.events[-state.config.recent_event_limit * 4 :]
            if _event_visible_to(event, agent, radius)
        ][-state.config.recent_event_limit :],
        "memory": list(agent.memory[-state.config.max_memory :]),
        "open_trades": open_trades,
        "known_groups": {
            gid: group.summary()
            for gid, group in state.groups.items()
            if agent.id in group.members or agent.id in group.invited
        },
        "valid_actions": ACTION_SCHEMA,
    }


def build_agent_prompt(observation: dict[str, Any]) -> str:
    """Build a neutral prompt that describes constraints, not objectives."""

    return "\n".join(
        [
            "You are an autonomous agent inside a constrained simulated world.",
            "You may choose any valid action available to you. The world engine will validate actions and reject impossible ones.",
            "Do not assume you can mutate world state directly. Return only structured JSON.",
            "Your response must have exactly these top-level keys: intent, actions, messages, memory_updates.",
            "Action objects must use one of the valid action schemas in the observation.",
            "The observation follows as JSON:",
            json.dumps(observation, indent=2, sort_keys=True),
        ]
    )


def parse_agent_response(response: str | dict[str, Any] | AgentDecision) -> AgentDecision:
    """Parse a JSON LLM response into an AgentDecision.

    Invalid JSON becomes a wait decision with the failure captured as intent.
    The world engine will still validate every action in the parsed decision.
    """

    if isinstance(response, AgentDecision):
        return response
    if isinstance(response, str):
        try:
            value = json.loads(response)
        except json.JSONDecodeError as exc:
            return AgentDecision(intent=f"Invalid JSON response: {exc}", actions=[{"type": "wait"}])
        return AgentDecision.from_json_like(value)
    return AgentDecision.from_json_like(response)


def _visible_positions(center: Position, radius: int, width: int, height: int) -> list[Position]:
    positions: list[Position] = []
    for y in range(max(0, center.y - radius), min(height, center.y + radius + 1)):
        for x in range(max(0, center.x - radius), min(width, center.x + radius + 1)):
            pos = Position(x, y)
            if center.distance_to(pos) <= radius:
                positions.append(pos)
    return positions


def _event_visible_to(event: Event, agent: Agent, radius: int) -> bool:
    if event.scope == "public":
        return True
    if event.actor_id == agent.id or agent.id in event.recipients:
        return True
    if event.scope == "private":
        return False
    return event.position is not None and agent.position.distance_to(event.position) <= radius


def _can_inspect_structure(agent: Agent, structure: Any) -> bool:
    return structure.owner_id == agent.id or agent.id in structure.access
