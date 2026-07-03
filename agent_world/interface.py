"""Agent observation and prompt construction."""

from __future__ import annotations

import json
from typing import Any

from agent_world.models import Agent, AgentDecision, Event, Position, WorldState
from agent_world.rules import ACTION_SCHEMA, MECHANICS_SUMMARY, RECIPES, TERRAIN_RULES


AGENT_IO_EVENT_TYPES = {"agent_observation", "agent_prompt", "agent_response"}


def build_observation(state: WorldState, agent_id: str) -> dict[str, Any]:
    agent = state.agents[agent_id]
    radius = state.config.visible_radius
    visible_positions = _visible_positions(agent.position, radius, state.config.width, state.config.height)
    local_tiles = []
    visible_agent_ids = set()
    nearby_agents: dict[str, dict[str, Any]] = {}
    for pos in visible_positions:
        tile = state.tile_at(pos)
        piles = [state.item_piles[pile_id].public_summary() for pile_id in tile.item_pile_ids]
        structures = [
            state.structures[structure_id].public_summary(
                include_inventory=_can_inspect_structure(agent, state.structures[structure_id])
            )
            | {"access_granted": _can_inspect_structure(agent, state.structures[structure_id])}
            for structure_id in tile.structure_ids
        ]
        agents_here = [
            other.public_summary()
            for other in state.agents.values()
            if other.alive and other.position == pos and other.id != agent.id
        ]
        for other_summary in agents_here:
            visible_agent_ids.add(other_summary["id"])
            nearby_agents[other_summary["id"]] = {
                **other_summary,
                "distance": agent.position.distance_to(pos),
            }
        local_tiles.append(
            {
                "x": pos.x,
                "y": pos.y,
                "terrain": tile.terrain,
                "passable": TERRAIN_RULES[tile.terrain].passable,
                "move_cost": TERRAIN_RULES[tile.terrain].move_cost,
                "resources": dict(tile.resources),
                "claimed_by": tile.claimed_by,
                "access_granted": _controls_owner(agent, tile.claimed_by) or _has_access_grant(agent, tile.access),
                "item_piles": piles,
                "structures": structures,
                "agents": agents_here,
            }
        )
    open_trades = [
        trade.summary()
        for trade in state.trades.values()
        if trade.status == "open" and _trade_visible_to_agent(state, agent, trade, radius)
    ]
    return {
        "tick": state.tick,
        "world": {
            "width": state.config.width,
            "height": state.config.height,
            "visible_radius": radius,
            "action_points_per_tick": state.config.action_points_per_tick,
            "reserve_scale": {
                "minimum": 0,
                "maximum": {
                    "food": state.config.food_reserve_max,
                    "water": state.config.water_reserve_max,
                    "energy": state.config.energy_reserve_max,
                },
                "meaning": "Food, water, and energy are reserves. Higher is better; lower is worse. 0 means empty/danger.",
            },
            "terrain_rules": {
                name: {
                    "passable": rule.passable,
                    "move_cost": rule.move_cost,
                    "max_occupants": rule.max_occupants,
                }
                for name, rule in TERRAIN_RULES.items()
            },
            "mechanics": MECHANICS_SUMMARY,
            "recipes": {
                name: {
                    "inputs": dict(recipe.inputs),
                    "outputs": dict(recipe.outputs),
                    "action_points": recipe.action_points,
                    "energy": recipe.energy,
                    "required_terrain": list(recipe.required_terrain),
                    "required_tool": recipe.required_tool,
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
            "reserves": agent.needs.as_dict(),
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
        "nearby_agents": [
            nearby_agents[agent_id]
            for agent_id in sorted(nearby_agents, key=lambda item: (nearby_agents[item]["distance"], item))
        ],
        "recent_events": [
            event.to_dict()
            for event in state.events[-state.config.recent_event_limit * 4 :]
            if event.type not in AGENT_IO_EVENT_TYPES and _event_visible_to(event, agent, radius)
        ][-state.config.recent_event_limit :],
        "recent_action_feedback": _recent_action_feedback(state, agent),
        "memory": list(agent.memory[-state.config.max_memory :]),
        "open_trades": open_trades,
        "known_groups": {
            gid: group.summary()
            for gid, group in state.groups.items()
            if agent.id in group.members or agent.id in group.invited
        },
        "action_format": {
            "shape": "flat_object",
            "rule": "Each action must be a flat JSON object with a top-level type key. Put arguments directly beside type.",
            "actions": "Submit actions as an ordered list. Multiple actions may be included in one response; plan against action costs because the world spends action points in order until no action points remain.",
            "messages": "Submit speech in messages. Speech is delivered before actions and does not spend action points.",
            "do_not_use_keys": ["fields", "parameters", "example"],
            "valid_example": {"type": "move", "direction": "east"},
            "invalid_example": {"type": "move", "fields": {"direction": "east"}},
        },
        "valid_actions": ACTION_SCHEMA,
    }


PROMPT_RULES = [
    "You are an autonomous agent inside a constrained simulated world.",
    "You may choose any valid action available to you. The world engine will validate actions and reject impossible ones.",
    "Do not assume you can mutate world state directly. Return only structured JSON.",
    "Your response must have exactly these top-level keys: intent, actions, messages, memory_updates.",
    "Action objects must be flat JSON objects. Put arguments directly beside type; never nest arguments under fields.",
    'Valid action example: {"type":"move","direction":"east"}. Invalid: {"type":"move","fields":{"direction":"east"}}.',
    "You may include multiple actions in the actions list; the world processes them in order until action points run out.",
    "Plan against the action costs listed below and your current action points and energy.",
    "Use messages for speech; messages are delivered without spending action points.",
    "Food, water, and energy in self.reserves are reserves where higher is better and 0 is danger.",
    "Balance immediate survival with longer-term resilience. If a problem keeps recurring, consider actions that could reduce future pressure.",
    "Use recent_action_feedback to avoid repeating invalid actions.",
]


def build_static_context(world: dict[str, Any]) -> str:
    """Render the fixed rulebook as terse text.

    This block is byte-identical for every agent and tick of a run, so it can sit at the
    start of the request as a stable, cacheable prefix. It carries the same information as
    the old JSON sections (valid_actions, mechanics, recipes, terrain_rules, reserve_scale)
    at roughly half the size.
    """

    reserve_max = world.get("reserve_scale", {}).get("maximum", {})
    lines: list[str] = []
    lines.extend(PROMPT_RULES)
    lines.append("")
    lines.append(
        f"WORLD: {world.get('width', '?')}x{world.get('height', '?')} grid, visible radius {world.get('visible_radius', '?')}, "
        f"{world.get('action_points_per_tick', '?')} action points per tick."
    )
    lines.append(
        "RESERVES (min 0, higher is better): "
        + ", ".join(f"{name} max {value}" for name, value in sorted(reserve_max.items()))
    )
    lines.append("")
    lines.append("TERRAIN (move_cost/max_occupants):")
    for name, rule in sorted(TERRAIN_RULES.items()):
        passable = "" if rule.passable else ", impassable"
        lines.append(f"- {name}: {rule.move_cost}/{rule.max_occupants}{passable}")
    lines.append("")
    lines.append("ACTIONS (cost: action points, energy):")
    for action in ACTION_SCHEMA:
        cost = action.get("cost", {})
        params = action.get("parameters", {})
        param_text = " {" + ", ".join(f"{key}: {value}" for key, value in params.items()) + "}" if params else ""
        cost_text = f"{cost.get('action_points', 0)}ap,{cost.get('energy', 0)}en"
        effect = cost.get("effect")
        effect_text = f" ({effect})" if effect else ""
        lines.append(f"- {action['type']}{param_text} cost:{cost_text}{effect_text}")
    lines.append("")
    lines.append("RECIPES (inputs -> cost, terrain):")
    for name, recipe in sorted(RECIPES.items()):
        inputs = "+".join(f"{qty} {item}" for item, qty in sorted(recipe.inputs.items()))
        terrain = f", terrain: {'|'.join(recipe.required_terrain)}" if recipe.required_terrain else ""
        lines.append(f"- {name}: {inputs} -> {recipe.action_points}ap,{recipe.energy}en{terrain}")
    lines.append("")
    lines.append("MECHANICS:")
    for section_name, section in MECHANICS_SUMMARY.items():
        if isinstance(section, dict):
            for key, text in section.items():
                lines.append(f"- {key}: {text}")
    return "\n".join(lines)


def build_dynamic_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Strip the static rulebook and default-valued noise from a full observation.

    Everything informative about the current state stays; fields that are empty, false,
    derivable from the static context (tile passable/move_cost), or internal to the engine
    (event scope/recipients/data) are omitted.
    """

    dynamic = {key: value for key, value in observation.items() if key not in ("valid_actions", "action_format", "world")}
    dynamic["tick"] = observation.get("tick", 0)
    dynamic["local_map"] = [_slim_tile(tile) for tile in observation.get("local_map", [])]
    dynamic["recent_events"] = [_slim_event(event) for event in observation.get("recent_events", [])[-12:]]
    dynamic["memory"] = list(observation.get("memory", []))[-16:]
    return {key: value for key, value in dynamic.items() if value not in ([], {}, None)}


def _slim_tile(tile: dict[str, Any]) -> dict[str, Any]:
    slim: dict[str, Any] = {
        "x": tile["x"],
        "y": tile["y"],
        "terrain": tile["terrain"],
    }
    resources = {item: qty for item, qty in tile.get("resources", {}).items() if qty}
    if resources:
        slim["resources"] = resources
    if tile.get("claimed_by"):
        slim["claimed_by"] = tile["claimed_by"]
        slim["access_granted"] = bool(tile.get("access_granted"))
    for key in ("item_piles", "structures", "agents"):
        if tile.get(key):
            slim[key] = tile[key]
    return slim


def _slim_event(event: dict[str, Any]) -> dict[str, Any]:
    slim: dict[str, Any] = {"tick": event.get("tick"), "type": event.get("type")}
    if event.get("actor_id"):
        slim["actor"] = event["actor_id"]
    if event.get("message"):
        slim["message"] = event["message"]
    return slim


def build_agent_prompt(observation: dict[str, Any], compact: bool = False) -> str:
    """Build a neutral prompt that describes constraints, not objectives.

    ``compact=True`` produces the static-context + slim-dynamic form the LLM brain sends
    (rules as terse text, state as minimal JSON). The default form keeps the full
    observation as indented JSON for logs and inspection.
    """

    if compact:
        return "\n".join(
            [
                build_static_context(observation.get("world", {})),
                "",
                "The current observation follows as JSON:",
                json.dumps(build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True),
            ]
        )
    return "\n".join(
        [
            *PROMPT_RULES,
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
            salvaged = _extract_json_object(response)
            if salvaged is not None:
                return AgentDecision.from_json_like(salvaged)
            return AgentDecision(intent=f"Invalid JSON response: {exc}", actions=[{"type": "wait"}])
        return AgentDecision.from_json_like(value)
    return AgentDecision.from_json_like(response)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Salvage the first balanced JSON object from noisy model output.

    Handles markdown code fences, prose before/after the JSON, and trailing garbage.
    Returns None when no parseable object exists (e.g. truncated output).
    """

    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start : index + 1])
                    except json.JSONDecodeError:
                        break
                    return value if isinstance(value, dict) else None
        start = text.find("{", start + 1)
    return None


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
    return _controls_owner(agent, structure.owner_id) or _has_access_grant(agent, structure.access)


def _trade_visible_to_agent(state: WorldState, agent: Agent, trade: Any, radius: int) -> bool:
    if trade.from_agent == agent.id or trade.to_agent == agent.id:
        return True
    if trade.to_agent != "any":
        return False
    offerer = state.agents.get(trade.from_agent)
    return offerer is not None and offerer.alive and agent.position.distance_to(offerer.position) <= radius


def _has_access_grant(agent: Agent, access: set[str]) -> bool:
    return agent.id in access or bool(agent.groups.intersection(access))


def _controls_owner(agent: Agent, owner_id: str | None) -> bool:
    return owner_id == agent.id or (owner_id is not None and owner_id in agent.groups)


def _recent_action_feedback(state: WorldState, agent: Agent) -> list[dict[str, Any]]:
    feedback = []
    for event in reversed(state.events):
        if event.actor_id != agent.id or event.type != "invalid_action":
            continue
        action = event.data.get("action", {})
        item = {
            "tick": event.tick,
            "reason": event.message,
            "attempted_action": action,
        }
        if isinstance(action, dict) and isinstance(action.get("fields"), dict):
            item["format_note"] = (
                "Do not put arguments inside fields. Move each field to the top level, "
                "for example {\"type\":\"move\",\"direction\":\"east\"}."
            )
        feedback.append(item)
        if len(feedback) >= 5:
            break
    return list(reversed(feedback))


