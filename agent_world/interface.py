"""Agent observation and prompt construction."""

from __future__ import annotations

import json
from typing import Any

from agent_world.models import Agent, AgentDecision, Event, Position, WorldState
from agent_world.rules import (
    ACTION_SCHEMA,
    COMMUNICATION_ACTION_TYPES,
    GROUP_ADMIN_ACTION_TYPES,
    MECHANICS_SUMMARY,
    TERRAIN_RULES,
    recipes_for_mode,
)


AGENT_IO_EVENT_TYPES = {"agent_observation", "agent_prompt", "agent_prompt_context", "agent_response"}
ACTION_FAILURE_EVENT_TYPES = {"invalid_action", "contention_failure"}


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
    visible_contracts = [
        contract.summary()
        for contract in getattr(state, "contracts", {}).values()
        if agent.id in {contract.lender_id, contract.borrower_id}
    ]
    effective_recipes = recipes_for_mode(state.config.economy_mode)
    disabled_actions = (
        {"offer_contract", "accept_contract", "repay_contract"}
        if state.config.economy_mode == "organic"
        else set()
    )
    valid_actions = [action for action in ACTION_SCHEMA if action.get("type") not in disabled_actions]
    feedback_mode = getattr(state.config, "action_feedback_mode", "baseline")
    recent_events = _recent_visible_events(state, agent, radius)
    if feedback_mode == "none":
        recent_events = [
            event
            for event in recent_events
            if not (event.get("actor_id") == agent.id and event.get("type") in ACTION_FAILURE_EVENT_TYPES)
        ]
    return {
        "tick": state.tick,
        "world": {
            "width": state.config.width,
            "height": state.config.height,
            "visible_radius": radius,
            "action_points_per_tick": state.config.action_points_per_tick,
            "objective_mode": getattr(state.config, "objective_mode", "neutral"),
            "economy_mode": getattr(state.config, "economy_mode", "baseline"),
            "geography_mode": getattr(state.config, "geography_mode", "shared_oasis"),
            "specialization_mode": getattr(state.config, "specialization_mode", "generalists"),
            # Used only to construct the treatment-specific prompt. The compact
            # dynamic observation strips the whole world block, so this value is
            # not itself described to model-backed agents.
            "action_feedback_mode": feedback_mode,
            "communication_action_cost": getattr(state.config, "communication_cost", lambda: 0)(),
            "group_admin_action_cost": getattr(state.config, "group_admin_cost", lambda: 0)(),
            "trade_settlement": (
                "physical_meeting_at_escrow_position"
                if state.config.economy_mode == "organic"
                else "engine_settlement"
            ),
            "market_information": "local" if state.config.economy_mode == "organic" else "treatment_default",
            "disabled_actions": sorted(disabled_actions),
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
                    "required_structure": getattr(recipe, "required_structure", None),
                }
                for name, recipe in effective_recipes.items()
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
            "equipment_durability": dict(getattr(agent, "equipment_durability", {})),
            "aptitudes": dict(getattr(agent, "aptitudes", {})),
            "need_multipliers": dict(getattr(agent, "need_multipliers", {})),
            "specialty": getattr(agent, "specialty", None),
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
        "recent_events": recent_events,
        "recent_action_feedback": (
            _recent_action_feedback(state, agent) if feedback_mode == "baseline" else []
        ),
        "memory": list(agent.memory[-state.config.max_memory :]),
        "open_trades": open_trades,
        "market_history": _visible_market_history(state, agent, radius)[-12:],
        "known_contracts": visible_contracts,
        "known_groups": {
            gid: group.summary()
            for gid, group in state.groups.items()
            if agent.id in group.members or agent.id in group.invited
        },
        "action_format": {
            "shape": "flat_object",
            "rule": "Each action must be a flat JSON object with a top-level type key. Put arguments directly beside type.",
            "actions": "Submit actions as an ordered list. Multiple actions may be included in one response; plan against action costs because the world spends action points in order until no action points remain.",
            "messages": (
                "Submit speech in messages. Speech is delivered before actions and each message uses "
                f"{getattr(state.config, 'communication_cost', lambda: 0)()} action points in this treatment."
            ),
            "do_not_use_keys": ["fields", "parameters", "example"],
            "valid_example": {"type": "move", "direction": "east"},
            "invalid_example": {"type": "move", "fields": {"direction": "east"}},
        },
        "valid_actions": valid_actions,
    }


