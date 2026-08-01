"""Recover an earlier completed-tick checkpoint from a durable run ledger.

This module is intentionally conservative: it replays already-paid agent
decisions through the deterministic world engine, verifies the resulting event
stream against the original ledger, and writes a new recovery directory.  The
source checkpoint and its invalid tail are never modified.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable

from agent_world.models import AgentDecision, Event
from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
from agent_world.world import WorldEngine


_AGENT_INPUT_EVENT_TYPES = {
    "agent_observation",
    "agent_prompt",
    "agent_prompt_context",
}

# Events emitted by SimulationSession rather than WorldEngine.create/tick.
_HARNESS_EVENT_TYPES = _AGENT_INPUT_EVENT_TYPES | {
    "benchmark_checkpoint",
    "run_completed",
    "run_failed",
    "run_health_check",
    "run_paused",
    "run_quota_retry",
    "run_quota_wait",
    "run_resumed",
    "run_started",
    "run_stopped",
}


@dataclass(frozen=True)
class RecoveryResult:
    output_dir: Path
    checkpoint_path: Path
    events_path: Path
    snapshot_path: Path
    usage_path: Path | None
    discarded_usage_path: Path | None
    resume_tick: int
    replayed_world_events: int
    preserved_ledger_events: int
    state_sha256: str
    source_events_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "checkpoint_path": str(self.checkpoint_path),
            "events_path": str(self.events_path),
            "snapshot_path": str(self.snapshot_path),
            "usage_path": str(self.usage_path) if self.usage_path else None,
            "discarded_usage_path": (
                str(self.discarded_usage_path) if self.discarded_usage_path else None
            ),
            "resume_tick": self.resume_tick,
            "replayed_world_events": self.replayed_world_events,
            "preserved_ledger_events": self.preserved_ledger_events,
            "state_sha256": self.state_sha256,
            "source_events_sha256": self.source_events_sha256,
        }


def recover_completed_tick_checkpoint(
    source_checkpoint: Path,
    *,
    resume_tick: int,
    output_dir: Path,
) -> RecoveryResult:
    """Reconstruct and validate the state immediately before ``resume_tick``.

    ``resume_tick=32`` means ticks 0 through 31 are replayed and the returned
    checkpoint is ready to ask agents for tick 32. The destination must not
    contain files, which prevents accidental replacement of run evidence.
    """

    source_checkpoint = source_checkpoint.resolve()
    output_dir = output_dir.resolve()
    if resume_tick < 0:
        raise ValueError("resume_tick must be non-negative")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Recovery output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    source_checkpoint_sha256 = _sha256_file(source_checkpoint)
    source_engine, source_extra = load_run_checkpoint(source_checkpoint)
    if resume_tick >= source_engine.state.tick:
        raise ValueError(
            f"resume_tick={resume_tick} must be earlier than the source checkpoint "
            f"tick {source_engine.state.tick}"
        )

    source_events = list(source_engine.state.events)
    boundary = _recovery_boundary(source_events, resume_tick)
    preserved_events = source_events[:boundary]
    source_events_path = _source_events_path(source_checkpoint, source_extra)
    source_events_sha256 = _sha256_file(source_events_path)

    names = [agent.name for agent in source_engine.state.agents.values()]
    replay = WorldEngine.create(
        config=copy.deepcopy(source_engine.state.config),
        agent_names=names,
    )
    if list(replay.state.agents) != list(source_engine.state.agents):
        raise ValueError("Recreated agent IDs do not match the source checkpoint")

    decisions_by_tick = _decisions_by_tick(source_events, resume_tick)
    for tick in range(resume_tick):
        living = {
            agent_id for agent_id, agent in replay.state.agents.items() if agent.alive
        }
        decisions = decisions_by_tick.get(tick, {})
        if set(decisions) != living:
            missing = sorted(living - set(decisions))
            unexpected = sorted(set(decisions) - living)
            raise ValueError(
                f"Tick {tick} decision coverage does not match the living population; "
                f"missing={missing}, unexpected={unexpected}"
            )
        replay.tick(decisions)

    expected_world_events = [
        event
        for event in preserved_events
        if event.type not in _HARNESS_EVENT_TYPES
    ]
    _validate_replayed_events(replay.state.events, expected_world_events)

    # Preserve the original, interleaved audit history while retaining the
    # reconstructed world and RNG state. Future resume writes append to this
    # exact prefix in the new directory.
    replay.state.events = copy.deepcopy(preserved_events)
    state_sha256 = _snapshot_sha256(replay)

    events_path = output_dir / "run.jsonl"
    snapshot_path = output_dir / "run-snapshot.json"
    checkpoint_path = output_dir / "run-checkpoint.pkl"
    recovered_extra = _recovered_checkpoint_extra(
        source_extra,
        events_path=events_path,
        snapshot_path=snapshot_path,
        source_checkpoint=source_checkpoint,
        source_checkpoint_sha256=source_checkpoint_sha256,
        source_events_sha256=source_events_sha256,
        resume_tick=resume_tick,
        state_sha256=state_sha256,
        replayed_world_events=len(expected_world_events),
        preserved_ledger_events=len(preserved_events),
    )
    writer = IncrementalRunWriter(
        events_path,
        snapshot_path,
        checkpoint_path=checkpoint_path,
    )
    writer.flush(replay, checkpoint_extra=recovered_extra)

    usage_path, discarded_usage_path = _recover_usage_ledgers(
        source_events_path,
        output_dir,
        resume_tick,
    )
    _copy_existing_partial_usage_ledgers(source_events_path, output_dir)

    result = RecoveryResult(
        output_dir=output_dir,
        checkpoint_path=checkpoint_path,
        events_path=events_path,
        snapshot_path=snapshot_path,
        usage_path=usage_path,
        discarded_usage_path=discarded_usage_path,
        resume_tick=resume_tick,
        replayed_world_events=len(expected_world_events),
        preserved_ledger_events=len(preserved_events),
        state_sha256=state_sha256,
        source_events_sha256=source_events_sha256,
    )
    _atomic_write_json(output_dir / "recovery-manifest.json", result.to_dict())

    if _sha256_file(source_checkpoint) != source_checkpoint_sha256:
        raise RuntimeError("Source checkpoint changed during recovery")
    if _sha256_file(source_events_path) != source_events_sha256:
        raise RuntimeError("Source event ledger changed during recovery")
    return result


def _recovery_boundary(events: list[Event], resume_tick: int) -> int:
    for index, event in enumerate(events):
        if event.tick == resume_tick and event.type in (
            _AGENT_INPUT_EVENT_TYPES | {"agent_response"}
        ):
            return index
    raise ValueError(
        f"Could not find the beginning of attempted tick {resume_tick} in the event ledger"
    )


def _decisions_by_tick(
    events: Iterable[Event], resume_tick: int
) -> dict[int, dict[str, AgentDecision]]:
    decisions: dict[int, dict[str, AgentDecision]] = {}
    for event in events:
        if event.tick >= resume_tick or event.type != "agent_response":
            continue
        if not event.actor_id:
            raise ValueError(f"Tick {event.tick} agent_response has no actor")
        tick_decisions = decisions.setdefault(event.tick, {})
        if event.actor_id in tick_decisions:
            raise ValueError(
                f"Tick {event.tick} has duplicate decisions for {event.actor_id}"
            )
        tick_decisions[event.actor_id] = AgentDecision.from_json_like(event.data)
    return decisions


def _validate_replayed_events(actual: list[Event], expected: list[Event]) -> None:
    if len(actual) != len(expected):
        raise ValueError(
            f"Replay produced {len(actual)} world events; expected {len(expected)}"
        )
    for index, (actual_event, expected_event) in enumerate(zip(actual, expected)):
        actual_dict = _normalized_event(actual_event.to_dict())
        expected_dict = _normalized_event(expected_event.to_dict())
        if actual_dict != expected_dict:
            raise ValueError(
                "Replay diverged from the source ledger at world event "
                f"{index + 1}: actual={actual_dict!r}, expected={expected_dict!r}"
            )


def _normalized_event(value: dict[str, Any]) -> dict[str, Any]:
    """Normalize audited, state-neutral schema additions across compatible code."""

    value = copy.deepcopy(value)
    if value.get("type") == "gift" and (value.get("data") or {}).get("kind") == "gift":
        value["data"].pop("kind", None)
    return value


def _recovered_checkpoint_extra(
    source_extra: dict[str, Any],
    **recovery: Any,
) -> dict[str, Any]:
    extra = copy.deepcopy(source_extra)
    saved_run = extra.get("run") if isinstance(extra.get("run"), dict) else {}
    saved_run["events_path"] = str(recovery["events_path"])
    saved_run["snapshot_path"] = str(recovery["snapshot_path"])
    extra["run"] = saved_run
    # Provider sessions are never required to reconstruct completed world
    # state. Resume with fresh stateless sessions at the recovered boundary.
    extra["brain_states"] = {}
    extra["plan_usage_checkpoints"] = [
        row
        for row in (extra.get("plan_usage_checkpoints") or [])
        if int(row.get("simulation_tick", -1)) <= int(recovery["resume_tick"])
    ]
    extra["checkpoint_recovery"] = {
        "schema_version": 1,
        "method": "deterministic_decision_replay_with_event_validation",
        **{
            key: str(value) if isinstance(value, Path) else value
            for key, value in recovery.items()
        },
    }
    return extra


def _source_events_path(
    source_checkpoint: Path, source_extra: dict[str, Any]
) -> Path:
    saved_run = source_extra.get("run") if isinstance(source_extra.get("run"), dict) else {}
    saved_path = saved_run.get("events_path")
    if saved_path and Path(saved_path).exists():
        return Path(saved_path).resolve()
    fallback = source_checkpoint.with_name("run.jsonl")
    if fallback.exists():
        return fallback.resolve()
    raise ValueError("Could not locate the source event ledger")


def _recover_usage_ledgers(
    source_events_path: Path,
    output_dir: Path,
    resume_tick: int,
) -> tuple[Path | None, Path | None]:
    source_usage_path = source_events_path.with_name(
        source_events_path.stem + "-usage.jsonl"
    )
    if not source_usage_path.exists():
        return None, None
    records = _read_jsonl(source_usage_path)
    retained: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []
    for record in records:
        tick = record.get("tick")
        if isinstance(tick, int) and tick >= resume_tick:
            discarded.append(record)
        else:
            retained.append(record)

    usage_path = output_dir / "run-usage.jsonl"
    _atomic_write_jsonl(usage_path, retained)
    discarded_path: Path | None = None
    if discarded:
        discarded_path = output_dir / f"run-usage-partial-tick-{resume_tick}.jsonl"
        _atomic_write_jsonl(discarded_path, discarded)
    return usage_path, discarded_path


def _copy_existing_partial_usage_ledgers(
    source_events_path: Path, output_dir: Path
) -> None:
    pattern = source_events_path.stem + "-usage-partial-tick-*.jsonl"
    for source in source_events_path.parent.glob(pattern):
        destination = output_dir / source.name
        if destination.exists():
            continue
        shutil.copy2(source, destination)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} line {index} is not an object")
            records.append(value)
    return records


def _snapshot_sha256(engine: WorldEngine) -> str:
    payload = json.dumps(
        engine.snapshot(), separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _atomic_write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    _atomic_write_text(
        path,
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
    )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover a completed-tick checkpoint by replaying stored decisions."
    )
    parser.add_argument("--source-checkpoint", type=Path, required=True)
    parser.add_argument(
        "--resume-tick",
        type=int,
        required=True,
        help="Tick to attempt next; decisions before this tick are replayed.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = recover_completed_tick_checkpoint(
        args.source_checkpoint,
        resume_tick=args.resume_tick,
        output_dir=args.output_dir,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
