"""Metrics for inspecting emergent economy and society signals."""

from __future__ import annotations

from collections import Counter
from typing import Any

from agent_world.models import WorldState
from agent_world.models import CreditContract, DeliveryContract
from agent_world.rules import ACCOUNTING_VALUES, STRUCTURE_TYPES, recipes_for_mode


def compute_metrics(state: WorldState) -> dict[str, Any]:
    living_agents = [agent for agent in state.agents.values() if agent.alive]
    wealth = {
        agent.id: sum(ACCOUNTING_VALUES.get(item, 1) * qty for item, qty in agent.inventory.items())
        for agent in state.agents.values()
    }
    for trade in state.trades.values():
        if trade.status == "open" and not trade.escrow_released:
            wealth[trade.from_agent] = wealth.get(trade.from_agent, 0) + sum(
                ACCOUNTING_VALUES.get(item, 1) * qty * getattr(trade, "lots_remaining", 1)
                for item, qty in trade.give.items()
            )
    for contract in getattr(state, "contracts", {}).values():
        if isinstance(contract, CreditContract) and contract.status == "offered" and not contract.advance_released:
            wealth[contract.lender_id] = wealth.get(contract.lender_id, 0) + _item_value(contract.advance)
        if isinstance(contract, CreditContract) and contract.status == "active" and not contract.collateral_released:
            wealth[contract.borrower_id] = wealth.get(contract.borrower_id, 0) + _item_value(contract.collateral)
        if isinstance(contract, DeliveryContract) and contract.status == "active":
            if contract.buyer_id:
                wealth[contract.buyer_id] = wealth.get(contract.buyer_id, 0) + _item_value(contract.receive)
            wealth[contract.proposer_id] = wealth.get(contract.proposer_id, 0) + _item_value(contract.collateral)
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
            resource_totals.update(
                {
                    item: quantity * getattr(trade, "lots_remaining", 1)
                    for item, quantity in trade.give.items()
                }
            )
    for contract in getattr(state, "contracts", {}).values():
        if isinstance(contract, CreditContract) and contract.status == "offered" and not contract.advance_released:
            resource_totals.update(contract.advance)
        if isinstance(contract, CreditContract) and contract.status == "active" and not contract.collateral_released:
            resource_totals.update(contract.collateral)
        if isinstance(contract, DeliveryContract) and contract.status == "active":
            resource_totals.update(contract.receive)
            resource_totals.update(contract.collateral)

    event_counts = Counter(event.type for event in state.events)
    complete_structures = [structure for structure in state.structures.values() if structure.is_complete]
    in_progress_structures = [structure for structure in state.structures.values() if not structure.is_complete]
    structure_counts = Counter(structure.type for structure in complete_structures)
    invalid_reasons = Counter(event.message for event in state.events if event.type == "invalid_action")
    contention_reasons = Counter(event.message for event in state.events if event.type == "contention_failure")
    llm_failures = [event for event in state.events if is_decision_failure_message(event.type, event.message)]
    build_readiness = _build_readiness(state)
    death_ticks = {event.actor_id: event.tick for event in state.events if event.type == "death"}
    lifespans = sorted(death_ticks.get(agent.id, state.tick) for agent in state.agents.values())
    spare_ap_samples = [int(sample.get("spare_ap", 0)) for sample in state.capacity_samples]
    energy_samples = [int(sample.get("energy", 0)) for sample in state.capacity_samples]
    trade_volume = 0
    for event in state.events:
        if event.type in {"accept_trade", "contract_settled"}:
            trade = event.data.get("trade") or event.data.get("contract") or {}
            trade_volume += _item_value(trade.get("give", {}))
            trade_volume += _item_value(trade.get("receive", {}))
    economic_flows = _economic_flow_metrics(state)
    specialization = _specialization_metrics(state)
    productive_assets = _productive_asset_metrics(state, wealth)

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
        "productive_assets": productive_assets,
        "economic_flows": economic_flows,
        "specialization": specialization,
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
            "accepted": event_counts.get("accept_trade", 0),
            "public_accepted": sum(
                1
                for event in state.events
                if event.type == "accept_trade"
                and isinstance(event.data.get("trade"), dict)
                and event.data["trade"].get("public")
            ),
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
        "action_failures": {
            "total": event_counts.get("invalid_action", 0) + event_counts.get("contention_failure", 0),
            "invalid_proposals": event_counts.get("invalid_action", 0),
            "contention_failures": event_counts.get("contention_failure", 0),
            "contention_reasons": dict(contention_reasons.most_common()),
            "contention_causes": dict(
                Counter(
                    event.data.get("contention_cause", "unspecified")
                    for event in state.events
                    if event.type == "contention_failure"
                ).most_common()
            ),
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
            "OpenRouter decision failed:",
            "OpenRouter harness failed:",
            "OpenRouter boundary failed:",
            "OpenRouter model output failed:",
            "OpenRouter model output contract failed:",
            "OpenRouter quota unavailable:",
            "OpenRouter provider unavailable:",
            "OpenAI decision failed:",
            "OpenAI harness failed:",
            "OpenAI boundary failed:",
            "OpenAI model output failed:",
            "OpenAI model output contract failed:",
            "OpenAI quota unavailable:",
            "Codex decision failed:",
            "Codex harness failed:",
            "Codex boundary failed:",
            "Codex model output failed:",
            "Codex model output contract failed:",
            "Codex quota unavailable:",
            "Codex provider unavailable:",
            "Claude decision failed:",
            "Claude harness failed:",
            "Claude boundary failed:",
            "Claude model output failed:",
            "Claude model output contract failed:",
            "Claude quota unavailable:",
            "Claude provider unavailable:",
            "Cursor decision failed:",
            "Cursor harness failed:",
            "Cursor boundary failed:",
            "Cursor model output failed:",
            "Cursor model output contract failed:",
            "Cursor quota unavailable:",
            "Cursor provider unavailable:",
            "Devin decision failed:",
            "Devin harness failed:",
            "Devin boundary failed:",
            "Devin model output failed:",
            "Devin model output contract failed:",
            "Devin quota unavailable:",
            "Devin provider unavailable:",
            "Grok decision failed:",
            "Grok harness failed:",
            "Grok boundary failed:",
            "Grok model output failed:",
            "Grok model output contract failed:",
            "Grok quota unavailable:",
            "Grok provider unavailable:",
            "ZCode decision failed:",
            "ZCode harness failed:",
            "ZCode boundary failed:",
            "ZCode model output failed:",
            "ZCode model output contract failed:",
            "ZCode quota unavailable:",
            "ZCode provider unavailable:",
            "Invalid JSON response:",
            "Agent brain failed:",
        )
    )


