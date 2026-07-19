"""Replay helpers for JSONL event logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_events(path: str | Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def format_event(event: dict[str, Any]) -> str:
    actor = event.get("actor_id") or "world"
    message = event.get("message") or ""
    data = event.get("data") or {}
    suffix = ""
    if event.get("type") in {
        "invalid_action",
        "contention_failure",
        "offer_trade",
        "accept_trade",
        "build",
        "claim_tile",
    }:
        suffix = f" {json.dumps(data, sort_keys=True)}"
    return f"[tick {event.get('tick')}] {event.get('type')} {actor}: {message}{suffix}"
