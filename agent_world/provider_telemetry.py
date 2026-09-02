"""Compact, provider-neutral telemetry for exceptional request attempts."""

from __future__ import annotations

import hashlib
import subprocess
import time
from typing import Any
import uuid


def record_provider_attempt(
    runtime: Any,
    *,
    event_type: str,
    failure_kind: str,
    provider: str,
    model: str | None,
    request_meta: dict[str, Any],
    attempt: int,
    max_attempts: int,
    duration_seconds: float,
    detail: str | None = None,
    exception: BaseException | None = None,
    response_model: str | None = None,
    billing_mode: str | None = None,
    reasoning_effort: str | None = None,
    provider_trace_id: str | None = None,
    http_status: int | None = None,
    retry_after_seconds: float | None = None,
) -> None:
    """Persist one failed provider attempt without prompts or raw output."""

    stdout = _exception_stream(exception, "output")
    stderr = _exception_stream(exception, "stderr")
    record = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "failure_kind": failure_kind,
        "provider": provider,
        "model": model,
        "response_model": response_model,
        "billing_mode": billing_mode,
        "reasoning_effort": reasoning_effort,
        "time": time.time(),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "duration_seconds": round(duration_seconds, 3),
        "provider_trace_id": provider_trace_id,
        "http_status": http_status,
        "retry_after_seconds": retry_after_seconds,
        "failure_detail": _compact_detail(detail),
        "partial_stdout_bytes": len(stdout),
        "partial_stdout_sha256": hashlib.sha256(stdout).hexdigest() if stdout else None,
        "partial_stderr_bytes": len(stderr),
        "partial_stderr_sha256": hashlib.sha256(stderr).hexdigest() if stderr else None,
        **request_meta,
    }
    runtime.record_provider_event(record)


def _exception_stream(exception: BaseException | None, name: str) -> bytes:
    if not isinstance(exception, subprocess.TimeoutExpired):
        return b""
    value = getattr(exception, name, None)
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    return b""


def _compact_detail(detail: str | None) -> str | None:
    if not detail:
        return None
    return " ".join(detail.split())[:1000]
