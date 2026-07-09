"""Structured per-run data export for cross-run iteration.

Every run distills into a `<stem>-report.json` (machine-readable, self-contained:
config, outcomes, milestones, economy networks, full say transcript) and a
`<stem>-report.md` (human-readable summary). Reports from different runs are
directly comparable because they share one schema.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from agent_world.rules import RESOURCE_VALUES

AGENT_IO_EVENT_TYPES = {"agent_observation", "agent_prompt", "agent_response"}
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
    if target_ticks is None:
        target_ticks = next(
            (
                event["data"].get("target_ticks")
                for event in sim_events
                if event["type"] in ("run_completed", "run_stopped") and event.get("data")
            ),
            None,
        )
    stop_event = next((event for event in sim_events if event["type"] == "run_stopped"), None)

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

    gift_events = [event for event in sim_events if event["type"] == "gift"]
    gift_edges: Counter[str] = Counter()
    for event in gift_events:
        recipient = (event.get("data") or {}).get("to")
        gift_edges[f"{event['actor_id']}->{recipient}"] += 1

    trades = {
        "offered": action_counts.get("offer_trade", 0),
        "accepted": action_counts.get("accept_trade", 0),
        "rejected": action_counts.get("reject_trade", 0),
        "expired": action_counts.get("expire_trade", 0),
        "cancelled": action_counts.get("cancel_trade", 0),
        "accepted_detail": [
            (event.get("data") or {}).get("trade")
            for event in sim_events
            if event["type"] == "accept_trade"
        ],
    }

    invalid_reasons = Counter(
        event["message"] for event in sim_events if event["type"] == "invalid_action"
    )
    llm_failures = [
        event
        for event in sim_events
        if "failure" in event["type"] or "error" in event["type"]
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
        "run": {
            "final_tick": final_tick,
            "target_ticks": target_ticks,
            "completed": stop_event is None,
            "stop_reason": (stop_event.get("data") or {}).get("reason") if stop_event else None,
        },
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
            "gifts": len(gift_events),
            "gift_network": dict(gift_edges),
            "trades": trades,
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
            "invalid_action_rate_pct": (
                round(100 * action_counts.get("invalid_action", 0) / len(sim_events), 1) if sim_events else 0.0
            ),
        },
        "usage": usage,
        "wealth_gini": _gini(wealth_values),
        "transcript": says,
    }


def render_markdown(report: dict[str, Any]) -> str:
    run = report["run"]
    survival = report["survival"]
    economy = report["economy"]
    structures = report["structures"]
    usage = report["usage"]
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
        f"- Trades: {economy['trades']['offered']} offered / {economy['trades']['accepted']} accepted"
        f" / {economy['trades']['expired']} expired",
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
    ("trades offered", ("economy", "trades", "offered")),
    ("trades accepted", ("economy", "trades", "accepted")),
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
