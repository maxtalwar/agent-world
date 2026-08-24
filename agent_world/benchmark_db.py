"""Build and query the durable Agent World model-capability database.

The compact leaderboard is one projection of this database. The database keeps
run, tick, and decision-level measurements so later agents can answer questions
without reparsing every raw benchmark artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from agent_world.benchmarks import _merge_numeric_tree, score_benchmark_counts
from agent_world.run_report import _normalize_loaded_usage_record
from agent_world.usage import (
    USD_RATE_CARD_EFFECTIVE_DATE,
    USD_RATE_CARD_SOURCES,
    summarize_usd_cost,
)


SCHEMA_VERSION = 3
DEFAULT_CATALOG = Path("data/run-sources.json")
DEFAULT_DATABASE = Path("data/model-benchmarks.sqlite")


def _path_get(value: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _related_path(report_path: Path, suffix: str) -> Path:
    name = report_path.name
    if not name.endswith("-report.json"):
        raise ValueError(f"Expected *-report.json path, got {report_path}")
    return report_path.with_name(name[: -len("-report.json")] + suffix)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _latency_summary(values: Iterable[float]) -> dict[str, float | int | None]:
    samples = [float(value) for value in values if value is not None and float(value) >= 0]
    return {
        "samples": len(samples),
        "mean": statistics.fmean(samples) if samples else None,
        "median": statistics.median(samples) if samples else None,
        "p90": _percentile(samples, 0.90),
        "p95": _percentile(samples, 0.95),
        "p99": _percentile(samples, 0.99),
        "min": min(samples) if samples else None,
        "max": max(samples) if samples else None,
        "stddev": statistics.pstdev(samples) if samples else None,
    }


def _display_number(value: float, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return f"{rounded:,.{places}f}"


def _iso_duration_seconds(started: Any, ended: Any) -> float | None:
    if not isinstance(started, str) or not isinstance(ended, str):
        return None
    try:
        return (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds()
    except ValueError:
        return None


def _benchmark_cohorts(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cohorts = _path_get(report, "benchmarks", "cohorts", default={}) or {}
    return cohorts if isinstance(cohorts, dict) else {}


def _score(cohort: dict[str, Any], name: str) -> float | None:
    value = _path_get(cohort, "scores", name, "score")
    return float(value) if value is not None else None


def _sum_counts(value: Any) -> int:
    if isinstance(value, dict):
        return sum(int(item or 0) for item in value.values())
    return int(value or 0)


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE database_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE experiments (
            experiment_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            question TEXT NOT NULL,
            design_json TEXT NOT NULL,
            started_at TEXT,
            status TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE models (
            model_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            suite TEXT NOT NULL,
            scoring_revision INTEGER,
            controlled_variant INTEGER NOT NULL DEFAULT 0,
            variant_note TEXT,
            leaderboard_eligible INTEGER NOT NULL DEFAULT 1,
            leaderboard_exclusion_reason TEXT
        );

        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK(kind IN ('benchmark_trial','controlled_variant','experiment','diagnostic')),
            experiment_id TEXT REFERENCES experiments(experiment_id),
            seed INTEGER NOT NULL,
            width INTEGER,
            height INTEGER,
            preset TEXT,
            economy_mode TEXT,
            geography_mode TEXT,
            specialization_mode TEXT,
            world_variant TEXT,
            source_report TEXT NOT NULL,
            source_usage TEXT NOT NULL,
            source_manifest TEXT,
            report_sha256 TEXT NOT NULL,
            usage_sha256 TEXT NOT NULL,
            manifest_sha256 TEXT,
            launch_commit TEXT,
            connector_profile TEXT,
            conversation_mode TEXT,
            global_max_workers INTEGER,
            started_at_utc TEXT,
            ended_at_utc TEXT,
            wall_clock_seconds REAL,
            usage_observed_span_seconds REAL,
            completed INTEGER NOT NULL,
            final_tick INTEGER,
            target_ticks INTEGER,
            integrity_status TEXT,
            quality_status TEXT,
            quality_flags_json TEXT NOT NULL,
            usage_coverage_pct REAL,
            configured_agents INTEGER,
            initial_agents INTEGER,
            living_agents INTEGER,
            deaths INTEGER,
            endpoint_health_points REAL,
            endpoint_health_capacity REAL,
            living_terminal_economic_value REAL,
            terminal_economic_value REAL,
            initial_endowment_value REAL,
            enterprise_supply_value REAL,
            net_goods_supply_value REAL,
            net_service_income REAL,
            informal_transfer_value REAL,
            own_capital_output_value REAL,
            completed_structures INTEGER,
            completed_structures_json TEXT NOT NULL,
            in_progress_structures INTEGER,
            cooperative_builds INTEGER,
            groups_created INTEGER,
            access_grants INTEGER,
            trades_offered INTEGER,
            trades_accepted INTEGER,
            trade_conversion_pct REAL,
            accepted_trade_value REAL,
            gifts INTEGER,
            gift_quantity INTEGER,
            gift_value REAL,
            contracts_fulfilled INTEGER,
            contracts_defaulted INTEGER,
            access_fee_value REAL,
            dividend_value REAL,
            communications INTEGER,
            construction_contributions INTEGER,
            decision_attempts INTEGER,
            decision_failure_rate_pct REAL,
            invalid_action_rate_pct REAL,
            contention_failure_rate_pct REAL,
            model_output_failures INTEGER,
            provider_failures INTEGER,
            quota_failures INTEGER,
            harness_failures INTEGER,
            calls INTEGER NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            cached_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            reasoning_tokens INTEGER NOT NULL,
            cache_hit_rate_pct REAL,
            api_list_cost_usd REAL,
            latency_coverage_pct REAL,
            latency_mean_seconds REAL,
            latency_median_seconds REAL,
            latency_p90_seconds REAL,
            latency_p95_seconds REAL,
            latency_p99_seconds REAL,
            latency_min_seconds REAL,
            latency_max_seconds REAL,
            latency_stddev_seconds REAL,
            action_counts_json TEXT NOT NULL,
            factors_json TEXT,
            notes TEXT
        );

        CREATE TABLE run_cohorts (
            run_id TEXT NOT NULL REFERENCES runs(run_id),
            cohort_id TEXT NOT NULL,
            model TEXT NOT NULL,
            resolved_model TEXT,
            provider TEXT,
            brain TEXT,
            reasoning_effort TEXT,
            cohort_max_workers INTEGER,
            agent_count INTEGER NOT NULL,
            agents_json TEXT NOT NULL,
            living_agents INTEGER,
            deaths INTEGER,
            execution REAL,
            competence REAL,
            entrepreneurship REAL,
            economic_productivity REAL,
            living_terminal_economic_value REAL,
            terminal_economic_value REAL,
            reasoning_tokens_per_decision REAL,
            reasoning_tokens_estimated INTEGER NOT NULL,
            calls INTEGER NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            cached_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            reasoning_tokens INTEGER NOT NULL,
            api_list_cost_usd REAL,
            latency_coverage_pct REAL,
            latency_mean_seconds REAL,
            latency_median_seconds REAL,
            latency_p90_seconds REAL,
            latency_p95_seconds REAL,
            latency_p99_seconds REAL,
            latency_min_seconds REAL,
            latency_max_seconds REAL,
            latency_stddev_seconds REAL,
            raw_metrics_json TEXT NOT NULL,
            scores_json TEXT NOT NULL,
            PRIMARY KEY (run_id, cohort_id)
        );

        CREATE TABLE benchmark_trials (
            run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
            benchmark_protocol TEXT,
            suite_id TEXT,
            scoring_revision INTEGER,
            source_fingerprint TEXT,
            certification TEXT NOT NULL CHECK(certification IN ('eligible_replication','diagnostic_only','controlled_variant')),
            included_in_model_result INTEGER NOT NULL DEFAULT 1,
            run_exclusion_reason TEXT,
            protocol_compliant INTEGER,
            source_fingerprint_compatible INTEGER
        );

        CREATE TABLE decisions (
            run_id TEXT NOT NULL REFERENCES runs(run_id),
            sequence_index INTEGER NOT NULL,
            tick INTEGER,
            agent_id TEXT,
            cohort_id TEXT,
            decision_time_unix REAL,
            duration_seconds REAL,
            provider TEXT,
            model TEXT,
            response_model TEXT,
            reasoning_effort TEXT,
            prompt_tokens INTEGER,
            cached_tokens INTEGER,
            completion_tokens INTEGER,
            reasoning_tokens INTEGER,
            cache_hit_pct REAL,
            request_payload_bytes INTEGER,
            api_list_cost_usd REAL,
            billing_mode TEXT,
            connector_profile TEXT,
            conversation_mode TEXT,
            conversation_turn INTEGER,
            conversation_resumed INTEGER,
            request_sha256 TEXT,
            static_prompt_sha256 TEXT,
            PRIMARY KEY (run_id, sequence_index)
        );

        CREATE TABLE tick_metrics (
            run_id TEXT NOT NULL REFERENCES runs(run_id),
            tick INTEGER NOT NULL,
            decision_count INTEGER NOT NULL,
            deciding_agent_count INTEGER NOT NULL,
            configured_agent_count INTEGER,
            effective_max_workers INTEGER,
            worker_batches INTEGER,
            latency_coverage_pct REAL,
            decision_latency_mean_seconds REAL,
            decision_latency_median_seconds REAL,
            decision_latency_p95_seconds REAL,
            decision_latency_max_seconds REAL,
            concurrent_wall_span_seconds REAL,
            concurrent_wall_span_per_deciding_agent_seconds REAL,
            concurrent_wall_span_per_configured_agent_seconds REAL,
            concurrent_wall_span_per_worker_batch_seconds REAL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            reasoning_tokens INTEGER NOT NULL,
            api_list_cost_usd REAL,
            PRIMARY KEY (run_id, tick)
        );

        CREATE TABLE model_results (
            model_key TEXT PRIMARY KEY REFERENCES models(model_key),
            rank INTEGER,
            run_count INTEGER NOT NULL,
            execution REAL NOT NULL,
            competence REAL NOT NULL,
            entrepreneurship REAL NOT NULL,
            economic_productivity REAL NOT NULL,
            execution_seed_range REAL,
            competence_seed_range REAL,
            entrepreneurship_seed_range REAL,
            reasoning_tokens_per_decision REAL,
            reasoning_tokens_estimated INTEGER NOT NULL,
            prompt_tokens_per_decision REAL,
            cached_tokens_per_decision REAL,
            completion_tokens_per_decision REAL,
            cache_hit_rate_pct REAL,
            api_list_cost_per_run_usd REAL,
            api_list_cost_total_usd REAL,
            api_list_cost_per_decision_usd REAL,
            latency_coverage_pct REAL,
            latency_mean_seconds REAL,
            latency_median_seconds REAL,
            latency_p90_seconds REAL,
            latency_p95_seconds REAL,
            latency_p99_seconds REAL,
            latency_max_seconds REAL,
            tick_wall_span_mean_seconds REAL,
            tick_wall_span_median_seconds REAL,
            tick_wall_span_p95_seconds REAL,
            tick_wall_per_deciding_agent_median_seconds REAL,
            tick_wall_per_deciding_agent_p95_seconds REAL,
            tick_wall_per_configured_agent_median_seconds REAL,
            tick_wall_per_configured_agent_p95_seconds REAL,
            tick_wall_per_worker_batch_median_seconds REAL,
            tick_wall_per_worker_batch_p95_seconds REAL,
            configured_agents_min INTEGER,
            configured_agents_max INTEGER,
            global_max_workers_min INTEGER,
            global_max_workers_max INTEGER,
            mean_run_wall_clock_seconds REAL,
            mean_usage_observed_span_seconds REAL,
            initial_agents INTEGER,
            living_agents INTEGER,
            deaths INTEGER,
            endpoint_health_pct REAL,
            living_terminal_economic_value REAL,
            initial_endowment_value REAL,
            net_living_value_created REAL,
            enterprise_supply_value REAL,
            net_goods_supply_value REAL,
            net_service_income REAL,
            informal_transfer_value REAL,
            own_capital_output_value REAL,
            completed_structures INTEGER,
            cooperative_builds INTEGER,
            access_grants INTEGER,
            trades_offered INTEGER,
            trades_accepted INTEGER,
            accepted_trade_value REAL,
            gifts INTEGER,
            gift_value REAL,
            communications INTEGER,
            invalid_action_rate_pct REAL,
            decision_failure_rate_pct REAL,
            degraded_runs INTEGER NOT NULL,
            raw_metrics_json TEXT NOT NULL,
            scores_json TEXT NOT NULL
        );

        CREATE VIEW leaderboard AS
        SELECT
            r.rank,
            m.label AS model,
            r.execution,
            r.competence,
            r.entrepreneurship,
            r.reasoning_tokens_per_decision,
            r.api_list_cost_per_run_usd,
            r.reasoning_tokens_estimated,
            m.controlled_variant
        FROM model_results r
        JOIN models m USING (model_key)
        WHERE m.leaderboard_eligible = 1
          AND EXISTS (
              SELECT 1
              FROM benchmark_trials bt
              JOIN run_cohorts rc ON rc.run_id = bt.run_id
              JOIN runs ru ON ru.run_id = bt.run_id
              WHERE rc.model = r.model_key
                AND bt.included_in_model_result = 1
          )
        ORDER BY r.rank;

        CREATE VIEW evidence AS
        SELECT
            ru.run_id,
            ru.kind,
            ru.experiment_id,
            ru.seed,
            (SELECT group_concat(model, ', ')
             FROM (SELECT DISTINCT model FROM run_cohorts c2
                   WHERE c2.run_id = ru.run_id ORDER BY model)) AS models,
            CASE WHEN count(rc.cohort_id) = 1 THEN max(rc.execution) END AS execution,
            CASE WHEN count(rc.cohort_id) = 1 THEN max(rc.competence) END AS competence,
            CASE WHEN count(rc.cohort_id) = 1 THEN max(rc.entrepreneurship) END AS entrepreneurship,
            sum(rc.api_list_cost_usd) AS api_list_cost_usd,
            ru.latency_median_seconds,
            bt.certification,
            bt.included_in_model_result,
            bt.run_exclusion_reason,
            ru.factors_json
        FROM runs ru
        JOIN run_cohorts rc USING (run_id)
        LEFT JOIN benchmark_trials bt USING (run_id)
        GROUP BY ru.run_id;

        CREATE VIEW model_capabilities AS
        SELECT m.*, r.*
        FROM models m
        JOIN model_results r USING (model_key);

        CREATE INDEX decisions_run_tick_idx ON decisions(run_id, tick);
        CREATE INDEX decisions_model_latency_idx ON decisions(model, duration_seconds);
        CREATE INDEX runs_kind_seed_idx ON runs(kind, seed);
        CREATE INDEX cohorts_model_idx ON run_cohorts(model);
        CREATE INDEX trials_included_idx ON benchmark_trials(included_in_model_result);
        """
    )


