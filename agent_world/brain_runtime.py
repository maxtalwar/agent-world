"""Run-scoped mutable state shared by every brain in one simulation."""

from __future__ import annotations

from collections import Counter
import hashlib
import uuid
import json
from pathlib import Path
import threading
import time
from typing import Any

from agent_world.usage import append_usage_record, append_usage_records, replace_usage_records


class BrainRuntime:
    """Own usage, quota, and throttling state for exactly one run.

    Brain instances are intentionally lightweight and may be created once per
    agent. Sharing this object between them preserves provider-wide throttling
    without leaking state into another run in the same Python process.
    """

    def __init__(
        self,
        usage_path: Path | None = None,
        *,
        initial_records: list[dict[str, Any]] | None = None,
        provider_events_path: Path | None = None,
        truncate_provider_events: bool = True,
    ):
        self.usage_path = usage_path
        self.provider_events_path = (
            provider_events_path or provider_events_path_for_usage(usage_path)
        )
        self._lock = threading.RLock()
        self._usage_records = [dict(record) for record in (initial_records or [])]
        self.run_identity = next((str(row["run_identity"]) for row in self._usage_records if row.get("run_identity")), uuid.uuid4().hex)
        self._provider_event_records: list[dict[str, Any]] = []
        if self.provider_events_path is not None:
            self.provider_events_path.parent.mkdir(parents=True, exist_ok=True)
            if truncate_provider_events:
                self.provider_events_path.write_text("", encoding="utf-8")
            else:
                self._provider_event_records = _read_jsonl_records(
                    self.provider_events_path
                )
        self._blocking_failures: dict[str, tuple[str, str]] = {}
        self._next_allowed_at: dict[str, float] = {}

    def record_usage(self, record: dict[str, Any]) -> None:
        item = dict(record)
        item.setdefault("record_id", uuid.uuid4().hex)
        item.setdefault("run_identity", self.run_identity)
        if item.get("agent_id") is not None and item.get("tick") is not None:
            identity = json.dumps([self.run_identity, item["tick"], item["agent_id"]])
            item.setdefault("logical_decision_id", hashlib.sha256(identity.encode()).hexdigest())
        item.setdefault("model_provenance", "observed" if item.get("response_model") else "requested_only")
        with self._lock:
            append_usage_record(item, self.usage_path)
            self._usage_records.append(item)

    def usage_records(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(record) for record in self._usage_records]

    def record_provider_event(self, record: dict[str, Any]) -> None:
        """Persist one exceptional provider attempt.

        Successful requests already have the usage ledger. This deliberately
        records only exceptional attempts so diagnostic telemetry stays tiny.
        """

        item = dict(record)
        with self._lock:
            append_usage_record(item, self.provider_events_path)
            self._provider_event_records.append(item)

    def provider_event_records(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(record) for record in self._provider_event_records]

    def provider_event_summary(self) -> dict[str, int]:
        with self._lock:
            counts = Counter(
                str(record.get("event_type") or "unknown")
                for record in self._provider_event_records
            )
        return dict(sorted(counts.items()))

    def usage_checkpoint(self) -> int:
        """Return a rollback marker for the current completed-tick ledger."""

        with self._lock:
            return len(self._usage_records)

    def rollback_usage(self, checkpoint: int, *, attempted_tick: int) -> Path | None:
        """Exclude partial-tick calls while preserving them in an audit ledger."""

        with self._lock:
            if checkpoint < 0 or checkpoint > len(self._usage_records):
                raise ValueError("Invalid usage rollback checkpoint.")
            kept = [dict(record) for record in self._usage_records[:checkpoint]]
            partial = [dict(record) for record in self._usage_records[checkpoint:]]
            if self.usage_path is None or not partial:
                self._usage_records = kept
                return None
            partial_path = self.usage_path.with_name(
                f"{self.usage_path.stem}-partial-tick-{attempted_tick}{self.usage_path.suffix}"
            )
            append_usage_records(partial, partial_path)
            replace_usage_records(kept, self.usage_path)
            self._usage_records = kept
            return partial_path

    def quota_message(self, scope: str = "default") -> str | None:
        with self._lock:
            failure = self._blocking_failures.get(scope)
            return failure[1] if failure is not None and failure[0] == "quota" else None

    def mark_quota_unavailable(self, message: str, scope: str = "default") -> None:
        with self._lock:
            self._blocking_failures[scope] = ("quota", message)

    def authentication_message(self, scope: str = "default") -> str | None:
        with self._lock:
            failure = self._blocking_failures.get(scope)
            return (
                failure[1]
                if failure is not None and failure[0] == "authentication"
                else None
            )

    def mark_authentication_required(
        self, message: str, scope: str = "default"
    ) -> None:
        with self._lock:
            self._blocking_failures[scope] = ("authentication", message)

    def blocking_failure(self, scope: str = "default") -> tuple[str, str] | None:
        """Return a persistent provider blocker for this run and scope.

        Only quota and authentication are persistent. Transient rate limits,
        timeouts, and transport/provider faults must never enter this circuit:
        the runner retries only their unresolved agents while the world stays
        frozen.
        """

        with self._lock:
            return self._blocking_failures.get(scope)

    def clear_quota_unavailable(self, scope: str | None = None) -> None:
        """Forget cached quota exhaustion so the next call reaches the provider."""

        with self._lock:
            if scope is None:
                self._blocking_failures = {
                    key: failure
                    for key, failure in self._blocking_failures.items()
                    if failure[0] != "quota"
                }
            else:
                failure = self._blocking_failures.get(scope)
                if failure is not None and failure[0] == "quota":
                    self._blocking_failures.pop(scope, None)

    def clear_authentication_required(self, scope: str | None = None) -> None:
        with self._lock:
            if scope is None:
                self._blocking_failures = {
                    key: failure
                    for key, failure in self._blocking_failures.items()
                    if failure[0] != "authentication"
                }
            else:
                failure = self._blocking_failures.get(scope)
                if failure is not None and failure[0] == "authentication":
                    self._blocking_failures.pop(scope, None)

    def throttle(self, minimum_interval_seconds: float, scope: str = "default") -> None:
        if minimum_interval_seconds <= 0:
            return
        with self._lock:
            now = time.monotonic()
            next_allowed_at = self._next_allowed_at.get(scope, 0.0)
            reserved_at = max(now, next_allowed_at)
            self._next_allowed_at[scope] = reserved_at + minimum_interval_seconds
        # Reserving is serialized; waiting must not block other providers or telemetry.
        if reserved_at > now:
            time.sleep(reserved_at - now)

    def scoped(self, scope: str) -> "ScopedBrainRuntime":
        """Return a provider-isolated view backed by this run's usage ledger."""

        return ScopedBrainRuntime(self, scope)


