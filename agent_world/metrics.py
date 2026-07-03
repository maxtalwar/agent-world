"""Metrics for inspecting emergent economy and society signals."""

from __future__ import annotations

from collections import Counter
from typing import Any

from agent_world.models import WorldState
from agent_world.rules import RECIPES, RESOURCE_VALUES, STRUCTURE_TYPES


def compute_metrics(state: WorldState) -> dict[str, Any]:
    living_agents = [agent for agent in state.agents.values() if agent.alive]
    wealth = {
        agent.id: sum(RESOURCE_VALUES.get(item, 1) * qty for item, qty in agent.inventory.items())
        for agent in state.agents.values()
    }
    for trade in state.trades.values():
        if trade.status == "open" and not trade.escrow_released:
            wealth[trade.from_agent] = wealth.get(trade.from_agent, 0) + sum(
                RESOURCE_VALUES.get(item, 1) * qty for item, qty in trade.give.items()
            )
    resource_totals: Counter[str] = Counter()
    for row in state.tiles:
        for tile in row:
            resource_totals.update(tile.resources)
    for agent in state.agents.values():
        resource_totals.update(agent.inventory)
    for structure in state.structures.values():
        resource_totals.update(structure.inventory)
    for pile in state.item_piles.values():
        resource_totals[pile.item] += pile.quantity
    for trade in state.trades.values():
        if trade.status == "open" and not trade.escrow_released:
            resource_totals.update(trade.give)

    event_counts = Counter(event.type for event in state.events)
    complete_structures = [structure for structure in state.structures.values() if structure.is_complete]
    in_progress_structures = [structure for structure in state.structures.values() if not structure.is_complete]
    structure_counts = Counter(structure.type for structure in complete_structures)
    invalid_reasons = Counter(event.message for event in state.events if event.type == "invalid_action")
    llm_failures = [event for event in state.events if is_decision_failure_message(event.type, event.message)]
    build_readiness = _build_readiness(state)
    death_ticks = {event.actor_id: event.tick for event in state.events if event.type == "death"}
    lifespans = sorted(death_ticks.get(agent.id, state.tick) for agent in state.agents.values())
    spare_ap_samples = [int(sample.get("spare_ap", 0)) for sample in state.capacity_samples]
    energy_samples = [int(sample.get("energy", 0)) for sample in state.capacity_samples]
    trade_volume = 0
    for event in state.events:
        if event.type == "accept_trade":
            value = event.data.get("value", {})
            trade_volume += int(value.get("give", 0)) + int(value.get("receive", 0))

    return {
        "tick": state.tick,
        "agents": {
            "total": len(state.agents),
            "living": len(living_agents),
            "dead": len(state.agents) - len(living_agents),
            "median_lifespan": _median(lifespans),
            "min_lifespan": lifespans[0] if lifespans else 0,
            "max_lifespan": lifespans[-1] if lifespans else 0,
        },
        "capacity": {
            "samples": len(state.capacity_samples),
            "median_spare_action_points": _median(spare_ap_samples),
            "median_energy": _median(energy_samples),
            "agent_ticks_with_spare_capacity_pct": (
                round(100 * sum(1 for value in spare_ap_samples if value > 0) / len(spare_ap_samples), 1)
                if spare_ap_samples
                else 0.0
            ),
        },
        "resources": dict(sorted(resource_totals.items())),
        "wealth": wealth,
        "wealth_gini": _gini(list(wealth.values())),
        "claims": {
            "tiles": sum(1 for row in state.tiles for tile in row if tile.claimed_by),
            "structures": len(state.structures),
            "item_piles": sum(1 for pile in state.item_piles.values() if pile.owner_id),
        },
        "infrastructure": {
            "structures_by_type": dict(sorted(structure_counts.items())),
            "storage_used": sum(structure.inventory_weight() for structure in complete_structures),
            "storage_capacity": sum(structure.capacity for structure in complete_structures),
            "farm_plots": structure_counts.get("farm_plot", 0),
            "wells": structure_counts.get("well", 0),
            "houses": structure_counts.get("house", 0),
            "workshops": structure_counts.get("workshop", 0),
            "builds": event_counts.get("build", 0),
            "ever_buildable": sorted(state.build_ready_ever),
            "never_buildable": sorted(STRUCTURE_TYPES - set(state.build_ready_ever)),
            "farm_actions": event_counts.get("farm", 0),
            "harvest_actions": event_counts.get("harvest", 0),
            "improved_food_gather_actions": sum(
                1 for event in state.events if event.type == "gather" and event.data.get("improved_land")
            ),
            "store_actions": event_counts.get("store", 0),
            "retrieve_actions": event_counts.get("retrieve", 0),
            "build_readiness": build_readiness,
        },
        "construction": {
            "sites_started": event_counts.get("build_started", 0),
            "sites_completed": event_counts.get("build", 0),
            "sites_in_progress": len(in_progress_structures),
            "contributions": event_counts.get("contribute", 0),
            "cooperative_sites": sum(1 for structure in state.structures.values() if len(structure.contributors) > 1),
            "in_progress_by_type": dict(sorted(Counter(structure.type for structure in in_progress_structures).items())),
        },
        "trade": {
            "open": sum(1 for trade in state.trades.values() if trade.status == "open"),
            "public_open": sum(1 for trade in state.trades.values() if trade.status == "open" and trade.to_agent == "any"),
            "accepted": sum(1 for trade in state.trades.values() if trade.status == "accepted"),
            "public_accepted": sum(1 for trade in state.trades.values() if trade.status == "accepted" and trade.to_agent == "any"),
            "rejected": sum(1 for trade in state.trades.values() if trade.status == "rejected"),
            "expired": sum(1 for trade in state.trades.values() if trade.status == "expired"),
            "volume": trade_volume,
        },
        "groups": {
            "count": len(state.groups),
            "memberships": sum(len(group.members) for group in state.groups.values()),
            "rules": sum(len(group.rules) for group in state.groups.values()),
            "agreements": sum(len(group.agreements) for group in state.groups.values()),
            "claimed_tiles": sum(1 for row in state.tiles for tile in row if tile.claimed_by in state.groups),
            "owned_structures": sum(1 for structure in state.structures.values() if structure.owner_id in state.groups),
        },
        "events": dict(sorted(event_counts.items())),
        "invalid_actions": {
            "total": event_counts.get("invalid_action", 0),
            "reasons": dict(invalid_reasons.most_common()),
        },
        "llm": {
            "decision_failures": len(llm_failures),
            "quota_failures": sum(is_quota_failure_message(event.type, event.message) for event in state.events),
            "rate_limit_failures": sum(
                ("429" in event.message or "rate_limit" in event.message)
                and not is_quota_failure_message(event.type, event.message)
                for event in llm_failures
            ),
        },
    }


