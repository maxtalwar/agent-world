"""Durable lifecycle controller for declaratively managed Agent World runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from agent_world.jsonl_tail import tail_for
from agent_world.managed_observer import read_control
from agent_world.io import atomic_write_json
from agent_world.managed_runs import (
    CONTROLLER_POLL_SECONDS,
    CONTROLLER_PROGRESS_INTERVAL_TICKS,
    CONTROLLER_STALL_SECONDS,
    _health_gate_status,
    _job_lock,
    _launch_cell,
    _tmux_active,
    cell_status,
    utc_now,
)


@dataclass(frozen=True)
class ControllerPolicy:
    poll_seconds: float = CONTROLLER_POLL_SECONDS
    progress_interval_ticks: int = CONTROLLER_PROGRESS_INTERVAL_TICKS
    stall_seconds: float = CONTROLLER_STALL_SECONDS
    max_auto_resumes: int = 6
    max_decisions_unusable_resumes: int = 1
    resume_backoff_seconds: tuple[float, ...] = (60.0, 300.0, 900.0, 1800.0)


DEFAULT_POLICY = ControllerPolicy()
CONTROL_EVENT_TYPES = {
    "run_completed",
    "run_failed",
    "run_health_check",
    "run_paused",
    "run_quota_retry",
    "run_quota_wait",
    "run_stopped",
}
AUTH_MARKERS = (
    "not logged in",
    "login required",
    "please login",
    "please run /login",
    "authentication required",
    "authentication failed",
    "unauthorized",
    "invalid api key",
    "invalid_api_key",
    "token expired",
)


def _load_job(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Managed job must be a JSON object: {path}")
    return value


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat()


def _append_controller_event(job: dict[str, Any], event_type: str, **data: Any) -> None:
    controller = job.get("controller") or {}
    path = Path(controller.get("events") or Path(job["job_dir"]) / "controller-events.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"type": event_type, "at_utc": utc_now(), **data}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()


def _latest_control_event(path: str | Path) -> dict[str, Any] | None:
    rows = tail_for(str(Path(path).resolve()), frozenset(CONTROL_EVENT_TYPES), True).read()
    return rows[-1] if rows else None


def _event_text(event: dict[str, Any] | None) -> str:
    if not event:
        return ""
    data = event.get("data") or {}
    messages = data.get("provider_messages") or []
    return "\n".join([str(event.get("message") or ""), *(str(item) for item in messages)]).lower()


def _requires_authentication(cell: dict[str, Any]) -> bool:
    text = _event_text(_latest_control_event(cell["events"]))
    return any(marker in text for marker in AUTH_MARKERS)


def _quota_waiting(cell: dict[str, Any]) -> bool:
    event = _latest_control_event(cell["events"])
    return bool(event and event.get("type") == "run_quota_wait")


def _quota_resume_at(cell: dict[str, Any]) -> datetime | None:
    event = _latest_control_event(cell["events"])
    if not event or event.get("type") != "run_quota_wait":
        return None
    data = event.get("data") or {}
    resume_at = data.get("resume_at_unix")
    if isinstance(resume_at, (int, float)) and not isinstance(resume_at, bool):
        return datetime.fromtimestamp(resume_at, tz=timezone.utc)
    wait_seconds = data.get("wait_seconds")
    if not isinstance(wait_seconds, (int, float)) or isinstance(wait_seconds, bool):
        return None
    try:
        written_at = datetime.fromtimestamp(
            Path(cell["events"]).stat().st_mtime, tz=timezone.utc
        )
    except OSError:
        return None
    return written_at + timedelta(seconds=max(0.0, float(wait_seconds)))

def _backoff(cell: dict[str, Any], policy: ControllerPolicy) -> float:
    attempts = int(cell.get("auto_resume_count") or 0)
    return policy.resume_backoff_seconds[min(attempts, len(policy.resume_backoff_seconds) - 1)]


def _retryable(
    cell: dict[str, Any], status: dict[str, Any], policy: ControllerPolicy
) -> tuple[bool, str]:
    state = status["state"]
    reason = status.get("stop_reason")
    attempts = int(cell.get("auto_resume_count") or 0)
    if _requires_authentication(cell):
        return False, "authentication_required"
    if reason == "insufficient_quota":
        return False, "quota_wait_budget_exhausted"
    if reason == "startup_health_check_failed":
        return False, "startup_health_check_failed"
    if reason == "decisions_unusable":
        return (
            attempts < policy.max_decisions_unusable_resumes,
            "decisions_unusable",
        )
    if state == "interrupted":
        return attempts < policy.max_auto_resumes, "supervisor_interrupted"
    if state == "paused_checkpoint" and reason == "provider_unavailable":
        return attempts < policy.max_auto_resumes, "provider_unavailable"
    if state == "stopped" and reason == "provider_unavailable":
        # A transient preflight outage gets one unattended retry. Repeated
        # tick-zero failure usually means missing login or provider setup.
        return attempts < 1, "provider_preflight_unavailable"
    return False, reason or state


def _kill_session(session: str | None) -> bool:
    if not session or not _tmux_active(session):
        return False
    return subprocess.run(
        ["tmux", "kill-session", "-t", session], capture_output=True
    ).returncode == 0


def _manual_finalization_active(job: dict[str, Any], now: datetime) -> bool:
    finalizer = job.get("finalization_supervisor") or {}
    started = _parse_time(finalizer.get("started_at_utc"))
    launching = (
        finalizer.get("status") == "running"
        and started is not None
        and (now - started).total_seconds() < 300
    )
    # Treat a newly recorded manual launch as active during the small gap
    # before tmux becomes observable. This closes the only window in which
    # manual and controller-owned finalization could start together.
    return _tmux_active(finalizer.get("session")) or launching



def _record_progress(
    job: dict[str, Any], cell: dict[str, Any], status: dict[str, Any],
    now: datetime, policy: ControllerPolicy,
) -> None:
    tick = status.get("tick")
    previous = cell.get("controller_last_tick")
    if isinstance(tick, int) and tick != previous:
        cell["controller_last_tick"] = tick
        cell["controller_last_progress_at_utc"] = _iso(now)
        interval = policy.progress_interval_ticks
        last_milestone = int(cell.get("controller_last_milestone_tick") or 0)
        milestone = ((last_milestone // interval) + 1) * interval
        while milestone <= tick:
            _append_controller_event(
                job,
                "progress_check",
                cell_id=cell["id"],
                seed=cell["seed"],
                tick=milestone,
                target_ticks=cell.get("target_ticks"),
            )
            cell["controller_last_milestone_tick"] = milestone
            milestone += interval
    elif not cell.get("controller_last_progress_at_utc"):
        cell["controller_last_progress_at_utc"] = _iso(now)


def _schedule_or_resume(
    job: dict[str, Any], cell: dict[str, Any], reason: str,
    now: datetime, policy: ControllerPolicy,
) -> None:
    scheduled = _parse_time(cell.get("next_auto_resume_at_utc"))
    if scheduled is None:
        scheduled = now + timedelta(seconds=_backoff(cell, policy))
        cell["next_auto_resume_at_utc"] = _iso(scheduled)
        cell["controller_state"] = "restart_scheduled"
        _append_controller_event(
            job,
            "auto_resume_scheduled",
            cell_id=cell["id"],
            seed=cell["seed"],
            reason=reason,
            resume_at_utc=_iso(scheduled),
        )
        return
    if now < scheduled:
        return
    cell["resume_count"] = int(cell.get("resume_count") or 0) + 1
    cell["auto_resume_count"] = int(cell.get("auto_resume_count") or 0) + 1
    try:
        _launch_cell(job, cell, resume=True)
    except Exception as exc:
        cell["last_auto_resume_error"] = f"{type(exc).__name__}: {exc}"
        cell["next_auto_resume_at_utc"] = _iso(
            now + timedelta(seconds=_backoff(cell, policy))
        )
        _append_controller_event(
            job,
            "auto_resume_failed",
            cell_id=cell["id"],
            seed=cell["seed"],
            reason=reason,
            error=cell["last_auto_resume_error"],
        )
    else:
        cell.pop("last_auto_resume_error", None)
        cell.pop("next_auto_resume_at_utc", None)
        cell.pop("controller_attention", None)
        cell["controller_state"] = "running"
        cell["controller_last_progress_at_utc"] = _iso(now)
        _append_controller_event(
            job,
            "auto_resumed",
            cell_id=cell["id"],
            seed=cell["seed"],
            reason=reason,
            resume_count=cell["resume_count"],
        )


def _launch_deferred_cell(job: dict[str, Any], cell: dict[str, Any]) -> None:
    Path(cell["output_dir"]).mkdir(parents=True, exist_ok=True)
    _launch_cell(job, cell)
    cell["controller_state"] = "running"
    _append_controller_event(
        job, "startup_gate_released", cell_id=cell["id"], seed=cell["seed"]
    )


def _reconcile_gate(job: dict[str, Any]) -> None:
    gate = job.get("startup_gate")
    if not isinstance(gate, dict) or gate.get("status") != "pending":
        return
    first = job["cells"][0]
    result = _health_gate_status(first)
    if result == "passed":
        gate.update({"status": "passed", "passed_at_utc": utc_now()})
        _append_controller_event(job, "startup_gate_passed", cell_id=first["id"])
        for cell in job["cells"][1:]:
            if cell.get("session") is None:
                try:
                    _launch_deferred_cell(job, cell)
                except Exception as exc:
                    cell["launch_error"] = f"{type(exc).__name__}: {exc}"
                    cell["controller_attention"] = "deferred_launch_failed"
                    _append_controller_event(
                        job,
                        "deferred_launch_failed",
                        cell_id=cell["id"],
                        seed=cell["seed"],
                        error=cell["launch_error"],
                    )
    elif result == "failed":
        gate.update(
            {
                "status": "failed",
                "failed_at_utc": utc_now(),
                "reason": "startup_health_check_failed",
            }
        )
        _append_controller_event(job, "startup_gate_failed", cell_id=first["id"])


def _write_heartbeat(job: dict[str, Any], statuses: list[dict[str, Any]]) -> None:
    controller = job.get("controller") or {}
    path = Path(controller.get("heartbeat") or Path(job["job_dir"]) / "controller-heartbeat.json")
    atomic_write_json(
        path,
        {
            "schema_version": 1,
            "checked_at_utc": utc_now(),
            "run_id": job["run_id"],
            "controller_status": controller.get("status"),
            "cells": [
                {
                    "id": status["id"],
                    "seed": status["seed"],
                    "state": status["state"],
                    "tick": status.get("tick"),
                    "target_ticks": status.get("target_ticks"),
                    "stop_reason": status.get("stop_reason"),
                    "controller_state": status.get("controller_state"),
                    "attention": status.get("controller_attention"),
                    "next_auto_resume_at_utc": status.get("next_auto_resume_at_utc"),
                }
                for status in statuses
            ],
        },
    )


def reconcile_once(
    job_path: Path,
    *,
    policy: ControllerPolicy = DEFAULT_POLICY,
    now: datetime | None = None,
) -> bool:
    """Reconcile one job cycle. Return True when the controller may exit."""

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    need_finalize: tuple[int, ...] | None = None
    with _job_lock(job_path.parent):
        job = _load_job(job_path)
        controller = job.setdefault("controller", {})
        controller["status"] = "running"
        controller["last_check_at_utc"] = _iso(now)
        _reconcile_gate(job)
        gate = job.get("startup_gate") or {}
        statuses: list[dict[str, Any]] = []
        for index, cell in enumerate(job["cells"]):
            status = cell_status(cell)
            statuses.append(status)
            _record_progress(job, cell, status, now, policy)
            if status.get("stale_supervisor"):
                if _kill_session(status.get("session")):
                    _append_controller_event(
                        job,
                        "stale_supervisor_removed",
                        cell_id=cell["id"],
                        seed=cell["seed"],
                        state=status["state"],
                    )
            if status["state"] == "completed":
                cell["controller_state"] = "completed"
                cell.pop("controller_attention", None)
                cell.pop("next_auto_resume_at_utc", None)
                continue
            if index and gate.get("status") == "pending" and cell.get("session") is None:
                cell["controller_state"] = "waiting_startup_gate"
                continue
            if index and gate.get("status") == "failed" and cell.get("session") is None:
                cell["controller_state"] = "blocked_startup_gate"
                cell["controller_attention"] = "startup_health_check_failed"
                continue
            if status["supervisor_active"]:
                if read_control(Path(cell["events"]).parent / "operator-control.json") == "pause":
                    cell["controller_state"] = "paused_by_operator"
                    continue
                quota_deadline = _quota_resume_at(cell)
                if _quota_waiting(cell) and (
                    quota_deadline is not None and now < quota_deadline + timedelta(seconds=policy.stall_seconds)
                ):
                    cell["controller_state"] = "waiting_quota"
                    continue
                cell["controller_state"] = "running"
                last_progress = _parse_time(cell.get("controller_last_progress_at_utc")) or now
                if (now - last_progress).total_seconds() >= policy.stall_seconds:
                    if _kill_session(status.get("session")):
                        cell["controller_state"] = "stalled_process_reaped"
                        cell["next_auto_resume_at_utc"] = _iso(now)
                        _append_controller_event(
                            job,
                            "stalled_supervisor_reaped",
                            cell_id=cell["id"],
                            seed=cell["seed"],
                            tick=status.get("tick"),
                            stalled_seconds=round((now - last_progress).total_seconds(), 1),
                        )
                continue
            quota_resume_at = _quota_resume_at(cell)
            if quota_resume_at is not None and now < quota_resume_at:
                cell["controller_state"] = "waiting_quota"
                cell["next_auto_resume_at_utc"] = _iso(quota_resume_at)
                cell.pop("controller_attention", None)
                continue
            if quota_resume_at is not None:
                cell["next_auto_resume_at_utc"] = _iso(quota_resume_at)
            retryable, reason = _retryable(cell, status, policy)
            if retryable and Path(cell["checkpoint"]).exists():
                _schedule_or_resume(job, cell, reason, now, policy)
            else:
                cell["controller_state"] = "needs_attention"
                cell["controller_attention"] = reason

        completed_signature = tuple(
            sorted(status["seed"] for status in statuses if status["state"] == "completed")
        )
        finalization_signature = tuple(controller.get("last_finalization_signature") or ())
        finalizing_signature = tuple(controller.get("finalization_in_progress_signature") or ())
        manual_finalization_active = _manual_finalization_active(job, now)
        if finalizing_signature and not manual_finalization_active:
            supervisor = job.get("finalization_supervisor") or {}
            if supervisor.get("status") == "completed":
                controller["last_finalization_signature"] = list(finalizing_signature)
                finalization_signature = finalizing_signature
                controller["finalization_retry_count"] = 0
            else:
                retries = int(controller.get("finalization_retry_count") or 0) + 1
                controller["finalization_retry_count"] = retries
                controller["finalization_retry_at"] = _iso(now + timedelta(seconds=min(1800, 60 * 2 ** (retries - 1))))
                if retries >= 3:
                    controller["finalization_error"] = supervisor.get("error") or "Finalizer repeatedly exited without completion"
                _append_controller_event(job, "automatic_finalization_recovered", seeds=list(finalizing_signature))
            controller.pop("finalization_in_progress_signature", None)
            finalizing_signature = ()
        if (
            job.get("kind") == "benchmark"
            and completed_signature
            and completed_signature != finalization_signature
            and completed_signature != finalizing_signature
            and not manual_finalization_active
            and int(controller.get("finalization_retry_count") or 0) < 3
            and now >= (_parse_time(controller.get("finalization_retry_at")) or now)
        ):
            controller["finalization_in_progress_signature"] = list(completed_signature)
            controller.pop("finalization_error", None)
            need_finalize = completed_signature
            _append_controller_event(
                job, "automatic_finalization_started", seeds=list(completed_signature)
            )
        atomic_write_json(job_path, job)
        _write_heartbeat(job, [cell_status(cell) for cell in job["cells"]])

    if need_finalize is not None:
        try:
            from agent_world.run_finalization import start_finalization
            start_finalization(_load_job(job_path)["run_id"], automatic_signature=need_finalize)
        except Exception as exc:
            with _job_lock(job_path.parent):
                job = _load_job(job_path)
                job.setdefault("finalization_supervisor", {}).update(
                    {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
                )
                atomic_write_json(job_path, job, fsync=True)

    with _job_lock(job_path.parent):
        job = _load_job(job_path)
        statuses = [cell_status(cell) for cell in job["cells"]]
        controller = job.setdefault("controller", {})
        all_completed = bool(statuses) and all(
            status["state"] == "completed" for status in statuses
        )
        if _manual_finalization_active(job, now):
            return False
        completed_signature = tuple(
            sorted(status["seed"] for status in statuses if status["state"] == "completed")
        )
        finalized_signature = tuple(controller.get("last_finalization_signature") or ())
        if all_completed and (
            job.get("kind") != "benchmark" or completed_signature == finalized_signature
        ):
            readiness = (job.get("analysis_readiness") or {}).get("status")
            controller["status"] = (
                "completed"
                if job.get("kind") != "benchmark" or readiness == "ready"
                else "completed_with_blockers"
            )
            controller["ended_at_utc"] = utc_now()
            _append_controller_event(
                job, "controller_completed", analysis_readiness=readiness
            )
            atomic_write_json(job_path, job)
            _write_heartbeat(job, statuses)
            return True
        if controller.get("finalization_in_progress_signature") or (
            controller.get("finalization_retry_at") and int(controller.get("finalization_retry_count") or 0) < 3
        ):
            return False
        active = any(status["supervisor_active"] for status in statuses)
        scheduled = any(cell.get("next_auto_resume_at_utc") for cell in job["cells"])
        blocked = all(
            status["state"] == "completed" or cell.get("controller_attention")
            for cell, status in zip(job["cells"], statuses, strict=True)
        )
        if blocked and not active and not scheduled:
            controller["status"] = "needs_attention"
            controller["ended_at_utc"] = utc_now()
            _append_controller_event(job, "controller_needs_attention")
            atomic_write_json(job_path, job)
            _write_heartbeat(job, statuses)
            return True
    return False


def supervise(job_path: Path, *, policy: ControllerPolicy = DEFAULT_POLICY) -> None:
    while True:
        if reconcile_once(job_path, policy=policy):
            return
        time.sleep(policy.poll_seconds)


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise SystemExit("Usage: python3 -m agent_world.run_controller JOB.json")
    job_path = Path(arguments[0]).resolve()
    try:
        supervise(job_path)
    except Exception as exc:
        try:
            with _job_lock(job_path.parent):
                job = _load_job(job_path)
                controller = job.setdefault("controller", {})
                controller.update(
                    {
                        "status": "failed",
                        "last_crash_at_utc": utc_now(),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                _append_controller_event(job, "controller_crashed", error=controller["error"])
                atomic_write_json(job_path, job)
        finally:
            raise


if __name__ == "__main__":
    main()
