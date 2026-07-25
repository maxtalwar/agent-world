"""Versioned, deterministic benchmarks for model behavior in Agent World."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from agent_world.metrics import is_decision_failure_message
from agent_world.rules import RESOURCE_VALUES, recipes_for_mode


BENCHMARK_SUITE_ID = "agent-world-participant-v1"
BENCHMARK_PROTOCOL_ID = "participant-v1"
BENCHMARK_SEEDS = frozenset({11, 41})

# These are mechanics-anchored "excellent" targets, not population percentiles.
# Versioning the suite freezes them so later runs remain directly comparable.
INITIATIVE_TARGET_PER_100_AGENT_TICKS = 20.0
REALIZED_VALUE_TARGET_PER_100_AGENT_TICKS = 40.0
TERMINAL_ENDOWMENT_MULTIPLE_TARGET = 3.0

VENTURE_INITIATIVE_EVENTS = frozenset(
    {"offer_trade", "build_started", "create_contract", "set_access_fee"}
)
BENCHMARK_FINGERPRINT_FILES = (
    "benchmarks.py",
    "interface.py",
    "maps.py",
    "models.py",
    "rules.py",
    "runner.py",
    "world.py",
)


def benchmark_code_fingerprint() -> str:
    """Hash benchmark formulas and behavior-defining world sources."""

    package_dir = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in BENCHMARK_FINGERPRINT_FILES:
        digest.update(name.encode("utf-8"))
        digest.update((package_dir / name).read_bytes())
    return digest.hexdigest()


def benchmark_protocol() -> dict[str, Any]:
    """Return the frozen participant-v1 trial and scoring specification."""

    return {
        "id": BENCHMARK_PROTOCOL_ID,
        "suite_id": BENCHMARK_SUITE_ID,
        "code_fingerprint_sha256": benchmark_code_fingerprint(),
        "replications": {"required_seeds": sorted(BENCHMARK_SEEDS), "minimum": 2},
        "trial": {
            "agents": 10,
            "ticks": 40,
            "preset": "organic-generalists",
            "economy_mode": "organic",
            "geography_mode": "dispersed",
            "specialization_mode": "generalists",
            "objective_mode": "neutral",
            "reasoning_effort": "medium",
            "decision_mode": "raw",
            "action_feedback_mode": "baseline",
            "connector_profile": "stateless-v3",
            "conversation_mode": "stateless",
            "population": "one uniform model cohort",
            "turn_resolution": "simultaneous",
            "global_max_workers": 4,
            "provider_max_workers": 4,
            "agent_io_log": True,
        },
        "score_scale": {"minimum": 0.0, "maximum": 100.0, "higher_is_better": True},
        "targets": {
            "terminal_endowment_multiple": TERMINAL_ENDOWMENT_MULTIPLE_TARGET,
            "venture_initiatives_per_100_agent_ticks": INITIATIVE_TARGET_PER_100_AGENT_TICKS,
            "realized_venture_value_per_100_agent_ticks": REALIZED_VALUE_TARGET_PER_100_AGENT_TICKS,
        },
        "aggregation": (
            "Pool raw numerators and denominators across the two required seeds, "
            "then apply the frozen formulas. Do not average per-run scores."
        ),
    }


def build_benchmark_results(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """Score every model cohort in a run and audit protocol compliance."""

    population = report.get("population") or {}
    cohorts = population.get("cohorts") or {}
    run = report.get("run") or {}
    config = report.get("config") or {}
    started = _latest_lifecycle_event(events)
    start_data = (started or {}).get("data") or {}
    trial_flags = _trial_flags(report, start_data, cohorts)
    trial_protocol = start_data.get("benchmark_protocol")

    scored: dict[str, Any] = {}
    for cohort_id, cohort in cohorts.items():
        member_ids = [str(value) for value in cohort.get("agents") or []]
        raw = _cohort_raw_metrics(
            events=events,
            snapshot=snapshot,
            config=config,
            member_ids=member_ids,
            final_tick=int(run.get("final_tick") or 0),
        )
        cohort_flags = list(trial_flags)
        if raw["submitted_actions_excluding_contention"] <= 0:
            cohort_flags.append("insufficient_action_sample")
        if raw["possible_agent_ticks"] <= 0:
            cohort_flags.append("insufficient_agent_tick_sample")
        if raw["decision_failures"]:
            cohort_flags.append("cohort_decision_failures_present")
        scores = score_benchmark_counts(raw)
        scored[str(cohort_id)] = {
            "brain": cohort.get("brain"),
            "model": cohort.get("model"),
            "reasoning_effort": cohort.get("reasoning_effort"),
            "provider": cohort.get("provider"),
            "agents": member_ids,
            "protocol_compliant": not cohort_flags,
            "quality_flags": sorted(set(cohort_flags)),
            "raw": raw,
            "scores": scores,
            "diagnostics": _cohort_diagnostics(events, set(member_ids), raw),
        }

    return {
        "suite_id": BENCHMARK_SUITE_ID,
        "protocol": benchmark_protocol(),
        "trial": {
            "declared_protocol": trial_protocol,
            "code_fingerprint_sha256": start_data.get(
                "benchmark_code_fingerprint"
            ),
            "protocol_compliant": not trial_flags,
            "quality_flags": sorted(set(trial_flags)),
            "seed": config.get("seed"),
            "completed": bool(run.get("completed")),
            "final_tick": run.get("final_tick"),
            "target_ticks": run.get("target_ticks"),
            "certification": (
                "eligible_replication"
                if not trial_flags
                else "diagnostic_only"
            ),
        },
        "cohorts": scored,
    }


def score_benchmark_counts(raw: dict[str, Any]) -> dict[str, Any]:
    """Apply the frozen participant-v1 formulas to pooled or per-run counts."""

    planning_denominator = float(raw.get("submitted_actions_excluding_contention") or 0)
    invalid = float(raw.get("invalid_proposals") or 0)
    planning = (
        _clamp_score(100.0 * (planning_denominator - invalid) / planning_denominator)
        if planning_denominator > 0
        else None
    )

    possible_ticks = float(raw.get("possible_agent_ticks") or 0)
    survival_exposure = (
        _clamp_score(100.0 * float(raw.get("decisions") or 0) / possible_ticks)
        if possible_ticks > 0
        else None
    )
    initial_endowment = float(raw.get("initial_endowment_value") or 0)
    terminal_value = float(raw.get("terminal_economic_value") or 0)
    material_target = initial_endowment * TERMINAL_ENDOWMENT_MULTIPLE_TARGET
    material = (
        _clamp_score(100.0 * terminal_value / material_target)
        if material_target > 0
        else None
    )
    competence = _geometric_mean((planning, survival_exposure, material))

    initiative_rate = (
        100.0 * float(raw.get("venture_initiatives") or 0) / possible_ticks
        if possible_ticks > 0
        else None
    )
    realized_rate = (
        100.0 * float(raw.get("realized_venture_value") or 0) / possible_ticks
        if possible_ticks > 0
        else None
    )
    initiative_score = (
        _clamp_score(100.0 * initiative_rate / INITIATIVE_TARGET_PER_100_AGENT_TICKS)
        if initiative_rate is not None
        else None
    )
    realization_score = (
        _clamp_score(100.0 * realized_rate / REALIZED_VALUE_TARGET_PER_100_AGENT_TICKS)
        if realized_rate is not None
        else None
    )
    entrepreneurship = _geometric_mean((initiative_score, realization_score))

    return {
        "planning_execution": {
            "score": planning,
            "components": {
                "submitted_actions": raw.get("submitted_actions", 0),
                "contention_excluded": raw.get("contention_failures", 0),
                "invalid_proposals": raw.get("invalid_proposals", 0),
                "action_point_overruns": raw.get("action_point_overruns", 0),
                "valid_proposal_rate_pct": planning,
            },
            "formula": (
                "100 * (submitted - contention - invalid) / "
                "(submitted - contention)"
            ),
        },
        "sustained_competence": {
            "score": competence,
            "components": {
                "planning_execution": planning,
                "survival_exposure_pct": survival_exposure,
                "material_outcome_pct": material,
                "terminal_economic_value": terminal_value,
                "initial_endowment_value": initial_endowment,
                "material_target_value": material_target,
            },
            "formula": (
                "geometric_mean(planning execution, survival exposure, "
                "terminal value relative to 3x starting endowment)"
            ),
        },
        "entrepreneurial_agency": {
            "score": entrepreneurship,
            "components": {
                "venture_initiatives": raw.get("venture_initiatives", 0),
                "venture_initiatives_per_100_agent_ticks": _rounded(initiative_rate),
                "initiative_score": initiative_score,
                "realized_venture_value": raw.get("realized_venture_value", 0),
                "realized_value_per_100_agent_ticks": _rounded(realized_rate),
                "realization_score": realization_score,
            },
            "formula": (
                "geometric_mean(initiative rate vs 20/100 agent-ticks, "
                "realized value rate vs 40/100 agent-ticks)"
            ),
        },
    }


def aggregate_benchmark_reports(reports: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Pool protocol-compliant replication counts into model benchmark results."""

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    expected_fingerprint = benchmark_code_fingerprint()
    for report in reports:
        benchmark = report.get("benchmarks") or {}
        if benchmark.get("suite_id") != BENCHMARK_SUITE_ID:
            rejected.append(
                {
                    "source": report.get("source"),
                    "reason": "missing_or_incompatible_benchmark_suite",
                }
            )
            continue
        if (
            (benchmark.get("protocol") or {}).get("code_fingerprint_sha256")
            != expected_fingerprint
        ):
            rejected.append(
                {
                    "source": report.get("source"),
                    "reason": "benchmark_code_fingerprint_mismatch",
                }
            )
            continue
        trial = benchmark.get("trial") or {}
        seed = trial.get("seed")
        for cohort_id, cohort in (benchmark.get("cohorts") or {}).items():
            identity = (
                str(cohort.get("brain") or "unknown"),
                str(cohort.get("model") or "unknown"),
                str(cohort.get("reasoning_effort") or "unknown"),
            )
            if not cohort.get("protocol_compliant"):
                rejected.append(
                    {
                        "source": report.get("source"),
                        "cohort": cohort_id,
                        "model": identity[1],
                        "reason": "diagnostic_only",
                        "quality_flags": cohort.get("quality_flags") or [],
                    }
                )
                continue
            row = grouped.setdefault(
                identity,
                {
                    "brain": identity[0],
                    "model": identity[1],
                    "reasoning_effort": identity[2],
                    "seeds": set(),
                    "seed_counts": Counter(),
                    "sources": [],
                    "raw": {},
                },
            )
            row["seeds"].add(int(seed))
            row["seed_counts"][int(seed)] += 1
            row["sources"].append(report.get("source"))
            _merge_numeric_tree(row["raw"], cohort.get("raw") or {})

    results: list[dict[str, Any]] = []
    for row in grouped.values():
        seeds = sorted(row.pop("seeds"))
        seed_counts = row.pop("seed_counts")
        raw = row.pop("raw")
        missing_seeds = sorted(BENCHMARK_SEEDS - set(seeds))
        certification_flags = []
        if missing_seeds:
            certification_flags.append("missing_required_seeds")
        if any(count != 1 for count in seed_counts.values()):
            certification_flags.append("duplicate_seed_replication")
        results.append(
            {
                **row,
                "seeds": seeds,
                "certified": not certification_flags,
                "certification_flags": certification_flags,
                "raw": raw,
                "scores": score_benchmark_counts(raw),
            }
        )
    results.sort(
        key=lambda row: (
            -_score_or_negative(row["scores"]["sustained_competence"]["score"]),
            row["model"],
        )
    )
    return {
        "suite_id": BENCHMARK_SUITE_ID,
        "protocol": benchmark_protocol(),
        "results": results,
        "rejected": rejected,
    }


