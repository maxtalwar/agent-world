"""Command line tools for running and inspecting Agent World."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
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
from agent_world.interface import build_agent_prompt, build_observation
from agent_world.io import atomic_write_text as _atomic_write_text
from agent_world.maps import render_tiles
from agent_world.metrics import compute_metrics
from agent_world.models import WorldConfig
from agent_world.openai_brain import OpenAIBrain
from agent_world.observer import serve_observer
from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
from agent_world.replay import format_event, read_events
from agent_world.run_report import format_comparison, load_run_files, write_report
from agent_world.session import SimulationSession
from agent_world.usage import summarize_codex_simulation_credits
from agent_world.world import WorldEngine


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="agent-world")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a deterministic simulation.")
    run_parser.add_argument("--ticks", type=int, default=None, help="Total target tick. Defaults to 25, or the saved target when resuming.")
    run_parser.add_argument("--agents", type=int, default=None)
    run_parser.add_argument("--seed", type=int, default=1)
    run_parser.add_argument("--width", type=int, default=16)
    run_parser.add_argument("--height", type=int, default=16)
    run_parser.add_argument("--objective-mode", choices=["neutral", "collective", "individual"], default="neutral")
    run_parser.add_argument("--economy-mode", choices=["baseline", "commerce", "organic"], default="baseline")
    run_parser.add_argument("--geography-mode", choices=["shared_oasis", "dispersed"], default="shared_oasis")
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
    run_parser.add_argument("--out", type=Path, default=None)
    run_parser.add_argument("--snapshot", type=Path, default=None)
    run_parser.add_argument("--checkpoint", type=Path, default=None, help="Crash-resume checkpoint path. Derived from --out when omitted.")
    run_parser.add_argument("--resume-checkpoint", type=Path, default=None, help="Resume a trusted local checkpoint; --ticks may extend its total target.")
    run_parser.add_argument("--no-agent-io-log", action="store_true", help="Do not log private observations/prompts.")
    run_parser.add_argument("--sequential-decisions", action="store_true", help="Disable same-tick concurrent brain calls.")
    run_parser.add_argument("--max-workers", type=int, default=None, help="Maximum same-tick brain calls. Provider-backed brains default to one worker.")
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
    elif args.command == "experiment":
        _experiment(args)


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
            ):
                raise ValueError(
                    "A population-aware checkpoint must be resumed with its saved population; "
                    "omit --population, --brain, --model, and --reasoning-effort."
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
    else:
        args.ticks = args.ticks if args.ticks is not None else 25
        if getattr(args, "population", None):
            if args.brain is not None or args.model is not None:
                raise ValueError("Use either --population or --brain/--model, not both.")
            population_spec = PopulationSpec.parse_many(
                args.population,
                reasoning_effort=args.reasoning_effort,
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
        )
        names = [f"Agent {index + 1}" for index in range(args.agents)]
        engine = WorldEngine.create(config=config, agent_names=names)

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
            max_workers=args.max_workers,
        )
        population_spec = PopulationSpec.uniform(len(engine.state.agents), brain_spec)
    else:
        brain_spec = population_spec.groups[0].brain
    max_workers = args.max_workers or max(
        group.brain.max_workers or 1 for group in population_spec.groups
    )
    args.model = brain_spec.model if not population_spec.mixed else None
    args.reasoning_effort = brain_spec.reasoning_effort if not population_spec.mixed else None
    args.max_workers = max_workers
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
        "objective_mode": engine.state.config.objective_mode,
        "economy_mode": engine.state.config.economy_mode,
        "geography_mode": engine.state.config.geography_mode,
    }

    session: SimulationSession

    def session_checkpoint_extra(current: SimulationSession) -> dict[str, Any]:
        return {
            "run": {
                "brain": population_spec.run_type,
                "model": brain_spec.model if not population_spec.mixed else None,
                "reasoning_effort": brain_spec.reasoning_effort if not population_spec.mixed else None,
                "population": population_spec.to_dict(engine.state.agents),
                "target_ticks": args.ticks,
                "events_path": str(args.out.resolve()) if args.out else None,
                "snapshot_path": str(args.snapshot.resolve()) if args.snapshot else None,
                "max_workers": max_workers,
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
    session = SimulationSession(
        engine=engine,
        brain_spec=brain_spec,
        runtime=runtime,
        writer=run_writer,
        target_ticks=args.ticks,
        brains=create_population_brains(engine, population_spec, runtime),
        population_spec=population_spec,
        max_workers=max_workers,
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
    observation: dict[str, Any] = build_observation(engine.state, args.agent)
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
