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

from agent_world.benchmarks import build_benchmark_results
from agent_world.metrics import (
    is_ambiguous_boundary_failure_message,
    is_decision_failure_message,
    is_harness_failure_message,
    is_model_output_failure_message,
    is_provider_failure_message,
    is_quota_failure_message,
)
from agent_world.rules import ACCOUNTING_VALUES, recipes_for_mode
from agent_world.usage import summarize_codex_simulation_credits

AGENT_IO_EVENT_TYPES = {"agent_observation", "agent_prompt", "agent_prompt_context", "agent_response"}
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
    plan_usage: dict[str, Any] | None = None,
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
                ACCOUNTING_VALUES.get(item, 1) * qty for item, qty in (agent.get("inventory") or {}).items()
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
    contention_reasons = Counter(
        event["message"] for event in sim_events if event["type"] == "contention_failure"
    )
    llm_failures = [
        event
        for event in events
        if is_decision_failure_message(event.get("type"), event.get("message"))
    ]
    model_output_failures = [
        event
        for event in llm_failures
        if is_model_output_failure_message(event.get("type"), event.get("message"))
    ]
    quota_failures = [
        event
        for event in llm_failures
        if is_quota_failure_message(event.get("type"), event.get("message"))
    ]
    provider_failures = [
        event
        for event in llm_failures
        if is_provider_failure_message(event.get("type"), event.get("message"))
    ]
    ambiguous_boundary_failures = [
        event
        for event in llm_failures
        if is_ambiguous_boundary_failure_message(
            event.get("type"),
            event.get("message"),
        )
    ]
    harness_failures = [
        event
        for event in llm_failures
        if is_harness_failure_message(event.get("type"), event.get("message"))
    ]
    decision_attempts = sum(event.get("type") == "agent_response" for event in events)
    decision_failure_rate = (
        round(100 * len(llm_failures) / decision_attempts, 2) if decision_attempts else 0.0
    )
    usage_coverage = (
        round(100 * len(usage_records) / decision_attempts, 2)
        if decision_attempts and usage_records
        else None
    )
    quality_flags: list[str] = []
    if model_output_failures:
        quality_flags.append("model_output_failures_present")
    if quota_failures:
        quality_flags.append("quota_failures_present")
    if provider_failures:
        quality_flags.append("provider_failures_present")
    if ambiguous_boundary_failures:
        quality_flags.append("ambiguous_boundary_failures_present")
    if harness_failures:
        quality_flags.append("harness_failures_present")
    if usage_coverage is not None and usage_coverage < 100:
        quality_flags.append("missing_usage_records")

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
    completion_tokens = sum(record.get("completion_tokens") or 0 for record in usage_records)
    usage = {
        "calls": len(usage_records),
        "total_cost_usd": round(total_cost, 4),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": sum(record.get("reasoning_tokens") or 0 for record in usage_records),
        "cache_hit_rate_pct": round(100 * cached_tokens / prompt_tokens, 1) if prompt_tokens else 0.0,
        "efficiency": {
            "mean_prompt_tokens_per_call": round(prompt_tokens / len(usage_records), 1)
            if usage_records
            else 0.0,
            "mean_uncached_input_tokens_per_call": round(
                sum(
                    max(0, (record.get("prompt_tokens") or 0) - (record.get("cached_tokens") or 0))
                    for record in usage_records
                )
                / len(usage_records),
                1,
            )
            if usage_records
            else 0.0,
            "mean_output_tokens_per_call": round(completion_tokens / len(usage_records), 1)
            if usage_records
            else 0.0,
            "mean_agent_static_context_chars": _mean_record_field(
                usage_records, "agent_static_context_chars"
            ),
            "mean_agent_dynamic_observation_chars": _mean_record_field(
                usage_records, "agent_dynamic_observation_chars"
            ),
            "mean_request_payload_bytes": _mean_record_field(usage_records, "request_payload_bytes"),
        },
        "simulation_credits": summarize_codex_simulation_credits(usage_records),
        "plan_limits": plan_usage,
        "dynamic_input_components": _dynamic_input_components(events),
    }
    population = _summarize_population(events, snapshot, usage_records)

    wealth_values = [agent["wealth"] for agent in agents.values()]
    report = {
        "schema_version": 1,
        "source": source,
        "run": run_summary,
        "config": snapshot.get("config", {}),
        "population": population,
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
            "failure_total": action_counts.get("invalid_action", 0)
            + action_counts.get("contention_failure", 0),
            "invalid_proposals": action_counts.get("invalid_action", 0),
            "contention_failures": action_counts.get("contention_failure", 0),
            "contention_reasons": dict(contention_reasons.most_common()),
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
            "quality_status": "degraded" if quality_flags else "clean",
            "benchmark_integrity_status": (
                "clean"
                if not quota_failures
                and not provider_failures
                and not ambiguous_boundary_failures
                and not harness_failures
                and (usage_coverage is None or usage_coverage >= 100)
                else "invalid"
            ),
            "quality_flags": quality_flags,
            "decision_attempts": decision_attempts,
            "decision_failure_rate_pct": decision_failure_rate,
            "usage_record_coverage_pct": usage_coverage,
            "llm_failure_events": len(llm_failures),
            "model_output_failure_events": len(model_output_failures),
            "llm_quota_failure_events": len(quota_failures),
            "llm_provider_failure_events": len(provider_failures),
            "ambiguous_boundary_failure_events": len(
                ambiguous_boundary_failures
            ),
            "harness_failure_events": len(harness_failures),
            "llm_failures_by_agent": dict(
                Counter(event.get("actor_id") or "unknown" for event in llm_failures).most_common()
            ),
            "invalid_action_rate_pct": (
                round(100 * action_counts.get("invalid_action", 0) / len(sim_events), 1) if sim_events else 0.0
            ),
            "contention_failure_rate_pct": (
                round(100 * action_counts.get("contention_failure", 0) / len(sim_events), 1)
                if sim_events
                else 0.0
            ),
            "action_failure_rate_pct": (
                round(
                    100
                    * (action_counts.get("invalid_action", 0) + action_counts.get("contention_failure", 0))
                    / len(sim_events),
                    1,
                )
                if sim_events
                else 0.0
            ),
        },
        "usage": usage,
        "wealth_gini": _gini(wealth_values),
        "transcript": says,
    }
    report["benchmarks"] = build_benchmark_results(events, snapshot, report)
    return report