def _insert(connection: sqlite3.Connection, table: str, values: dict[str, Any]) -> None:
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)


def _run_record(
    repo_root: Path,
    model: dict[str, Any],
    run_spec: dict[str, Any],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any] | None,
    dict[str, Any],
]:
    report_path = repo_root / run_spec["report_path"]
    usage_path = repo_root / run_spec.get("usage_path", _related_path(report_path, "-usage.jsonl").relative_to(repo_root))
    manifest_path = repo_root / run_spec.get(
        "manifest_path", _related_path(report_path, "-manifest.json").relative_to(repo_root)
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    usage = [
        _normalize_loaded_usage_record(json.loads(line))
        for line in usage_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    benchmark_cohorts = _benchmark_cohorts(report)
    population_cohorts = _path_get(report, "population", "cohorts", default={}) or {}
    if not isinstance(population_cohorts, dict):
        population_cohorts = {}
    manifest_groups = {
        str(group.get("id")): group
        for group in (_path_get(manifest, "population", "groups", default=[]) or [])
        if isinstance(group, dict) and group.get("id") is not None
    }
    assignments = (
        _path_get(report, "population", "assignments", default={})
        or _path_get(manifest, "population", "assignments", default={})
        or {}
    )
    cohort_ids = sorted(set(benchmark_cohorts) | set(population_cohorts) | set(manifest_groups))
    if not cohort_ids:
        cohort_ids = ["cohort-1"]
    primary = benchmark_cohorts.get(cohort_ids[0], {})
    raw = primary.get("raw") or {}
    scores = primary.get("scores") or {}
    reliability = report.get("reliability") or {}
    economy = report.get("economy") or {}
    structures = report.get("structures") or {}
    construction = economy.get("construction") or {}
    institutions = economy.get("institutions") or {}
    trade = economy.get("trades") or {}
    durations = [row.get("duration_seconds") for row in usage]
    latency = _latency_summary(durations)
    cost = summarize_usd_cost(usage)
    cost_total = (
        _path_get(cost, "cost_usd", "total") if isinstance(cost, dict) and cost.get("available") else None
    )
    completed_structures = structures.get("complete") or {}
    in_progress_structures = structures.get("in_progress") or {}
    started = manifest.get("started_at_utc")
    ended = manifest.get("ended_at_utc")
    run_id = str(run_spec.get("run_id") or f"{model['model_key']}:seed-{run_spec['seed']}")
    calls = len(usage)
    usage_starts = [
        float(row["time"]) - float(row["duration_seconds"])
        for row in usage
        if row.get("time") is not None and row.get("duration_seconds") is not None
    ]
    usage_ends = [float(row["time"]) for row in usage if row.get("time") is not None]
    latency_coverage = 100.0 * int(latency["samples"] or 0) / calls if calls else 0.0
    report_usage = report.get("usage") or {}
    provider_failures = int(reliability.get("llm_provider_failure_events") or 0)
    config = manifest.get("config") or report.get("config") or {}
    kind = str(run_spec.get("kind") or model.get("kind") or "benchmark_trial")
    run_record = {
            "run_id": run_id,
            "kind": kind,
            "experiment_id": run_spec.get("experiment_id") or model.get("experiment_id"),
            "seed": int(run_spec["seed"]),
            "width": config.get("width"),
            "height": config.get("height"),
            "preset": manifest.get("preset"),
            "economy_mode": config.get("economy_mode"),
            "geography_mode": config.get("geography_mode"),
            "specialization_mode": config.get("specialization_mode"),
            "world_variant": config.get("world_variant"),
            "source_report": str(report_path.relative_to(repo_root)),
            "source_usage": str(usage_path.relative_to(repo_root)),
            "source_manifest": str(manifest_path.relative_to(repo_root)) if manifest_path.exists() else None,
            "report_sha256": _sha256(report_path),
            "usage_sha256": _sha256(usage_path),
            "manifest_sha256": _sha256(manifest_path) if manifest_path.exists() else None,
            "launch_commit": _path_get(manifest, "provenance", "git_sha_at_launch")
            or _path_get(manifest, "provenance", "git_sha"),
            "connector_profile": _path_get(manifest, "agent_boundary", "connector_profile")
            or _path_get(report, "population", "connector_profile"),
            "conversation_mode": _path_get(manifest, "agent_boundary", "conversation_mode"),
            "global_max_workers": _path_get(manifest, "concurrency", "global"),
            "started_at_utc": started,
            "ended_at_utc": ended,
            "wall_clock_seconds": _iso_duration_seconds(started, ended),
            "usage_observed_span_seconds": max(usage_ends) - min(usage_starts)
            if usage_starts and usage_ends
            else None,
            "completed": int(bool(_path_get(report, "run", "completed", default=False))),
            "final_tick": _path_get(report, "run", "final_tick"),
            "target_ticks": _path_get(report, "run", "target_ticks"),
            "integrity_status": reliability.get("benchmark_integrity_status"),
            "quality_status": reliability.get("quality_status"),
            "quality_flags_json": _json(reliability.get("quality_flags") or []),
            "usage_coverage_pct": reliability.get("usage_record_coverage_pct"),
            "configured_agents": _path_get(manifest, "population", "total_agents")
            or raw.get("initial_agents"),
            "initial_agents": raw.get("initial_agents"),
            "living_agents": raw.get("living_agents"),
            "deaths": _path_get(report, "survival", "dead"),
            "endpoint_health_points": raw.get("endpoint_health_points"),
            "endpoint_health_capacity": raw.get("endpoint_health_capacity"),
            "living_terminal_economic_value": raw.get("living_terminal_economic_value"),
            "terminal_economic_value": raw.get("terminal_economic_value"),
            "initial_endowment_value": raw.get("initial_endowment_value"),
            "enterprise_supply_value": raw.get("enterprise_supply_value"),
            "net_goods_supply_value": _path_get(raw, "enterprise_supply_by_source", "net_goods_supplied_to_others", default=0),
            "net_service_income": _path_get(raw, "enterprise_supply_by_source", "net_service_income", default=0),
            "informal_transfer_value": raw.get("informal_transfer_value"),
            "own_capital_output_value": raw.get("own_capital_output_value"),
            "completed_structures": _sum_counts(completed_structures),
            "completed_structures_json": _json(completed_structures),
            "in_progress_structures": _sum_counts(in_progress_structures),
            "cooperative_builds": len(structures.get("coop_builds") or []),
            "groups_created": _path_get(primary, "diagnostics", "groups_created", default=0),
            "access_grants": economy.get("access_grants") or 0,
            "trades_offered": trade.get("offered") or 0,
            "trades_accepted": trade.get("accepted") or 0,
            "trade_conversion_pct": trade.get("conversion_rate_pct"),
            "accepted_trade_value": trade.get("accepted_value") or 0,
            "gifts": economy.get("gifts") or 0,
            "gift_quantity": economy.get("gift_quantity") or 0,
            "gift_value": economy.get("gift_value") or 0,
            "contracts_fulfilled": _path_get(institutions, "contracts", "fulfilled", default=0),
            "contracts_defaulted": _path_get(institutions, "contracts", "defaulted", default=0),
            "access_fee_value": _path_get(institutions, "access_fees", "value", default=0),
            "dividend_value": _path_get(institutions, "dividends", "value", default=0),
            "communications": _path_get(primary, "diagnostics", "communications", default=0),
            "construction_contributions": _path_get(construction, "contributions", "events", default=0),
            "decision_attempts": reliability.get("decision_attempts"),
            "decision_failure_rate_pct": reliability.get("decision_failure_rate_pct"),
            "invalid_action_rate_pct": reliability.get("invalid_action_rate_pct"),
            "contention_failure_rate_pct": reliability.get("contention_failure_rate_pct"),
            "model_output_failures": reliability.get("model_output_failure_events") or 0,
            "provider_failures": provider_failures,
            "quota_failures": reliability.get("llm_quota_failure_events") or 0,
            "harness_failures": reliability.get("harness_failure_events") or 0,
            "calls": calls,
            "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in usage),
            "cached_tokens": sum(int(row.get("cached_tokens") or 0) for row in usage),
            "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in usage),
            "reasoning_tokens": sum(int(row.get("reasoning_tokens") or 0) for row in usage),
            "cache_hit_rate_pct": report_usage.get("cache_hit_rate_pct"),
            "api_list_cost_usd": cost_total,
            "latency_coverage_pct": latency_coverage,
            "latency_mean_seconds": latency["mean"],
            "latency_median_seconds": latency["median"],
            "latency_p90_seconds": latency["p90"],
            "latency_p95_seconds": latency["p95"],
            "latency_p99_seconds": latency["p99"],
            "latency_min_seconds": latency["min"],
            "latency_max_seconds": latency["max"],
            "latency_stddev_seconds": latency["stddev"],
            "action_counts_json": _json(_path_get(report, "actions", "counts", default={}) or {}),
            "factors_json": _json(run_spec["factors"]) if run_spec.get("factors") is not None else None,
            "notes": run_spec.get("notes"),
        }

    cohort_records: list[dict[str, Any]] = []
    reasoning_estimated = int(bool(report_usage.get("reasoning_tokens_estimated")))
    for cohort_id in cohort_ids:
        benchmark_cohort = benchmark_cohorts.get(cohort_id) or {}
        population_cohort = population_cohorts.get(cohort_id) or {}
        group = manifest_groups.get(cohort_id) or {}
        agents = list(benchmark_cohort.get("agents") or population_cohort.get("agents") or [])
        if not agents:
            agents = sorted(str(agent) for agent, assigned in assignments.items() if assigned == cohort_id)
        cohort_usage = [row for row in usage if row.get("agent_id") in set(agents)] if agents else list(usage)
        cohort_latency = _latency_summary(row.get("duration_seconds") for row in cohort_usage)
        cohort_cost = summarize_usd_cost(cohort_usage)
        cohort_cost_total = (
            _path_get(cohort_cost, "cost_usd", "total")
            if isinstance(cohort_cost, dict) and cohort_cost.get("available")
            else None
        )
        response_models = sorted(
            {str(row["response_model"]) for row in cohort_usage if row.get("response_model")}
        )
        declared_model = (
            benchmark_cohort.get("model")
            or population_cohort.get("model")
            or group.get("model")
            or model.get("model_id")
            or model["model_key"]
        )
        model_key = model["model_key"] if model.get("catalog_model", True) else str(declared_model)
        cohort_raw = benchmark_cohort.get("raw") or {}
        cohort_scores = benchmark_cohort.get("scores") or {}
        cohort_calls = len(cohort_usage)
        living = population_cohort.get("living", cohort_raw.get("living_agents"))
        initial = population_cohort.get("initial_agents", cohort_raw.get("initial_agents"))
        deaths = population_cohort.get("dead")
        if deaths is None and initial is not None and living is not None:
            deaths = int(initial) - int(living)
        cohort_records.append(
            {
                "run_id": run_id,
                "cohort_id": cohort_id,
                "model": model_key,
                "resolved_model": response_models[0] if len(response_models) == 1 else declared_model,
                "provider": benchmark_cohort.get("provider") or population_cohort.get("provider") or group.get("provider"),
                "brain": benchmark_cohort.get("brain") or population_cohort.get("brain") or group.get("type"),
                "reasoning_effort": benchmark_cohort.get("reasoning_effort") or population_cohort.get("reasoning_effort") or group.get("reasoning_effort"),
                "cohort_max_workers": group.get("max_workers"),
                "agent_count": len(agents) or int(group.get("count") or initial or 0),
                "agents_json": _json(agents),
                "living_agents": living,
                "deaths": deaths,
                "execution": _score(benchmark_cohort, "effective_execution"),
                "competence": _score(benchmark_cohort, "sustained_competence"),
                "entrepreneurship": _score(benchmark_cohort, "entrepreneurial_agency"),
                "economic_productivity": _score(benchmark_cohort, "economic_productivity"),
                "living_terminal_economic_value": cohort_raw.get("living_terminal_economic_value"),
                "terminal_economic_value": cohort_raw.get("terminal_economic_value"),
                "reasoning_tokens_per_decision": sum(int(row.get("reasoning_tokens") or 0) for row in cohort_usage) / cohort_calls if cohort_calls else None,
                "reasoning_tokens_estimated": reasoning_estimated,
                "calls": cohort_calls,
                "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in cohort_usage),
                "cached_tokens": sum(int(row.get("cached_tokens") or 0) for row in cohort_usage),
                "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in cohort_usage),
                "reasoning_tokens": sum(int(row.get("reasoning_tokens") or 0) for row in cohort_usage),
                "api_list_cost_usd": cohort_cost_total,
                "latency_coverage_pct": 100.0 * int(cohort_latency["samples"] or 0) / cohort_calls if cohort_calls else 0.0,
                "latency_mean_seconds": cohort_latency["mean"],
                "latency_median_seconds": cohort_latency["median"],
                "latency_p90_seconds": cohort_latency["p90"],
                "latency_p95_seconds": cohort_latency["p95"],
                "latency_p99_seconds": cohort_latency["p99"],
                "latency_min_seconds": cohort_latency["min"],
                "latency_max_seconds": cohort_latency["max"],
                "latency_stddev_seconds": cohort_latency["stddev"],
                "raw_metrics_json": _json(cohort_raw or population_cohort),
                "scores_json": _json(cohort_scores),
            }
        )

    trial = _path_get(report, "benchmarks", "trial", default={}) or {}
    benchmark_record = None
    if kind != "experiment":
        certification = run_spec.get("certification")
        if certification is None:
            certification = "controlled_variant" if kind == "controlled_variant" else (
                "diagnostic_only" if kind == "diagnostic" else "eligible_replication"
            )
        benchmark_record = {
            "run_id": run_id,
            "benchmark_protocol": trial.get("declared_protocol"),
            "suite_id": _path_get(report, "benchmarks", "suite_id") or model.get("suite"),
            "scoring_revision": _path_get(report, "benchmarks", "protocol", "scoring_revision") or model.get("scoring_revision"),
            "source_fingerprint": trial.get("code_fingerprint_sha256"),
            "certification": certification,
            "included_in_model_result": int(run_spec.get("included_in_model_result", True)),
            "run_exclusion_reason": run_spec.get("run_exclusion_reason"),
            "protocol_compliant": int(bool(trial.get("protocol_compliant"))) if "protocol_compliant" in trial else None,
            "source_fingerprint_compatible": int(bool(trial.get("source_fingerprint_compatible"))) if "source_fingerprint_compatible" in trial else None,
        }

    aggregate_record = dict(run_record)
    aggregate_record.update(
        {
            "model_key": model["model_key"],
            "included_in_model_result": int(run_spec.get("included_in_model_result", True)),
            "run_exclusion_reason": run_spec.get("run_exclusion_reason"),
            "resolved_model": cohort_records[0]["resolved_model"],
            "provider": cohort_records[0]["provider"],
            "brain": cohort_records[0]["brain"],
            "reasoning_effort": cohort_records[0]["reasoning_effort"],
            "reasoning_tokens_estimated": reasoning_estimated,
            "benchmark_protocol": trial.get("declared_protocol"),
            "source_fingerprint": trial.get("code_fingerprint_sha256"),
            "cohort_max_workers": cohort_records[0]["cohort_max_workers"],
            "execution": cohort_records[0]["execution"],
            "competence": cohort_records[0]["competence"],
            "entrepreneurship": cohort_records[0]["entrepreneurship"],
            "economic_productivity": cohort_records[0]["economic_productivity"],
            "raw_metrics_json": _json(raw),
            "scores_json": _json(scores),
        }
    )
    return run_record, cohort_records, usage, benchmark_record, aggregate_record


def _decision_record(
    run_id: str,
    index: int,
    usage: dict[str, Any],
    agent_to_cohort: dict[str, str] | None = None,
) -> dict[str, Any]:
    prompt = int(usage.get("prompt_tokens") or 0)
    cached = int(usage.get("cached_tokens") or 0)
    cost = summarize_usd_cost([usage])
    return {
        "run_id": run_id,
        "sequence_index": index,
        "tick": usage.get("tick"),
        "agent_id": usage.get("agent_id"),
        "cohort_id": (agent_to_cohort or {}).get(str(usage.get("agent_id"))),
        "decision_time_unix": usage.get("time"),
        "duration_seconds": usage.get("duration_seconds"),
        "provider": usage.get("provider"),
        "model": usage.get("model"),
        "response_model": usage.get("response_model"),
        "reasoning_effort": usage.get("reasoning_effort"),
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "reasoning_tokens": int(usage.get("reasoning_tokens") or 0),
        "cache_hit_pct": 100.0 * cached / prompt if prompt else 0.0,
        "request_payload_bytes": usage.get("request_payload_bytes"),
        "api_list_cost_usd": (
            _path_get(cost, "cost_usd", "total") if isinstance(cost, dict) and cost.get("available") else None
        ),
        "billing_mode": usage.get("billing_mode"),
        "connector_profile": usage.get("connector_profile"),
        "conversation_mode": usage.get("conversation_mode"),
        "conversation_turn": usage.get("conversation_turn"),
        "conversation_resumed": int(bool(usage.get("conversation_resumed"))),
        "request_sha256": usage.get("request_sha256"),
        "static_prompt_sha256": usage.get("static_prompt_sha256"),
    }


def _insert_tick_metrics(
    connection: sqlite3.Connection,
    run_record: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> None:
    run_id = run_record["run_id"]
    by_tick: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        if decision.get("tick") is not None:
            by_tick[int(decision["tick"])].append(decision)
    for tick, rows in sorted(by_tick.items()):
        durations = [row.get("duration_seconds") for row in rows]
        latency = _latency_summary(durations)
        starts = [
            float(row["decision_time_unix"]) - float(row["duration_seconds"])
            for row in rows
            if row.get("decision_time_unix") is not None and row.get("duration_seconds") is not None
        ]
        ends = [
            float(row["decision_time_unix"])
            for row in rows
            if row.get("decision_time_unix") is not None and row.get("duration_seconds") is not None
        ]
        costs = [row.get("api_list_cost_usd") for row in rows]
        deciding_agent_ids = {
            str(row["agent_id"]) for row in rows if row.get("agent_id") is not None
        }
        deciding_agents = len(deciding_agent_ids) or len(rows)
        configured_agents = run_record.get("configured_agents")
        max_workers = run_record.get("global_max_workers") or run_record.get("cohort_max_workers")
        worker_batches = (
            math.ceil(deciding_agents / int(max_workers))
            if deciding_agents and max_workers and int(max_workers) > 0
            else None
        )
        concurrent_wall_span = max(ends) - min(starts) if starts and ends else None
        _insert(
            connection,
            "tick_metrics",
            {
                "run_id": run_id,
                "tick": tick,
                "decision_count": len(rows),
                "deciding_agent_count": deciding_agents,
                "configured_agent_count": configured_agents,
                "effective_max_workers": max_workers,
                "worker_batches": worker_batches,
                "latency_coverage_pct": 100.0 * int(latency["samples"] or 0) / len(rows),
                "decision_latency_mean_seconds": latency["mean"],
                "decision_latency_median_seconds": latency["median"],
                "decision_latency_p95_seconds": latency["p95"],
                "decision_latency_max_seconds": latency["max"],
                "concurrent_wall_span_seconds": concurrent_wall_span,
                "concurrent_wall_span_per_deciding_agent_seconds": concurrent_wall_span / deciding_agents
                if concurrent_wall_span is not None and deciding_agents
                else None,
                "concurrent_wall_span_per_configured_agent_seconds": concurrent_wall_span
                / int(configured_agents)
                if concurrent_wall_span is not None and configured_agents
                else None,
                "concurrent_wall_span_per_worker_batch_seconds": concurrent_wall_span / worker_batches
                if concurrent_wall_span is not None and worker_batches
                else None,
                "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in rows),
                "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in rows),
                "reasoning_tokens": sum(int(row.get("reasoning_tokens") or 0) for row in rows),
                "api_list_cost_usd": sum(float(value) for value in costs if value is not None)
                if costs and all(value is not None for value in costs)
                else None,
            },
        )


def _insert_model_results(
    connection: sqlite3.Connection,
    models: list[dict[str, Any]],
    run_records: dict[str, list[dict[str, Any]]],
    run_decisions: dict[str, list[dict[str, Any]]],
) -> None:
    pending: list[dict[str, Any]] = []
    for model in models:
        records = [
            record
            for record in run_records[model["model_key"]]
            if connection.execute(
                "SELECT included_in_model_result FROM benchmark_trials WHERE run_id = ?",
                (record["run_id"],),
            ).fetchone()[0]
        ]
        if not records:
            continue
        raw: dict[str, Any] = {}
        for record in records:
            _merge_numeric_tree(raw, json.loads(record["raw_metrics_json"]))
        scores = score_benchmark_counts(raw)
        decisions = [decision for record in records for decision in run_decisions[record["run_id"]]]
        latency = _latency_summary(decision.get("duration_seconds") for decision in decisions)
        calls = sum(record["calls"] for record in records)
        reasoning = sum(record["reasoning_tokens"] for record in records)
        prompt = sum(record["prompt_tokens"] for record in records)
        cached = sum(record["cached_tokens"] for record in records)
        completion = sum(record["completion_tokens"] for record in records)
        costs = [record["api_list_cost_usd"] for record in records]
        wall = [record["wall_clock_seconds"] for record in records if record["wall_clock_seconds"] is not None]
        observed_spans = [
            record["usage_observed_span_seconds"]
            for record in records
            if record["usage_observed_span_seconds"] is not None
        ]
        submitted = sum(int(json.loads(record["raw_metrics_json"]).get("submitted_actions") or 0) for record in records)
        invalid = sum(int(json.loads(record["raw_metrics_json"]).get("invalid_proposals") or 0) for record in records)
        decisions_total = sum(int(record["decision_attempts"] or 0) for record in records)
        decision_failures = sum(
            int(json.loads(record["raw_metrics_json"]).get("decision_failures") or 0) for record in records
        )
        endpoint_points = sum(float(record["endpoint_health_points"] or 0) for record in records)
        endpoint_capacity = sum(float(record["endpoint_health_capacity"] or 0) for record in records)
        run_ids = [record["run_id"] for record in records]
        placeholders = ",".join("?" for _ in run_ids)
        tick_rows = connection.execute(
            f"SELECT concurrent_wall_span_seconds, "
            f"concurrent_wall_span_per_deciding_agent_seconds, "
            f"concurrent_wall_span_per_configured_agent_seconds, "
            f"concurrent_wall_span_per_worker_batch_seconds "
            f"FROM tick_metrics "
            f"WHERE run_id IN ({placeholders}) AND concurrent_wall_span_seconds IS NOT NULL",
            run_ids,
        ).fetchall()
        tick_spans = [float(row[0]) for row in tick_rows]
        tick_per_deciding_agent = [float(row[1]) for row in tick_rows if row[1] is not None]
        tick_per_configured_agent = [float(row[2]) for row in tick_rows if row[2] is not None]
        tick_per_worker_batch = [float(row[3]) for row in tick_rows if row[3] is not None]
        tick_latency = _latency_summary(tick_spans)
        tick_deciding_agent_latency = _latency_summary(tick_per_deciding_agent)
        tick_configured_agent_latency = _latency_summary(tick_per_configured_agent)
        tick_worker_batch_latency = _latency_summary(tick_per_worker_batch)
        configured_agent_counts = [
            int(record["configured_agents"])
            for record in records
            if record["configured_agents"]
        ]
        global_worker_counts = [
            int(record["global_max_workers"])
            for record in records
            if record["global_max_workers"]
        ]
        execution_scores = [float(record["execution"]) for record in records]
        competence_scores = [float(record["competence"]) for record in records]
        entrepreneurship_scores = [float(record["entrepreneurship"]) for record in records]
        pending.append(
            {
                "model_key": model["model_key"],
                "rank": 0,
                "run_count": len(records),
                "execution": scores["effective_execution"]["score"],
                "competence": scores["sustained_competence"]["score"],
                "entrepreneurship": scores["entrepreneurial_agency"]["score"],
                "economic_productivity": scores["economic_productivity"]["score"],
                "execution_seed_range": max(execution_scores) - min(execution_scores),
                "competence_seed_range": max(competence_scores) - min(competence_scores),
                "entrepreneurship_seed_range": max(entrepreneurship_scores) - min(entrepreneurship_scores),
                "reasoning_tokens_per_decision": reasoning / calls if calls else None,
                "reasoning_tokens_estimated": int(any(record["reasoning_tokens_estimated"] for record in records)),
                "prompt_tokens_per_decision": prompt / calls if calls else None,
                "cached_tokens_per_decision": cached / calls if calls else None,
                "completion_tokens_per_decision": completion / calls if calls else None,
                "cache_hit_rate_pct": 100.0 * cached / prompt if prompt else None,
                "api_list_cost_per_run_usd": sum(float(value) for value in costs) / len(costs)
                if costs and all(value is not None for value in costs)
                else None,
                "api_list_cost_total_usd": sum(float(value) for value in costs)
                if costs and all(value is not None for value in costs)
                else None,
                "api_list_cost_per_decision_usd": sum(float(value) for value in costs) / calls
                if costs and all(value is not None for value in costs) and calls
                else None,
                "latency_coverage_pct": 100.0 * int(latency["samples"] or 0) / len(decisions) if decisions else 0.0,
                "latency_mean_seconds": latency["mean"],
                "latency_median_seconds": latency["median"],
                "latency_p90_seconds": latency["p90"],
                "latency_p95_seconds": latency["p95"],
                "latency_p99_seconds": latency["p99"],
                "latency_max_seconds": latency["max"],
                "tick_wall_span_mean_seconds": tick_latency["mean"],
                "tick_wall_span_median_seconds": tick_latency["median"],
                "tick_wall_span_p95_seconds": tick_latency["p95"],
                "tick_wall_per_deciding_agent_median_seconds": tick_deciding_agent_latency["median"],
                "tick_wall_per_deciding_agent_p95_seconds": tick_deciding_agent_latency["p95"],
                "tick_wall_per_configured_agent_median_seconds": tick_configured_agent_latency["median"],
                "tick_wall_per_configured_agent_p95_seconds": tick_configured_agent_latency["p95"],
                "tick_wall_per_worker_batch_median_seconds": tick_worker_batch_latency["median"],
                "tick_wall_per_worker_batch_p95_seconds": tick_worker_batch_latency["p95"],
                "configured_agents_min": min(configured_agent_counts) if configured_agent_counts else None,
                "configured_agents_max": max(configured_agent_counts) if configured_agent_counts else None,
                "global_max_workers_min": min(global_worker_counts) if global_worker_counts else None,
                "global_max_workers_max": max(global_worker_counts) if global_worker_counts else None,
                "mean_run_wall_clock_seconds": statistics.fmean(wall) if wall else None,
                "mean_usage_observed_span_seconds": statistics.fmean(observed_spans)
                if observed_spans
                else None,
                "initial_agents": raw.get("initial_agents"),
                "living_agents": raw.get("living_agents"),
                "deaths": sum(int(record["deaths"] or 0) for record in records),
                "endpoint_health_pct": 100.0 * endpoint_points / endpoint_capacity if endpoint_capacity else None,
                "living_terminal_economic_value": raw.get("living_terminal_economic_value"),
                "initial_endowment_value": raw.get("initial_endowment_value"),
                "net_living_value_created": float(raw.get("living_terminal_economic_value") or 0)
                - float(raw.get("initial_endowment_value") or 0),
                "enterprise_supply_value": raw.get("enterprise_supply_value"),
                "net_goods_supply_value": _path_get(
                    raw, "enterprise_supply_by_source", "net_goods_supplied_to_others", default=0
                ),
                "net_service_income": _path_get(
                    raw, "enterprise_supply_by_source", "net_service_income", default=0
                ),
                "informal_transfer_value": raw.get("informal_transfer_value"),
                "own_capital_output_value": raw.get("own_capital_output_value"),
                "completed_structures": sum(int(record["completed_structures"] or 0) for record in records),
                "cooperative_builds": sum(int(record["cooperative_builds"] or 0) for record in records),
                "access_grants": sum(int(record["access_grants"] or 0) for record in records),
                "trades_offered": sum(int(record["trades_offered"] or 0) for record in records),
                "trades_accepted": sum(int(record["trades_accepted"] or 0) for record in records),
                "accepted_trade_value": sum(float(record["accepted_trade_value"] or 0) for record in records),
                "gifts": sum(int(record["gifts"] or 0) for record in records),
                "gift_value": sum(float(record["gift_value"] or 0) for record in records),
                "communications": sum(int(record["communications"] or 0) for record in records),
                "invalid_action_rate_pct": 100.0 * invalid / submitted if submitted else None,
                "decision_failure_rate_pct": 100.0 * decision_failures / decisions_total if decisions_total else None,
                "degraded_runs": sum(record["quality_status"] != "clean" for record in records),
                "raw_metrics_json": _json(raw),
                "scores_json": _json(scores),
            }
        )
    eligible = {model["model_key"] for model in models if model.get("leaderboard_eligible", True)}
    ranked = sorted(
        (row for row in pending if row["model_key"] in eligible),
        key=lambda row: (-float(row["competence"]), -float(row["execution"]), row["model_key"]),
    )
    ranks = {row["model_key"]: rank for rank, row in enumerate(ranked, start=1)}
    for result in pending:
        result["rank"] = ranks.get(result["model_key"])
        _insert(connection, "model_results", result)


def build_database(catalog_path: Path, output_path: Path, repo_root: Path | None = None) -> None:
    repo_root = (repo_root or Path.cwd()).resolve()
    catalog_path = (catalog_path if catalog_path.is_absolute() else repo_root / catalog_path).resolve()
    output_path = (output_path if output_path.is_absolute() else repo_root / output_path).resolve()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if int(catalog.get("schema_version") or 0) != 2:
        raise ValueError("Unsupported run source catalog schema")
    models = catalog.get("models") or []
    experiments = catalog.get("experiments") or []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=output_path.name + ".", dir=output_path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary_path)
        connection.row_factory = sqlite3.Row
        _create_schema(connection)
        metadata = {
            "schema_version": str(SCHEMA_VERSION),
            "catalog_path": str(catalog_path.relative_to(repo_root)),
            "catalog_sha256": _sha256(catalog_path),
            "builder_sha256": _sha256(Path(__file__)),
            "updated_at_utc": str(catalog.get("updated_at_utc") or ""),
            "usd_rate_card_effective_date": USD_RATE_CARD_EFFECTIVE_DATE,
            "usd_rate_card_sources": _json(USD_RATE_CARD_SOURCES),
            "purpose": "Universal simulation-run evidence with benchmarking as a certification layer.",
            "latency_semantics": "duration_seconds is end-to-end provider decision latency including adapter retries; tick concurrent_wall_span_seconds approximates user-visible world-turn latency.",
        }
        for key, value in metadata.items():
            connection.execute("INSERT INTO database_metadata(key, value) VALUES (?, ?)", (key, value))
        run_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
        run_decisions: dict[str, list[dict[str, Any]]] = {}
        for experiment in experiments:
            _insert(
                connection,
                "experiments",
                {
                    "experiment_id": experiment["experiment_id"],
                    "title": experiment["title"],
                    "question": experiment["question"],
                    "design_json": _json(experiment.get("design") or {}),
                    "started_at": experiment.get("started_at"),
                    "status": experiment.get("status") or "in_progress",
                    "notes": experiment.get("notes"),
                },
            )
        for model in models:
            model["catalog_model"] = True
            _insert(
                connection,
                "models",
                {
                    "model_key": model["model_key"],
                    "label": model["label"],
                    "suite": model.get("suite") or catalog.get("suite") or "",
                    "scoring_revision": model.get("scoring_revision", catalog.get("scoring_revision")),
                    "controlled_variant": int(bool(model.get("controlled_variant"))),
                    "variant_note": model.get("variant_note"),
                    "leaderboard_eligible": int(model.get("leaderboard_eligible", True)),
                    "leaderboard_exclusion_reason": model.get("leaderboard_exclusion_reason"),
                },
            )
            for run_spec in model.get("runs") or []:
                if "kind" not in run_spec:
                    if model.get("controlled_variant"):
                        run_spec["kind"] = "controlled_variant"
                    elif not model.get("leaderboard_eligible", True):
                        run_spec["kind"] = "diagnostic"
                    else:
                        run_spec["kind"] = "benchmark_trial"
                record, cohorts, usage, trial, aggregate = _run_record(repo_root, model, run_spec)
                _insert(connection, "runs", record)
                for cohort in cohorts:
                    _insert(connection, "run_cohorts", cohort)
                if trial is not None:
                    _insert(connection, "benchmark_trials", trial)
                agent_to_cohort = {
                    str(agent): cohort["cohort_id"]
                    for cohort in cohorts
                    for agent in json.loads(cohort["agents_json"])
                }
                decisions = [
                    _decision_record(record["run_id"], index, row, agent_to_cohort)
                    for index, row in enumerate(usage)
                ]
                for decision in decisions:
                    _insert(connection, "decisions", decision)
                _insert_tick_metrics(connection, record, decisions)
                run_records[model["model_key"]].append(aggregate)
                run_decisions[record["run_id"]] = decisions
        for experiment in experiments:
            for run_spec in experiment.get("runs") or []:
                run_spec = dict(run_spec)
                run_spec["kind"] = "experiment"
                run_spec["experiment_id"] = experiment["experiment_id"]
                source = {
                    "model_key": run_spec.get("run_id") or experiment["experiment_id"],
                    "catalog_model": False,
                    "experiment_id": experiment["experiment_id"],
                }
                record, cohorts, usage, trial, _aggregate = _run_record(repo_root, source, run_spec)
                _insert(connection, "runs", record)
                for cohort in cohorts:
                    _insert(connection, "run_cohorts", cohort)
                agent_to_cohort = {
                    str(agent): cohort["cohort_id"]
                    for cohort in cohorts
                    for agent in json.loads(cohort["agents_json"])
                }
                decisions = [
                    _decision_record(record["run_id"], index, row, agent_to_cohort)
                    for index, row in enumerate(usage)
                ]
                for decision in decisions:
                    _insert(connection, "decisions", decision)
                _insert_tick_metrics(connection, record, decisions)
        _insert_model_results(connection, models, run_records, run_decisions)
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError(f"SQLite foreign-key check failed: {foreign_key_errors}")
        connection.execute("VACUUM")
        connection.close()
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def leaderboard_rows(database_path: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute("SELECT * FROM leaderboard ORDER BY rank").fetchall()
    finally:
        connection.close()


def format_leaderboard(database_path: Path) -> str:
    lines = [
        "| Rank | Model | Execution | Competence | Entrepreneurship | Reasoning/decision | Cost/run |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    rows = leaderboard_rows(database_path)
    variant_ranks = [int(row["rank"]) for row in rows if row["controlled_variant"]]
    analytical_boundary = min(variant_ranks) if variant_ranks else None
    for row in rows:
        analytical = analytical_boundary is not None and int(row["rank"]) >= analytical_boundary
        rank = f"{row['rank']}†" if analytical else str(row["rank"])
        reasoning = row["reasoning_tokens_per_decision"]
        reasoning_prefix = "~" if row["reasoning_tokens_estimated"] else ""
        cost = row["api_list_cost_per_run_usd"]
        lines.append(
            f"| {rank} | {row['model']} | {_display_number(row['execution'], 1)} | "
            f"{_display_number(row['competence'], 1)} | "
            f"{_display_number(row['entrepreneurship'], 1)} | "
            f"{reasoning_prefix}{_display_number(reasoning, 0)} tok | "
            f"{'unavailable' if cost is None else f'${cost:.2f}'} |"
        )
    return "\n".join(lines) + "\n"


def verify_database(database_path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database_path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        models = connection.execute("SELECT COUNT(*) FROM model_results").fetchone()[0]
        runs = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        decisions = connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        ticks = connection.execute("SELECT COUNT(*) FROM tick_metrics").fetchone()[0]
        latency = connection.execute(
            "SELECT COUNT(duration_seconds), COUNT(*) FROM decisions"
        ).fetchone()
        return {
            "integrity": integrity,
            "foreign_key_errors": len(foreign_key_errors),
            "models": models,
            "runs": runs,
            "decisions": decisions,
            "ticks": ticks,
            "latency_coverage_pct": 100.0 * latency[0] / latency[1] if latency[1] else 0.0,
        }
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build the SQLite database from the source catalog")
    build.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    build.add_argument("--out", type=Path, default=DEFAULT_DATABASE)
    show = subparsers.add_parser("leaderboard", help="Print the compact leaderboard projection")
    show.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    verify = subparsers.add_parser("verify", help="Run integrity and coverage checks")
    verify.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args(argv)
    if args.command == "build":
        build_database(args.catalog, args.out)
        print(json.dumps(verify_database(args.out), indent=2, sort_keys=True))
    elif args.command == "leaderboard":
        print(format_leaderboard(args.db), end="")
    else:
        print(json.dumps(verify_database(args.db), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
