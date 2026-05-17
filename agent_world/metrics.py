"""Metrics for inspecting emergent economy and society signals."""

from __future__ import annotations

from collections import Counter
from typing import Any

from agent_world.models import WorldState
from agent_world.rules import RESOURCE_VALUES


def compute_metrics(state: WorldState) -> dict[str, Any]:
    living_agents = [agent for agent in state.agents.values() if agent.alive]
    wealth = {
        agent.id: sum(RESOURCE_VALUES.get(item, 1) * qty for item, qty in agent.inventory.items())
        for agent in state.agents.values()
    }
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

    event_counts = Counter(event.type for event in state.events)
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
        },
        "resources": dict(sorted(resource_totals.items())),
        "wealth": wealth,
        "wealth_gini": _gini(list(wealth.values())),
        "claims": {
            "tiles": sum(1 for row in state.tiles for tile in row if tile.claimed_by),
            "structures": len(state.structures),
            "item_piles": sum(1 for pile in state.item_piles.values() if pile.owner_id),
        },
        "trade": {
            "open": sum(1 for trade in state.trades.values() if trade.status == "open"),
            "accepted": sum(1 for trade in state.trades.values() if trade.status == "accepted"),
            "rejected": sum(1 for trade in state.trades.values() if trade.status == "rejected"),
            "expired": sum(1 for trade in state.trades.values() if trade.status == "expired"),
            "volume": trade_volume,
        },
        "groups": {
            "count": len(state.groups),
            "memberships": sum(len(group.members) for group in state.groups.values()),
            "rules": sum(len(group.rules) for group in state.groups.values()),
        },
        "events": dict(sorted(event_counts.items())),
    }


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