def is_decision_failure_message(event_type: str | None, message: str | None) -> bool:
    if event_type != "agent_response" or not message:
        return False
    return message.startswith(
        (
            "OpenAI decision failed:",
            "OpenAI quota unavailable:",
            "Invalid JSON response:",
            "Agent brain failed:",
        )
    )


def is_quota_failure_message(event_type: str | None, message: str | None) -> bool:
    if event_type != "agent_response" or not message:
        return False
    return message.startswith("OpenAI quota unavailable:") or "insufficient_quota" in message


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def _gini(values: list[int]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    total = sum(sorted_values)
    if total == 0:
        return 0.0
    weighted_sum = sum((index + 1) * value for index, value in enumerate(sorted_values))
    n = len(sorted_values)
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


def _build_readiness(state: WorldState) -> dict[str, Any]:
    """Structure types each agent could start AND finish from its own inventory right now.

    With construction sites a build no longer needs everything at once, so this is only the
    "instant build" signal; staged progress shows up in the construction metrics instead.
    """
    ready_counts: Counter[str] = Counter()
    for agent in state.agents.values():
        if not agent.alive:
            continue
        tile = state.tile_at(agent.position)
        for structure_type in STRUCTURE_TYPES:
            recipe = RECIPES[structure_type]
            missing = {
                item: qty - agent.inventory.get(item, 0)
                for item, qty in recipe.inputs.items()
                if agent.inventory.get(item, 0) < qty
            }
            terrain_ok = not recipe.required_terrain or tile.terrain in recipe.required_terrain
            energy_ok = agent.needs.energy >= recipe.energy
            claim_ok = not tile.claimed_by or _controls_owner(agent, tile.claimed_by) or _has_access_grant(agent, tile.access)
            duplicate_ok = not (
                structure_type in {"farm_plot", "well"}
                and any(state.structures[sid].type == structure_type for sid in tile.structure_ids)
            )
            if not missing and terrain_ok and energy_ok and claim_ok and duplicate_ok:
                ready_counts[structure_type] += 1
    return {"ready_counts": dict(sorted(ready_counts.items()))}


def _has_access_grant(agent: Any, access: set[str]) -> bool:
    return agent.id in access or bool(agent.groups.intersection(access))


def _controls_owner(agent: Any, owner_id: str | None) -> bool:
    return owner_id == agent.id or (owner_id is not None and owner_id in agent.groups)
