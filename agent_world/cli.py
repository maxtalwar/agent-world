"""Command line tools for running and inspecting Agent World."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from agent_world.ablation import format_table, run_ablation
from agent_world.agents import AgentBrain, SurvivalBrain
from agent_world.env import load_dotenv
from agent_world.experiments import run_factorial_experiment
from agent_world.interface import build_agent_prompt, build_observation
from agent_world.maps import render_tiles
from agent_world.metrics import compute_metrics, is_quota_failure_message
from agent_world.models import WorldConfig
from agent_world.openai_brain import OpenAIBrain
from agent_world.observer import serve_observer
from agent_world.replay import format_event, read_events
from agent_world.run_report import format_comparison, load_run_files, write_report
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="agent-world")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a deterministic simulation.")
    run_parser.add_argument("--ticks", type=int, default=25)
    run_parser.add_argument("--agents", type=int, default=5)
    run_parser.add_argument("--seed", type=int, default=1)
    run_parser.add_argument("--width", type=int, default=16)
    run_parser.add_argument("--height", type=int, default=16)
    run_parser.add_argument("--objective-mode", choices=["neutral", "collective", "individual"], default="neutral")
    run_parser.add_argument("--economy-mode", choices=["baseline", "commerce", "organic"], default="baseline")
    run_parser.add_argument("--geography-mode", choices=["shared_oasis", "dispersed"], default="shared_oasis")
    run_parser.add_argument("--brain", choices=["survival", "llm"], default="survival")
    run_parser.add_argument("--model", default=None, help="OpenAI model for --brain llm. Defaults to OPENAI_MODEL.")
    run_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=None,
        help="Reasoning effort for --brain llm. Defaults to OPENAI_REASONING_EFFORT.",
    )
    run_parser.add_argument("--out", type=Path, default=None)
    run_parser.add_argument("--snapshot", type=Path, default=None)
    run_parser.add_argument("--no-agent-io-log", action="store_true", help="Do not log private observations/prompts.")
    run_parser.add_argument("--sequential-decisions", action="store_true", help="Disable same-tick concurrent brain calls.")
    run_parser.add_argument("--max-workers", type=int, default=None, help="Maximum same-tick brain calls. For LLM runs, defaults to OPENAI_MAX_PARALLEL_AGENTS or 1.")
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
    ablate_parser.add_argument("--brain", choices=["survival", "llm"], default="survival")
    ablate_parser.add_argument("--model", default=None)
    ablate_parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"], default=None)
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
        choices=["survival", "llm"],
        default="survival",
        help="Defaults to the free local scripted brain. LLM calls occur only when explicitly selected.",
    )
    experiment_parser.add_argument("--model", default=None)
    experiment_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
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
    if args.brain == "llm":
        OpenAIBrain.reset_runtime_state()
    if args.brain == "llm" and args.out:
        usage_path = args.out.with_name(args.out.stem + "-usage.jsonl")
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        usage_path.write_text("", encoding="utf-8")
        os.environ["AGENT_WORLD_USAGE_LOG"] = str(usage_path)
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
    brains = _make_brains(engine, args)
    runner = SimulationRunner(
        engine,
        brains,
        log_agent_io=not args.no_agent_io_log,
        concurrent_decisions=not args.sequential_decisions and _max_workers(args) != 1,
        max_workers=_max_workers(args),
    )
    engine.log_event(
        "run_started",
        message=f"Started {args.brain} run with {args.agents} agents.",
        data={
            "brain": args.brain,
            "agents": args.agents,
            "seed": args.seed,
            "target_ticks": args.ticks,
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "objective_mode": getattr(args, "objective_mode", "neutral"),
            "economy_mode": getattr(args, "economy_mode", "baseline"),
            "geography_mode": getattr(args, "geography_mode", "shared_oasis"),
        },
        scope="public",
    )
    stopped_reason: str | None = None
    for _ in range(args.ticks):
        events = runner.step()
        if _contains_quota_failure(events):
            stopped_reason = "OpenAI quota is unavailable; stopped early so the run is not mistaken for agent behavior."
            engine.log_event(
                "run_stopped",
                message=stopped_reason,
                data={"reason": "insufficient_quota", "target_ticks": args.ticks},
                scope="public",
            )
        if args.progress:
            print(f"completed tick {engine.state.tick}/{args.ticks}", flush=True)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(args.out, engine.export_events_jsonl() + "\n")
        if args.snapshot:
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(args.snapshot, json.dumps(engine.snapshot(), indent=2, sort_keys=True))
        if stopped_reason:
            break

    if stopped_reason is None:
        engine.log_event(
            "run_completed",
            message=f"Completed {args.ticks} target ticks.",
            data={"target_ticks": args.ticks},
            scope="public",
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(args.out, engine.export_events_jsonl() + "\n")
    if args.snapshot:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(args.snapshot, json.dumps(engine.snapshot(), indent=2, sort_keys=True))

    metrics = compute_metrics(engine.state)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    if stopped_reason:
        print(stopped_reason)
    if args.out:
        print(f"Wrote event log to {args.out}")
    if args.snapshot:
        print(f"Wrote snapshot to {args.snapshot}")
    if args.brain == "llm":
        _report_llm_usage(args, engine.state.tick)
    if args.out:
        usage_records = OpenAIBrain.usage_records() if args.brain == "llm" else []
        stem = args.out.with_name(args.out.stem)
        write_report(
            [json.loads(line) for line in engine.export_events_jsonl().splitlines() if line.strip()],
            engine.snapshot(),
            usage_records,
            stem,
            target_ticks=args.ticks,
        )
        print(f"Wrote run report to {stem}-report.json and {stem}-report.md")


def _report_llm_usage(args: argparse.Namespace, ticks_completed: int) -> None:
    records = OpenAIBrain.usage_records()
    if not records:
        return
    usage_path = None
    if args.out:
        usage_path = args.out.with_name(args.out.stem + "-usage.jsonl")
        _atomic_write_text(usage_path, "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n")
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

    def brain_factory(_agent_id: str) -> AgentBrain:
        if args.brain == "llm":
            return OpenAIBrain(model=args.model, reasoning_effort=args.reasoning_effort)
        return SurvivalBrain()

    results = run_ablation(
        agents=args.agents,
        ticks=args.ticks,
        seed=args.seed,
        brain_factory=brain_factory,
    )
    print(f"Ablation sweep (brain={args.brain}, agents={args.agents}, seed={args.seed}, baseline ticks={args.ticks})")
    print("builds/buildable are only meaningful with --brain llm; lifespan/spare capacity are model-independent.\n")
    print(format_table(results))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(args.out, json.dumps({name: row for name, row in results}, indent=2, sort_keys=True))
        print(f"\nWrote rows to {args.out}")


def _make_brains(engine: WorldEngine, args: argparse.Namespace) -> dict[str, AgentBrain]:
    if args.brain == "llm":
        return {
            agent_id: OpenAIBrain(model=args.model, reasoning_effort=args.reasoning_effort)
            for agent_id in engine.state.agents
        }
    return {agent_id: SurvivalBrain() for agent_id in engine.state.agents}


def _max_workers(args: argparse.Namespace) -> int | None:
    if args.max_workers is not None:
        return args.max_workers
    if args.brain == "llm":
        return int(os.environ.get("OPENAI_MAX_PARALLEL_AGENTS", "1"))
    return None


def _atomic_write_text(path: Path, text: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _default_experiment_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("runs") / "experiments" / stamp


def _contains_quota_failure(events: list[Any]) -> bool:
    return any(is_quota_failure_message(getattr(event, "type", None), getattr(event, "message", None)) for event in events)


if __name__ == "__main__":
    main()