def _summarize_population(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    usage_records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    started = next(
        (event for event in reversed(events) if event.get("type") in {"run_started", "run_resumed"}),
        None,
    )
    metadata = ((started or {}).get("data") or {}).get("population")
    if not isinstance(metadata, dict):
        return None
    raw_groups = metadata.get("groups")
    assignments = metadata.get("assignments")
    if not isinstance(raw_groups, list) or not isinstance(assignments, dict):
        return None

    agents = snapshot.get("agents") or {}
    cohorts: dict[str, dict[str, Any]] = {}
    for raw in raw_groups:
        if not isinstance(raw, dict):
            continue
        group_id = str(raw.get("id") or "unknown")
        member_ids = sorted(
            agent_id for agent_id, assigned_group in assignments.items() if assigned_group == group_id
        )
        member_set = set(member_ids)
        cohort_events = [event for event in events if event.get("actor_id") in member_set]
        cohort_usage = [record for record in usage_records if record.get("agent_id") in member_set]
        prompt_tokens = sum(record.get("prompt_tokens") or 0 for record in cohort_usage)
        completion_tokens = sum(record.get("completion_tokens") or 0 for record in cohort_usage)
        action_counts = Counter(
            event.get("type")
            for event in cohort_events
            if event.get("type") not in AGENT_IO_EVENT_TYPES
        )
        decision_count = sum(event.get("type") == "agent_response" for event in cohort_events)
        resolved_models = Counter(
            str(record.get("response_model") or record.get("model") or "unknown")
            for record in cohort_usage
        )
        cohorts[group_id] = {
            "brain": raw.get("type"),
            "model": raw.get("model"),
            "reasoning_effort": raw.get("reasoning_effort"),
            "provider": raw.get("provider"),
            "billing_mode": raw.get("billing_mode"),
            "agents": member_ids,
            "initial_agents": len(member_ids),
            "living": sum(bool((agents.get(agent_id) or {}).get("alive")) for agent_id in member_ids),
            "dead": sum(not bool((agents.get(agent_id) or {}).get("alive")) for agent_id in member_ids),
            "actions": dict(action_counts.most_common()),
            "communication": action_counts.get("say", 0),
            "gifts_sent": action_counts.get("gift", 0),
            "trades_offered": action_counts.get("offer_trade", 0),
            "trades_accepted": action_counts.get("accept_trade", 0),
            "invalid_actions": action_counts.get("invalid_action", 0),
            "contention_failures": action_counts.get("contention_failure", 0),
            "invalid_actions_per_decision": round(
                action_counts.get("invalid_action", 0) / decision_count, 3
            ) if decision_count else None,
            "decisions": decision_count,
            "usage": {
                "calls": len(cohort_usage),
                "total_cost_usd": round(sum(record.get("cost") or 0 for record in cohort_usage), 4),
                "prompt_tokens": prompt_tokens,
                "cached_tokens": sum(record.get("cached_tokens") or 0 for record in cohort_usage),
                "completion_tokens": completion_tokens,
                "simulation_credits": summarize_codex_simulation_credits(cohort_usage),
                "resolved_models": dict(resolved_models),
            },
        }
    successful_offers: Counter[str] = Counter()
    trade_matrix: Counter[str] = Counter()
    gift_matrix: Counter[str] = Counter()
    construction_matrix: Counter[str] = Counter()
    for event in events:
        actor = str(event.get("actor_id") or "")
        actor_group = assignments.get(actor)
        data = event.get("data") or {}
        if event.get("type") == "accept_trade":
            trade = data.get("trade") or {}
            origin_group = assignments.get(str(trade.get("from_agent") or ""))
            if origin_group:
                successful_offers[origin_group] += 1
                trade_matrix[f"{origin_group}->{actor_group or 'unknown'}"] += 1
        elif event.get("type") == "gift" and actor_group:
            target_group = assignments.get(str(data.get("to") or ""), "unknown")
            gift_matrix[f"{actor_group}->{target_group}"] += 1
        elif event.get("type") == "contribute" and actor_group:
            structure = data.get("structure") or {}
            owner_group = assignments.get(str(structure.get("owner_id") or ""), "unknown")
            construction_matrix[f"{actor_group}->{owner_group}"] += 1
    for group_id, cohort in cohorts.items():
        success = successful_offers[group_id]
        cohort["successful_offers"] = success
        offered = cohort["trades_offered"]
        cohort["offer_conversion_rate_pct"] = round(100 * success / offered, 1) if offered else 0.0
    return {
        "type": metadata.get("type"),
        "total_agents": metadata.get("total_agents"),
        "assignments": dict(sorted((str(key), str(value)) for key, value in assignments.items())),
        "assignment_strategy": metadata.get("assignment_strategy"),
        "assignment_seed": metadata.get("assignment_seed"),
        "cohorts": cohorts,
        "interaction_matrices": {
            "accepted_trades": dict(trade_matrix),
            "gifts": dict(gift_matrix),
            "construction_contributions": dict(construction_matrix),
        },
    }


def _dynamic_input_components(events: list[dict[str, Any]]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    samples = 0
    for event in events:
        if event.get("type") != "agent_prompt":
            continue
        components = (event.get("data") or {}).get("dynamic_component_chars")
        if not isinstance(components, dict):
            continue
        samples += 1
        totals.update({str(key): int(value) for key, value in components.items()})
    return {
        "samples": samples,
        "mean_chars": {
            key: round(value / samples, 1) for key, value in totals.most_common()
        } if samples else {},
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
            item: ACCOUNTING_VALUES.get(item, 1) * quantity
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
        if event.get("type") in {"invalid_action", "contention_failure"}
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
    economy_mode = str((snapshot.get("config") or {}).get("economy_mode", "baseline"))

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
        replacement_value = _structure_replacement_value(structure_type, economy_mode)
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


def _structure_replacement_value(structure_type: str, economy_mode: str = "baseline") -> int:
    recipe = recipes_for_mode(economy_mode).get(structure_type)
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
    return sum(ACCOUNTING_VALUES.get(item, 1) * quantity for item, quantity in items.items())


def _positive_int(value: Any) -> int | None:
    parsed = _nonnegative_int(value, default=-1)
    return parsed if parsed > 0 else None


def _mean_record_field(records: list[dict[str, Any]], field: str) -> float | None:
    values = [record[field] for record in records if isinstance(record.get(field), (int, float))]
    return round(sum(values) / len(values), 1) if values else None


def _nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _render_plan_usage_lines(plan_usage: Any) -> list[str]:
    if not isinstance(plan_usage, dict):
        return []
    if not plan_usage.get("available"):
        return ["- Codex plan limits: unavailable"]
    lines: list[str] = []
    for limit_id, bucket in (plan_usage.get("buckets") or {}).items():
        if not isinstance(bucket, dict):
            continue
        pieces: list[str] = []
        for label, window_name in (("primary", "primary"), ("secondary", "secondary")):
            window = bucket.get(window_name)
            if not isinstance(window, dict):
                continue
            before = window.get("before_used_percent")
            after = window.get("after_used_percent")
            delta = window.get("used_percent_delta")
            delta_text = f", delta {delta:+g}pp" if isinstance(delta, (int, float)) else ", window reset/changed"
            pieces.append(f"{label} {before}% to {after}%{delta_text}")
        credits = bucket.get("credits")
        if isinstance(credits, dict) and credits.get("before_balance") is not None:
            pieces.append(
                f"credits {credits.get('before_balance')} to {credits.get('after_balance')}"
                f" (delta {credits.get('balance_delta')})"
            )
        name = bucket.get("limit_name") or limit_id
        lines.append(f"- Codex plan [{name}]: " + " | ".join(pieces))
    return lines or ["- Codex plan limits: snapshot contained no buckets"]


def _render_simulation_credit_lines(simulation_credits: Any) -> list[str]:
    if not isinstance(simulation_credits, dict):
        return []
    credits = simulation_credits.get("credits") or {}
    if not simulation_credits.get("available"):
        unknown = ", ".join(simulation_credits.get("unknown_models") or [])
        return [f"- Simulation plan credits: unavailable for model(s): {unknown}"]
    return [
        f"- Simulation plan credits: {credits.get('total', 0)} exact run-scoped credits"
        f" (input {credits.get('uncached_input', 0)} + cached {credits.get('cached_input', 0)}"
        f" + output {credits.get('output', 0)})"
    ]


def _render_efficiency_lines(efficiency: Any) -> list[str]:
    if not isinstance(efficiency, dict):
        return []
    line = (
        f"- Per call: {efficiency.get('mean_prompt_tokens_per_call', 0)} input tokens "
        f"({efficiency.get('mean_uncached_input_tokens_per_call', 0)} uncached), "
        f"{efficiency.get('mean_output_tokens_per_call', 0)} output tokens"
    )
    static_chars = efficiency.get("mean_agent_static_context_chars")
    dynamic_chars = efficiency.get("mean_agent_dynamic_observation_chars")
    if static_chars is not None or dynamic_chars is not None:
        line += f"; agent context chars static/dynamic {static_chars or 0}/{dynamic_chars or 0}"
    return [line]


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
    population = report.get("population") or {}
    cohort_lines = []
    for cohort_id, cohort in (population.get("cohorts") or {}).items():
        cohort_lines.append(
            f"- {cohort_id}: {cohort.get('model') or cohort.get('brain')} — "
            f"{cohort.get('living')}/{cohort.get('initial_agents')} living, "
            f"{cohort.get('usage', {}).get('calls', 0)} calls, "
            f"{cohort.get('gifts_sent', 0)} gifts, "
            f"{cohort.get('trades_offered', 0)} offers/{cohort.get('trades_accepted', 0)} accepts"
        )
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
        *(_render_efficiency_lines(usage.get("efficiency")) if usage["calls"] else []),
        *_render_simulation_credit_lines(usage.get("simulation_credits")),
        *_render_plan_usage_lines(usage.get("plan_limits")),
        *(["", "## Model cohorts", *cohort_lines] if len(cohort_lines) > 1 else []),
        *_render_benchmark_lines(report.get("benchmarks")),
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
        f"- Invalid proposals: {report['actions']['invalid_proposals']}"
        f" ({report['reliability']['invalid_action_rate_pct']}% of events)",
        f"- Contention failures: {report['actions']['contention_failures']}"
        f" ({report['reliability']['contention_failure_rate_pct']}% of events)",
        f"- LLM failure events: {report['reliability']['llm_failure_events']}",
        f"- Decision quality: {report['reliability']['quality_status']}"
        f" | failure rate {report['reliability']['decision_failure_rate_pct']}%"
        f" | flags {report['reliability']['quality_flags']}",
        "",
    ]
    return "\n".join(lines)


def _render_benchmark_lines(benchmarks: Any) -> list[str]:
    if not isinstance(benchmarks, dict) or not benchmarks.get("cohorts"):
        return []
    trial = benchmarks.get("trial") or {}
    status = (
        "eligible replication"
        if trial.get("protocol_compliant")
        else "diagnostic only"
    )
    cohorts = list((benchmarks.get("cohorts") or {}).items())
    cohort_labels = [
        f"{cohort_id} ({cohort.get('model') or cohort.get('brain')})"
        for cohort_id, cohort in cohorts
    ]
    lines = [
        "",
        f"## Model benchmarks ({benchmarks.get('suite_id')})",
        "",
        f"Trial status: **{status}**.",
        "",
        "> **Primary benchmark scorecard**",
        ">",
        "> | Benchmark | " + " | ".join(cohort_labels) + " |",
        "> |---|" + "|".join("---:" for _ in cohorts) + "|",
    ]
    for label, score_key in (
        ("**Effective execution**", "effective_execution"),
        ("**Sustained competence**", "sustained_competence"),
        ("**Entrepreneurial agency**", "entrepreneurial_agency"),
    ):
        values = [
            _render_score((cohort.get("scores") or {}).get(score_key, {}).get("score"))
            for _, cohort in cohorts
        ]
        lines.append(
            f"> | {label} | " + " | ".join(values) + " |"
        )
    lines += [
        "",
        "### Supporting execution diagnostics",
        "",
        "| Metric | " + " | ".join(cohort_labels) + " |",
        "|---|" + "|".join("---:" for _ in cohorts) + "|",
    ]
    submitted = [
        int((cohort.get("raw") or {}).get("submitted_actions") or 0)
        for _, cohort in cohorts
    ]
    for label, raw_key, denominators in (
        ("Invalid proposals", "invalid_proposals", submitted),
        ("Contention failures", "contention_failures", submitted),
    ):
        values = [
            _render_count_rate(
                (cohort.get("raw") or {}).get(raw_key),
                denominators[index],
            )
            for index, (_, cohort) in enumerate(cohorts)
        ]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    lines.append(
        "| Action-point overruns | "
        + " | ".join(
            str(int((cohort.get("raw") or {}).get("action_point_overruns") or 0))
            for _, cohort in cohorts
        )
        + " |"
    )
    lines.append(
        "| Purposeful agent-ticks | "
        + " | ".join(
            _render_count_rate(
                (cohort.get("raw") or {}).get("purposeful_agent_ticks"),
                int((cohort.get("raw") or {}).get("decisions") or 0),
            )
            for _, cohort in cohorts
        )
        + " |"
    )
    lines += [
        "",
        "### Supporting economic diagnostics",
        "",
        "| Metric | " + " | ".join(cohort_labels) + " |",
        "|---|" + "|".join("---:" for _ in cohorts) + "|",
    ]
    for label, value_getter in (
        (
            "Living terminal value",
            lambda cohort: (cohort.get("raw") or {}).get(
                "living_terminal_economic_value"
            ),
        ),
        (
            "Starting endowment",
            lambda cohort: (cohort.get("raw") or {}).get(
                "initial_endowment_value"
            ),
        ),
        (
            "Net value created",
            lambda cohort: (
                (
                    (cohort.get("scores") or {}).get("economic_productivity")
                    or {}
                ).get("components")
                or {}
            ).get("net_value_created"),
        ),
        (
            "Net value / 100 agent-ticks",
            lambda cohort: (
                (
                    (cohort.get("scores") or {}).get("economic_productivity")
                    or {}
                ).get("components")
                or {}
            ).get("net_value_created_per_100_agent_ticks"),
        ),
        (
            "Venture initiatives",
            lambda cohort: (cohort.get("raw") or {}).get(
                "venture_initiatives"
            ),
        ),
        (
            "Economic productivity score",
            lambda cohort: (
                (cohort.get("scores") or {}).get("economic_productivity") or {}
            ).get("score"),
        ),
    ):
        lines.append(
            f"| {label} | "
            + " | ".join(
                _render_score(value_getter(cohort))
                for _, cohort in cohorts
            )
            + " |"
        )
    trajectory = benchmarks.get("trajectory") or []
    if trajectory:
        lines += [
            "",
            "### Benchmark score trajectory",
            "",
            "| Tick | Cohort | Role | Execution | Competence | Entrepreneurship | Living | Endpoint health | Living value |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for checkpoint in trajectory:
            role = str(checkpoint.get("role") or "diagnostic_checkpoint").replace(
                "_", " "
            )
            for cohort_id, cohort in (checkpoint.get("cohorts") or {}).items():
                scores = cohort.get("scores") or {}
                raw = cohort.get("raw") or {}
                competence_components = (
                    scores.get("sustained_competence") or {}
                ).get("components") or {}
                lines.append(
                    f"| {checkpoint.get('tick')} | {cohort_id} | {role} "
                    f"| {_render_score((scores.get('effective_execution') or {}).get('score'))} "
                    f"| {_render_score((scores.get('sustained_competence') or {}).get('score'))} "
                    f"| {_render_score((scores.get('entrepreneurial_agency') or {}).get('score'))} "
                    f"| {int(raw.get('living_agents') or 0)} "
                    f"| {_render_score(competence_components.get('endpoint_population_health_pct'))} "
                    f"| {_render_score(raw.get('living_terminal_economic_value'))} |"
                )
    if trial.get("quality_flags"):
        lines += [
            "",
            "Protocol flags: " + ", ".join(str(value) for value in trial["quality_flags"]) + ".",
        ]
    return lines


def _render_score(value: Any) -> str:
    return f"{float(value):.1f}" if isinstance(value, (int, float)) else "n/a"


def _render_count_rate(value: Any, denominator: int) -> str:
    count = int(value or 0)
    if denominator <= 0:
        return f"{count} (n/a)"
    return f"{count} ({100.0 * count / denominator:.1f}%)"


def write_report(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    usage_records: list[dict[str, Any]] | None,
    out_stem: Path,
    target_ticks: int | None = None,
    plan_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_report(
        events,
        snapshot,
        usage_records,
        source=out_stem.name,
        target_ticks=target_ticks,
        plan_usage=plan_usage,
    )
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
