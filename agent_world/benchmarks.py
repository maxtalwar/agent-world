"""Versioned, deterministic benchmarks for model behavior in Agent World."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from agent_world.metrics import (
    is_ambiguous_boundary_failure_message,
    is_confirmed_model_contract_failure_message,
    is_decision_failure_message,
    is_harness_failure_message,
    is_model_output_failure_message,
    is_provider_failure_message,
    is_quota_failure_message,
)
from agent_world.rules import ACCOUNTING_VALUES, recipes_for_mode


BENCHMARK_SUITE_ID = "agent-world-participant-v4"
BENCHMARK_PROTOCOL_ID = "participant-v4"
BENCHMARK_SEEDS = frozenset({11, 41})
BENCHMARK_EXTENDED_SEEDS = frozenset({73, 101, 137})
BENCHMARK_ALLOWED_SEEDS = BENCHMARK_SEEDS | BENCHMARK_EXTENDED_SEEDS
BENCHMARK_PROVISIONAL_SEED = 11
BENCHMARK_DIAGNOSTIC_TICKS = (30, 40, 50)
BENCHMARK_SCORING_REVISION = 1
BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS: frozenset[str] = frozenset()
BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS: frozenset[str] = frozenset()

# These are mechanics-anchored "excellent" targets, not population percentiles.
# Versioning the suite freezes them so later runs remain directly comparable.
# Participant v4 anchors are intentionally close to demonstrated strong-model
# behavior instead of preserving v3's unreachable scale. Five initiatives per
# 100 agent-ticks is just above the 4.25 rate in the clean GPT-5.4 v2 reference.
INITIATIVE_TARGET_PER_100_AGENT_TICKS = 5.0
NET_VALUE_CREATION_TARGET_PER_100_AGENT_TICKS = 20.0
TERMINAL_ENDOWMENT_MULTIPLE_TARGET = 3.0

VENTURE_INITIATIVE_EVENTS = frozenset(
    {"offer_trade", "build_started", "create_contract", "set_access_fee"}
)
PURPOSEFUL_ACTION_EVENTS = frozenset(
    {
        "move",
        "gather",
        "chop",
        "mine",
        "harvest",
        "fish",
        "farm",
        "craft",
        "repair",
        "pick_up",
        "claimed_item_taken",
        "drop",
        "claim_item",
        "consume",
        "equip",
        "store",
        "retrieve",
        "offer_trade",
        "accept_trade",
        "reject_trade",
        "create_contract",
        "accept_contract",
        "repay_contract",
        "fulfill_contract",
        "gift",
        "claim_tile",
        "contest_claim",
        "build",
        "build_started",
        "contribute",
        "set_access_fee",
        "claim_dividend",
        "maintain_structure",
        "grant_access",
        "revoke_access",
        "create_group",
        "invite_member",
        "join_group",
        "leave_group",
        "publish_rule",
        "record_agreement",
    }
)
BENCHMARK_FINGERPRINT_FILES = (
    "benchmarks.py",
    "brain_boundary.py",
    "brain_runtime.py",
    "claude_brain.py",
    "cli.py",
    "codex_brain.py",
    "cursor_brain.py",
    "decision_failure.py",
    "interface.py",
    "maps.py",
    "models.py",
    "openai_brain.py",
    "rules.py",
    "run_report.py",
    "runner.py",
    "session.py",
    "world.py",
)


def _recipe_consistent_accounting_values(economy_mode: str) -> dict[str, int]:
    """Raise book values until every single-output recipe preserves input value."""

    values = dict(ACCOUNTING_VALUES)
    recipes = recipes_for_mode(economy_mode)
    for _ in range(max(1, len(recipes) + 1)):
        changed = False
        for recipe in recipes.values():
            outputs = {
                str(item): max(0, int(quantity or 0))
                for item, quantity in recipe.outputs.items()
                if int(quantity or 0) > 0
            }
            if len(outputs) != 1:
                continue
            output_item, output_quantity = next(iter(outputs.items()))
            input_value = sum(
                values.get(str(item), 1) * max(0, int(quantity or 0))
                for item, quantity in recipe.inputs.items()
            )
            minimum_unit_value = math.ceil(input_value / output_quantity)
            if minimum_unit_value > values.get(output_item, 1):
                values[output_item] = minimum_unit_value
                changed = True
        if not changed:
            break
    return values


BENCHMARK_ACCOUNTING_VALUES = _recipe_consistent_accounting_values("organic")


def benchmark_code_fingerprint() -> str:
    """Hash benchmark formulas and behavior-defining world sources."""

    package_dir = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in BENCHMARK_FINGERPRINT_FILES:
        digest.update(name.encode("utf-8"))
        digest.update((package_dir / name).read_bytes())
    return digest.hexdigest()


def benchmark_protocol() -> dict[str, Any]:
    """Return the frozen participant-v4 trial and scoring specification."""

    return {
        "id": BENCHMARK_PROTOCOL_ID,
        "scoring_revision": BENCHMARK_SCORING_REVISION,
        "suite_id": BENCHMARK_SUITE_ID,
        "code_fingerprint_sha256": benchmark_code_fingerprint(),
        "replications": {
            "required_seeds": sorted(BENCHMARK_SEEDS),
            "minimum": len(BENCHMARK_SEEDS),
            "provisional_seed": BENCHMARK_PROVISIONAL_SEED,
            "provisional_minimum": 1,
            "optional_extended_seeds": sorted(BENCHMARK_EXTENDED_SEEDS),
            "policy": (
                "One clean complete seed-11 run is a provisional benchmark. "
                "Clean runs on required seeds 11 and 41 are a replicated certified "
                "benchmark. Seeds 73, 101, and 137 are optional extended evidence "
                "and never block certification."
            ),
        },
        "trial": {
            "agents": 10,
            "ticks": 50,
            "diagnostic_score_ticks": list(BENCHMARK_DIAGNOSTIC_TICKS),
            "official_score_tick": 50,
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
            "model_output_failure_policy": (
                "Independently validate each extracted decision against the "
                "declared contract. Count confirmed output-contract violations "
                "as invalid proposals; invalidate adapter, ambiguous-boundary, "
                "provider, quota, and harness failures."
            ),
        },
        "score_scale": {
            "minimum": 0.0,
            "maximum": None,
            "higher_is_better": True,
            "metric_specific": True,
            "details": "See score_scales for per-benchmark bounds.",
        },
        "score_scales": {
            "effective_execution": {
                "minimum": 0.0,
                "maximum": 100.0,
                "higher_is_better": True,
            },
            "sustained_competence": {
                "minimum": 0.0,
                "maximum": 100.0,
                "higher_is_better": True,
            },
            "entrepreneurial_agency": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
            },
            "economic_productivity": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
                "diagnostic": True,
            },
        },
        "targets": {
            "terminal_endowment_multiple": TERMINAL_ENDOWMENT_MULTIPLE_TARGET,
            "venture_initiatives_per_100_agent_ticks": INITIATIVE_TARGET_PER_100_AGENT_TICKS,
            "net_value_created_per_100_agent_ticks": NET_VALUE_CREATION_TARGET_PER_100_AGENT_TICKS,
        },
        "accounting_values": {
            "method": (
                "Start from the world book-value table and raise output values "
                "until every single-output recipe is worth at least its inputs."
            ),
            "values": dict(sorted(BENCHMARK_ACCOUNTING_VALUES.items())),
        },
        "aggregation": (
            "For a provisional result, apply the frozen formulas to the clean "
            "seed-11 raw counts. For replicated certification, pool raw numerators "
            "and denominators across required seeds 11 and 41 before scoring. "
            "Optional extended seeds are reported separately and do not change the "
            "official certified score. Report individual seed scores plus their "
            "range and absolute difference; do not claim a confidence interval. "
            "Tick-30 and tick-40 score snapshots are diagnostic trajectories; only "
            "tick 50 is official."
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
        member_set = set(member_ids)
        raw = _cohort_raw_metrics(
            events=events,
            snapshot=snapshot,
            config=config,
            member_ids=member_ids,
            final_tick=int(run.get("final_tick") or 0),
            target_ticks=int(run.get("target_ticks") or 0),
        )
        cohort_flags = list(trial_flags)
        if raw["submitted_actions_excluding_contention"] <= 0:
            cohort_flags.append("insufficient_action_sample")
        if raw["possible_agent_ticks"] <= 0:
            cohort_flags.append("insufficient_agent_tick_sample")
        confirmed_contract_failures = sum(
            is_confirmed_model_contract_failure_message(
                event.get("type"),
                event.get("message"),
            )
            for event in events
            if event.get("actor_id") in member_set
        )
        if raw["model_output_failures"] > confirmed_contract_failures:
            cohort_flags.append("unverified_model_output_attribution")
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
            "source_fingerprint_compatible": (
                start_data.get("benchmark_code_fingerprint")
                in BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS
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
        "trajectory": _benchmark_trajectory(events),
    }


def score_benchmark_counts(raw: dict[str, Any]) -> dict[str, Any]:
    """Apply the frozen participant-v4 formulas to pooled or per-run counts."""

    feasibility_denominator = float(
        raw.get("submitted_actions_excluding_contention") or 0
    )
    invalid = float(raw.get("invalid_proposals") or 0)
    action_feasibility = (
        _clamp_score(
            100.0
            * (feasibility_denominator - invalid)
            / feasibility_denominator
        )
        if feasibility_denominator > 0
        else None
    )
    decisions = float(raw.get("decisions") or 0)
    purposeful_agent_ticks = float(raw.get("purposeful_agent_ticks") or 0)
    purposeful_agent_tick_pct = (
        _clamp_score(100.0 * purposeful_agent_ticks / decisions)
        if decisions > 0
        else None
    )
    effective_execution = _geometric_mean(
        (action_feasibility, purposeful_agent_tick_pct)
    )

    possible_ticks = float(raw.get("possible_agent_ticks") or 0)
    survival_exposure = (
        _clamp_score(100.0 * decisions / possible_ticks)
        if possible_ticks > 0
        else None
    )
    endpoint_health_capacity = float(raw.get("endpoint_health_capacity") or 0)
    endpoint_population_health = (
        _clamp_score(
            100.0
            * float(raw.get("endpoint_health_points") or 0)
            / endpoint_health_capacity
        )
        if endpoint_health_capacity > 0
        else None
    )
    survival_continuity = _geometric_mean(
        (survival_exposure, endpoint_population_health)
    )
    initial_endowment = float(raw.get("initial_endowment_value") or 0)
    living_terminal_value = float(
        raw.get("living_terminal_economic_value") or 0
    )
    material_target = initial_endowment * TERMINAL_ENDOWMENT_MULTIPLE_TARGET
    material = (
        _clamp_score(100.0 * living_terminal_value / material_target)
        if material_target > 0
        else None
    )
    competence = _geometric_mean(
        (effective_execution, survival_continuity, material)
    )

    initiative_rate = (
        100.0 * float(raw.get("venture_initiatives") or 0) / possible_ticks
        if possible_ticks > 0
        else None
    )
    net_value_created = max(
        0.0,
        living_terminal_value - initial_endowment,
    )
    net_value_creation_rate = (
        100.0 * net_value_created / possible_ticks
        if possible_ticks > 0
        else None
    )
    initiative_score = (
        _nonnegative_score(
            100.0 * initiative_rate / INITIATIVE_TARGET_PER_100_AGENT_TICKS
        )
        if initiative_rate is not None
        else None
    )
    value_creation_score = (
        _nonnegative_score(
            100.0
            * net_value_creation_rate
            / NET_VALUE_CREATION_TARGET_PER_100_AGENT_TICKS
        )
        if net_value_creation_rate is not None
        else None
    )
    entrepreneurship = _geometric_mean((initiative_score, value_creation_score))

    return {
        "effective_execution": {
            "score": effective_execution,
            "components": {
                "submitted_actions": raw.get("submitted_actions", 0),
                "contention_excluded": raw.get("contention_failures", 0),
                "invalid_proposals": raw.get("invalid_proposals", 0),
                "engine_invalid_proposals": raw.get(
                    "engine_invalid_proposals",
                    raw.get("invalid_proposals", 0),
                ),
                "model_output_failures": raw.get("model_output_failures", 0),
                "action_point_overruns": raw.get("action_point_overruns", 0),
                "action_feasibility_pct": action_feasibility,
                "purposeful_agent_ticks": raw.get("purposeful_agent_ticks", 0),
                "decision_opportunities": raw.get("decisions", 0),
                "purposeful_agent_tick_pct": purposeful_agent_tick_pct,
            },
            "formula": (
                "geometric_mean(action feasibility, purposeful agent-tick rate); "
                "action feasibility = 100 * (submitted - contention - engine "
                "invalid - model-output failures) / (submitted - contention)"
            ),
        },
        "sustained_competence": {
            "score": competence,
            "components": {
                "effective_execution": effective_execution,
                "survival_exposure_pct": survival_exposure,
                "endpoint_population_health_pct": endpoint_population_health,
                "survival_continuity_pct": survival_continuity,
                "living_agents": raw.get("living_agents", 0),
                "initial_agents": raw.get("initial_agents", 0),
                "material_outcome_pct": material,
                "living_terminal_economic_value": living_terminal_value,
                "total_terminal_economic_value": raw.get(
                    "terminal_economic_value", 0
                ),
                "initial_endowment_value": initial_endowment,
                "material_target_value": material_target,
            },
            "formula": (
                "geometric_mean(effective execution, "
                "geometric_mean(target-horizon survival exposure, "
                "endpoint population health), living-accessible terminal value "
                "relative to 3x starting endowment)"
            ),
        },
        "entrepreneurial_agency": {
            "score": entrepreneurship,
            "components": {
                "venture_initiatives": raw.get("venture_initiatives", 0),
                "venture_initiatives_per_100_agent_ticks": _rounded(initiative_rate),
                "initiative_score": initiative_score,
                "net_value_created": _rounded(net_value_created),
                "net_value_created_per_100_agent_ticks": _rounded(
                    net_value_creation_rate
                ),
                "value_creation_score": value_creation_score,
            },
            "formula": (
                "geometric_mean(initiative rate vs 5/100 agent-ticks, "
                "positive living-accessible net value creation rate vs "
                "20/100 agent-ticks); 100 is the "
                "reference target, not a maximum"
            ),
            "scale": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
            },
        },
        "economic_productivity": {
            "score": value_creation_score,
            "components": {
                "living_terminal_economic_value": living_terminal_value,
                "initial_endowment_value": initial_endowment,
                "net_value_created": _rounded(net_value_created),
                "net_value_created_per_100_agent_ticks": _rounded(
                    net_value_creation_rate
                ),
            },
            "formula": (
                "positive living-accessible terminal value minus starting "
                "endowment, per 100 agent-ticks, relative to the frozen target"
            ),
            "scale": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
            },
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
        report_protocol = benchmark.get("protocol") or {}
        report_fingerprint = report_protocol.get("code_fingerprint_sha256")
        source_revision = int(report_protocol.get("scoring_revision") or 1)
        compatible_prior_report = (
            source_revision < BENCHMARK_SCORING_REVISION
            and report_fingerprint in BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS
        )
        if report_fingerprint != expected_fingerprint and not compatible_prior_report:
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
            cohort_raw = cohort.get("raw") or {}
            row = grouped.setdefault(
                identity,
                {
                    "brain": identity[0],
                    "model": identity[1],
                    "reasoning_effort": identity[2],
                    "seeds": set(),
                    "seed_counts": Counter(),
                    "sources": [],
                    "source_scoring_revisions": set(),
                    "replications": [],
                },
            )
            row["seeds"].add(int(seed))
            row["seed_counts"][int(seed)] += 1
            row["sources"].append(report.get("source"))
            row["source_scoring_revisions"].add(
                int(report_protocol.get("scoring_revision") or 1)
            )
            row["replications"].append(
                {
                    "seed": int(seed),
                    "source": report.get("source"),
                    "raw": cohort_raw,
                    "scores": score_benchmark_counts(cohort_raw),
                }
            )

    results: list[dict[str, Any]] = []
    for row in grouped.values():
        seeds = sorted(row.pop("seeds"))
        seed_counts = row.pop("seed_counts")
        source_scoring_revisions = sorted(row.pop("source_scoring_revisions"))
        replications = sorted(
            row.pop("replications"),
            key=lambda replication: (
                replication["seed"],
                str(replication.get("source") or ""),
            ),
        )
        required_seeds = sorted(BENCHMARK_SEEDS & set(seeds))
        extended_seeds = sorted(BENCHMARK_EXTENDED_SEEDS & set(seeds))
        required_replications = [
            replication
            for replication in replications
            if replication["seed"] in BENCHMARK_SEEDS
        ]
        extended_replications = [
            replication
            for replication in replications
            if replication["seed"] in BENCHMARK_EXTENDED_SEEDS
        ]
        official_raw: dict[str, Any] = {}
        for replication in required_replications:
            _merge_numeric_tree(official_raw, replication.get("raw") or {})
        all_raw: dict[str, Any] = {}
        for replication in replications:
            _merge_numeric_tree(all_raw, replication.get("raw") or {})

        missing_seeds = sorted(BENCHMARK_SEEDS - set(required_seeds))
        certification_flags = []
        if missing_seeds:
            certification_flags.append("missing_required_seeds")
        if any(seed_counts[seed] != 1 for seed in required_seeds):
            certification_flags.append("duplicate_seed_replication")
        certified = not certification_flags
        provisional = (
            required_seeds == [BENCHMARK_PROVISIONAL_SEED]
            and seed_counts[BENCHMARK_PROVISIONAL_SEED] == 1
            and certification_flags == ["missing_required_seeds"]
        )
        if certified:
            status = "certified"
        elif provisional:
            status = "provisional"
        else:
            status = "incomplete_replication"
        results.append(
            {
                **row,
                "seeds": seeds,
                "required_seeds": required_seeds,
                "extended_seeds": extended_seeds,
                "certified": certified,
                "provisional": provisional,
                "status": status,
                "certification_flags": certification_flags,
                "source_scoring_revisions": source_scoring_revisions,
                "scoring_revision": BENCHMARK_SCORING_REVISION,
                "replications": replications,
                "required_replications": required_replications,
                "extended_replications": extended_replications,
                "score_spread": _score_spread(required_replications),
                "extended_score_spread": (
                    _score_spread(replications) if extended_replications else None
                ),
                "raw": official_raw,
                "scores": score_benchmark_counts(official_raw),
                "extended_raw": all_raw if extended_replications else None,
                "extended_scores": (
                    score_benchmark_counts(all_raw)
                    if extended_replications
                    else None
                ),
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
        "| Model | Seeds | Execution | Competence | Entrepreneurship | Invalid proposals | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in aggregate.get("results") or []:
        scores = row.get("scores") or {}
        raw = row.get("raw") or {}
        status = row.get("status") or (
            "certified" if row.get("certified") else "incomplete_replication"
        )
        status = str(status).replace("_", " ")
        seed_text = ",".join(
            str(value) for value in row.get("required_seeds") or []
        )
        if row.get("extended_seeds"):
            seed_text += f" (+{len(row['extended_seeds'])} extended)"
        lines.append(
            f"| {row.get('model')} | {seed_text} "
            f"| {_format_score(scores.get('effective_execution', {}).get('score'))} "
            f"| {_format_score(scores.get('sustained_competence', {}).get('score'))} "
            f"| {_format_score(scores.get('entrepreneurial_agency', {}).get('score'))} "
            f"| {_format_count_rate(raw.get('invalid_proposals'), raw.get('submitted_actions'))} "
            f"| {status} |"
        )
    replications = [
        (row, replication)
        for row in aggregate.get("results") or []
        for replication in row.get("replications") or []
    ]
    if replications:
        lines += [
            "",
            "## Per-replication scores",
            "",
            "| Model | Seed | Role | Execution | Competence | Entrepreneurship |",
            "|---|---:|---|---:|---:|---:|",
        ]
        for row, replication in replications:
            scores = replication.get("scores") or {}
            role = (
                "certification"
                if replication.get("seed") in BENCHMARK_SEEDS
                else "optional extended"
            )
            lines.append(
                f"| {row.get('model')} | {replication.get('seed')} | {role} "
                f"| {_format_score((scores.get('effective_execution') or {}).get('score'))} "
                f"| {_format_score((scores.get('sustained_competence') or {}).get('score'))} "
                f"| {_format_score((scores.get('entrepreneurial_agency') or {}).get('score'))} |"
            )
        lines += [
            "",
            "Descriptive spread:",
            "",
        ]
        for row in aggregate.get("results") or []:
            competence_spread = (
                (row.get("score_spread") or {}).get("sustained_competence") or {}
            )
            difference = competence_spread.get("absolute_difference")
            difference_text = (
                _format_score(difference) if difference is not None else "n/a"
            )
            lines.append(
                f"- {row.get('model')}: official competence range "
                f"{_format_score(competence_spread.get('minimum'))}–"
                f"{_format_score(competence_spread.get('maximum'))}, "
                f"absolute seed difference {difference_text}."
            )
            if row.get("extended_score_spread"):
                extended_competence = (
                    row["extended_score_spread"].get("sustained_competence") or {}
                )
                lines.append(
                    f"  Optional extended evidence ({len(row.get('extended_seeds') or [])} "
                    f"extra seed(s)): full range "
                    f"{_format_score(extended_competence.get('minimum'))}–"
                    f"{_format_score(extended_competence.get('maximum'))}."
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
    target_ticks: int,
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
    benchmark_horizon = target_ticks if target_ticks > 0 else final_tick
    possible_ticks = len(member_ids) * benchmark_horizon
    observed_ticks = len(member_ids) * final_tick
    initial_per_agent = _initial_endowment_value(config)
    terminal_value = _terminal_economic_value(snapshot, config, members)
    snapshot_agents = snapshot.get("agents") or {}
    living_members = {
        agent_id
        for agent_id in members
        if bool((snapshot_agents.get(agent_id) or {}).get("alive"))
    }
    living_terminal_value = _terminal_economic_value(
        snapshot,
        config,
        living_members,
    )
    endpoint_health_points = sum(
        max(
            0.0,
            min(
                100.0,
                float((snapshot_agents.get(agent_id) or {}).get("health") or 0),
            ),
        )
        for agent_id in members
    )
    initiative_counts = Counter(
        str(event.get("type"))
        for event in events
        if event.get("actor_id") in members
        and (
            event.get("type") in VENTURE_INITIATIVE_EVENTS
            or (
                event.get("type") == "build"
                and "contributed" in (event.get("data") or {})
            )
        )
    )
    purposeful_agent_ticks = {
        (int(event.get("tick") or 0), str(event.get("actor_id") or ""))
        for event in events
        if event.get("actor_id") in members
        and event.get("type") in PURPOSEFUL_ACTION_EVENTS
        and (
            event.get("type") != "fulfill_contract"
            or (event.get("data") or {}).get("voluntary") is True
        )
    }
    decision_failures = sum(
        is_decision_failure_message(event.get("type"), event.get("message"))
        for event in responses
    )
    model_output_failures = sum(
        is_model_output_failure_message(event.get("type"), event.get("message"))
        for event in responses
    )
    external_decision_failures = sum(
        is_quota_failure_message(event.get("type"), event.get("message"))
        or is_provider_failure_message(event.get("type"), event.get("message"))
        or is_harness_failure_message(event.get("type"), event.get("message"))
        or is_ambiguous_boundary_failure_message(
            event.get("type"),
            event.get("message"),
        )
        for event in responses
    )
    engine_invalid_proposals = len(invalid_events)
    return {
        "initial_agents": len(member_ids),
        "possible_agent_ticks": possible_ticks,
        "observed_agent_ticks": observed_ticks,
        "decisions": len(responses),
        "decision_failures": decision_failures,
        "model_output_failures": model_output_failures,
        "external_decision_failures": external_decision_failures,
        "submitted_actions": submitted,
        "contention_failures": len(contention_events),
        "submitted_actions_excluding_contention": max(
            0, submitted - len(contention_events)
        ),
        "engine_invalid_proposals": engine_invalid_proposals,
        "invalid_proposals": engine_invalid_proposals + model_output_failures,
        "action_point_overruns": sum(
            "action point" in str(event.get("message") or "").lower()
            for event in invalid_events
        ),
        "initial_endowment_value": initial_per_agent * len(member_ids),
        "terminal_economic_value": _rounded(terminal_value),
        "living_agents": len(living_members),
        "endpoint_health_points": _rounded(endpoint_health_points),
        "endpoint_health_capacity": 100 * len(member_ids),
        "living_terminal_economic_value": _rounded(living_terminal_value),
        "purposeful_agent_ticks": len(purposeful_agent_ticks),
        "venture_initiatives": sum(initiative_counts.values()),
        "venture_initiatives_by_type": dict(sorted(initiative_counts.items())),
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
    source_fingerprint = start_data.get("benchmark_code_fingerprint")
    compatible_source = (
        start_data.get("benchmark_protocol") == BENCHMARK_PROTOCOL_ID
        and source_fingerprint in BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS
    )
    if start_data.get("benchmark_protocol") != BENCHMARK_PROTOCOL_ID:
        flags.append("benchmark_protocol_not_declared")
    if (
        source_fingerprint != benchmark_code_fingerprint()
        and not compatible_source
    ):
        flags.append("benchmark_code_fingerprint_mismatch")
    if config.get("seed") not in BENCHMARK_ALLOWED_SEEDS:
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
    integrity_status = reliability.get("benchmark_integrity_status")
    if integrity_status is not None:
        if integrity_status != "clean":
            flags.append("run_integrity_not_clean")
    elif reliability.get("quality_status") != "clean":
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
            "Social activity is diagnostic only in v4: frequency does not establish "
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
            value += BENCHMARK_ACCOUNTING_VALUES.get(
                str(item.get("item") or ""), 1
            ) * int(item.get("quantity") or 0)

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
        BENCHMARK_ACCOUNTING_VALUES.get(str(item), 1)
        * max(0, int(quantity or 0))
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


def _benchmark_trajectory(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recover durable v4 checkpoints and apply the current scoring revision."""

    checkpoints: dict[int, dict[str, Any]] = {}
    for event in events:
        if event.get("type") != "benchmark_checkpoint":
            continue
        data = event.get("data") or {}
        if (
            data.get("suite_id") != BENCHMARK_SUITE_ID
            or data.get("protocol_id") != BENCHMARK_PROTOCOL_ID
        ):
            continue
        try:
            tick = int(data.get("tick"))
        except (TypeError, ValueError):
            continue
        stored_cohorts = data.get("cohorts")
        if tick not in BENCHMARK_DIAGNOSTIC_TICKS or not isinstance(stored_cohorts, dict):
            continue
        checkpoint_model_failures: int | None = None
        checkpoint_external_failures: int | None = None
        if len(stored_cohorts) == 1:
            checkpoint_responses = [
                candidate
                for candidate in events
                if candidate.get("type") == "agent_response"
                and int(candidate.get("tick") or 0) < tick
            ]
            checkpoint_model_failures = sum(
                is_model_output_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                for candidate in checkpoint_responses
            )
            checkpoint_external_failures = sum(
                is_quota_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                or is_provider_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                or is_harness_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                or is_ambiguous_boundary_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                for candidate in checkpoint_responses
            )
        cohorts: dict[str, Any] = {}
        for cohort_id, cohort in stored_cohorts.items():
            if not isinstance(cohort, dict):
                continue
            raw = _normalize_model_failure_raw(
                cohort.get("raw") or {},
                model_output_failures=checkpoint_model_failures,
                external_decision_failures=checkpoint_external_failures,
            )
            cohorts[str(cohort_id)] = {
                **cohort,
                "raw": raw,
                "scores": score_benchmark_counts(raw),
            }
        try:
            score_horizon = int(data.get("score_horizon_ticks") or tick)
        except (TypeError, ValueError):
            score_horizon = tick
        checkpoints[tick] = {
            "tick": tick,
            "score_horizon_ticks": score_horizon,
            "role": (
                "official_endpoint"
                if tick == BENCHMARK_DIAGNOSTIC_TICKS[-1]
                else "diagnostic_checkpoint"
            ),
            "cohorts": cohorts,
        }
    return [checkpoints[tick] for tick in sorted(checkpoints)]


