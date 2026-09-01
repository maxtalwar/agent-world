"""Reproducible factorial experiments for Agent World.

The experiment runner deliberately defaults to the local ``SurvivalBrain``. An
LLM is only contacted when the caller explicitly selects ``brain="openrouter"``,
``brain="codex"``, ``brain="claude"``, ``brain="cursor"``, or
``brain="devin"``, ``brain="grok"``, or ``brain="zcode"``.
Every cell gets its own directory, usage log, provenance manifest, report, and
raw outputs so interrupted or mixed-provider batches remain auditable.
"""

from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from agent_world.brain_factory import BrainSpec, create_brains
from agent_world.brain_runtime import BrainRuntime
from agent_world.claude_brain import ClaudeBrain, build_claude_prompts
from agent_world.codex_brain import CodexBrain, build_codex_prompt, summarize_plan_usage
from agent_world.cursor_brain import CursorBrain, build_cursor_prompt
from agent_world.interface import build_dynamic_observation, build_observation, build_static_context
from agent_world.io import atomic_write_json as _atomic_write_json
from agent_world.io import atomic_write_text as _atomic_write_text
from agent_world.metrics import compute_metrics
from agent_world.models import WorldConfig
from agent_world.openrouter_brain import OpenRouterBrain, SYSTEM_INSTRUCTIONS
from agent_world.persistence import IncrementalRunWriter
from agent_world.session import SimulationSession
from agent_world.usage import summarize_codex_simulation_credits
from agent_world.devin_brain import DevinBrain, build_devin_prompt
from agent_world.grok_brain import GrokBrain, build_grok_prompts
from agent_world.zcode_brain import ZCodeBrain, build_zcode_prompt
from agent_world.world import WorldEngine


SCHEMA_VERSION = 1

# A two-axis design. The environment treatment intentionally bundles geography
# and economic affordances because the research question is whether *usable*
# comparative advantage changes behavior, not whether a label changes it.
ENVIRONMENT_TREATMENTS: dict[str, dict[str, str]] = {
    "baseline": {
        "geography_mode": "shared_oasis",
        "economy_mode": "baseline",
    },
    "commerce": {
        "geography_mode": "dispersed",
        "economy_mode": "commerce",
    },
    "organic": {
        "geography_mode": "dispersed",
        "economy_mode": "organic",
    },
}

OBJECTIVE_TREATMENTS: dict[str, dict[str, str]] = {
    "neutral": {"objective_mode": "neutral"},
    "collective": {"objective_mode": "collective"},
    "individual": {"objective_mode": "individual"},
}

HEADLINE_METRICS = (
    "final_tick",
    "living_agents",
    "survival_rate",
    "gifts",
    "gift_units",
    "gift_value",
    "trade_offers",
    "trades_accepted",
    "trade_volume",
    "market_conversion_pct",
    "market_actions",
    "contract_actions",
    "construction_contribution_events",
    "construction_contribution_value",
    "complete_structures",
    "productive_asset_value",
    "groups",
    "wealth_gini",
    "asset_adjusted_gini",
    "division_of_labor_index",
    "llm_cost_usd",
)


def selected_conditions(
    environments: Iterable[str] = ("baseline", "commerce"),
    objectives: Iterable[str] = ("collective", "individual"),
) -> list[dict[str, Any]]:
    """Return validated factorial cells in a stable order."""

    environment_names = _unique(tuple(environments))
    objective_names = _unique(tuple(objectives))
    unknown_environments = sorted(set(environment_names) - set(ENVIRONMENT_TREATMENTS))
    unknown_objectives = sorted(set(objective_names) - set(OBJECTIVE_TREATMENTS))
    if unknown_environments:
        raise ValueError(f"Unknown environment treatment(s): {', '.join(unknown_environments)}")
    if unknown_objectives:
        raise ValueError(f"Unknown objective treatment(s): {', '.join(unknown_objectives)}")
    if not environment_names or not objective_names:
        raise ValueError("At least one environment and objective treatment are required.")

    conditions: list[dict[str, Any]] = []
    for environment in environment_names:
        for objective in objective_names:
            overrides = {
                **ENVIRONMENT_TREATMENTS[environment],
                **OBJECTIVE_TREATMENTS[objective],
            }
            conditions.append(
                {
                    "id": f"{environment}-{objective}",
                    "environment": environment,
                    "objective": objective,
                    "config_overrides": overrides,
                }
            )
    return conditions


