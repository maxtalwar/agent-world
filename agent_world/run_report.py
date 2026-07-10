"""Structured per-run data export for cross-run iteration.

Every run distills into a `<stem>-report.json` (machine-readable, self-contained:
config, outcomes, milestones, economy networks, full say transcript) and a
`<stem>-report.md` (human-readable summary). Reports from different runs are
directly comparable because they share one schema.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from agent_world.metrics import is_decision_failure_message, is_quota_failure_message
from agent_world.rules import RECIPES, RESOURCE_VALUES

AGENT_IO_EVENT_TYPES = {"agent_observation", "agent_prompt", "agent_response"}
SUBSISTENCE_ITEMS = frozenset({"food", "water"})
MILESTONE_EVENT_TYPES = (
    "build_started",
    "build",
    "create_group",
    "join_group",
    "offer_trade",
    "accept_trade",
    "gift",
    "claim_tile",
    "grant_access",
    "craft",
    "death",
    "publish_rule",
    "record_agreement",
)


def build_report(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    usage_records: list[dict[str, Any]] | None = None,
    source: str | None = None,
    target_ticks: int | None = None,
) -> dict[str, Any]:
    usage_records = usage_records or []
    sim_events = [event for event in events if event["type"] not in AGENT_IO_EVENT_TYPES]
    action_counts = Counter(event["type"] for event in sim_events)
    final_tick = snapshot.get("tick", max((event["tick"] for event in events), default=0))
    run_summary = _summarize_run(sim_events, final_tick=final_tick, explicit_target_ticks=target_ticks)

    deaths = [
        {"tick": event["tick"], "agent": event["actor_id"], "message": event["message"]}
        for event in sim_events
        if event["type"] == "death"
    ]
    agents = {
        agent_id: {
            "alive": agent.get("alive"),
            "health": agent.get("health"),
            "inventory": {item: qty for item, qty in (agent.get("inventory") or {}).items() if qty},
            "groups": agent.get("groups", []),
            "wealth": sum(
                RESOURCE_VALUES.get(item, 1) * qty for item, qty in (agent.get("inventory") or {}).items()
            ),
        }
        for agent_id, agent in sorted(snapshot.get("agents", {}).items())
    }

    structures = list(snapshot.get("structures", {}).values())
    complete = [structure for structure in structures if structure.get("status") == "complete"]
    coop_builds = [structure for structure in structures if len(structure.get("contributors", [])) > 1]
    structure_timeline = [
        {"tick": event["tick"], "agent": event["actor_id"], "message": event["message"]}
        for event in sim_events
        if event["type"] == "build_started"
        or (event["type"] == "build" and "completed" in (event.get("message") or ""))
    ]

    transfer_group_context = _transfer_group_context(events, snapshot)
    gifts = _summarize_gifts(sim_events, transfer_group_context)
    trades = _summarize_trades(sim_events, snapshot, transfer_group_context)
    construction = _summarize_construction_economy(sim_events, snapshot)
    institutions = _summarize_economic_institutions(sim_events, snapshot)

    invalid_reasons = Counter(
        event["message"] for event in sim_events if event["type"] == "invalid_action"
    )
    llm_failures = [
        event
        for event in events
        if is_decision_failure_message(event.get("type"), event.get("message"))
    ]

    firsts: dict[str, int] = {}
    for event in sim_events:
        if event["type"] in MILESTONE_EVENT_TYPES and event["type"] not in firsts:
            firsts[event["type"]] = event["tick"]

    says = [
        {
            "tick": event["tick"],
            "agent": event["actor_id"],
            "scope": event.get("scope"),
            "message": event.get("message"),
        }
        for event in sim_events
        if event["type"] == "say"
    ]

    total_cost = sum(record.get("cost") or 0 for record in usage_records)
    prompt_tokens = sum(record.get("prompt_tokens") or 0 for record in usage_records)
    cached_tokens = sum(record.get("cached_tokens") or 0 for record in usage_records)
    usage = {
        "calls": len(usage_records),
        "total_cost_usd": round(total_cost, 4),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": sum(record.get("completion_tokens") or 0 for record in usage_records),
        "reasoning_tokens": sum(record.get("reasoning_tokens") or 0 for record in usage_records),
        "cache_hit_rate_pct": round(100 * cached_tokens / prompt_tokens, 1) if prompt_tokens else 0.0,
    }

    wealth_values = [agent["wealth"] for agent in agents.values()]
    return {
        "schema_version": 1,
        "source": source,
        "run": run_summary,
        "config": snapshot.get("config", {}),
        "survival": {
            "living": sum(1 for agent in agents.values() if agent["alive"]),
            "dead": len(deaths),
            "deaths": deaths,
            "survival_damage_events": action_counts.get("survival_damage", 0),
            "agents": agents,
        },
        "actions": {
            "counts": dict(action_counts.most_common()),
            "per_agent": {
                agent_id: dict(
                    Counter(
                        event["type"]
                        for event in sim_events
                        if event.get("actor_id") == agent_id and event["type"] != "say"
                    ).most_common()
                )
                for agent_id in agents
            },
            "invalid_total": action_counts.get("invalid_action", 0),
            "invalid_reasons": dict(invalid_reasons.most_common()),
        },
        "structures": {
            "complete": dict(Counter(structure["type"] for structure in complete)),
            "in_progress": dict(
                Counter(structure["type"] for structure in structures if structure.get("status") != "complete")
            ),
            "ownership": dict(Counter(structure.get("owner_id") for structure in structures)),
            "coop_builds": [
                {"type": structure["type"], "contributors": structure.get("contributors", [])}
                for structure in coop_builds
            ],
            "timeline": structure_timeline,
        },
        "groups": {
            group_id: {"name": group.get("name"), "members": group.get("members", [])}
            for group_id, group in snapshot.get("groups", {}).items()
        },
        "economy": {
            **gifts,
            "trades": trades,
            "construction": construction,
            "institutions": institutions,
            "food_spoilage_events": action_counts.get("food_spoilage", 0),
            "claimed_tiles": action_counts.get("claim_tile", 0),
            "access_grants": action_counts.get("grant_access", 0),
        },
        "communication": {
            "says_total": len(says),
            "says_per_agent": dict(Counter(say["agent"] for say in says)),
        },
        "milestone_first_ticks": firsts,
        "reliability": {
            "llm_failure_events": len(llm_failures),
            "llm_quota_failure_events": sum(
                is_quota_failure_message(event.get("type"), event.get("message")) for event in llm_failures
            ),
            "llm_failures_by_agent": dict(
                Counter(event.get("actor_id") or "unknown" for event in llm_failures).most_common()
            ),
            "invalid_action_rate_pct": (
                round(100 * action_counts.get("invalid_action", 0) / len(sim_events), 1) if sim_events else 0.0
            ),
        },
        "usage": usage,
        "wealth_gini": _gini(wealth_values),
        "transcript": says,
    }


def _summarize_run(
    events: list[dict[str, Any]],
    final_tick: int,
    explicit_target_ticks: int | None,
) -> dict[str, Any]:
    started_index = next(
        (
            index
            for index in range(len(events) - 1, -1, -1)
            if events[index].get("type") == "run_started"
        ),
        None,
    )
    started_event = events[started_index] if started_index is not None else None
    terminal_search_start = started_index + 1 if started_index is not None else 0
    terminal_event = next(
        (
            events[index]
            for index in range(len(events) - 1, terminal_search_start - 1, -1)
            if events[index].get("type") in {"run_completed", "run_stopped", "run_failed"}
        ),
        None,
    )

    target_ticks = _positive_int(explicit_target_ticks)
    if target_ticks is None and terminal_event is not None:
        target_ticks = _positive_int((terminal_event.get("data") or {}).get("target_ticks"))
    if target_ticks is None and started_event is not None:
        started_data = started_event.get("data") or {}
        target_ticks = _positive_int(started_data.get("target_ticks"))
        if target_ticks is None:
            target_ticks = _positive_int((started_data.get("config") or {}).get("ticks"))

    if terminal_event is not None:
        terminal_type = terminal_event.get("type")
        completed = terminal_type == "run_completed"
        status = {
            "run_completed": "completed",
            "run_stopped": "stopped",
            "run_failed": "failed",
        }[terminal_type]
        terminal_data = terminal_event.get("data") or {}
        stop_reason = None
        if not completed:
            stop_reason = (
                terminal_data.get("reason")
                or terminal_data.get("error")
                or terminal_event.get("message")
                or status
            )
        completion_evidence = terminal_type
    elif started_event is not None:
        # A run_started marker establishes that lifecycle events are supported. If
        # its matching terminal marker is absent, the durable log was interrupted.
        completed = False
        status = "interrupted"
        stop_reason = "interrupted"
        completion_evidence = "missing_terminal_event"
    elif target_ticks is not None:
        completed = final_tick >= target_ticks
        status = "completed" if completed else "interrupted"
        stop_reason = None if completed else "interrupted"
        completion_evidence = "target_reached" if completed else "target_not_reached"
    else:
        # Pre-lifecycle logs had neither a target nor terminal markers. Preserve
        # their historical report semantics instead of reclassifying all of them.
        completed = True
        status = "completed"
        stop_reason = None
        completion_evidence = "legacy_assumed"

    return {
        "final_tick": final_tick,
        "target_ticks": target_ticks,
        "completed": completed,
        "status": status,
        "stop_reason": stop_reason,
        "completion_evidence": completion_evidence,
    }


def _summarize_gifts(
    events: list[dict[str, Any]],
    group_context: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    gift_events = [event for event in events if event.get("type") == "gift"]
    event_network: Counter[str] = Counter()
    quantity_network: Counter[str] = Counter()
    value_network: Counter[str] = Counter()
    items_total: Counter[str] = Counter()
    category_items: dict[str, Counter[str]] = {
        "subsistence": Counter(),
        "materials": Counter(),
    }
    event_categories: Counter[str] = Counter()
    group_statuses: Counter[str] = Counter()
    details: list[dict[str, Any]] = []

    for event in gift_events:
        data = event.get("data") or {}
        sender = event.get("actor_id")
        recipient = data.get("to")
        items = _positive_item_counts(data.get("items"))
        quantity = sum(items.values())
        value = _book_value(items)
        edge = f"{sender}->{recipient}"
        event_network[edge] += 1
        quantity_network[edge] += quantity
        value_network[edge] += value
        items_total.update(items)

        subsistence = Counter({item: qty for item, qty in items.items() if item in SUBSISTENCE_ITEMS})
        materials = Counter({item: qty for item, qty in items.items() if item not in SUBSISTENCE_ITEMS})
        category_items["subsistence"].update(subsistence)
        category_items["materials"].update(materials)
        if subsistence and materials:
            event_category = "mixed"
        elif subsistence:
            event_category = "subsistence_only"
        elif materials:
            event_category = "materials_only"
        else:
            event_category = "empty"
        event_categories[event_category] += 1

        context = group_context.get(id(event), {"status": "unknown", "shared_groups": []})
        group_statuses[context["status"]] += 1
        details.append(
            {
                "tick": event.get("tick"),
                "from": sender,
                "to": recipient,
                "items": dict(sorted(items.items())),
                "quantity": quantity,
                "value": value,
                "category": event_category,
                "group_status": context["status"],
                "shared_groups": context["shared_groups"],
            }
        )

    return {
        # Retain the original headline fields for report consumers.
        "gifts": len(gift_events),
        "gift_network": dict(event_network),
        "gift_quantity": sum(items_total.values()),
        "gift_value": _book_value(items_total),
        "gift_by_item": dict(sorted(items_total.items())),
        "gift_value_by_item": {
            item: RESOURCE_VALUES.get(item, 1) * quantity
            for item, quantity in sorted(items_total.items())
        },
        "gift_network_quantity": dict(quantity_network),
        "gift_network_value": dict(value_network),
        "gift_categories": {
            category: {
                "quantity": sum(items.values()),
                "value": _book_value(items),
                "by_item": dict(sorted(items.items())),
            }
            for category, items in category_items.items()
        },
        "gift_event_categories": {
            category: event_categories.get(category, 0)
            for category in ("subsistence_only", "materials_only", "mixed", "empty")
        },
        "gift_group_status": {
            status: group_statuses.get(status, 0) for status in ("in_group", "out_group", "unknown")
        },
        "gift_detail": details,
    }


def _summarize_trades(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    group_context: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    offered_events = [event for event in events if event.get("type") == "offer_trade"]
    accepted_events = [event for event in events if event.get("type") == "accept_trade"]
    rejected = sum(event.get("type") == "reject_trade" for event in events)
    expired = sum(event.get("type") == "expire_trade" for event in events)
    cancelled = sum(event.get("type") == "cancel_trade" for event in events)
    offers_by_id: dict[str, dict[str, Any]] = {}
    for event in offered_events:
        trade = (event.get("data") or {}).get("trade") or {}
        if trade.get("id"):
            offers_by_id[str(trade["id"])] = trade

    accepted_items: Counter[str] = Counter()
    accepted_value = 0
    accepted_give_value = 0
    accepted_receive_value = 0
    latencies: list[int] = []
    group_statuses: Counter[str] = Counter()
    accepted_transfer_detail: list[dict[str, Any]] = []
    for event in accepted_events:
        data = event.get("data") or {}
        trade = data.get("trade") or {}
        if not trade and data.get("trade_id"):
            trade = offers_by_id.get(str(data["trade_id"]), {})
        give = _positive_item_counts(trade.get("give"))
        receive = _positive_item_counts(trade.get("receive"))
        accepted_items.update(give)
        accepted_items.update(receive)
        values = data.get("value") or {}
        give_value = _nonnegative_int(values.get("give"), default=_book_value(give))
        receive_value = _nonnegative_int(values.get("receive"), default=_book_value(receive))
        accepted_give_value += give_value
        accepted_receive_value += receive_value
        accepted_value += give_value + receive_value

        created_tick = _nonnegative_int(trade.get("created_tick"), default=-1)
        accepted_tick = _nonnegative_int(event.get("tick"), default=-1)
        latency = accepted_tick - created_tick if created_tick >= 0 and accepted_tick >= created_tick else None
        if latency is not None:
            latencies.append(latency)

        context = group_context.get(id(event), {"status": "unknown", "shared_groups": []})
        group_statuses[context["status"]] += 1
        accepted_transfer_detail.append(
            {
                "tick": event.get("tick"),
                "trade_id": trade.get("id"),
                "from": trade.get("from_agent"),
                "to": trade.get("accepted_by") or event.get("actor_id"),
                "give": dict(sorted(give.items())),
                "receive": dict(sorted(receive.items())),
                "give_value": give_value,
                "receive_value": receive_value,
                "latency_ticks": latency,
                "group_status": context["status"],
                "shared_groups": context["shared_groups"],
            }
        )

    invalid_accept_events = [
        event
        for event in events
        if event.get("type") == "invalid_action"
        and ((event.get("data") or {}).get("action") or {}).get("type") == "accept_trade"
    ]
    invalid_accept_reasons = Counter(event.get("message") or "unknown" for event in invalid_accept_events)
    offered = len(offered_events)
    accepted = len(accepted_events)
    accept_attempts = accepted + len(invalid_accept_events)
    resolved = accepted + rejected + expired + cancelled
    snapshot_trades = snapshot.get("trades") or {}
    if isinstance(snapshot_trades, dict):
        status_counts = Counter(
            (trade or {}).get("status", "unknown") for trade in snapshot_trades.values()
        )
    else:
        status_counts = Counter()
    public_offers = sum(bool(((event.get("data") or {}).get("trade") or {}).get("public")) for event in offered_events)
    offered_group_statuses = Counter(
        group_context.get(id(event), {"status": "unknown"})["status"] for event in offered_events
    )

    return {
        "offered": offered,
        "accepted": accepted,
        "rejected": rejected,
        "expired": expired,
        "cancelled": cancelled,
        "open": status_counts.get("open", 0),
        "status_counts": dict(sorted(status_counts.items())),
        "public_offered": public_offers,
        "direct_offered": offered - public_offers,
        "conversion_rate_pct": round(100 * accepted / offered, 1) if offered else 0.0,
        "resolution_rate_pct": round(100 * resolved / offered, 1) if offered else 0.0,
        "resolved_conversion_rate_pct": round(100 * accepted / resolved, 1) if resolved else 0.0,
        "accepted_value": accepted_value,
        "accepted_give_value": accepted_give_value,
        "accepted_receive_value": accepted_receive_value,
        "accepted_by_item": dict(sorted(accepted_items.items())),
        "acceptance_latency_ticks": _latency_summary(latencies),
        "accept_attempts": accept_attempts,
        "accept_success_rate_pct": round(100 * accepted / accept_attempts, 1) if accept_attempts else 0.0,
        "invalid_accepts": len(invalid_accept_events),
        "invalid_accept_reasons": dict(invalid_accept_reasons.most_common()),
        "offered_group_status": {
            status: offered_group_statuses.get(status, 0)
            for status in ("in_group", "out_group", "unknown")
        },
        "accepted_group_status": {
            status: group_statuses.get(status, 0) for status in ("in_group", "out_group", "unknown")
        },
        "accepted_detail": [
            (event.get("data") or {}).get("trade") for event in accepted_events
        ],
        "accepted_transfer_detail": accepted_transfer_detail,
    }


def _transfer_group_context(
    events: list[dict[str, Any]],
    _snapshot: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    """Classify transfers using group membership at the event's position in the log.

    A complete world log starts with world_created. For partial logs, a known
    shared group is still reportable, while a missing shared group remains
    unknown rather than being mislabeled as out-of-group.
    """

    complete_history = any(event.get("type") == "world_created" for event in events)
    members_by_group: dict[str, set[str]] = {}
    contexts: dict[int, dict[str, Any]] = {}
    for event in events:
        event_type = event.get("type")
        if event_type in {"create_group", "join_group", "leave_group"}:
            data = event.get("data") or {}
            group = data.get("group") or {}
            group_id = group.get("id") or data.get("group_id")
            if group_id:
                if isinstance(group.get("members"), list):
                    members_by_group[str(group_id)] = {str(member) for member in group["members"]}
                else:
                    members = members_by_group.setdefault(str(group_id), set())
                    actor = event.get("actor_id")
                    if actor and event_type in {"create_group", "join_group"}:
                        members.add(str(actor))
                    elif actor and event_type == "leave_group":
                        members.discard(str(actor))

        parties: tuple[Any, Any] | None = None
        if event_type == "gift":
            parties = (event.get("actor_id"), (event.get("data") or {}).get("to"))
        elif event_type == "offer_trade":
            trade = (event.get("data") or {}).get("trade") or {}
            recipient = trade.get("to_agent")
            parties = (
                trade.get("from_agent") or event.get("actor_id"),
                None if recipient in {None, "any"} else recipient,
            )
        elif event_type == "accept_trade":
            trade = (event.get("data") or {}).get("trade") or {}
            parties = (trade.get("from_agent"), trade.get("accepted_by") or event.get("actor_id"))
        if parties is None:
            continue
        sender, recipient = parties
        if not sender or not recipient:
            status = "unknown"
            shared_groups: list[str] = []
        else:
            shared_groups = sorted(
                group_id
                for group_id, members in members_by_group.items()
                if str(sender) in members and str(recipient) in members
            )
            if shared_groups:
                status = "in_group"
            elif complete_history:
                status = "out_group"
            else:
                status = "unknown"
        contexts[id(event)] = {"status": status, "shared_groups": shared_groups}
    return contexts


def _summarize_construction_economy(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    structures = snapshot.get("structures") or {}
    if not isinstance(structures, dict):
        structures = {}
    groups = snapshot.get("groups") or {}
    agents = snapshot.get("agents") or {}

    assets_by_owner_raw: dict[str, dict[str, Any]] = {}
    total_replacement_value = 0
    total_inventory_value = 0
    complete_count = 0
    for structure_id, structure in structures.items():
        structure = structure or {}
        owner_id = str(structure.get("owner_id") or "unowned")
        owner_kind = _owner_kind(owner_id, agents, groups)
        record = assets_by_owner_raw.setdefault(
            owner_id,
            {
                "owner_kind": owner_kind,
                "structure_ids": [],
                "count": 0,
                "complete": 0,
                "in_progress": 0,
                "by_type": Counter(),
                "replacement_cost_value": 0,
                "stored_inventory_value": 0,
            },
        )
        structure_type = str(structure.get("type") or "unknown")
        replacement_value = _structure_replacement_value(structure_type)
        inventory_value = _book_value(_positive_item_counts(structure.get("inventory")))
        is_complete = structure.get("status") == "complete"
        record["structure_ids"].append(str(structure_id))
        record["count"] += 1
        record["complete" if is_complete else "in_progress"] += 1
        record["by_type"][structure_type] += 1
        record["replacement_cost_value"] += replacement_value
        record["stored_inventory_value"] += inventory_value
        total_replacement_value += replacement_value
        total_inventory_value += inventory_value
        complete_count += int(is_complete)

    assets_by_owner = {
        owner_id: {
            **record,
            "structure_ids": sorted(record["structure_ids"]),
            "by_type": dict(sorted(record["by_type"].items())),
        }
        for owner_id, record in sorted(assets_by_owner_raw.items())
    }
    assets = {
        "count": len(structures),
        "complete": complete_count,
        "in_progress": len(structures) - complete_count,
        "replacement_cost_value": total_replacement_value,
        "stored_inventory_value": total_inventory_value,
        "by_owner_kind": dict(
            sorted(
                Counter(
                    structure.get("owner_kind", "other")
                    for structure in assets_by_owner.values()
                    for _ in range(structure.get("count", 0))
                ).items()
            )
        ),
        "by_owner": assets_by_owner,
    }

    contribution_items: Counter[str] = Counter()
    contribution_events = 0
    by_agent_raw: dict[str, dict[str, Any]] = {}
    by_structure_raw: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("type") not in {"build_started", "build", "contribute"}:
            continue
        data = event.get("data") or {}
        items = _positive_item_counts(data.get("contributed"))
        if not items:
            continue
        contribution_events += 1
        contribution_items.update(items)
        contributor = str(event.get("actor_id") or "unknown")
        structure_data = data.get("structure") if isinstance(data.get("structure"), dict) else {}
        structure_id = data.get("structure_id") or structure_data.get("id")
        structure_id = str(structure_id) if structure_id else "unknown"
        snapshot_structure = structures.get(structure_id) or structure_data
        owner_id = str((snapshot_structure or {}).get("owner_id") or "unowned")
        structure_type = str((snapshot_structure or {}).get("type") or "unknown")

        agent_record = by_agent_raw.setdefault(
            contributor,
            {"events": 0, "items": Counter(), "structure_ids": set()},
        )
        agent_record["events"] += 1
        agent_record["items"].update(items)
        if structure_id != "unknown":
            agent_record["structure_ids"].add(structure_id)

        structure_record = by_structure_raw.setdefault(
            structure_id,
            {
                "owner_id": owner_id,
                "owner_kind": _owner_kind(owner_id, agents, groups),
                "type": structure_type,
                "items": Counter(),
                "by_agent": defaultdict(Counter),
            },
        )
        structure_record["items"].update(items)
        structure_record["by_agent"][contributor].update(items)

    by_agent = {
        agent_id: {
            "events": record["events"],
            "quantity": sum(record["items"].values()),
            "value": _book_value(record["items"]),
            "by_item": dict(sorted(record["items"].items())),
            "structure_ids": sorted(record["structure_ids"]),
        }
        for agent_id, record in sorted(by_agent_raw.items())
    }
    by_structure: dict[str, dict[str, Any]] = {}
    for structure_id, record in sorted(by_structure_raw.items()):
        by_structure[structure_id] = {
            "owner_id": record["owner_id"],
            "owner_kind": record["owner_kind"],
            "type": record["type"],
            "quantity": sum(record["items"].values()),
            "value": _book_value(record["items"]),
            "by_item": dict(sorted(record["items"].items())),
            "by_agent": {
                agent_id: {
                    "quantity": sum(items.values()),
                    "value": _book_value(items),
                    "by_item": dict(sorted(items.items())),
                }
                for agent_id, items in sorted(record["by_agent"].items())
            },
        }
    contributions = {
        "events": contribution_events,
        "quantity": sum(contribution_items.values()),
        "value": _book_value(contribution_items),
        "by_item": dict(sorted(contribution_items.items())),
        "by_agent": by_agent,
        "by_structure": by_structure,
    }

    contributor_ownership: dict[str, dict[str, Any]] = {}
    for contributor, contribution in by_agent.items():
        owner_contributions: Counter[str] = Counter()
        group_owned_value = 0
        self_owned_value = 0
        other_owned_value = 0
        for structure in by_structure.values():
            agent_value = (structure.get("by_agent") or {}).get(contributor, {}).get("value", 0)
            if not agent_value:
                continue
            owner_id = structure["owner_id"]
            owner_contributions[owner_id] += agent_value
            if owner_id == contributor:
                self_owned_value += agent_value
            elif structure["owner_kind"] == "group":
                group_owned_value += agent_value
            else:
                other_owned_value += agent_value
        owned_assets = assets_by_owner.get(contributor, {})
        contributor_ownership[contributor] = {
            "contributed_quantity": contribution["quantity"],
            "contributed_value": contribution["value"],
            "owned_asset_count": owned_assets.get("count", 0),
            "owned_asset_replacement_cost_value": owned_assets.get("replacement_cost_value", 0),
            "contribution_value_to_self_owned_assets": self_owned_value,
            "contribution_value_to_group_owned_assets": group_owned_value,
            "contribution_value_to_other_owned_assets": other_owned_value,
            "contribution_value_by_owner": dict(owner_contributions),
        }

    return {
        "contributions": contributions,
        "assets": assets,
        "contributor_ownership": contributor_ownership,
    }


def _summarize_economic_institutions(
    events: list[dict[str, Any]], snapshot: dict[str, Any]
) -> dict[str, Any]:
    event_counts = Counter(str(event.get("type", "")) for event in events)
    contracts = list((snapshot.get("contracts") or {}).values())
    contract_status = Counter(str(contract.get("status", "unknown")) for contract in contracts)
    advances: Counter[str] = Counter()
    repayments: Counter[str] = Counter()
    collateral: Counter[str] = Counter()
    for contract in contracts:
        advances.update(_positive_item_counts(contract.get("advance")))
        repayments.update(_positive_item_counts(contract.get("repayment")))
        collateral.update(_positive_item_counts(contract.get("collateral")))

    fee_items: Counter[str] = Counter()
    fee_by_structure: dict[str, Counter[str]] = defaultdict(Counter)
    for event in events:
        if event.get("type") != "pay_access_fee":
            continue
        data = event.get("data") or {}
        items = _positive_item_counts(data.get("fee"))
        fee_items.update(items)
        fee_by_structure[str(data.get("structure_id") or "unknown")].update(items)

    dividend_items: Counter[str] = Counter()
    for event in events:
        if event.get("type") != "claim_dividend":
            continue
        data = event.get("data") or {}
        item = str(data.get("item") or "")
        quantity = _nonnegative_int(data.get("quantity"))
        if item and quantity:
            dividend_items[item] += quantity

    maintenance_items: Counter[str] = Counter()
    for event in events:
        if event.get("type") != "maintain_structure":
            continue
        maintenance_items.update(_positive_item_counts((event.get("data") or {}).get("items")))

    return {
        "contracts": {
            "offered": event_counts.get("create_contract", 0),
            "accepted": event_counts.get("accept_contract", 0),
            "fulfilled": event_counts.get("fulfill_contract", 0),
            "defaulted": event_counts.get("default_contract", 0),
            "status": dict(sorted(contract_status.items())),
            "advance_value": _book_value(advances),
            "repayment_value": _book_value(repayments),
            "collateral_value": _book_value(collateral),
        },
        "access_fees": {
            "policies_set": event_counts.get("set_access_fee", 0),
            "payments": event_counts.get("pay_access_fee", 0),
            "quantity": sum(fee_items.values()),
            "value": _book_value(fee_items),
            "by_item": dict(sorted(fee_items.items())),
            "by_structure": {
                structure_id: dict(sorted(items.items()))
                for structure_id, items in sorted(fee_by_structure.items())
            },
        },
        "dividends": {
            "claims": event_counts.get("claim_dividend", 0),
            "quantity": sum(dividend_items.values()),
            "value": _book_value(dividend_items),
            "by_item": dict(sorted(dividend_items.items())),
        },
        "upkeep": {
            "maintenance_actions": event_counts.get("maintain_structure", 0),
            "paid_cycles": event_counts.get("structure_upkeep_paid", 0),
            "missed_cycles": event_counts.get("structure_upkeep_missed", 0),
            "supplied_value": _book_value(maintenance_items),
            "by_item": dict(sorted(maintenance_items.items())),
        },
        "market_history_entries": len(snapshot.get("market_history") or []),
    }


def _owner_kind(owner_id: str, agents: Any, groups: Any) -> str:
    if owner_id == "unowned":
        return "unowned"
    if isinstance(groups, dict) and owner_id in groups:
        return "group"
    if isinstance(agents, dict) and owner_id in agents:
        return "agent"
    return "other"


def _structure_replacement_value(structure_type: str) -> int:
    recipe = RECIPES.get(structure_type)
    if recipe is None:
        return 0
    return _book_value(getattr(recipe, "inputs", {}))


def _latency_summary(latencies: list[int]) -> dict[str, Any]:
    if not latencies:
        return {"samples": 0, "average": None, "median": None, "min": None, "max": None}
    ordered = sorted(latencies)
    midpoint = len(ordered) // 2
    median = (
        float(ordered[midpoint])
        if len(ordered) % 2
        else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    )
    return {
        "samples": len(ordered),
        "average": round(sum(ordered) / len(ordered), 2),
        "median": median,
        "min": ordered[0],
        "max": ordered[-1],
    }


def _positive_item_counts(value: Any) -> Counter[str]:
    parsed: Counter[str] = Counter()
    if not isinstance(value, dict):
        return parsed
    for item, raw_quantity in value.items():
        quantity = _nonnegative_int(raw_quantity)
        if quantity > 0:
            parsed[str(item)] += quantity
    return parsed


def _book_value(items: Any) -> int:
    return sum(RESOURCE_VALUES.get(item, 1) * quantity for item, quantity in items.items())


def _positive_int(value: Any) -> int | None:
    parsed = _nonnegative_int(value, default=-1)
    return parsed if parsed > 0 else None


def _nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def render_markdown(report: dict[str, Any]) -> str:
    run = report["run"]
    survival = report["survival"]
    economy = report["economy"]
    structures = report["structures"]
    usage = report["usage"]
    institutions = economy.get("institutions", {})
    gift_categories = economy.get("gift_categories", {})
    subsistence_gifts = gift_categories.get("subsistence", {}).get("quantity", "?")
    material_gifts = gift_categories.get("materials", {}).get("quantity", "?")
    construction = economy.get("construction", {})
    lines = [
        f"# Run report: {report.get('source') or 'unnamed'}",
        "",
        f"- Ticks: {run['final_tick']}/{run['target_ticks'] or '?'}"
        + ("" if run["completed"] else f" — **stopped early: {run['stop_reason']}**"),
        f"- Agents: {survival['living']} living / {survival['dead']} dead",
        f"- Action points/tick: {report['config'].get('action_points_per_tick')} | seed: {report['config'].get('seed')}",
        f"- LLM: {usage['calls']} calls, ${usage['total_cost_usd']}, {usage['cache_hit_rate_pct']}% cache hit"
        if usage["calls"]
        else "- Brain: scripted (no LLM usage)",
        "",
        "## Society",
        f"- Groups: {len(report['groups'])}"
        + (
            " — " + "; ".join(f"{group['name']} ({len(group['members'])} members)" for group in report["groups"].values())
            if report["groups"]
            else ""
        ),
        f"- Structures complete: {structures['complete']} | co-op builds: {len(structures['coop_builds'])}",
        f"- Ownership: {structures['ownership']}",
        "",
        "## Economy",
        f"- Gifts: {economy['gifts']} {economy['gift_network']}",
        f"- Gift flow: {economy.get('gift_quantity', '?')} units"
        f" / {economy.get('gift_value', '?')} book value"
        f" | subsistence/material units: {subsistence_gifts}/{material_gifts}"
        f" | group status: {economy.get('gift_group_status', {})}",
        f"- Trades: {economy['trades']['offered']} offered / {economy['trades']['accepted']} accepted"
        f" / {economy['trades']['expired']} expired"
        f" | conversion: {economy['trades'].get('conversion_rate_pct', '?')}%"
        f" | invalid accepts: {economy['trades'].get('invalid_accepts', 0)}",
        f"- Construction contributions: {construction.get('contributions', {}).get('value', '?')} value"
        f" | productive assets: {construction.get('assets', {}).get('count', '?')}",
        f"- Contracts: {institutions.get('contracts', {}).get('offered', 0)} offered"
        f" / {institutions.get('contracts', {}).get('fulfilled', 0)} fulfilled"
        f" / {institutions.get('contracts', {}).get('defaulted', 0)} defaulted"
        f" | access-fee value: {institutions.get('access_fees', {}).get('value', 0)}"
        f" | dividend value: {institutions.get('dividends', {}).get('value', 0)}",
        f"- Food spoilage events: {economy['food_spoilage_events']}"
        f" | tile claims: {economy['claimed_tiles']} | access grants: {economy['access_grants']}",
        "",
        "## Milestones (first tick)",
    ]
    milestones = report["milestone_first_ticks"]
    lines.append(
        "- " + ", ".join(f"{name}: t{tick}" for name, tick in sorted(milestones.items(), key=lambda kv: kv[1]))
        if milestones
        else "- none"
    )
    lines += [
        "",
        "## Agents",
    ]
    for agent_id, agent in survival["agents"].items():
        status = "alive" if agent["alive"] else "DEAD"
        lines.append(
            f"- {agent_id}: {status}, hp {agent['health']}, wealth {agent['wealth']},"
            f" inventory {agent['inventory']}, groups {agent['groups']}"
        )
    lines += [
        "",
        "## Reliability",
        f"- Invalid actions: {report['actions']['invalid_total']}"
        f" ({report['reliability']['invalid_action_rate_pct']}% of events)",
        f"- LLM failure events: {report['reliability']['llm_failure_events']}",
        "",
    ]
    return "\n".join(lines)


def write_report(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    usage_records: list[dict[str, Any]] | None,
    out_stem: Path,
    target_ticks: int | None = None,
) -> dict[str, Any]:
    report = build_report(events, snapshot, usage_records, source=out_stem.name, target_ticks=target_ticks)
    json_path = out_stem.with_name(out_stem.name + "-report.json")
    md_path = out_stem.with_name(out_stem.name + "-report.md")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return report


def load_run_files(stem: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    events = [
        json.loads(line)
        for line in stem.with_name(stem.name + ".jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    snapshot = json.loads(stem.with_name(stem.name + "-snapshot.json").read_text(encoding="utf-8"))
    usage_path = stem.with_name(stem.name + "-usage.jsonl")
    usage_records = (
        [json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if usage_path.exists()
        else []
    )
    return events, snapshot, usage_records


COMPARISON_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ticks", ("run", "final_tick")),
    ("action points", ("config", "action_points_per_tick")),
    ("seed", ("config", "seed")),
    ("living agents", ("survival", "living")),
    ("deaths", ("survival", "dead")),
    ("groups", ("groups",)),
    ("structures complete", ("structures", "complete")),
    ("co-op builds", ("structures", "coop_builds")),
    ("gifts", ("economy", "gifts")),
    ("gift units", ("economy", "gift_quantity")),
    ("gift value", ("economy", "gift_value")),
    ("trades offered", ("economy", "trades", "offered")),
    ("trades accepted", ("economy", "trades", "accepted")),
    ("trade conversion pct", ("economy", "trades", "conversion_rate_pct")),
    ("construction contribution value", ("economy", "construction", "contributions", "value")),
    ("productive asset value", ("economy", "construction", "assets", "replacement_cost_value")),
    ("contracts fulfilled", ("economy", "institutions", "contracts", "fulfilled")),
    ("contracts defaulted", ("economy", "institutions", "contracts", "defaulted")),
    ("access fee value", ("economy", "institutions", "access_fees", "value")),
    ("dividend value", ("economy", "institutions", "dividends", "value")),
    ("says", ("communication", "says_total")),
    ("invalid actions", ("actions", "invalid_total")),
    ("wealth gini", ("wealth_gini",)),
    ("LLM cost usd", ("usage", "total_cost_usd")),
)


def format_comparison(reports: list[dict[str, Any]]) -> str:
    headers = ["metric"] + [report.get("source") or f"run{index}" for index, report in enumerate(reports)]
    rows = [headers]
    for label, path in COMPARISON_ROWS:
        row = [label]
        for report in reports:
            value: Any = report
            for key in path:
                value = value.get(key, {}) if isinstance(value, dict) else {}
            if isinstance(value, dict):
                value = sum(value.values()) if all(isinstance(v, int) for v in value.values()) else len(value)
            elif isinstance(value, list):
                value = len(value)
            row.append(str(value))
        rows.append(row)
    widths = [max(len(row[column]) for row in rows) for column in range(len(headers))]
    lines = []
    for index, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(widths[column]) for column, cell in enumerate(row)).rstrip())
        if index == 0:
            lines.append("  ".join("-" * widths[column] for column in range(len(headers))))
    return "\n".join(lines)


def _gini(values: list[int]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    ordered = sorted(values)
    total = sum(ordered)
    cumulative = 0.0
    for index, value in enumerate(ordered, start=1):
        cumulative += index * value
    count = len(ordered)
    return round((2 * cumulative) / (count * total) - (count + 1) / count, 4)