def _normalize_model_failure_raw(
    raw: dict[str, Any],
    *,
    model_output_failures: int | None,
    external_decision_failures: int | None,
) -> dict[str, Any]:
    """Normalize durable checkpoint failure counts from the event ledger."""

    normalized = dict(raw)
    if "engine_invalid_proposals" in normalized:
        return normalized
    engine_invalid = int(normalized.get("invalid_proposals") or 0)
    model_failures = int(
        model_output_failures
        if model_output_failures is not None
        else normalized.get("model_output_failures")
        or 0
    )
    normalized["engine_invalid_proposals"] = engine_invalid
    normalized["model_output_failures"] = model_failures
    normalized["external_decision_failures"] = int(
        external_decision_failures
        if external_decision_failures is not None
        else normalized.get("external_decision_failures")
        or 0
    )
    normalized["invalid_proposals"] = engine_invalid + model_failures
    return normalized


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


def _nonnegative_score(value: float) -> float:
    return round(max(0.0, value), 2)


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _score_or_negative(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else -1.0


def _format_score(value: Any) -> str:
    return f"{float(value):.1f}" if isinstance(value, (int, float)) else "n/a"


def _format_count_rate(value: Any, denominator: Any) -> str:
    count = int(value or 0)
    total = int(denominator or 0)
    if total <= 0:
        return f"{count} (n/a)"
    return f"{count} ({100.0 * count / total:.1f}%)"


def _score_spread(replications: list[dict[str, Any]]) -> dict[str, Any]:
    """Return transparent descriptive uncertainty without changing pooled scores."""

    spread: dict[str, Any] = {}
    for score_key in (
        "effective_execution",
        "sustained_competence",
        "entrepreneurial_agency",
        "economic_productivity",
    ):
        values = [
            float(score)
            for replication in replications
            if isinstance(
                score := (
                    (replication.get("scores") or {}).get(score_key) or {}
                ).get("score"),
                (int, float),
            )
        ]
        if not values:
            continue
        row: dict[str, Any] = {
            "n": len(values),
            "values": [round(value, 2) for value in values],
            "minimum": round(min(values), 2),
            "maximum": round(max(values), 2),
            "range_width": round(max(values) - min(values), 2),
        }
        if len(values) == 2:
            row["absolute_difference"] = round(abs(values[1] - values[0]), 2)
        spread[score_key] = row
    return spread


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