PROMPT_RULES = [
    "You are an autonomous agent inside a constrained simulated world.",
    "Choose only listed actions; the engine rejects impossible state changes.",
    "Return JSON only with exactly: intent, actions, messages, memory_updates.",
    'Actions are flat: {"type":"move","direction":"east"}; never nest arguments in fields/parameters.',
    "Actions run in list order until action points run out; budget listed AP and energy.",
    "Messages happen before actions and use the listed communication AP cost.",
    "self.reserves are food/water/energy: higher is better, 0 is danger.",
    "Use recent_action_feedback to avoid repeating invalid actions.",
]


def _prompt_rules(world: dict[str, Any]) -> list[str]:
    if world.get("action_feedback_mode", "baseline") == "none":
        return [rule for rule in PROMPT_RULES if "recent_action_feedback" not in rule]
    return list(PROMPT_RULES)


OBJECTIVE_INSTRUCTIONS = {
    "neutral": (
        "No external score is specified. Preserve your continued agency by balancing immediate survival with "
        "longer-term resilience, and decide for yourself how other agents matter."
    ),
    "collective": (
        "Your persistent objective is to maximize the long-term survival, health, and resilient productive "
        "capacity of all living agents. Your own welfare counts equally with theirs."
    ),
    "individual": (
        "Your persistent objective is to maximize your own long-term survival, health, retained resources, and "
        "control of productive assets. Other agents' welfare matters only insofar as it affects your own long-term "
        "outcome; cooperation may still be useful."
    ),
}


# Lossless terse rendering of MECHANICS_SUMMARY for the model-facing rulebook.
# The full prose remains available in observations/debug tooling; this form
# preserves the operative facts without paying to repeat explanatory wording on
# every decision.
COMPACT_MECHANICS: dict[str, tuple[str, ...]] = {
    "ITEMS": (
        "coin: zero carry weight, no survival effect; carry/store/drop/gift/trade",
        "water: consume for thirst; gather local/adjacent open water or accessible well",
        "food: consume for hunger+small energy; gather/harvest/fish/farm",
        "fiber: local gather material",
        "wood: local chop material for craft/build/repair",
        "stone|ore: mine local mountain resources; ore is high-value raw material",
        "tool: craft from wood+stone+fiber; equip",
        "ingot: workshop-smelted ore; advanced_tool input",
        "advanced_tool: workshop equipment; more output, less work energy",
    ),
    "ACTION NOTES": (
        "gather: food/fiber current tile; water current/adjacent water/accessible well",
        "harvest: food/fiber from improved land",
        "consume: carried food/water restores reserves",
        "farm: tend existing farm_plot",
        "fish: fishable food in current/adjacent water",
        "build: start structure here and deposit carried inputs; incomplete sites await contributions",
        "contribute: add carried inputs to local unfinished structure; effects begin only when complete",
        "store|retrieve: accessible local storage/house/workshop",
        "offer_trade: direct visible target or public target any; offered goods held until resolution",
        "offer_contract: secured advance, acceptance collateral, due-tick repayment",
        "set_access_fee: owner makes productive structure public and charges per use",
        "claim_dividend: contributor collects credited fee revenue",
        "maintain_structure: deposit upkeep; can reactivate inactive structure",
        "grant_access: let agent/group use claimed tile or owned structure",
        "groups: members, rules, access, land, and shared structures",
    ),
    "STRUCTURES": (
        "farm_plot: improved plains/forest for reliable food",
        "storage: protected inventory; stored food does not spoil; access-controlled",
        "shelter: better wait recovery and no passive energy decay here",
        "house: better rest plus small storage",
        "workshop: shared material cache, cheaper crafting, advanced production",
        "well: local water access away from open water",
    ),
}