def is_quota_failure_message(event_type: str | None, message: str | None) -> bool:
    if event_type != "agent_response" or not message:
        return False
    return (
        message.startswith(
            (
                "OpenRouter quota unavailable:",
                "OpenAI quota unavailable:",
                "Codex quota unavailable:",
                "Claude quota unavailable:",
                "Cursor quota unavailable:",
                "Devin quota unavailable:",
                "Grok quota unavailable:",
                "ZCode quota unavailable:",
            )
        )
        or "insufficient_quota" in message
    )


def is_provider_failure_message(event_type: str | None, message: str | None) -> bool:
    if event_type != "agent_response" or not message:
        return False
    return message.startswith(
        (
            "OpenRouter provider unavailable:",
            "Claude provider unavailable:",
            "Codex provider unavailable:",
            "Cursor provider unavailable:",
            "Devin provider unavailable:",
            "OpenAI provider unavailable:",
            "Grok provider unavailable:",
            "ZCode provider unavailable:",
        )
    )


def is_model_output_failure_message(
    event_type: str | None,
    message: str | None,
) -> bool:
    """Return whether a completed provider turn contained unusable model output."""

    if event_type != "agent_response" or not message:
        return False
    return message.startswith(
        (
            "OpenRouter model output failed:",
            "OpenRouter model output contract failed:",
            "OpenAI model output failed:",
            "OpenAI model output contract failed:",
            "Codex model output failed:",
            "Codex model output contract failed:",
            "Claude model output failed:",
            "Claude model output contract failed:",
            "Cursor model output failed:",
            "Cursor model output contract failed:",
            "Devin model output failed:",
            "Devin model output contract failed:",
            "Grok model output failed:",
            "Grok model output contract failed:",
            "ZCode model output failed:",
            "ZCode model output contract failed:",
            "Codex decision failed: Codex action arguments_json is invalid:",
            "Codex decision failed: Codex action arguments_json must decode to an object",
            "Codex decision failed: Codex decision was not a JSON object",
            "Invalid JSON response:",
        )
    ) or _is_structured_output_exhaustion_message(message)


def _is_structured_output_exhaustion_message(message: str) -> bool:
    """Return whether a boundary failure was the provider's schema retries running out.

    Scoring revision 2. Runs recorded before the adapter separated this case
    logged it under the generic boundary prefix, which counted it as an
    ambiguous failure and invalidated the trial. The provider validated every
    attempt against the decision schema and exhausted its retries, so the fault
    is the model's output contract. Matching the retained message reclassifies
    those preserved ledgers from the raw evidence without re-running a trial or
    changing any trial behavior. Attribution stays unverified, because no failed
    payload was surfaced for the independent contract validator.
    """

    return (
        message.startswith("Claude boundary failed:")
        and "error_max_structured_output_retries" in message
    )


