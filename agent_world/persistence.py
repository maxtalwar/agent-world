"""Crash-tolerant incremental run persistence."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import pickle
import tempfile
from typing import Any

from agent_world.io import atomic_write_json
from agent_world.models import Event, Position
from agent_world.world import WorldEngine


class IncrementalRunWriter:
    """Append each event once and atomically replace the current snapshot."""

    def __init__(
        self,
        events_path: Path | None,
        snapshot_path: Path | None,
        *,
        checkpoint_path: Path | None = None,
        fsync: bool = True,
        truncate_events: bool = True,
    ):
        self.events_path = events_path
        self.snapshot_path = snapshot_path
        self.checkpoint_path = checkpoint_path
        self.fsync = fsync
        self.event_offset = 0
        if self.events_path is not None:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            if truncate_events:
                self.events_path.write_text("", encoding="utf-8")
        if self.snapshot_path is not None:
            self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        if self.checkpoint_path is not None:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    def rebase(self, engine: WorldEngine) -> None:
        """Make an existing checkpoint's ledger the append baseline."""

        if self.events_path is not None:
            existing_count = _jsonl_line_count(self.events_path)
            if existing_count != len(engine.state.events):
                _atomic_write_event_log(self.events_path, engine.state.events, fsync=self.fsync)
        self.event_offset = len(engine.state.events)

    def flush(self, engine: WorldEngine, *, checkpoint_extra: dict[str, Any] | None = None) -> None:
        events = engine.state.events
        if self.event_offset > len(events):
            raise ValueError("Event ledger shrank after incremental writer initialization.")
        if self.events_path is not None and self.event_offset < len(events):
            with self.events_path.open("a", encoding="utf-8") as handle:
                for event in events[self.event_offset :]:
                    handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
                handle.flush()
                if self.fsync:
                    os.fsync(handle.fileno())
        self.event_offset = len(events)
        if self.snapshot_path is not None:
            atomic_write_json(self.snapshot_path, engine.snapshot(), fsync=True)
        if self.checkpoint_path is not None:
            checkpoint_engine = engine
            event_ledger: str | None = None
            if self.events_path is not None:
                # The append-only JSONL is already the durable history. Excluding
                # it from the checkpoint keeps per-tick checkpoint writes O(world
                # state) instead of growing with the complete run history.
                checkpoint_engine = copy.copy(engine)
                checkpoint_engine.state = copy.copy(engine.state)
                checkpoint_engine.state.events = []
                event_ledger = str(self.events_path.resolve())
            _atomic_write_pickle(
                self.checkpoint_path,
                {
                    "schema_version": 1,
                    "engine": checkpoint_engine,
                    "event_ledger": event_ledger,
                    "event_ledger_name": self.events_path.name if self.events_path is not None else None,
                    "event_count": len(events),
                    "extra": checkpoint_extra or {},
                },
            )


def load_run_checkpoint(path: Path) -> tuple[WorldEngine, dict[str, Any]]:
    """Load an explicitly selected local checkpoint.

    Checkpoints are Python pickles and must never be loaded from an untrusted
    source. The CLI only calls this function for a path the user supplies.
    """

    with path.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported Agent World checkpoint schema.")
    engine = payload.get("engine")
    if not isinstance(engine, WorldEngine):
        raise ValueError("Checkpoint does not contain a WorldEngine.")
    event_count = payload.get("event_count")
    event_ledger = payload.get("event_ledger")
    if event_ledger is not None:
        if not isinstance(event_count, int) or event_count < 0:
            raise ValueError("Checkpoint has an invalid event ledger length.")
        ledger_path = Path(event_ledger)
        if not ledger_path.exists() and payload.get("event_ledger_name"):
            ledger_path = path.parent / str(payload["event_ledger_name"])
        engine.state.events = _read_event_log(ledger_path, event_count)
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    return engine, extra


def _read_event_log(path: Path, expected_count: int) -> list[Event]:
    if not path.exists():
        raise ValueError(f"Checkpoint event ledger is missing: {path}")
    events: list[Event] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(events) >= expected_count:
                break
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Checkpoint event ledger is corrupt at event {len(events) + 1}.") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Checkpoint event ledger has a non-object event at {len(events) + 1}.")
            position = value.get("position")
            events.append(
                Event(
                    tick=int(value.get("tick", 0)),
                    type=str(value.get("type", "")),
                    actor_id=value.get("actor_id"),
                    position=(
                        Position(x=int(position["x"]), y=int(position["y"]))
                        if isinstance(position, dict)
                        else None
                    ),
                    message=str(value.get("message") or ""),
                    data=value.get("data") if isinstance(value.get("data"), dict) else {},
                    scope=str(value.get("scope") or "local"),
                    recipients=set(value.get("recipients") or []),
                )
            )
    if len(events) != expected_count:
        raise ValueError(
            f"Checkpoint requires {expected_count} events but its ledger contains only {len(events)}."
        )
    return events


def _jsonl_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def _atomic_write_event_log(path: Path, events: list[Event], *, fsync: bool) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _atomic_write_pickle(path: Path, value: Any) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