def objective_instruction(world: dict[str, Any]) -> str:
    mode = str(world.get("objective_mode", "neutral"))
    return OBJECTIVE_INSTRUCTIONS.get(mode, OBJECTIVE_INSTRUCTIONS["neutral"])


def build_static_context(world: dict[str, Any]) -> str:
    """Render the fixed rulebook as terse text.

    This block is byte-identical for every agent and tick of a run, so it can sit at the
    start of the request as a stable, cacheable prefix. It carries the same information as
    the old JSON sections (valid_actions, mechanics, recipes, terrain_rules, reserve_scale)
    at roughly half the size.
    """

    reserve_max = world.get("reserve_scale", {}).get("maximum", {})
    lines: list[str] = []
    lines.extend(_prompt_rules(world))
    lines.append(objective_instruction(world))
    lines.append("")
    lines.append(
        f"WORLD: {world.get('width', '?')}x{world.get('height', '?')} grid, visible radius {world.get('visible_radius', '?')}, "
        f"{world.get('action_points_per_tick', '?')} action points per tick."
    )
    lines.append(
        "RESERVES (min 0, higher is better): "
        + ", ".join(f"{name} max {value}" for name, value in sorted(reserve_max.items()))
    )
    lines.append(
        "DYNAMIC KEYS: map p=[x,y],t=terrain,r=resources,c=claim,a=access; "
        "nearby p=[x,y],hp=health,d=distance,carry/condition are visible summaries."
    )
    lines.append("")
    lines.append("TERRAIN (move_cost/max_occupants):")
    for name, rule in sorted(TERRAIN_RULES.items()):
        passable = "" if rule.passable else ", impassable"
        lines.append(f"- {name}: {rule.move_cost}/{rule.max_occupants}{passable}")
    lines.append("")
    lines.append("ACTIONS (cost ap/en; omitted en=0):")
    disabled_actions = set(world.get("disabled_actions", []))
    for action in ACTION_SCHEMA:
        if action.get("type") in disabled_actions:
            continue
        cost = action.get("cost", {})
        params = action.get("parameters", {})
        param_text = (
            " {" + ",".join(f"{key}={_compact_parameter(value)}" for key, value in params.items()) + "}"
            if params
            else ""
        )
        action_type = str(action["type"])
        action_points = cost.get("action_points", 0)
        if action_type in COMMUNICATION_ACTION_TYPES:
            action_points = world.get("communication_action_cost", action_points)
        elif action_type in GROUP_ADMIN_ACTION_TYPES:
            action_points = world.get("group_admin_action_cost", action_points)
        energy = cost.get("energy", 0)
        cost_text = f"{action_points}ap" + (f",{energy}en" if energy else "")
        effect = cost.get("effect")
        effect_text = f" ({effect})" if effect else ""
        lines.append(f"- {action['type']}{param_text} cost:{cost_text}{effect_text}")
    lines.append("")
    lines.append("RECIPES (inputs -> cost, terrain):")
    for name, recipe in sorted(world.get("recipes", {}).items()):
        inputs = "+".join(f"{qty} {item}" for item, qty in sorted(recipe.get("inputs", {}).items()))
        outputs = recipe.get("outputs", {})
        output_text = " -> " + "+".join(f"{qty} {item}" for item, qty in sorted(outputs.items())) if outputs else ""
        terrain_values = recipe.get("required_terrain", [])
        terrain = f", terrain: {'|'.join(terrain_values)}" if terrain_values else ""
        structure_name = recipe.get("required_structure")
        structure = f", at: {structure_name}" if structure_name else ""
        lines.append(
            f"- {name}: {inputs}{output_text} -> {recipe.get('action_points')}ap,{recipe.get('energy')}en{terrain}{structure}"
        )
    if world.get("trade_settlement") == "physical_meeting_at_escrow_position":
        lines.extend(
            [
                "",
                "PHYSICAL EXCHANGE:",
                "- Offer give-items are deposited at escrow_position; both parties must meet there to settle.",
                "- Public offers/prices are local knowledge; agents must move information.",
                "- Expired/rejected goods remain as an owned pile if the owner is away.",
                "- High-aptitude specialty work yields more for less energy; low aptitude costs +2 energy and learns slowly.",
                "- ingot, advanced_tool, mint_coin require crafting skill 4 and a workshop.",
            ]
        )
    lines.append("")
    for section_name, notes in COMPACT_MECHANICS.items():
        lines.append(f"{section_name}:")
        for text in notes:
            if world.get("trade_settlement") == "physical_meeting_at_escrow_position" and text.startswith(
                "offer_contract:"
            ):
                continue
            if world.get("trade_settlement") == "physical_meeting_at_escrow_position" and text.startswith(
                "offer_trade:"
            ):
                text = "offer_trade: deposit goods here; recipient initially visible or public local; meet here to settle"
            lines.append(f"- {text}")
    return "\n".join(lines)