class ScopedBrainRuntime:
    """BrainRuntime-compatible view with provider-scoped quota and throttling."""

    def __init__(self, parent: BrainRuntime, scope: str):
        self.parent = parent
        self.scope = scope

    @property
    def usage_path(self) -> Path | None:
        return self.parent.usage_path

    @property
    def provider_events_path(self) -> Path | None:
        return self.parent.provider_events_path

    def record_usage(self, record: dict[str, Any]) -> None:
        self.parent.record_usage(record)

    def usage_records(self) -> list[dict[str, Any]]:
        return self.parent.usage_records()

    def record_provider_event(self, record: dict[str, Any]) -> None:
        self.parent.record_provider_event(record)

    def provider_event_records(self) -> list[dict[str, Any]]:
        return self.parent.provider_event_records()

    def provider_event_summary(self) -> dict[str, int]:
        return self.parent.provider_event_summary()

    def quota_message(self) -> str | None:
        return self.parent.quota_message(self.scope)

    def mark_quota_unavailable(self, message: str) -> None:
        self.parent.mark_quota_unavailable(message, self.scope)

    def authentication_message(self) -> str | None:
        return self.parent.authentication_message(self.scope)

    def mark_authentication_required(self, message: str) -> None:
        self.parent.mark_authentication_required(message, self.scope)

    def blocking_failure(self) -> tuple[str, str] | None:
        return self.parent.blocking_failure(self.scope)

    def clear_quota_unavailable(self) -> None:
        self.parent.clear_quota_unavailable(self.scope)

    def clear_authentication_required(self) -> None:
        self.parent.clear_authentication_required(self.scope)

    def throttle(self, minimum_interval_seconds: float) -> None:
        self.parent.throttle(minimum_interval_seconds, self.scope)


def provider_events_path_for_usage(usage_path: Path | None) -> Path | None:
    if usage_path is None:
        return None
    stem = usage_path.stem
    if stem.endswith("-usage"):
        stem = stem[: -len("-usage")]
    return usage_path.with_name(f"{stem}-provider-events.jsonl")


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
    except (OSError, json.JSONDecodeError):
        return []
    return records