def run_factorial_experiment(
    *,
    out_dir: Path,
    seeds: Iterable[int],
    ticks: int,
    agents: int,
    brain: str = "survival",
    model: str | None = None,
    reasoning_effort: str | None = None,
    connector_profile: str = "stateless-v1",
    conversation_mode: str = "stateless",
    session_max_turns: int = 10,
    environments: Iterable[str] = ("baseline", "commerce"),
    objectives: Iterable[str] = ("collective", "individual"),
    width: int = 16,
    height: int = 16,
    log_agent_io: bool = True,
    max_workers: int | None = None,
    overwrite: bool = False,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run selected cells and seeds, returning the final experiment manifest.

    Cells execute sequentially. Conditions rotate between seeds to reduce a
    fixed treatment-order/time confound in provider-backed runs. Agent decisions
    within an LLM tick can still be parallelized explicitly with ``max_workers``.
    """

    seed_values = _unique(tuple(int(seed) for seed in seeds))
    if not seed_values:
        raise ValueError("At least one seed is required.")
    if ticks < 1:
        raise ValueError("ticks must be at least 1.")
    if agents < 1:
        raise ValueError("agents must be at least 1.")
    if brain not in {
        "survival",
        "openrouter",
        "codex",
        "claude",
        "cursor",
        "devin",
        "grok",
    }:
        raise ValueError(
            "brain must be 'survival', 'openrouter', 'codex', 'claude', 'cursor', 'devin', or 'grok'."
        )
    if max_workers is not None and max_workers < 1:
        raise ValueError("max_workers must be at least 1.")

    conditions = selected_conditions(environments, objectives)
    output_root = out_dir.expanduser().resolve()
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Experiment output directory is not empty: {output_root}. "
            "Choose another --out-dir or pass --overwrite."
        )
    output_root.mkdir(parents=True, exist_ok=True)

    experiment_brain_spec = BrainSpec.resolve(
        brain,
        model=model,
        reasoning_effort=reasoning_effort,
        max_workers=max_workers,
        connector_profile=connector_profile,
        conversation_mode=conversation_mode,
        session_max_turns=session_max_turns,
    )
    effective_workers = experiment_brain_spec.max_workers or 1
    created_at = _utc_now()
    manifest_path = output_root / "experiment-manifest.json"
    summary_json_path = output_root / "summary.json"
    summary_md_path = output_root / "summary.md"
    experiment_manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": output_root.name,
        "created_at_utc": created_at,
        "updated_at_utc": created_at,
        "status": "running",
        "provenance": _code_provenance(),
        "design": {
            "type": "factorial",
            "environment_axis": {
                name: dict(ENVIRONMENT_TREATMENTS[name])
                for name in _unique(tuple(environments))
            },
            "objective_axis": {
                name: dict(OBJECTIVE_TREATMENTS[name])
                for name in _unique(tuple(objectives))
            },
            "conditions": conditions,
            "seeds": seed_values,
            "counterbalanced_execution": True,
        },
        "run_settings": {
            "brain": brain,
            "agents": agents,
            "target_ticks": ticks,
            "width": width,
            "height": height,
            "log_agent_io": log_agent_io,
            "max_workers": effective_workers,
            "connector_profile": connector_profile,
            "conversation_mode": conversation_mode,
            "session_max_turns": session_max_turns,
            **_declared_brain_settings(
                brain,
                experiment_brain_spec.model,
                experiment_brain_spec.reasoning_effort,
            ),
        },
        "outputs": {
            "root": str(output_root),
            "manifest": str(manifest_path),
            "summary_json": str(summary_json_path),
            "summary_markdown": str(summary_md_path),
        },
        "runs": [],
        "aggregate_summary": None,
    }
    _atomic_write_json(manifest_path, experiment_manifest)

    results: list[dict[str, Any]] = []
    execution_index = 0
    for seed_index, seed in enumerate(seed_values):
        # Rotate, rather than shuffle, so order is transparent and reproducible.
        offset = seed_index % len(conditions)
        ordered_conditions = conditions[offset:] + conditions[:offset]
        for condition in ordered_conditions:
            execution_index += 1
            config, applied, unsupported = _configured_world(
                width=width,
                height=height,
                seed=seed,
                overrides=condition["config_overrides"],
            )
            run_id = f"{condition['id']}-seed-{seed}"
            result = _run_single(
                output_root=output_root,
                experiment_id=experiment_manifest["experiment_id"],
                execution_index=execution_index,
                run_id=run_id,
                condition=condition,
                seed=seed,
                config=config,
                applied_overrides=applied,
                unsupported_overrides=unsupported,
                ticks=ticks,
                agents=agents,
                brain=brain,
                model=model,
                reasoning_effort=reasoning_effort,
                log_agent_io=log_agent_io,
                max_workers=effective_workers,
                progress_callback=progress_callback,
            )
            results.append(result)
            experiment_manifest["runs"] = [_run_index_entry(row) for row in results]
            experiment_manifest["updated_at_utc"] = _utc_now()
            _atomic_write_json(manifest_path, experiment_manifest)

    aggregate = aggregate_results(results, conditions, seed_values)
    _atomic_write_json(summary_json_path, aggregate)
    _atomic_write_text(summary_md_path, render_summary_markdown(aggregate))
    experiment_manifest["status"] = (
        "completed" if all(result.get("valid_for_analysis") for result in results) else "completed_with_exclusions"
    )
    experiment_manifest["updated_at_utc"] = _utc_now()
    experiment_manifest["aggregate_summary"] = aggregate
    _atomic_write_json(manifest_path, experiment_manifest)
    return experiment_manifest


def _run_single(
    *,
    output_root: Path,
    experiment_id: str,
    execution_index: int,
    run_id: str,
    condition: dict[str, Any],
    seed: int,
    config: WorldConfig,
    applied_overrides: dict[str, Any],
    unsupported_overrides: dict[str, Any],
    ticks: int,
    agents: int,
    brain: str,
    model: str | None,
    reasoning_effort: str | None,
    log_agent_io: bool,
    max_workers: int,
    progress_callback: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    stem = run_dir / "run"
    events_path = stem.with_suffix(".jsonl")
    snapshot_path = stem.with_name("run-snapshot.json")
    usage_path = stem.with_name("run-usage.jsonl")
    plan_usage_path = stem.with_name("run-plan-usage.json")
    checkpoint_path = stem.with_name("run-checkpoint.pkl")
    report_json_path = stem.with_name("run-report.json")
    report_md_path = stem.with_name("run-report.md")
    manifest_path = run_dir / "manifest.json"
    created_at = _utc_now()
    brain_spec = BrainSpec.resolve(
        brain,
        model=model,
        reasoning_effort=reasoning_effort,
        max_workers=max_workers,
    )
    run_manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "execution_index": execution_index,
        "created_at_utc": created_at,
        "updated_at_utc": created_at,
        "status": "initializing",
        "seed": seed,
        "condition": {
            "id": condition["id"],
            "environment": condition["environment"],
            "objective": condition["objective"],
            "requested_config_overrides": dict(condition["config_overrides"]),
            "applied_config_overrides": applied_overrides,
            "unsupported_config_overrides": unsupported_overrides,
        },
        "target_ticks": ticks,
        "final_ticks": 0,
        "agents": agents,
        "log_agent_io": log_agent_io,
        "config": asdict(config),
        "provenance": _code_provenance(),
        "brain": _declared_brain_settings(
            brain_spec.type, brain_spec.model, brain_spec.reasoning_effort
        )
        | {"type": brain_spec.type, "max_workers": brain_spec.max_workers},
        "hashes": _source_hashes(),
        "outputs": {
            "directory": str(run_dir),
            "events": str(events_path),
            "snapshot": str(snapshot_path),
            "usage": (
                str(usage_path)
                if brain in {"openrouter", "codex", "claude", "cursor", "devin", "grok"}
                else None
            ),
            "plan_usage": str(plan_usage_path) if brain == "codex" else None,
            "checkpoint": str(checkpoint_path),
            "report_json": str(report_json_path),
            "report_markdown": str(report_md_path),
            "manifest": str(manifest_path),
        },
        "summary": None,
        "valid_for_analysis": False,
        "stop_reason": None,
        "error": None,
        "data_quality": None,
        "simulation_usage": None,
        "codex_plan_usage": None,
    }
    _atomic_write_json(manifest_path, run_manifest)

    engine: WorldEngine | None = None
    run_writer: IncrementalRunWriter | None = None
    session: SimulationSession | None = None
    try:
        if brain_spec.model_backed:
            usage_path.write_text("", encoding="utf-8")
        runtime = BrainRuntime(usage_path if brain_spec.model_backed else None)
        names = [f"Agent {index + 1}" for index in range(agents)]
        engine = WorldEngine.create(config=config, agent_names=names)
        run_writer = IncrementalRunWriter(
            events_path,
            snapshot_path,
            checkpoint_path=checkpoint_path,
        )
        brains = create_brains(engine, brain_spec, runtime)
        first_brain = next(iter(brains.values()), None)
        if isinstance(
            first_brain,
            (OpenRouterBrain, CodexBrain, ClaudeBrain, CursorBrain, DevinBrain, GrokBrain, ZCodeBrain),
        ):
            run_manifest["brain"] = _brain_runtime_settings(
                first_brain, brain_spec.max_workers or 1
            )

        run_manifest["status"] = "running"
        _atomic_write_json(manifest_path, run_manifest)

        def checkpoint_extra(current: SimulationSession) -> dict[str, Any]:
            return _experiment_checkpoint_extra(
                run_manifest,
                current.plan_usage_checkpoints,
                current.export_brain_states(),
            )

        def on_tick(current: SimulationSession, _events: list[Any]) -> None:
            run_manifest["final_ticks"] = current.engine.state.tick
            run_manifest["updated_at_utc"] = _utc_now()
            if current.plan_usage_checkpoints:
                run_manifest["codex_plan_usage"] = summarize_plan_usage(
                    current.plan_usage_checkpoints
                )
            _atomic_write_json(manifest_path, run_manifest)
            if progress_callback:
                progress_callback(
                    {
                        "run_id": run_id,
                        "condition": condition["id"],
                        "seed": seed,
                        "tick": current.engine.state.tick,
                        "target_ticks": ticks,
                    }
                )

        session = SimulationSession(
            engine=engine,
            brain_spec=brain_spec,
            runtime=runtime,
            writer=run_writer,
            target_ticks=ticks,
            brains=brains,
            log_agent_io=log_agent_io,
            concurrent_decisions=(brain_spec.max_workers or 1) > 1,
            lifecycle_metadata={
                "experiment_id": experiment_id,
                "run_id": run_id,
                "condition": condition["id"],
            },
            checkpoint_extra=checkpoint_extra,
            on_tick=on_tick,
            report_stem=stem,
            plan_usage_path=plan_usage_path if brain_spec.type == "codex" else None,
        )
        session.start()
        if isinstance(
            first_brain,
            (OpenRouterBrain, CodexBrain, ClaudeBrain, CursorBrain, DevinBrain, GrokBrain, ZCodeBrain),
        ):
            run_manifest["brain"] = _brain_runtime_settings(
                first_brain, brain_spec.max_workers or 1
            )
        run_manifest["hashes"].update(_initial_prompt_hashes(engine, brain_spec.type))
        _atomic_write_json(manifest_path, run_manifest)
        result = session.run()
        report = result.report
        if report is None:
            raise RuntimeError("Simulation session did not emit its run report.")
        usage_records = result.usage_records
        run_manifest["codex_plan_usage"] = result.plan_usage
        run_manifest["simulation_usage"] = {
            "codex_credits": summarize_codex_simulation_credits(usage_records)
        }
        metrics = compute_metrics(engine.state)
        run_manifest["summary"] = _run_summary(metrics, report, agents)
        run_manifest["data_quality"] = {
            key: report.get("reliability", {}).get(key)
            for key in (
                "quality_status",
                "quality_flags",
                "decision_attempts",
                "decision_failure_rate_pct",
                "usage_record_coverage_pct",
            )
        }
        run_manifest["final_ticks"] = result.final_tick
        run_manifest["status"] = result.status
        run_manifest["stop_reason"] = result.stop_reason
        run_manifest["error"] = result.error
        run_manifest["valid_for_analysis"] = (
            result.status == "completed"
            and result.final_tick == ticks
            and not unsupported_overrides
        )
    except Exception as exc:  # Preserve partial artifacts and let other cells run.
        run_manifest["status"] = "failed"
        run_manifest["error"] = f"{type(exc).__name__}: {exc}"
        if engine is not None:
            if not engine.state.events or engine.state.events[-1].type != "run_failed":
                engine.log_event(
                    "run_failed",
                    message=run_manifest["error"],
                    data={"target_ticks": ticks},
                    scope="public",
                )
            run_manifest["final_ticks"] = engine.state.tick
            if run_writer is not None:
                run_writer.flush(
                    engine,
                    checkpoint_extra=_experiment_checkpoint_extra(
                        run_manifest,
                        session.plan_usage_checkpoints if session is not None else [],
                        session.export_brain_states() if session is not None else {},
                    ),
                )
    finally:
        run_manifest["updated_at_utc"] = _utc_now()
        _atomic_write_json(manifest_path, run_manifest)

    return run_manifest


def aggregate_results(
    results: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    seeds: list[int],
) -> dict[str, Any]:
    """Aggregate valid complete runs and retain explicit exclusion counts."""

    by_condition: dict[str, Any] = {}
    for condition in conditions:
        rows = [result for result in results if result.get("condition", {}).get("id") == condition["id"]]
        valid_rows = [result for result in rows if result.get("valid_for_analysis") and result.get("summary")]
        excluded = [result["run_id"] for result in rows if result not in valid_rows]
        headline = {
            metric: _numeric_stats(
                [row["summary"]["headline"][metric] for row in valid_rows if metric in row["summary"]["headline"]]
            )
            for metric in HEADLINE_METRICS
        }
        event_names = sorted(
            {
                event_name
                for row in valid_rows
                for event_name in row["summary"].get("event_counts", {})
            }
        )
        by_condition[condition["id"]] = {
            "condition": condition,
            "runs": len(rows),
            "valid_runs": len(valid_rows),
            "excluded_runs": excluded,
            "headline": headline,
            "events": {
                event_name: _numeric_stats(
                    [row["summary"].get("event_counts", {}).get(event_name, 0) for row in valid_rows]
                )
                for event_name in event_names
            },
        }

    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    valid_results = [result for result in results if result.get("valid_for_analysis") and result.get("summary")]
    total_cost = sum(row["summary"]["headline"].get("llm_cost_usd", 0) for row in results if row.get("summary"))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "run_count": len(results),
        "valid_run_count": len(valid_results),
        "excluded_run_count": len(results) - len(valid_results),
        "status_counts": status_counts,
        "seeds": seeds,
        "total_llm_cost_usd": round(total_cost, 6),
        "by_condition": by_condition,
        "factorial_contrasts": _factorial_contrasts(valid_results),
    }


def render_summary_markdown(summary: dict[str, Any]) -> str:
    """Render a compact, scan-friendly factorial comparison."""

    lines = [
        "# Agent World factorial experiment",
        "",
        f"- Runs: {summary['run_count']} total, {summary['valid_run_count']} valid, "
        f"{summary['excluded_run_count']} excluded",
        f"- Seeds: {', '.join(str(seed) for seed in summary['seeds'])}",
        f"- LLM cost: ${summary['total_llm_cost_usd']:.6f}",
        "",
        "| condition | valid/runs | ticks | survival | gifts/value | offers | accepted | trade value | contracts | contribution value | asset value | structures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition_id, row in summary["by_condition"].items():
        metric = row["headline"]
        lines.append(
            "| "
            + " | ".join(
                [
                    condition_id,
                    f"{row['valid_runs']}/{row['runs']}",
                    _mean_text(metric["final_tick"]),
                    _mean_text(metric["survival_rate"]),
                    f"{_mean_text(metric['gifts'])}/{_mean_text(metric['gift_value'])}",
                    _mean_text(metric["trade_offers"]),
                    _mean_text(metric["trades_accepted"]),
                    _mean_text(metric["trade_volume"]),
                    _mean_text(metric["contract_actions"]),
                    _mean_text(metric["construction_contribution_value"]),
                    _mean_text(metric["productive_asset_value"]),
                    _mean_text(metric["complete_structures"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Paired factorial contrasts", ""])
    contrasts = summary.get("factorial_contrasts", {})
    if not contrasts:
        lines.append("No complete paired cells were available.")
    else:
        for contrast_name, contrast_rows in contrasts.items():
            lines.append(f"### {contrast_name.replace('_', ' ').title()}")
            lines.append("")
            for cell, metrics in contrast_rows.items():
                useful = [
                    f"{metric}: {row['mean_delta']:+.3f} (n={row['pairs']})"
                    for metric, row in metrics.items()
                    if row.get("pairs")
                ]
                lines.append(f"- {cell}: " + (", ".join(useful) if useful else "no complete pairs"))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _configured_world(
    *, width: int, height: int, seed: int, overrides: dict[str, Any]
) -> tuple[WorldConfig, dict[str, Any], dict[str, Any]]:
    base = WorldConfig(width=width, height=height, seed=seed)
    supported_names = {field.name for field in fields(base)}
    applied = {key: value for key, value in overrides.items() if key in supported_names}
    unsupported = {key: value for key, value in overrides.items() if key not in supported_names}
    return replace(base, **applied), applied, unsupported


def _initial_prompt_hashes(engine: WorldEngine, brain: str) -> dict[str, str]:
    first_agent_id = sorted(engine.state.agents)[0]
    observation = build_observation(engine.state, first_agent_id)
    static_context = build_static_context(observation.get("world", {}))
    dynamic_json = json.dumps(build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True)
    system_prompt = f"{SYSTEM_INSTRUCTIONS}\n\n{static_context}"
    user_prompt = f"The current observation follows as JSON:\n{dynamic_json}"
    hashes = {
        "initial_api_system_prompt_sha256": _sha256_text(system_prompt),
        "initial_api_user_prompt_sha256": _sha256_text(user_prompt),
        "initial_static_context_sha256": _sha256_text(static_context),
    }
    if brain == "codex":
        hashes["initial_codex_prompt_sha256"] = _sha256_text(build_codex_prompt(static_context, dynamic_json))
    if brain == "claude":
        claude_system, claude_user = build_claude_prompts(static_context, dynamic_json)
        hashes["initial_claude_system_prompt_sha256"] = _sha256_text(claude_system)
        hashes["initial_claude_user_prompt_sha256"] = _sha256_text(claude_user)
    if brain == "cursor":
        hashes["initial_cursor_prompt_sha256"] = _sha256_text(
            build_cursor_prompt(static_context, dynamic_json)
        )
    if brain == "grok":
        grok_system, grok_user = build_grok_prompts(static_context, dynamic_json)
        hashes["initial_grok_system_prompt_sha256"] = _sha256_text(grok_system)
        hashes["initial_grok_user_prompt_sha256"] = _sha256_text(grok_user)
    if brain == "zcode":
        hashes["initial_zcode_prompt_sha256"] = _sha256_text(
            build_zcode_prompt(static_context, dynamic_json)
        )
    if brain == "devin":
        hashes["initial_devin_prompt_sha256"] = _sha256_text(
            build_devin_prompt(static_context, dynamic_json)
        )
    return hashes


def _source_hashes() -> dict[str, str]:
    module_dir = Path(__file__).resolve().parent
    return {
        "experiments_source_sha256": _sha256_file(module_dir / "experiments.py"),
        "models_source_sha256": _sha256_file(module_dir / "models.py"),
        "maps_source_sha256": _sha256_file(module_dir / "maps.py"),
        "rules_source_sha256": _sha256_file(module_dir / "rules.py"),
        "world_source_sha256": _sha256_file(module_dir / "world.py"),
        "interface_source_sha256": _sha256_file(module_dir / "interface.py"),
        "openrouter_brain_source_sha256": _sha256_file(
            module_dir / "openrouter_brain.py"
        ),
        "codex_brain_source_sha256": _sha256_file(module_dir / "codex_brain.py"),
        "claude_brain_source_sha256": _sha256_file(module_dir / "claude_brain.py"),
        "cursor_brain_source_sha256": _sha256_file(module_dir / "cursor_brain.py"),
        "grok_brain_source_sha256": _sha256_file(module_dir / "grok_brain.py"),
        "zcode_brain_source_sha256": _sha256_file(module_dir / "zcode_brain.py"),
        "devin_brain_source_sha256": _sha256_file(
            module_dir / "devin_brain.py"
        ),
        "runner_source_sha256": _sha256_file(module_dir / "runner.py"),
    }


def _code_provenance() -> dict[str, Any]:
    module_dir = Path(__file__).resolve().parent
    root = _git_output(["rev-parse", "--show-toplevel"], module_dir)
    cwd = Path(root) if root else module_dir.parent
    sha = _git_output(["rev-parse", "HEAD"], cwd)
    status = _git_output(["status", "--porcelain=v1"], cwd, strip=False)
    return {
        "git_sha": sha or None,
        "git_dirty": bool(status and status.strip()),
        "git_root": str(cwd),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


def _git_output(args: list[str], cwd: Path, *, strip: bool = True) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip() if strip else completed.stdout


def _declared_brain_settings(brain: str, model: str | None, reasoning_effort: str | None) -> dict[str, Any]:
    if brain == "survival":
        return {
            "provider": "local",
            "model": "SurvivalBrain",
            "reasoning_effort": None,
            "api_style": None,
            "base_url": None,
        }
    if brain == "codex":
        return {
            "provider": "codex_cli",
            "model": model or os.environ.get("CODEX_MODEL", "gpt-5.6-luna"),
            "reasoning_effort": reasoning_effort or os.environ.get("CODEX_REASONING_EFFORT", "low"),
            "api_style": "codex_exec",
            "base_url": None,
            "billing_mode": "chatgpt_plan",
            "timeout_seconds": int(os.environ.get("CODEX_TIMEOUT_SECONDS", "300")),
        }
    if brain == "claude":
        return {
            "provider": "claude_cli",
            "model": model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
            "reasoning_effort": reasoning_effort or os.environ.get("CLAUDE_REASONING_EFFORT", "low"),
            "api_style": "claude_print",
            "base_url": None,
            "billing_mode": "claude_plan",
            "timeout_seconds": int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "300")),
        }
    if brain == "cursor":
        return {
            "provider": "cursor_cli",
            "model": model or os.environ.get("CURSOR_MODEL", "cursor-grok-4.5"),
            "reasoning_effort": reasoning_effort or os.environ.get("CURSOR_REASONING_EFFORT", "low"),
            "api_style": "cursor_agent_print",
            "base_url": None,
            "billing_mode": "cursor_subscription",
            "timeout_seconds": int(os.environ.get("CURSOR_TIMEOUT_SECONDS", "300")),
        }
    if brain == "grok":
        return {
            "provider": "grok_cli",
            "model": model or os.environ.get("GROK_MODEL", "grok-4.6"),
            "reasoning_effort": reasoning_effort or os.environ.get("GROK_REASONING_EFFORT", "medium"),
            "api_style": "grok_single_json_schema",
            "base_url": None,
            "billing_mode": "grok_subscription",
            "timeout_seconds": int(os.environ.get("GROK_TIMEOUT_SECONDS", "300")),
        }
    if brain == "zcode":
        return {
            "provider": "zcode_cli",
            "model": model or os.environ.get("ZCODE_MODEL_ID", "glm-5.3"),
            "reasoning_effort": reasoning_effort or os.environ.get("ZCODE_REASONING_EFFORT", "max"),
            "api_style": "zcode_headless_json",
            "base_url": None,
            "billing_mode": "zai_coding_plan",
            "timeout_seconds": int(os.environ.get("ZCODE_TIMEOUT_SECONDS", "300")),
        }
    if brain == "devin":
        return {
            "provider": "devin_cli",
            "model": model or os.environ.get("DEVIN_MODEL", "swe-1-6-fast"),
            "reasoning_effort": reasoning_effort
            or os.environ.get("DEVIN_REASONING_EFFORT", "low"),
            "api_style": "agent_client_protocol",
            "base_url": None,
            "billing_mode": "devin_subscription",
            "connector_runtime": "devin_cli",
            "timeout_seconds": int(
                os.environ.get("DEVIN_TIMEOUT_SECONDS", "300")
            ),
        }
    base_url = os.environ.get(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    ).rstrip("/")
    return {
        "provider": "openrouter",
        "model": model or os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.2"),
        "reasoning_effort": (
            reasoning_effort
            or os.environ.get("OPENROUTER_REASONING_EFFORT", "medium")
        ),
        "api_style": "chat",
        "base_url": _safe_base_url(base_url),
        "provider_order": [
            value.strip()
            for value in os.environ.get("OPENROUTER_PROVIDER_ORDER", "").split(",")
            if value.strip()
        ],
        "max_output_tokens": int(
            os.environ.get("OPENROUTER_MAX_OUTPUT_TOKENS", "5000")
        ),
    }


def _brain_runtime_settings(
    brain: OpenRouterBrain | CodexBrain | ClaudeBrain | CursorBrain | DevinBrain | GrokBrain | ZCodeBrain,
    max_workers: int,
) -> dict[str, Any]:
    if isinstance(brain, CodexBrain):
        return {
            "type": "codex",
            "provider": "codex_cli",
            "model": brain.model,
            "reasoning_effort": brain.reasoning_effort,
            "api_style": "codex_exec",
            "base_url": None,
            "billing_mode": "chatgpt_plan",
            "executable": brain.executable,
            "timeout_seconds": brain.timeout_seconds,
            "max_workers": max_workers,
            "connector_profile": brain.connector_profile,
            "conversation_mode": brain.conversation_mode,
            "session_max_turns": brain.session_max_turns,
        }
    if isinstance(brain, ClaudeBrain):
        return {
            "type": "claude",
            "provider": "claude_cli",
            "model": brain.model,
            "reasoning_effort": brain.reasoning_effort,
            "api_style": "claude_print",
            "base_url": None,
            "billing_mode": "claude_plan",
            "executable": brain.executable,
            "timeout_seconds": brain.timeout_seconds,
            "max_workers": max_workers,
            "connector_profile": brain.connector_profile,
            "conversation_mode": brain.conversation_mode,
            "session_max_turns": brain.session_max_turns,
        }
    if isinstance(brain, CursorBrain):
        return {
            "type": "cursor",
            "provider": "cursor_cli",
            "model": brain.model,
            "resolved_model": brain.resolved_model,
            "reasoning_effort": brain.reasoning_effort,
            "api_style": "cursor_agent_print",
            "base_url": None,
            "billing_mode": "cursor_subscription",
            "executable": brain.executable,
            "timeout_seconds": brain.timeout_seconds,
            "max_workers": max_workers,
            "connector_profile": brain.connector_profile,
            "conversation_mode": brain.conversation_mode,
            "session_max_turns": brain.session_max_turns,
        }
    if isinstance(brain, GrokBrain):
        return {
            "type": "grok",
            "provider": "grok_cli",
            "model": brain.model,
            "resolved_model": brain.resolved_model,
            "reasoning_effort": brain.reasoning_effort,
            "api_style": "grok_single_json_schema",
            "base_url": None,
            "billing_mode": "grok_subscription",
            "executable": brain.executable,
            "timeout_seconds": brain.timeout_seconds,
            "max_workers": max_workers,
            "connector_profile": brain.connector_profile,
            "conversation_mode": brain.conversation_mode,
        }
    if isinstance(brain, ZCodeBrain):
        return {
            "type": "zcode",
            "provider": "zcode_cli",
            "model": brain.model,
            "resolved_model": brain.resolved_model,
            "reasoning_effort": brain.reasoning_effort,
            "api_style": "zcode_headless_json",
            "base_url": None,
            "billing_mode": "zai_coding_plan",
            "executable": brain.executable,
            "timeout_seconds": brain.timeout_seconds,
            "max_workers": max_workers,
            "connector_profile": brain.connector_profile,
            "conversation_mode": brain.conversation_mode,
        }
    if isinstance(brain, DevinBrain):
        return {
            "type": "devin",
            "provider": "devin_cli",
            "connector_runtime": "devin_cli",
            "model": brain.model,
            "resolved_model": brain.resolved_model,
            "reasoning_effort": brain.reasoning_effort,
            "api_style": "agent_client_protocol",
            "base_url": None,
            "billing_mode": "devin_subscription",
            "executable": brain.executable,
            "timeout_seconds": brain.timeout_seconds,
            "max_workers": max_workers,
            "connector_profile": brain.connector_profile,
            "conversation_mode": brain.conversation_mode,
            "session_max_turns": brain.session_max_turns,
        }
    return {
        "type": "openrouter",
        "provider": "openrouter",
        "model": brain.model,
        "reasoning_effort": brain.reasoning_effort,
        "api_style": brain.api_style,
        "base_url": _safe_base_url(brain.base_url),
        "provider_order": [
            value.strip()
            for value in os.environ.get("OPENROUTER_PROVIDER_ORDER", "").split(",")
            if value.strip()
        ],
        "max_output_tokens": brain.max_output_tokens,
        "timeout_seconds": brain.timeout_seconds,
        "max_retries": brain.max_retries,
        "min_request_interval_seconds": brain.min_request_interval_seconds,
        "max_workers": max_workers,
    }


def _run_summary(metrics: dict[str, Any], report: dict[str, Any], agent_count: int) -> dict[str, Any]:
    event_counts = dict(metrics.get("events", {}))
    market_event_names = {
        "offer_trade",
        "accept_trade",
        "reject_trade",
        "cancel_trade",
        "create_contract",
        "accept_contract",
        "repay_contract",
        "fulfill_contract",
        "default_contract",
        "set_access_fee",
        "pay_access_fee",
        "claim_dividend",
        "maintain_structure",
        "structure_upkeep_paid",
        "structure_upkeep_missed",
    }
    contract_event_names = {
        "create_contract",
        "accept_contract",
        "repay_contract",
        "fulfill_contract",
        "default_contract",
    }
    complete_structures = sum(metrics.get("infrastructure", {}).get("structures_by_type", {}).values())
    living = int(metrics.get("agents", {}).get("living", 0))
    flows = metrics.get("economic_flows", {})
    gifts = flows.get("gifts", {})
    market = flows.get("market", {})
    productive_assets = metrics.get("productive_assets", {})
    specialization = metrics.get("specialization", {})
    construction_economy = report.get("economy", {}).get("construction", {})
    contribution_summary = construction_economy.get("contributions", {})
    headline = {
        "final_tick": int(metrics.get("tick", 0)),
        "living_agents": living,
        "survival_rate": round(living / agent_count, 6) if agent_count else 0.0,
        "gifts": int(gifts.get("actions", event_counts.get("gift", report.get("economy", {}).get("gifts", 0)))),
        "gift_units": int(gifts.get("units", 0)),
        "gift_value": int(gifts.get("value", 0)),
        "trade_offers": int(market.get("offers", event_counts.get("offer_trade", 0))),
        "trades_accepted": int(market.get("accepted", metrics.get("trade", {}).get("accepted", 0))),
        "trade_volume": int(market.get("transfer_value", metrics.get("trade", {}).get("volume", 0))),
        "market_conversion_pct": float(market.get("conversion_pct", 0)),
        "market_actions": sum(int(event_counts.get(name, 0)) for name in market_event_names),
        "contract_actions": sum(int(event_counts.get(name, 0)) for name in contract_event_names),
        "construction_contribution_events": int(contribution_summary.get("events", 0)),
        "construction_contribution_value": int(contribution_summary.get("value", 0)),
        "complete_structures": int(complete_structures),
        "productive_asset_value": sum(
            int(value) for value in productive_assets.get("structure_replacement_value", {}).values()
        ),
        "groups": int(metrics.get("groups", {}).get("count", 0)),
        "wealth_gini": float(metrics.get("wealth_gini", 0)),
        "asset_adjusted_gini": float(productive_assets.get("asset_adjusted_gini", 0)),
        "division_of_labor_index": float(specialization.get("division_of_labor_index", 0)),
        "llm_cost_usd": float(report.get("usage", {}).get("total_cost_usd", 0)),
    }
    return {
        "headline": headline,
        "event_counts": event_counts,
        "metrics": metrics,
        "report_summary": {
            "completed": report.get("run", {}).get("completed"),
            "stop_reason": report.get("run", {}).get("stop_reason"),
            "usage": report.get("usage", {}),
        },
    }


def _factorial_contrasts(results: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {
        (
            row.get("seed"),
            row.get("condition", {}).get("environment"),
            row.get("condition", {}).get("objective"),
        ): row["summary"]["headline"]
        for row in results
    }
    contrasts: dict[str, Any] = {
        "environment_effect_commerce_minus_baseline": {},
        "objective_effect_individual_minus_collective": {},
        "interaction_effect": {},
    }
    contrast_metrics = [metric for metric in HEADLINE_METRICS if metric != "llm_cost_usd"]
    seed_values = sorted({int(row["seed"]) for row in results})

    for objective in OBJECTIVE_TREATMENTS:
        metrics: dict[str, Any] = {}
        for metric in contrast_metrics:
            deltas = []
            for seed in seed_values:
                baseline = lookup.get((seed, "baseline", objective))
                commerce = lookup.get((seed, "commerce", objective))
                if baseline is not None and commerce is not None:
                    deltas.append(float(commerce[metric]) - float(baseline[metric]))
            metrics[metric] = _delta_stats(deltas)
        contrasts["environment_effect_commerce_minus_baseline"][objective] = metrics

    for environment in ENVIRONMENT_TREATMENTS:
        metrics = {}
        for metric in contrast_metrics:
            deltas = []
            for seed in seed_values:
                collective = lookup.get((seed, environment, "collective"))
                individual = lookup.get((seed, environment, "individual"))
                if collective is not None and individual is not None:
                    deltas.append(float(individual[metric]) - float(collective[metric]))
            metrics[metric] = _delta_stats(deltas)
        contrasts["objective_effect_individual_minus_collective"][environment] = metrics

    interaction_metrics: dict[str, Any] = {}
    for metric in contrast_metrics:
        deltas = []
        for seed in seed_values:
            baseline_collective = lookup.get((seed, "baseline", "collective"))
            baseline_individual = lookup.get((seed, "baseline", "individual"))
            commerce_collective = lookup.get((seed, "commerce", "collective"))
            commerce_individual = lookup.get((seed, "commerce", "individual"))
            if all(
                row is not None
                for row in (baseline_collective, baseline_individual, commerce_collective, commerce_individual)
            ):
                commerce_delta = float(commerce_individual[metric]) - float(commerce_collective[metric])
                baseline_delta = float(baseline_individual[metric]) - float(baseline_collective[metric])
                deltas.append(commerce_delta - baseline_delta)
        interaction_metrics[metric] = _delta_stats(deltas)
    contrasts["interaction_effect"]["all_cells"] = interaction_metrics
    return contrasts


def _numeric_stats(values: list[int | float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "min": None, "max": None, "total": 0}
    numeric = [float(value) for value in values]
    return {
        "n": len(numeric),
        "mean": round(sum(numeric) / len(numeric), 6),
        "min": min(numeric),
        "max": max(numeric),
        "total": round(sum(numeric), 6),
    }


def _delta_stats(values: list[float]) -> dict[str, Any]:
    stats = _numeric_stats(values)
    return {
        "pairs": stats["n"],
        "mean_delta": stats["mean"],
        "min_delta": stats["min"],
        "max_delta": stats["max"],
    }


def _run_index_entry(run_manifest: dict[str, Any]) -> dict[str, Any]:
    summary = run_manifest["summary"]
    compact_summary = None
    if summary:
        compact_summary = {
            "headline": summary.get("headline", {}),
            "event_counts": summary.get("event_counts", {}),
            "report_summary": summary.get("report_summary", {}),
        }
    return {
        "run_id": run_manifest["run_id"],
        "execution_index": run_manifest["execution_index"],
        "seed": run_manifest["seed"],
        "condition": run_manifest["condition"],
        "status": run_manifest["status"],
        "target_ticks": run_manifest["target_ticks"],
        "final_ticks": run_manifest["final_ticks"],
        "valid_for_analysis": run_manifest["valid_for_analysis"],
        "stop_reason": run_manifest["stop_reason"],
        "error": run_manifest["error"],
        "data_quality": run_manifest.get("data_quality"),
        "manifest": run_manifest["outputs"]["manifest"],
        "summary": compact_summary,
    }


def _experiment_checkpoint_extra(
    run_manifest: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    brain_states: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brain = run_manifest["brain"]
    outputs = run_manifest["outputs"]
    return {
        "experiment_id": run_manifest["experiment_id"],
        "run_id": run_manifest["run_id"],
        "target_ticks": run_manifest["target_ticks"],
        "brain": dict(brain),
        "outputs": dict(outputs),
        "run": {
            "brain": brain["type"],
            "model": brain.get("model"),
            "reasoning_effort": brain.get("reasoning_effort"),
            "target_ticks": run_manifest["target_ticks"],
            "events_path": outputs["events"],
            "snapshot_path": outputs["snapshot"],
            "max_workers": brain.get("max_workers", 1),
            "log_agent_io": bool(run_manifest.get("log_agent_io", True)),
            "sequential_decisions": brain.get("max_workers", 1) <= 1,
            "connector_profile": brain.get("connector_profile", "stateless-v1"),
            "conversation_mode": brain.get("conversation_mode", "stateless"),
            "session_max_turns": brain.get("session_max_turns", 10),
        },
        "plan_usage_checkpoints": list(checkpoints),
        "brain_states": dict(brain_states or {}),
    }


def _provider_name(base_url: str) -> str:
    host = (urlsplit(base_url).hostname or "").lower()
    if "openrouter.ai" in host:
        return "openrouter"
    if "openai.com" in host:
        return "openai"
    return host or "custom"


def _safe_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}{parsed.path}".rstrip("/")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique(values: tuple[Any, ...]) -> list[Any]:
    return list(dict.fromkeys(values))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mean_text(stats: dict[str, Any]) -> str:
    value = stats.get("mean")
    return "—" if value is None else f"{value:.3f}"