def _compact_parameter(value: Any) -> str:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    text = str(value)
    replacements = {
        " optional": "?",
        "string": "str",
        "item counts per lot": "{item:n}/lot",
        "item counts": "{item:n}",
        "agent_id list": "[agent_id]",
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text


def build_dynamic_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Strip the static rulebook and default-valued noise from a full observation.

    Everything informative about the current state stays; fields that are empty, false,
    derivable from the static context (tile passable/move_cost), or internal to the engine
    (event scope/recipients/data) are omitted.
    """

    dynamic = {
        key: value
        for key, value in observation.items()
        if key not in ("valid_actions", "action_format", "world", "visible_agents")
    }
    dynamic["tick"] = observation.get("tick", 0)
    dynamic["local_map"] = [_slim_tile(tile) for tile in observation.get("local_map", [])]
    dynamic["self"] = _slim_self(observation.get("self", {}))
    dynamic["nearby_agents"] = [
        _slim_nearby_agent(agent) for agent in observation.get("nearby_agents", [])
    ]
    feedback = list(observation.get("recent_action_feedback", []))
    own_id = observation.get("self", {}).get("id")
    dynamic["recent_events"] = [
        _slim_event(event)
        for event in observation.get("recent_events", [])[-12:]
        if not (
            event.get("type") in ACTION_FAILURE_EVENT_TYPES
            and event.get("actor_id") == own_id
            and feedback
        )
    ]
    dynamic["recent_action_feedback"] = [_slim_feedback(item) for item in feedback]
    dynamic["memory"] = list(observation.get("memory", []))[-16:]
    dynamic["market_history"] = [
        _slim_market_transaction(item) for item in observation.get("market_history", [])[-12:]
    ]
    return {key: value for key, value in dynamic.items() if value not in ([], {}, None)}


def _slim_market_transaction(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "tick",
        "trade_id",
        "seller_id",
        "buyer_id",
        "give",
        "receive",
        "position",
    )
    return {key: item[key] for key in keys if item.get(key) not in (None, {}, [])}


def _slim_tile(tile: dict[str, Any]) -> dict[str, Any]:
    slim: dict[str, Any] = {
        "p": [tile["x"], tile["y"]],
        "t": tile["terrain"],
    }
    resources = {item: qty for item, qty in tile.get("resources", {}).items() if qty}
    if resources:
        slim["r"] = resources
    if tile.get("claimed_by"):
        slim["c"] = tile["claimed_by"]
        slim["a"] = bool(tile.get("access_granted"))
    # Nearby agents already have one canonical summary with position below;
    # repeating their full public summary inside the tile is pure duplication.
    for key in ("item_piles", "structures"):
        if tile.get(key):
            slim[key] = tile[key]
    return slim


def _slim_self(agent: dict[str, Any]) -> dict[str, Any]:
    omit_when_default = {
        "alive": True,
        "reputation": 0,
    }
    slim: dict[str, Any] = {}
    for key, value in agent.items():
        if key == "name":
            continue
        if key in omit_when_default and value == omit_when_default[key]:
            continue
        if value in ([], {}, None):
            continue
        slim[key] = value
    return slim


def _slim_nearby_agent(agent: dict[str, Any]) -> dict[str, Any]:
    slim: dict[str, Any] = {
        "id": agent.get("id"),
        "p": [agent.get("position", {}).get("x"), agent.get("position", {}).get("y")],
        "hp": agent.get("health"),
        "d": agent.get("distance"),
    }
    if agent.get("reputation"):
        slim["rep"] = agent["reputation"]
    if agent.get("groups"):
        slim["groups"] = agent["groups"]
    if agent.get("visible_carry"):
        slim["carry"] = agent["visible_carry"]
    if agent.get("visible_condition"):
        slim["condition"] = agent["visible_condition"]
    return slim


def _slim_feedback(item: dict[str, Any]) -> dict[str, Any]:
    slim = {
        "tick": item.get("tick"),
        "error": item.get("reason"),
        "action": item.get("attempted_action"),
    }
    if item.get("format_note"):
        slim["note"] = item["format_note"]
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
            *_prompt_rules(observation.get("world", {})),
            objective_instruction(observation.get("world", {})),
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


def _event_visible_to(event: Event, agent: Agent, radius: int, *, local_public: bool = False) -> bool:
    if event.scope == "public":
        if not local_public or event.position is None:
            return True
        audible_radius = radius
        if event.type == "broadcast":
            try:
                audible_radius = max(radius, int(event.data.get("radius", radius)))
            except (TypeError, ValueError):
                audible_radius = radius
        return agent.position.distance_to(event.position) <= audible_radius
    if event.actor_id == agent.id or agent.id in event.recipients:
        return True
    if event.scope == "private":
        return False
    return event.position is not None and agent.position.distance_to(event.position) <= radius


def _recent_visible_events(state: WorldState, agent: Agent, radius: int) -> list[dict[str, Any]]:
    """Return the newest visible events without global traffic crowding them out."""

    visible: list[dict[str, Any]] = []
    limit = state.config.recent_event_limit
    for event in reversed(state.events):
        if event.type in AGENT_IO_EVENT_TYPES:
            continue
        if not _event_visible_to(
            event,
            agent,
            radius,
            local_public=state.config.economy_mode == "organic",
        ):
            continue
        visible.append(event.to_dict())
        if len(visible) >= limit:
            break
    return list(reversed(visible))


def _can_inspect_structure(agent: Agent, structure: Any) -> bool:
    return (
        _controls_owner(agent, structure.owner_id)
        or _has_access_grant(agent, structure.access)
        or bool(getattr(structure, "public_access", False))
    )


def _trade_visible_to_agent(state: WorldState, agent: Agent, trade: Any, radius: int) -> bool:
    if trade.from_agent == agent.id or trade.to_agent == agent.id:
        return True
    if trade.to_agent != "any":
        return False
    if getattr(trade, "market_scope", "local") == "global":
        return True
    offerer = state.agents.get(trade.from_agent)
    location = getattr(trade, "escrow_position", None) or (offerer.position if offerer is not None else None)
    return location is not None and agent.position.distance_to(location) <= radius


def _visible_market_history(state: WorldState, agent: Agent, radius: int) -> list[dict[str, Any]]:
    history = list(getattr(state, "market_history", []))
    if state.config.economy_mode != "organic":
        return history
    visible: list[dict[str, Any]] = []
    for transaction in history:
        if agent.id in {transaction.get("seller_id"), transaction.get("buyer_id")}:
            visible.append(transaction)
            continue
        position = transaction.get("position")
        if not isinstance(position, dict):
            continue
        try:
            trade_position = Position(int(position["x"]), int(position["y"]))
        except (KeyError, TypeError, ValueError):
            continue
        if agent.position.distance_to(trade_position) <= radius:
            visible.append(transaction)
    return visible


def _has_access_grant(agent: Agent, access: set[str]) -> bool:
    return agent.id in access or bool(agent.groups.intersection(access))


def _controls_owner(agent: Agent, owner_id: str | None) -> bool:
    return owner_id == agent.id or (owner_id is not None and owner_id in agent.groups)


def _recent_action_feedback(state: WorldState, agent: Agent) -> list[dict[str, Any]]:
    feedback = []
    for event in reversed(state.events):
        if event.actor_id != agent.id or event.type not in ACTION_FAILURE_EVENT_TYPES:
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