def format_benchmark_leaderboard(aggregate: dict[str, Any]) -> str:
    """Render a compact human-readable leaderboard."""

    lines = [
        f"# Agent World benchmark: {aggregate.get('suite_id')}",
        "",
        "| Model | Seeds | Planning | Competence | Entrepreneurship | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in aggregate.get("results") or []:
        scores = row.get("scores") or {}
        status = "certified" if row.get("certified") else "provisional"
        lines.append(
            f"| {row.get('model')} | {','.join(str(value) for value in row.get('seeds') or [])} "
            f"| {_format_score(scores.get('planning_execution', {}).get('score'))} "
            f"| {_format_score(scores.get('sustained_competence', {}).get('score'))} "
            f"| {_format_score(scores.get('entrepreneurial_agency', {}).get('score'))} "
            f"| {status} |"
        )
    if aggregate.get("rejected"):
        lines += [
            "",
            f"Excluded diagnostic/noncompliant cohort results: {len(aggregate['rejected'])}.",
        ]
    return "\n".join(lines) + "\n"


def _cohort_raw_metrics(
    *,
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    config: dict[str, Any],
    member_ids: list[str],
    final_tick: int,
) -> dict[str, Any]:
    members = set(member_ids)
    responses = [
        event
        for event in events
        if event.get("type") == "agent_response" and event.get("actor_id") in members
    ]
    submitted = sum(
        len((event.get("data") or {}).get("actions") or [])
        for event in responses
    )
    invalid_events = [
        event
        for event in events
        if event.get("type") == "invalid_action" and event.get("actor_id") in members
    ]
    contention_events = [
        event
        for event in events
        if event.get("type") == "contention_failure" and event.get("actor_id") in members
    ]
    possible_ticks = len(member_ids) * final_tick
    initial_per_agent = _initial_endowment_value(config)
    terminal_value = _terminal_economic_value(snapshot, config, members)
    initiative_counts = Counter(
        str(event.get("type"))
        for event in events
        if event.get("actor_id") in members
        and event.get("type") in VENTURE_INITIATIVE_EVENTS
    )
    realized = _realized_venture_value(events, snapshot, config, members)
    decision_failures = sum(
        is_decision_failure_message(event.get("type"), event.get("message"))
        for event in responses
    )
    return {
        "initial_agents": len(member_ids),
        "possible_agent_ticks": possible_ticks,
        "decisions": len(responses),
        "decision_failures": decision_failures,
        "submitted_actions": submitted,
        "contention_failures": len(contention_events),
        "submitted_actions_excluding_contention": max(
            0, submitted - len(contention_events)
        ),
        "invalid_proposals": len(invalid_events),
        "action_point_overruns": sum(
            "action point" in str(event.get("message") or "").lower()
            for event in invalid_events
        ),
        "initial_endowment_value": initial_per_agent * len(member_ids),
        "terminal_economic_value": _rounded(terminal_value),
        "venture_initiatives": sum(initiative_counts.values()),
        "venture_initiatives_by_type": dict(sorted(initiative_counts.items())),
        "realized_venture_value": _rounded(realized["total"]),
        "realized_venture_value_by_source": realized["by_source"],
    }


def _trial_flags(
    report: dict[str, Any],
    start_data: dict[str, Any],
    cohorts: dict[str, Any],
) -> list[str]:
    run = report.get("run") or {}
    config = report.get("config") or {}
    reliability = report.get("reliability") or {}
    flags: list[str] = []

    expected = benchmark_protocol()["trial"]
    checks = {
        "agents": ((report.get("population") or {}).get("total_agents"), expected["agents"]),
        "ticks": (run.get("target_ticks"), expected["ticks"]),
        "final_tick": (run.get("final_tick"), expected["ticks"]),
        "economy_mode": (config.get("economy_mode"), expected["economy_mode"]),
        "geography_mode": (config.get("geography_mode"), expected["geography_mode"]),
        "specialization_mode": (
            config.get("specialization_mode"),
            expected["specialization_mode"],
        ),
        "objective_mode": (config.get("objective_mode"), expected["objective_mode"]),
        "decision_mode": (start_data.get("decision_mode"), expected["decision_mode"]),
        "action_feedback_mode": (
            start_data.get("action_feedback_mode"),
            expected["action_feedback_mode"],
        ),
        "connector_profile": (
            start_data.get("connector_profile"),
            expected["connector_profile"],
        ),
        "conversation_mode": (
            start_data.get("conversation_mode"),
            expected["conversation_mode"],
        ),
        "turn_resolution": (
            start_data.get("turn_resolution"),
            expected["turn_resolution"],
        ),
        "global_max_workers": (
            start_data.get("global_max_workers"),
            expected["global_max_workers"],
        ),
    }
    for name, (actual, wanted) in checks.items():
        if actual != wanted:
            flags.append(f"protocol_mismatch:{name}")
    if start_data.get("benchmark_protocol") != BENCHMARK_PROTOCOL_ID:
        flags.append("benchmark_protocol_not_declared")
    if start_data.get("benchmark_code_fingerprint") != benchmark_code_fingerprint():
        flags.append("benchmark_code_fingerprint_mismatch")
    if config.get("seed") not in BENCHMARK_SEEDS:
        flags.append("nonstandard_seed")
    if not run.get("completed"):
        flags.append("run_not_completed")
    if len(cohorts) != 1:
        flags.append("population_not_uniform")
    else:
        cohort = next(iter(cohorts.values()))
        if cohort.get("reasoning_effort") != expected["reasoning_effort"]:
            flags.append("protocol_mismatch:reasoning_effort")
        if cohort.get("initial_agents") != expected["agents"]:
            flags.append("protocol_mismatch:cohort_size")
    if reliability.get("quality_status") != "clean":
        flags.append("run_quality_not_clean")
    if reliability.get("usage_record_coverage_pct") != 100.0:
        flags.append("usage_coverage_not_complete")
    provider_limits = start_data.get("provider_max_workers") or {}
    used_provider = next(
        (
            str(cohort.get("provider"))
            for cohort in cohorts.values()
            if cohort.get("provider")
        ),
        None,
    )
    if (
        used_provider is None
        or provider_limits.get(used_provider) != expected["provider_max_workers"]
    ):
        flags.append("protocol_mismatch:provider_max_workers")
    if start_data.get("agent_io_log") is not True:
        flags.append("protocol_mismatch:agent_io_log")
    return flags


def _cohort_diagnostics(
    events: list[dict[str, Any]],
    members: set[str],
    raw: dict[str, Any],
) -> dict[str, Any]:
    counts = Counter(
        str(event.get("type"))
        for event in events
        if event.get("actor_id") in members
    )
    possible = float(raw.get("possible_agent_ticks") or 0)
    return {
        "communications": counts.get("say", 0)
        + counts.get("whisper", 0)
        + counts.get("broadcast", 0),
        "gifts": counts.get("gift", 0),
        "trades_accepted": counts.get("accept_trade", 0),
        "construction_contributions": counts.get("contribute", 0),
        "groups_created": counts.get("create_group", 0),
        "communications_per_100_agent_ticks": (
            round(
                100
                * (
                    counts.get("say", 0)
                    + counts.get("whisper", 0)
                    + counts.get("broadcast", 0)
                )
                / possible,
                2,
            )
            if possible
            else None
        ),
        "note": (
            "Social activity is diagnostic only in v1: frequency does not establish "
            "coordination quality or prosocial/antisocial intent."
        ),
    }


def _terminal_economic_value(
    snapshot: dict[str, Any],
    config: dict[str, Any],
    members: set[str],
) -> float:
    value = 0.0
    agents = snapshot.get("agents") or {}
    for agent_id in members:
        value += _book_value((agents.get(agent_id) or {}).get("inventory"))

    groups = snapshot.get("groups") or {}
    for structure in (snapshot.get("structures") or {}).values():
        if structure.get("status") != "complete":
            continue
        asset_value = float(
            _structure_replacement_value(
                str(structure.get("type") or ""),
                str(config.get("economy_mode") or "baseline"),
            )
        )
        asset_value += _book_value(structure.get("inventory"))
        asset_value += _book_value(structure.get("treasury"))
        asset_value += _book_value(structure.get("upkeep_reserve"))
        value += _attributed_owner_value(
            str(structure.get("owner_id") or ""),
            asset_value,
            members,
            groups,
        )

    for item in (snapshot.get("items") or {}).values():
        owner = str(item.get("owner_id") or "")
        if owner in members:
            value += RESOURCE_VALUES.get(str(item.get("item") or ""), 1) * int(
                item.get("quantity") or 0
            )

    for trade in (snapshot.get("trades") or {}).values():
        if (
            trade.get("status") == "open"
            and str(trade.get("from_agent") or "") in members
        ):
            value += _book_value(trade.get("give")) * int(
                trade.get("lots_remaining") or 1
            )
    for contract in (snapshot.get("contracts") or {}).values():
        if (
            contract.get("status") == "offered"
            and str(contract.get("lender_id") or "") in members
        ):
            value += _book_value(contract.get("advance"))
        elif (
            contract.get("status") == "active"
            and str(contract.get("borrower_id") or "") in members
        ):
            value += _book_value(contract.get("collateral"))
    return value


def _realized_venture_value(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    config: dict[str, Any],
    members: set[str],
) -> dict[str, Any]:
    groups = snapshot.get("groups") or {}
    asset_value = 0.0
    for structure in (snapshot.get("structures") or {}).values():
        if structure.get("status") != "complete":
            continue
        replacement = _structure_replacement_value(
            str(structure.get("type") or ""),
            str(config.get("economy_mode") or "baseline"),
        )
        asset_value += _attributed_owner_value(
            str(structure.get("owner_id") or ""),
            float(replacement),
            members,
            groups,
        )

    trade_value = 0.0
    fee_value = 0.0
    contract_value = 0.0
    structures = snapshot.get("structures") or {}
    for event in events:
        data = event.get("data") or {}
        if event.get("type") == "accept_trade":
            trade = data.get("trade") or {}
            if str(trade.get("from_agent") or "") in members:
                reported = data.get("value") or {}
                trade_value += float(
                    reported.get("give", _book_value(trade.get("give")))
                )
                trade_value += float(
                    reported.get("receive", _book_value(trade.get("receive")))
                )
        elif event.get("type") == "pay_access_fee":
            structure = structures.get(str(data.get("structure_id") or "")) or {}
            fee = _book_value(data.get("fee"))
            fee_value += _attributed_owner_value(
                str(structure.get("owner_id") or ""),
                float(fee),
                members,
                groups,
            )
        elif event.get("type") == "fulfill_contract":
            contract = data.get("contract") or {}
            if str(contract.get("lender_id") or "") in members:
                contract_value += _book_value(contract.get("repayment"))

    by_source = {
        "completed_asset_value": _rounded(asset_value),
        "originated_accepted_trade_value": _rounded(trade_value),
        "access_fee_income_value": _rounded(fee_value),
        "fulfilled_contract_repayment_value": _rounded(contract_value),
    }
    return {"total": sum(float(value) for value in by_source.values()), "by_source": by_source}


def _attributed_owner_value(
    owner_id: str,
    value: float,
    members: set[str],
    groups: dict[str, Any],
) -> float:
    if owner_id in members:
        return value
    group = groups.get(owner_id)
    if not isinstance(group, dict):
        return 0.0
    group_members = [str(agent_id) for agent_id in group.get("members") or []]
    if not group_members:
        return 0.0
    matching = sum(agent_id in members for agent_id in group_members)
    return value * matching / len(group_members)


def _initial_endowment_value(config: dict[str, Any]) -> int:
    inventory = {"food": 1, "water": 2}
    if config.get("economy_mode") == "organic":
        inventory["coin"] = 4
    return _book_value(inventory)


def _structure_replacement_value(structure_type: str, economy_mode: str) -> int:
    recipe = recipes_for_mode(economy_mode).get(structure_type)
    return _book_value(getattr(recipe, "inputs", {})) if recipe is not None else 0


def _book_value(items: Any) -> int:
    if not isinstance(items, dict):
        return 0
    return sum(
        RESOURCE_VALUES.get(str(item), 1) * max(0, int(quantity or 0))
        for item, quantity in items.items()
    )


def _latest_lifecycle_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            event
            for event in reversed(events)
            if event.get("type") in {"run_started", "run_resumed"}
        ),
        None,
    )


def _geometric_mean(values: Iterable[float | None]) -> float | None:
    supplied = tuple(values)
    parsed = [float(value) for value in supplied if value is not None]
    if not parsed:
        return None
    if len(parsed) != len(supplied):
        return None
    if any(value <= 0 for value in parsed):
        return 0.0
    return round(math.prod(parsed) ** (1.0 / len(parsed)), 2)


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _score_or_negative(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else -1.0


def _format_score(value: Any) -> str:
    return f"{float(value):.1f}" if isinstance(value, (int, float)) else "n/a"


def _merge_numeric_tree(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            target[key] = target.get(key, 0) + value
        elif isinstance(value, dict):
            nested = target.setdefault(key, {})
            if isinstance(nested, dict):
                _merge_numeric_tree(nested, value)