def is_confirmed_model_contract_failure_message(
    event_type: str | None,
    message: str | None,
) -> bool:
    if event_type != "agent_response" or not message:
        return False
    return message.startswith(
        (
            "OpenRouter model output contract failed:",
            "OpenAI model output contract failed:",
            "Codex model output contract failed:",
            "Claude model output contract failed:",
            "Cursor model output contract failed:",
            "Devin model output contract failed:",
            "Grok model output contract failed:",
            "ZCode model output contract failed:",
        )
    )


def is_ambiguous_boundary_failure_message(
    event_type: str | None,
    message: str | None,
) -> bool:
    if event_type != "agent_response" or not message:
        return False
    if _is_structured_output_exhaustion_message(message):
        # Attributed to model output, not to an undiagnosable boundary.
        return False
    return message.startswith(
        (
            "OpenRouter boundary failed:",
            "OpenAI boundary failed:",
            "Codex boundary failed:",
            "Claude boundary failed:",
            "Cursor boundary failed:",
            "Devin boundary failed:",
            "Grok boundary failed:",
            "ZCode boundary failed:",
        )
    )


def is_harness_failure_message(
    event_type: str | None,
    message: str | None,
) -> bool:
    if event_type != "agent_response" or not message:
        return False
    return message.startswith(
        (
            "OpenRouter harness failed:",
            "OpenRouter decision failed:",
            "OpenAI harness failed:",
            "Codex harness failed:",
            "Claude harness failed:",
            "Cursor harness failed:",
            "Devin harness failed:",
            "Grok harness failed:",
            "ZCode harness failed:",
            "OpenAI decision failed:",
            "Codex decision failed:",
            "Claude decision failed:",
            "Cursor decision failed:",
            "Devin decision failed:",
            "Grok decision failed:",
            "ZCode decision failed:",
            "Agent brain failed:",
        )
    ) and not is_model_output_failure_message(event_type, message)


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


def _item_value(items: dict[str, int] | Counter[str]) -> int:
    return sum(ACCOUNTING_VALUES.get(item, 1) * int(quantity) for item, quantity in items.items())


def _economic_flow_metrics(state: WorldState) -> dict[str, Any]:
    gift_events = [event for event in state.events if event.type == "gift"]
    gift_by_item: Counter[str] = Counter()
    gift_edges: Counter[str] = Counter()
    within_group_actions = 0
    for event in gift_events:
        items = event.data.get("items", {})
        if isinstance(items, dict):
            gift_by_item.update({str(item): int(qty) for item, qty in items.items() if int(qty) > 0})
        recipient = str(event.data.get("to", ""))
        gift_edges[f"{event.actor_id}->{recipient}"] += 1
        giver = state.agents.get(str(event.actor_id))
        receiver = state.agents.get(recipient)
        if giver is not None and receiver is not None and giver.groups.intersection(receiver.groups):
            within_group_actions += 1

    accept_events = [
        event for event in state.events if event.type in {"accept_trade", "contract_settled"}
    ]
    acceptance_latencies = []
    trade_value = 0
    for event in accept_events:
        trade = event.data.get("trade") or event.data.get("contract") or {}
        if isinstance(trade, dict):
            created = trade.get("created_tick")
            if isinstance(created, int):
                acceptance_latencies.append(max(0, event.tick - created))
            give = trade.get("give", {})
            receive = trade.get("receive", {})
            if isinstance(give, dict):
                trade_value += _item_value(give)
            if isinstance(receive, dict):
                trade_value += _item_value(receive)

    reciprocal_edges = sum(
        1
        for edge in gift_edges
        if "->" in edge and f"{edge.split('->', 1)[1]}->{edge.split('->', 1)[0]}" in gift_edges
    ) // 2
    offers = sum(event.type == "offer_trade" for event in state.events)
    invalid_accepts = sum(
        event.type in {"invalid_action", "contention_failure"}
        and isinstance(event.data.get("action"), dict)
        and event.data["action"].get("type") == "accept_trade"
        for event in state.events
    )
    contract_types = (
        "create_contract",
        "accept_contract",
        "fulfill_contract",
        "default_contract",
        "repay_contract",
        "contract_proposed",
        "contract_accepted",
        "contract_settled",
        "contract_defaulted",
        "contract_cancelled",
        "contract_expired",
    )
    return {
        "gifts": {
            "actions": len(gift_events),
            "units": sum(gift_by_item.values()),
            "value": _item_value(gift_by_item),
            "by_item": dict(sorted(gift_by_item.items())),
            "subsistence_units": gift_by_item.get("food", 0) + gift_by_item.get("water", 0),
            "productive_input_units": sum(
                quantity for item, quantity in gift_by_item.items() if item not in {"food", "water"}
            ),
            "edges": dict(sorted(gift_edges.items())),
            "reciprocal_pairs": reciprocal_edges,
            "within_final_group_actions": within_group_actions,
        },
        "market": {
            "offers": offers,
            "accepted": len(accept_events),
            "conversion_pct": round(100 * len(accept_events) / offers, 1) if offers else 0.0,
            "invalid_accept_attempts": invalid_accepts,
            "transfer_value": trade_value,
            "median_acceptance_ticks": _median(acceptance_latencies),
            "completed_price_history": len(getattr(state, "market_history", [])),
        },
        "contracts": {
            event_type: sum(event.type == event_type for event in state.events)
            for event_type in contract_types
        },
    }


