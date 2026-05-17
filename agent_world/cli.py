"""Command line tools for running and inspecting Agent World."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent_world.agents import AgentBrain, SurvivalBrain
from agent_world.env import load_dotenv
from agent_world.interface import build_agent_prompt, build_observation
from agent_world.metrics import compute_metrics
from agent_world.models import WorldConfig
from agent_world.openai_brain import OpenAIBrain
from agent_world.replay import format_event, read_events
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
    run_parser.add_argument("--brain", choices=["survival", "llm"], default="survival")
    run_parser.add_argument("--model", default=None, help="OpenAI model for --brain llm. Defaults to OPENAI_MODEL.")
    run_parser.add_argument("--out", type=Path, default=None)
    run_parser.add_argument("--snapshot", type=Path, default=None)
    run_parser.add_argument("--no-agent-io-log", action="store_true", help="Do not log private observations/prompts.")

    replay_parser = subparsers.add_parser("replay", help="Print events from a JSONL log.")
    replay_parser.add_argument("path", type=Path)
    replay_parser.add_argument("--last", type=int, default=50)

    prompt_parser = subparsers.add_parser("prompt", help="Print a neutral LLM prompt for an agent.")
    prompt_parser.add_argument("--seed", type=int, default=1)
    prompt_parser.add_argument("--agents", type=int, default=2)
    prompt_parser.add_argument("--agent", default="agent-1")
    prompt_parser.add_argument("--width", type=int, default=16)
    prompt_parser.add_argument("--height", type=int, default=16)

    args = parser.parse_args(argv)
    if args.command == "run":
        _run(args)
    elif args.command == "replay":
        _replay(args)
    elif args.command == "prompt":
        _prompt(args)


def _run(args: argparse.Namespace) -> None:
    load_dotenv()
    config = WorldConfig(width=args.width, height=args.height, seed=args.seed)
    names = [f"Agent {index + 1}" for index in range(args.agents)]
    engine = WorldEngine.create(config=config, agent_names=names)
    brains = _make_brains(engine, args)
    runner = SimulationRunner(engine, brains, log_agent_io=not args.no_agent_io_log)
    for _ in range(args.ticks):
        runner.step()

    metrics = compute_metrics(engine.state)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(engine.export_events_jsonl() + "\n", encoding="utf-8")
        print(f"Wrote event log to {args.out}")
    if args.snapshot:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(json.dumps(engine.snapshot(), indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote snapshot to {args.snapshot}")


def _replay(args: argparse.Namespace) -> None:
    events = read_events(args.path)
    for event in events[-args.last :]:
        print(format_event(event))


def _prompt(args: argparse.Namespace) -> None:
    config = WorldConfig(width=args.width, height=args.height, seed=args.seed)
    names = [f"Agent {index + 1}" for index in range(args.agents)]
    engine = WorldEngine.create(config=config, agent_names=names)
    observation: dict[str, Any] = build_observation(engine.state, args.agent)
    print(build_agent_prompt(observation))


def _make_brains(engine: WorldEngine, args: argparse.Namespace) -> dict[str, AgentBrain]:
    if args.brain == "llm":
        return {agent_id: OpenAIBrain(model=args.model) for agent_id in engine.state.agents}
    return {agent_id: SurvivalBrain() for agent_id in engine.state.agents}


if __name__ == "__main__":
    main()
