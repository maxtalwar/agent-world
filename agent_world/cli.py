"""Command line tools for running and inspecting Agent World."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from agent_world.ablation import format_table, run_ablation
from agent_world.agents import AgentBrain, SurvivalBrain
from agent_world.brain_factory import (
    BrainSpec,
    PopulationSpec,
    create_population_brains,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.claude_brain import ClaudeBrain
from agent_world.codex_brain import CodexBrain
from agent_world.env import load_dotenv
from agent_world.experiments import run_factorial_experiment
from agent_world.interface import OBSERVATION_MODES, build_agent_prompt, build_observation
from agent_world.io import atomic_write_json, atomic_write_text as _atomic_write_text
from agent_world.maps import render_tiles
from agent_world.metrics import compute_metrics
from agent_world.models import WorldConfig
from agent_world.openai_brain import OpenAIBrain
from agent_world.observer import serve_observer
from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
from agent_world.replay import format_event, read_events
from agent_world.role_benchmark import run_role_viability_benchmark
from agent_world.run_report import format_comparison, load_run_files, write_report
from agent_world.session import SimulationSession
from agent_world.usage import summarize_codex_simulation_credits
from agent_world.world import WorldEngine


RUN_PRESETS = {
    "baseline": {
        "economy_mode": "baseline",
        "geography_mode": "shared_oasis",
        "objective_mode": "neutral",
        "specialization_mode": "generalists",
    },
    "organic-generalists": {
        "economy_mode": "organic",
        "geography_mode": "dispersed",
        "objective_mode": "neutral",
        "specialization_mode": "generalists",
    },
    "experimental-organic-specialists": {
        "economy_mode": "organic",
        "geography_mode": "dispersed",
        "objective_mode": "neutral",
        "specialization_mode": "specialists",
    },
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="agent-world")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a deterministic simulation.")
    run_parser.add_argument("--ticks", type=int, default=None, help="Total target tick. Defaults to 25, or the saved target when resuming.")
    run_parser.add_argument("--agents", type=int, default=None)
    run_parser.add_argument("--seed", type=int, default=1)
    run_parser.add_argument("--width", type=int, default=16)
    run_parser.add_argument("--height", type=int, default=16)
    run_parser.add_argument("--preset", choices=sorted(RUN_PRESETS), default=None)
    run_parser.add_argument("--objective-mode", choices=["neutral", "collective", "individual"], default=None)
    run_parser.add_argument("--economy-mode", choices=["baseline", "commerce", "organic"], default=None)
    run_parser.add_argument("--geography-mode", choices=["shared_oasis", "dispersed"], default=None)
    run_parser.add_argument("--specialization-mode", choices=["generalists", "specialists"], default=None)
    run_parser.add_argument("--brain", choices=["survival", "llm", "codex", "claude"], default=None)
    run_parser.add_argument("--model", default=None, help="Model for --brain llm/codex/claude. Uses the selected brain's environment default.")
    run_parser.add_argument(
        "--population",
        action="append",
        default=None,
        metavar="COUNT@MODEL",
        help=(
            "Repeat for mixed populations, e.g. --population 10@claude-sonnet-5 "
            "--population 10@gpt-5.6-luna. Explicit COUNT@BRAIN:MODEL is also accepted."
        ),
    )
    run_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
        default=None,
        help="Reasoning effort for --brain llm/codex/claude. Uses the selected brain's environment default.",
    )
    run_parser.add_argument(
        "--claude-thinking-budget-tokens",
        type=int,
        default=None,
        help="Extended-thinking token allowance for Claude decisions (default: CLAUDE_MAX_THINKING_TOKENS or 0).",
    )
    run_parser.add_argument("--out", type=Path, default=None)
    run_parser.add_argument("--snapshot", type=Path, default=None)
    run_parser.add_argument("--checkpoint", type=Path, default=None, help="Crash-resume checkpoint path. Derived from --out when omitted.")
    run_parser.add_argument("--resume-checkpoint", type=Path, default=None, help="Resume a trusted local checkpoint; --ticks may extend its total target.")
    run_parser.add_argument("--no-agent-io-log", action="store_true", help="Do not log private observations/prompts.")
    run_parser.add_argument("--sequential-decisions", action="store_true", help="Disable same-tick concurrent brain calls.")
    run_parser.add_argument("--max-workers", type=int, default=None, help="Maximum same-tick brain calls. Provider-backed brains default to one worker.")
    run_parser.add_argument("--codex-max-workers", type=int, default=None)
    run_parser.add_argument("--claude-max-workers", type=int, default=None)
    run_parser.add_argument("--llm-max-workers", type=int, default=None)
    run_parser.add_argument("--assignment-strategy", choices=["ordered", "stratified"], default=None)
    run_parser.add_argument("--assignment-seed", type=int, default=None)
    run_parser.add_argument(
        "--assignment-from-manifest",
        type=Path,
        default=None,
        help="Reuse the exact agent-to-cohort mapping from a prior compatible run manifest.",
    )
    run_parser.add_argument("--decision-mode", choices=["raw", "validated"], default=None)
    run_parser.add_argument(
        "--observation-mode",
        choices=OBSERVATION_MODES,
        default=None,
        help="Versioned model-facing agent boundary (default: compact-v2).",
    )
    run_parser.add_argument("--progress", action="store_true", help="Print progress after each tick.")

    replay_parser = subparsers.add_parser("replay", help="Print events from a JSONL log.")
    replay_parser.add_argument("path", type=Path)
    replay_parser.add_argument("--last", type=int, default=50)

    prompt_parser = subparsers.add_parser("prompt", help="Print a neutral LLM prompt for an agent.")
    prompt_parser.add_argument("--seed", type=int, default=1)
    prompt_parser.add_argument("--agents", type=int, default=2)
    prompt_parser.add_argument("--agent", default="agent-1")
    prompt_parser.add_argument("--width", type=int, default=16)
    prompt_parser.add_argument("--height", type=int, default=16)
    prompt_parser.add_argument("--objective-mode", choices=["neutral", "collective", "individual"], default="neutral")
    prompt_parser.add_argument("--economy-mode", choices=["baseline", "commerce", "organic"], default="baseline")
    prompt_parser.add_argument("--geography-mode", choices=["shared_oasis", "dispersed"], default="shared_oasis")
    prompt_parser.add_argument("--observation-mode", choices=OBSERVATION_MODES, default="compact-v2")

    map_parser = subparsers.add_parser("map", help="Print the standard world map.")
    map_parser.add_argument("--width", type=int, default=16)
    map_parser.add_argument("--height", type=int, default=16)

    view_parser = subparsers.add_parser("view", help="Serve a live observatory for a run log and snapshot.")
    view_parser.add_argument("--snapshot", type=Path, default=Path("runs/live-snapshot.json"))
    view_parser.add_argument("--events", type=Path, default=Path("runs/live.jsonl"))
    view_parser.add_argument("--host", default="127.0.0.1")
    view_parser.add_argument("--port", type=int, default=8765)

    ablate_parser = subparsers.add_parser(
        "ablate",
        help="Sweep single-variable config changes on a fixed seed and diff the metrics.",
    )
    ablate_parser.add_argument("--agents", type=int, default=4)
    ablate_parser.add_argument("--ticks", type=int, default=30, help="Baseline tick count (horizon variants scale this).")
    ablate_parser.add_argument("--seed", type=int, default=11)
    ablate_parser.add_argument("--brain", choices=["survival", "llm", "codex", "claude"], default="survival")
    ablate_parser.add_argument("--model", default=None)
    ablate_parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high", "xhigh", "max"], default=None)
    ablate_parser.add_argument("--out", type=Path, default=None, help="Optional JSON output path for the rows.")

    report_parser = subparsers.add_parser(
        "report",
        help="Export structured -report.json/-report.md summaries for run logs; compares runs when given several.",
    )
    report_parser.add_argument("paths", type=Path, nargs="+", help="Run event logs (.jsonl) with matching -snapshot.json files.")

    role_parser = subparsers.add_parser(
        "benchmark-roles",
        help="Measure the non-social scripted survival floor of experimental specialist packages.",
    )
    role_parser.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 101)))
    role_parser.add_argument("--ticks", type=int, default=50)
    role_parser.add_argument("--out", type=Path, default=None)

    experiment_parser = subparsers.add_parser(
        "experiment",
        help="Run a reproducible multi-seed environment x objective factorial experiment.",
    )
    experiment_parser.add_argument("--agents", type=int, default=5)
    experiment_parser.add_argument("--ticks", type=int, default=60)
    experiment_parser.add_argument("--seeds", type=int, nargs="+", default=[11])
    experiment_parser.add_argument(
        "--brain",
        choices=["survival", "llm", "codex", "claude"],
        default="survival",
        help="Defaults to the free local scripted brain. LLM calls occur only when explicitly selected.",
    )
    experiment_parser.add_argument("--model", default=None)
    experiment_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
        default=None,
    )
    experiment_parser.add_argument(
        "--environment",
        choices=["all", "baseline", "commerce", "organic"],
        default="all",
        help="baseline=shared oasis; commerce=global market treatment; organic=dispersed specialists with physical local exchange.",
    )
    experiment_parser.add_argument(
        "--objective",
        choices=["all", "neutral", "collective", "individual"],
        default="all",
    )
    experiment_parser.add_argument("--width", type=int, default=16)
    experiment_parser.add_argument("--height", type=int, default=16)
    experiment_parser.add_argument("--out-dir", type=Path, default=None)
    experiment_parser.add_argument("--no-agent-io-log", action="store_true")
    experiment_parser.add_argument("--max-workers", type=int, default=None)
    experiment_parser.add_argument("--overwrite", action="store_true")
    experiment_parser.add_argument("--progress", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "run":
        _run(args)
    elif args.command == "replay":
        _replay(args)
    elif args.command == "prompt":
        _prompt(args)
    elif args.command == "map":
        _map(args)
    elif args.command == "view":
        _view(args)
    elif args.command == "ablate":
        _ablate(args)
    elif args.command == "report":
        _report(args)
    elif args.command == "benchmark-roles":
        _benchmark_roles(args)
    elif args.command == "experiment":
        _experiment(args)


def _benchmark_roles(args: argparse.Namespace) -> None:
    result = run_role_viability_benchmark(args.seeds, ticks=args.ticks)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        atomic_write_json(args.out, result)
        print(f"Wrote role viability benchmark to {args.out}")


def _run(args: argparse.Namespace) -> None:
    load_dotenv()
    resume_checkpoint = getattr(args, "resume_checkpoint", None)
    resumed = resume_checkpoint is not None
    checkpoint_extra: dict[str, Any] = {}
    population_spec: PopulationSpec | None = None
    if resumed:
        engine, checkpoint_extra = load_run_checkpoint(resume_checkpoint)
        saved = checkpoint_extra.get("run") if isinstance(checkpoint_extra.get("run"), dict) else {}
        saved_population = saved.get("population")
        if isinstance(saved_population, dict):
            if (
                getattr(args, "population", None)
                or args.brain
                or args.model
                or args.reasoning_effort
                or getattr(args, "claude_thinking_budget_tokens", None) is not None
            ):
                raise ValueError(
                    "A population-aware checkpoint must be resumed with its saved population; "
                    "omit --population, --brain, --model, --reasoning-effort, and --claude-thinking-budget-tokens."
                )
            population_spec = PopulationSpec.from_dict(saved_population)
        else:
            saved_brain = str(saved.get("brain") or "survival")
            if args.brain is not None and args.brain != saved_brain:
                raise ValueError(
                    f"Checkpoint uses brain={saved_brain!r}; refusing to resume it with brain={args.brain!r}."
                )
            args.brain = saved_brain
            saved_model = saved.get("model")
            if args.model is not None and saved_model is not None and args.model != saved_model:
                raise ValueError("A checkpoint must be resumed with its original model.")
            args.model = saved_model if saved_model is not None else args.model
            saved_effort = saved.get("reasoning_effort")
            if args.reasoning_effort is not None and saved_effort is not None and args.reasoning_effort != saved_effort:
                raise ValueError("A checkpoint must be resumed with its original reasoning effort.")
            args.reasoning_effort = saved_effort if saved_effort is not None else args.reasoning_effort
            saved_thinking_budget = saved.get("claude_thinking_budget_tokens")
            if (
                getattr(args, "claude_thinking_budget_tokens", None) is not None
                and saved_thinking_budget is not None
                and args.claude_thinking_budget_tokens != saved_thinking_budget
            ):
                raise ValueError("A checkpoint must be resumed with its original Claude thinking budget.")
            args.claude_thinking_budget_tokens = (
                saved_thinking_budget
                if saved_thinking_budget is not None
                else getattr(args, "claude_thinking_budget_tokens", None)
            )
        args.ticks = args.ticks if args.ticks is not None else int(saved.get("target_ticks") or engine.state.tick)
        args.agents = len(engine.state.agents)
        if args.out is None and saved.get("events_path"):
            args.out = Path(saved["events_path"])
        if args.snapshot is None and saved.get("snapshot_path"):
            args.snapshot = Path(saved["snapshot_path"])
        if args.max_workers is None and saved.get("max_workers") is not None:
            args.max_workers = int(saved["max_workers"])
        if not args.no_agent_io_log:
            args.no_agent_io_log = not bool(saved.get("log_agent_io", True))
        if not args.sequential_decisions:
            args.sequential_decisions = bool(saved.get("sequential_decisions", False))
        saved_observation_mode = saved.get("observation_mode") or "compact-v2"
        if (
            getattr(args, "observation_mode", None) is not None
            and args.observation_mode != saved_observation_mode
        ):
            raise ValueError(
                "A checkpoint must be resumed with its original observation mode."
            )
        for name in (
            "codex_max_workers",
            "claude_max_workers",
            "llm_max_workers",
            "decision_mode",
            "observation_mode",
        ):
            if getattr(args, name, None) is None and saved.get(name) is not None:
                setattr(args, name, saved[name])
    else:
        args.ticks = args.ticks if args.ticks is not None else 25
        preset_name = getattr(args, "preset", None) or "baseline"
        preset = RUN_PRESETS[preset_name]
        args.objective_mode = getattr(args, "objective_mode", None) or preset["objective_mode"]
        args.economy_mode = getattr(args, "economy_mode", None) or preset["economy_mode"]
        args.geography_mode = getattr(args, "geography_mode", None) or preset["geography_mode"]
        args.specialization_mode = getattr(args, "specialization_mode", None) or preset["specialization_mode"]
        args.decision_mode = getattr(args, "decision_mode", None) or "raw"
        args.observation_mode = getattr(args, "observation_mode", None) or "compact-v2"
        if getattr(args, "population", None):
            if args.brain is not None or args.model is not None:
                raise ValueError("Use either --population or --brain/--model, not both.")
            population_spec = PopulationSpec.parse_many(
                args.population,
                reasoning_effort=args.reasoning_effort,
                claude_thinking_budget_tokens=getattr(args, "claude_thinking_budget_tokens", None),
                max_workers=args.max_workers,
            )
            if args.agents is not None and args.agents != population_spec.total_agents:
                raise ValueError(
                    f"--agents={args.agents} conflicts with population total {population_spec.total_agents}"
                )
            args.agents = population_spec.total_agents
        else:
            args.brain = args.brain or "survival"
            args.agents = args.agents if args.agents is not None else 5
        config = WorldConfig(
            width=args.width,
            height=args.height,
            seed=args.seed,
            objective_mode=getattr(args, "objective_mode", "neutral"),
            economy_mode=getattr(args, "economy_mode", "baseline"),
            geography_mode=getattr(args, "geography_mode", "shared_oasis"),
            specialization_mode=getattr(args, "specialization_mode", "generalists"),
        )
        names = [f"Agent {index + 1}" for index in range(args.agents)]
        engine = WorldEngine.create(config=config, agent_names=names)

        assignment_manifest = getattr(args, "assignment_from_manifest", None)
        if assignment_manifest is not None:
            if population_spec is None:
                raise ValueError("--assignment-from-manifest requires --population")
            population_spec = _population_with_manifest_assignments(
                population_spec,
                assignment_manifest,
                set(engine.state.agents),
            )
            if args.assignment_strategy is not None and args.assignment_strategy != population_spec.assignment_strategy:
                raise ValueError("--assignment-strategy conflicts with the source manifest")
            if args.assignment_seed is not None and args.assignment_seed != population_spec.assignment_seed:
                raise ValueError("--assignment-seed conflicts with the source manifest")

    if args.ticks < engine.state.tick:
        raise ValueError(
            f"Target tick {args.ticks} is behind checkpoint tick {engine.state.tick}. "
            "Use --ticks with an equal or larger total target."
        )

    if population_spec is None:
        brain_spec = BrainSpec.resolve(
            args.brain,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            thinking_budget_tokens=(
                getattr(args, "claude_thinking_budget_tokens", None)
                if args.brain == "claude"
                else None
            ),
            max_workers=args.max_workers,
        )
        population_spec = PopulationSpec.uniform(len(engine.state.agents), brain_spec)
    else:
        brain_spec = population_spec.groups[0].brain
    if not population_spec.assigned_groups:
        assignment_strategy = getattr(args, "assignment_strategy", None) or (
            "stratified" if population_spec.mixed else "ordered"
        )
        raw_assignment_seed = getattr(args, "assignment_seed", None)
        assignment_seed = raw_assignment_seed if raw_assignment_seed is not None else engine.state.config.seed
        population_spec = population_spec.bind_assignments(
            engine, strategy=assignment_strategy, seed=assignment_seed
        )
    max_workers = args.max_workers or max(
        group.brain.max_workers or 1 for group in population_spec.groups
    )
    args.model = brain_spec.model if not population_spec.mixed else None
    args.reasoning_effort = brain_spec.reasoning_effort if not population_spec.mixed else None
    args.max_workers = max_workers
    provider_max_workers = {
        "codex_cli": int(getattr(args, "codex_max_workers", None) or min(max_workers, 4)),
        "claude_cli": int(getattr(args, "claude_max_workers", None) or min(max_workers, 4)),
        "openai_compatible": int(getattr(args, "llm_max_workers", None) or min(max_workers, 2)),
    }
    decision_mode = args.decision_mode or "raw"
    observation_mode = args.observation_mode or "compact-v2"
    usage_path: Path | None = None
    initial_usage: list[dict[str, Any]] = []
    if population_spec.model_backed and args.out:
        usage_path = args.out.with_name(args.out.stem + "-usage.jsonl")
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        if resumed:
            initial_usage = _read_jsonl_records(usage_path)
            _atomic_write_text(
                usage_path,
                "".join(json.dumps(record, sort_keys=True) + "\n" for record in initial_usage),
            )
        else:
            usage_path.write_text("", encoding="utf-8")
    runtime = BrainRuntime(usage_path, initial_records=initial_usage)

    checkpoint_path = getattr(args, "checkpoint", None)
    if checkpoint_path is None:
        checkpoint_path = resume_checkpoint
    if checkpoint_path is None and args.out is not None:
        checkpoint_path = args.out.with_name(args.out.stem + "-checkpoint.pkl")
    run_writer = IncrementalRunWriter(
        args.out,
        args.snapshot,
        checkpoint_path=checkpoint_path,
        truncate_events=not resumed,
    )
    if resumed:
        run_writer.rebase(engine)
    lifecycle_metadata = {
        "preset": getattr(args, "preset", None) or "baseline",
        "objective_mode": engine.state.config.objective_mode,
        "economy_mode": engine.state.config.economy_mode,
        "geography_mode": engine.state.config.geography_mode,
        "specialization_mode": engine.state.config.specialization_mode,
        "decision_mode": decision_mode,
        "observation_mode": observation_mode,
        "provider_max_workers": provider_max_workers,
        "provider_settings": _provider_settings(population_spec),
        "assignment_source_manifest": (
            str(args.assignment_from_manifest) if getattr(args, "assignment_from_manifest", None) else None
        ),
    }

    if not resumed:
        cohort_text = ", ".join(
            f"{group.count} {group.brain.model or group.brain.type}"
            for group in population_spec.groups
        )
        print(
            f"Starting {population_spec.total_agents}-agent {population_spec.run_type} run | "
            f"world={engine.state.config.economy_mode}/{engine.state.config.geography_mode}/"
            f"{engine.state.config.specialization_mode}/{engine.state.config.objective_mode} | population={cohort_text} | "
            f"ticks={args.ticks} | assignment={population_spec.assignment_strategy}:"
            f"{population_spec.assignment_seed} | harness={decision_mode}/{observation_mode}",
            flush=True,
        )

    session: SimulationSession

    def session_checkpoint_extra(current: SimulationSession) -> dict[str, Any]:
        return {
            "run": {
                "brain": population_spec.run_type,
                "model": brain_spec.model if not population_spec.mixed else None,
                "reasoning_effort": brain_spec.reasoning_effort if not population_spec.mixed else None,
                "claude_thinking_budget_tokens": (
                    brain_spec.thinking_budget_tokens if not population_spec.mixed else None
                ),
                "population": population_spec.to_dict(engine.state.agents),
                "target_ticks": args.ticks,
                "events_path": str(args.out.resolve()) if args.out else None,
                "snapshot_path": str(args.snapshot.resolve()) if args.snapshot else None,
                "max_workers": max_workers,
                "codex_max_workers": provider_max_workers["codex_cli"],
                "claude_max_workers": provider_max_workers["claude_cli"],
                "llm_max_workers": provider_max_workers["openai_compatible"],
                "decision_mode": decision_mode,
                "observation_mode": observation_mode,
                "log_agent_io": not args.no_agent_io_log,
                "sequential_decisions": args.sequential_decisions,
            },
            "plan_usage_checkpoints": current.plan_usage_checkpoints,
        }

    def on_tick(current: SimulationSession, _events: list[Any]) -> None:
        if args.progress:
            print(f"completed tick {current.engine.state.tick}/{args.ticks}", flush=True)

    plan_usage_path = (
        args.out.with_name(args.out.stem + "-plan-usage.json")
        if args.out and any(group.brain.type == "codex" for group in population_spec.groups)
        else None
    )
    report_stem = args.out.with_name(args.out.stem) if args.out else None
    manifest_path = args.out.with_name(args.out.stem + "-manifest.json") if args.out else None
    run_manifest = _ordinary_run_manifest(
        engine=engine,
        population=population_spec,
        args=args,
        provider_max_workers=provider_max_workers,
        decision_mode=decision_mode,
        observation_mode=observation_mode,
        events_path=args.out,
        snapshot_path=args.snapshot,
        checkpoint_path=checkpoint_path,
        report_stem=report_stem,
    )
    if manifest_path is not None:
        atomic_write_json(manifest_path, run_manifest)
    session = SimulationSession(
        engine=engine,
        brain_spec=brain_spec,
        runtime=runtime,
        writer=run_writer,
        target_ticks=args.ticks,
        brains=create_population_brains(engine, population_spec, runtime),
        population_spec=population_spec,
        max_workers=max_workers,
        provider_max_workers=provider_max_workers,
        decision_mode=decision_mode,
        observation_mode=observation_mode,
        log_agent_io=not args.no_agent_io_log,
        concurrent_decisions=not args.sequential_decisions and max_workers > 1,
        lifecycle_metadata=lifecycle_metadata,
        resumed=resumed,
        checkpoint_extra=session_checkpoint_extra,
        on_tick=on_tick,
        report_stem=report_stem,
        plan_usage_path=plan_usage_path,
        plan_usage_checkpoints=list(checkpoint_extra.get("plan_usage_checkpoints") or []),
    )
    result = session.run()

    metrics = compute_metrics(engine.state)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    if result.stop_reason:
        print(f"Run {result.status}: {result.stop_reason}")
    if result.error:
        print(result.error)
    if args.out:
        print(f"Wrote event log to {args.out}")
    if args.snapshot:
        print(f"Wrote snapshot to {args.snapshot}")
    if checkpoint_path:
        print(f"Wrote crash checkpoint to {checkpoint_path}")
    durable_usage = _read_jsonl_records(usage_path) if usage_path is not None else []
    usage_records = _merge_usage_records(durable_usage, result.usage_records)
    if usage_path is not None and usage_records:
        _atomic_write_text(
            usage_path,
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in usage_records),
        )
    if population_spec.model_backed:
        _report_llm_usage(args, engine.state.tick, usage_records)
    if result.plan_usage:
        print("Codex plan usage summary:")
        print(json.dumps(result.plan_usage, indent=2, sort_keys=True))
    if args.out:
        print(f"Wrote run report to {report_stem}-report.json and {report_stem}-report.md")
    if manifest_path is not None:
        run_manifest.update(
            {
                "status": result.status,
                "final_tick": result.final_tick,
                "stop_reason": result.stop_reason,
                "error": result.error,
                "ended_at_utc": datetime.now(timezone.utc).isoformat(),
                "resolved_models": dict(
                    sorted(
                        __import__("collections").Counter(
                            str(record.get("response_model") or record.get("model") or "unknown")
                            for record in usage_records
                        ).items()
                    )
                ),
                "provider_context_parity": _provider_context_parity(usage_records),
            }
        )
        atomic_write_json(manifest_path, run_manifest)
        print(f"Wrote run manifest to {manifest_path}")


def _ordinary_run_manifest(
    *,
    engine: WorldEngine,
    population: PopulationSpec,
    args: argparse.Namespace,
    provider_max_workers: dict[str, int],
    decision_mode: str,
    observation_mode: str,
    events_path: Path | None,
    snapshot_path: Path | None,
    checkpoint_path: Path | None,
    report_stem: Path | None,
) -> dict[str, Any]:
    try:
        git_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        git_sha, dirty = None, None
    return {
        "schema_version": 1,
        "status": "running",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_ticks": args.ticks,
        "final_tick": engine.state.tick,
        "preset": getattr(args, "preset", None) or "baseline",
        "decision_mode": decision_mode,
        "observation_mode": observation_mode,
        "command": ["python3", "-m", "agent_world.cli", *sys.argv[1:]],
        "config": asdict(engine.state.config),
        "population": population.to_dict(engine.state.agents),
        "assignment_source_manifest": (
            str(args.assignment_from_manifest) if getattr(args, "assignment_from_manifest", None) else None
        ),
        "concurrency": {"global": args.max_workers, "providers": provider_max_workers},
        "provider_settings": _provider_settings(population),
        "provenance": {"git_sha": git_sha, "dirty_worktree": dirty},
        "outputs": {
            "events": str(events_path) if events_path else None,
            "snapshot": str(snapshot_path) if snapshot_path else None,
            "checkpoint": str(checkpoint_path) if checkpoint_path else None,
            "report_json": f"{report_stem}-report.json" if report_stem else None,
            "report_markdown": f"{report_stem}-report.md" if report_stem else None,
        },
    }


def _provider_context_parity(records: list[dict[str, Any]]) -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}
    for provider in sorted({str(record.get("provider") or "unknown") for record in records}):
        provider_records = [record for record in records if str(record.get("provider") or "unknown") == provider]
        providers[provider] = {
            "records": len(provider_records),
            "formats": sorted({str(record.get("game_context_format")) for record in provider_records if record.get("game_context_format")}),
            "static_context_sha256": sorted({str(record.get("game_static_context_sha256")) for record in provider_records if record.get("game_static_context_sha256")}),
        }
    static_sets = [tuple(provider["static_context_sha256"]) for provider in providers.values() if provider["static_context_sha256"]]
    format_sets = [tuple(provider["formats"]) for provider in providers.values() if provider["formats"]]
    return {
        "providers": providers,
        "same_static_game_context": len(set(static_sets)) <= 1 if static_sets else None,
        "same_context_format": len(set(format_sets)) <= 1 if format_sets else None,
    }


def _provider_settings(population: PopulationSpec) -> dict[str, Any]:
    claude_budgets = sorted(
        {
            int(group.brain.thinking_budget_tokens or 0)
            for group in population.groups
            if group.brain.type == "claude"
        }
    )
    return {
        "claude_cli": {"thinking_budget_tokens": claude_budgets}
        if claude_budgets
        else None
    }


def _population_with_manifest_assignments(
    requested: PopulationSpec,
    manifest_path: Path,
    agent_ids: set[str],
) -> PopulationSpec:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_population = payload.get("population") if isinstance(payload, dict) else None
    if not isinstance(raw_population, dict):
        raise ValueError("assignment manifest is missing population metadata")
    source = PopulationSpec.from_dict(raw_population)
    requested_signatures = [
        (group.id, group.count, group.brain.type, group.brain.model)
        for group in requested.groups
    ]
    source_signatures = [
        (group.id, group.count, group.brain.type, group.brain.model)
        for group in source.groups
    ]
    if requested_signatures != source_signatures:
        raise ValueError("assignment manifest cohort ids, counts, brain types, or models do not match")
    assigned_ids = {agent_id for agent_id, _group_id in source.assigned_groups}
    if assigned_ids != agent_ids:
        raise ValueError("assignment manifest agent ids do not match the new world")
    return PopulationSpec(
        requested.groups,
        assignment_strategy=source.assignment_strategy,
        assignment_seed=source.assignment_seed,
        assigned_groups=source.assigned_groups,
    )


def _report_llm_usage(args: argparse.Namespace, ticks_completed: int, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    usage_path = args.out.with_name(args.out.stem + "-usage.jsonl") if args.out else None
    total_cost = sum(record.get("cost") or 0 for record in records)
    prompt_tokens = sum(record.get("prompt_tokens") or 0 for record in records)
    cached_tokens = sum(record.get("cached_tokens") or 0 for record in records)
    completion_tokens = sum(record.get("completion_tokens") or 0 for record in records)
    reasoning_tokens = sum(record.get("reasoning_tokens") or 0 for record in records)
    summary = {
        "calls": len(records),
        "ticks_completed": ticks_completed,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_call_usd": round(total_cost / len(records), 6),
        "cost_per_tick_usd": round(total_cost / ticks_completed, 6) if ticks_completed else None,
        "prompt_tokens": prompt_tokens,
        "cached_prompt_tokens": cached_tokens,
        "cache_hit_rate_pct": round(100 * cached_tokens / prompt_tokens, 1) if prompt_tokens else 0,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "simulation_credits": summarize_codex_simulation_credits(records),
    }
    print("LLM usage summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if usage_path:
        print(f"Wrote per-call usage records to {usage_path}")


def _report(args: argparse.Namespace) -> None:
    reports = []
    for path in args.paths:
        stem = path.with_name(path.stem)
        events, snapshot, usage_records = load_run_files(stem)
        reports.append(write_report(events, snapshot, usage_records, stem))
        print(f"Wrote {stem}-report.json and {stem}-report.md")
    if len(reports) > 1:
        print()
        print(format_comparison(reports))


def _experiment(args: argparse.Namespace) -> None:
    load_dotenv()
    environments = ["baseline", "commerce"] if args.environment == "all" else [args.environment]
    objectives = ["collective", "individual"] if args.objective == "all" else [args.objective]
    out_dir = args.out_dir or _default_experiment_dir()

    def progress(row: dict[str, Any]) -> None:
        if args.progress:
            print(
                f"{row['run_id']}: completed tick {row['tick']}/{row['target_ticks']}",
                flush=True,
            )

    manifest = run_factorial_experiment(
        out_dir=out_dir,
        seeds=args.seeds,
        ticks=args.ticks,
        agents=args.agents,
        brain=args.brain,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        environments=environments,
        objectives=objectives,
        width=args.width,
        height=args.height,
        log_agent_io=not args.no_agent_io_log,
        max_workers=args.max_workers,
        overwrite=args.overwrite,
        progress_callback=progress,
    )
    aggregate = manifest["aggregate_summary"]
    print(
        f"Experiment {manifest['status']}: {aggregate['valid_run_count']}/{aggregate['run_count']} "
        f"runs valid for analysis; LLM cost ${aggregate['total_llm_cost_usd']:.6f}."
    )
    print(f"Wrote experiment manifest to {manifest['outputs']['manifest']}")
    print(f"Wrote aggregate summary to {manifest['outputs']['summary_json']}")


def _replay(args: argparse.Namespace) -> None:
    events = read_events(args.path)
    for event in events[-args.last :]:
        print(format_event(event))


def _prompt(args: argparse.Namespace) -> None:
    config = WorldConfig(
        width=args.width,
        height=args.height,
        seed=args.seed,
        objective_mode=args.objective_mode,
        economy_mode=args.economy_mode,
        geography_mode=args.geography_mode,
    )
    names = [f"Agent {index + 1}" for index in range(args.agents)]
    engine = WorldEngine.create(config=config, agent_names=names)
    observation: dict[str, Any] = build_observation(
        engine.state, args.agent, observation_mode=args.observation_mode
    )
    print(build_agent_prompt(observation))


def _map(args: argparse.Namespace) -> None:
    config = WorldConfig(width=args.width, height=args.height)
    engine = WorldEngine.create(config=config, agent_names=[])
    print("Legend: . plains, F forest, M mountain, W water")
    print(render_tiles(engine.state.tiles))


def _view(args: argparse.Namespace) -> None:
    serve_observer(snapshot_path=args.snapshot, events_path=args.events, host=args.host, port=args.port)


def _ablate(args: argparse.Namespace) -> None:
    load_dotenv()
    runtime = BrainRuntime()

    def brain_factory(_agent_id: str) -> AgentBrain:
        if args.brain == "llm":
            return OpenAIBrain(model=args.model, reasoning_effort=args.reasoning_effort, runtime=runtime)
        if args.brain == "codex":
            return CodexBrain(model=args.model, reasoning_effort=args.reasoning_effort, runtime=runtime)
        if args.brain == "claude":
            return ClaudeBrain(model=args.model, reasoning_effort=args.reasoning_effort, runtime=runtime)
        return SurvivalBrain()

    results = run_ablation(
        agents=args.agents,
        ticks=args.ticks,
        seed=args.seed,
        brain_factory=brain_factory,
    )
    print(f"Ablation sweep (brain={args.brain}, agents={args.agents}, seed={args.seed}, baseline ticks={args.ticks})")
    print("builds/buildable are only meaningful with an LLM brain; lifespan/spare capacity are model-independent.\n")
    print(format_table(results))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(args.out, json.dumps({name: row for name, row in results}, indent=2, sort_keys=True))
        print(f"\nWrote rows to {args.out}")


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _merge_usage_records(*record_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for records in record_sets:
        for record in records:
            identity = json.dumps(record, sort_keys=True, separators=(",", ":"))
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(record)
    return merged


def _default_experiment_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("runs") / "experiments" / stamp


if __name__ == "__main__":
    main()