def _specialization_metrics(state: WorldState) -> dict[str, Any]:
    productive_types = {"gather", "chop", "mine", "harvest", "fish", "farm", "craft"}
    by_agent: dict[str, Counter[str]] = {agent_id: Counter() for agent_id in state.agents}
    by_action: dict[str, Counter[str]] = {action: Counter() for action in productive_types}
    for event in state.events:
        if event.type not in productive_types or event.actor_id not in by_agent:
            continue
        by_agent[event.actor_id][event.type] += 1
        by_action[event.type][event.actor_id] += 1

    agent_rows: dict[str, Any] = {}
    agent_hhi: list[float] = []
    for agent_id, counts in sorted(by_agent.items()):
        total = sum(counts.values())
        hhi = sum((count / total) ** 2 for count in counts.values()) if total else 0.0
        if total:
            agent_hhi.append(hhi)
        agent_rows[agent_id] = {
            "actions": dict(counts.most_common()),
            "dominant_activity": counts.most_common(1)[0][0] if counts else None,
            "activity_concentration": round(hhi, 3),
        }

    occupation_hhi = []
    for counts in by_action.values():
        total = sum(counts.values())
        if total:
            occupation_hhi.append(sum((count / total) ** 2 for count in counts.values()))
    return {
        "agents": agent_rows,
        "mean_agent_activity_concentration": round(sum(agent_hhi) / len(agent_hhi), 3) if agent_hhi else 0.0,
        "division_of_labor_index": round(sum(occupation_hhi) / len(occupation_hhi), 3) if occupation_hhi else 0.0,
    }


def _productive_asset_metrics(state: WorldState, inventory_wealth: dict[str, int]) -> dict[str, Any]:
    recipes = recipes_for_mode(
        state.config.economy_mode, getattr(state.config, "world_variant", "classic")
    )
    owner_values: Counter[str] = Counter()
    structure_values: dict[str, int] = {}
    for structure in state.structures.values():
        recipe = recipes.get(structure.type)
        replacement_value = _item_value(dict(recipe.inputs)) if recipe is not None else 0
        stored_value = _item_value(structure.inventory)
        value = replacement_value + stored_value
        structure_values[structure.id] = value
        owner_values[structure.owner_id] += value

    extended = {agent_id: int(value) for agent_id, value in inventory_wealth.items()}
    for owner_id, value in owner_values.items():
        if owner_id in extended:
            extended[owner_id] += value
            continue
        group = state.groups.get(owner_id)
        if group is None or not group.members:
            continue
        quotient, remainder = divmod(value, len(group.members))
        for index, agent_id in enumerate(sorted(group.members)):
            extended[agent_id] = extended.get(agent_id, 0) + quotient + (1 if index < remainder else 0)
    return {
        "structure_replacement_value": dict(sorted(structure_values.items())),
        "value_by_owner": dict(sorted(owner_values.items())),
        "agent_wealth_including_asset_shares": dict(sorted(extended.items())),
        "asset_adjusted_gini": _gini(list(extended.values())),
    }


def _build_readiness(state: WorldState) -> dict[str, Any]:
    """Structure types each agent could start AND finish from its own inventory right now.

    With construction sites a build no longer needs everything at once, so this is only the
    "instant build" signal; staged progress shows up in the construction metrics instead.
    """
    ready_counts: Counter[str] = Counter()
    recipes = recipes_for_mode(
        state.config.economy_mode, getattr(state.config, "world_variant", "classic")
    )
    for agent in state.agents.values():
        if not agent.alive:
            continue
        tile = state.tile_at(agent.position)
        for structure_type in STRUCTURE_TYPES:
            recipe = recipes[structure_type]
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
