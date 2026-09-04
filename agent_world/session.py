"""Shared lifecycle owner for CLI, experiment, and observatory simulations."""

from __future__ import annotations

from agent_world.request_context import RunBudgetExceeded

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import time
from typing import Any, Callable

from agent_world.agents import AgentBrain
from agent_world.brain_factory import BrainSpec, PopulationSpec, create_population_brains
from agent_world.brain_runtime import BrainRuntime
from agent_world.codex_brain import summarize_plan_usage
from agent_world.io import atomic_write_json
from agent_world.metrics import (
    event_matches_failure,
    is_authentication_detail,
    is_decision_failure_message,
    is_provider_failure_message,
    is_quota_failure_message,
)
from agent_world.persistence import IncrementalRunWriter
from agent_world.run_report import build_report, write_report
from agent_world.provider_limits import quota_reset_at
from agent_world.runner import (
    ModelAuthenticationRequiredError,
    ModelDecisionsUnusableError,
    ModelProviderUnavailableError,
    ModelQuotaUnavailableError,
    SimulationRunner,
    pending_tick_path_for_artifacts,
)
from agent_world.world import WorldEngine


@dataclass
class SessionResult:
    status: str
    final_tick: int
    target_ticks: int
    stop_reason: str | None
    error: str | None
    usage_records: list[dict[str, Any]]
    plan_usage: dict[str, Any] | None
    report: dict[str, Any] | None


class SimulationSession:
    """Execute one run while keeping entry-point-specific concerns in hooks."""

    def __init__(
        self,
        *,
        engine: WorldEngine,
        brain_spec: BrainSpec,
        runtime: BrainRuntime,
        writer: IncrementalRunWriter,
        target_ticks: int,
        brains: dict[str, AgentBrain] | None = None,
        population_spec: PopulationSpec | None = None,
        max_workers: int | None = None,
        provider_max_workers: dict[str, int] | None = None,
        decision_mode: str = "raw",
        observation_history_policy: str | None = None,
        resource_limits: dict[str, Any] | None = None,
        log_agent_io: bool = True,
        concurrent_decisions: bool | None = None,
        lifecycle_metadata: dict[str, Any] | None = None,
        resumed: bool = False,
        checkpoint_extra: Callable[["SimulationSession"], dict[str, Any]] | None = None,
        before_tick: Callable[[], bool] | None = None,
        on_tick: Callable[["SimulationSession", list[Any]], None] | None = None,
        on_terminal: Callable[["SimulationSession", SessionResult], None] | None = None,
        report_stem: Path | None = None,
        plan_usage_path: Path | None = None,
        plan_usage_checkpoints: list[dict[str, Any]] | None = None,
        benchmark_checkpoint_ticks: tuple[int, ...] = (),
        startup_health_check_tick: int | None = 5,
        startup_health_max_failure_rate: float = 0.2,
        quota_wait_max_seconds: float = 0.0,
        quota_wait_poll_max_seconds: float = 1800.0,
        pending_tick_path: Path | None = None,
        provider_retry_rounds: int | None = None,
        provider_retry_backoff_seconds: float = 15.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if target_ticks < engine.state.tick:
            raise ValueError(
                f"Target tick {target_ticks} is behind current tick {engine.state.tick}."
            )
        self.engine = engine
        self.brain_spec = brain_spec
        self.population_spec = population_spec or PopulationSpec.uniform(
            len(engine.state.agents), brain_spec
        )
        self.runtime = runtime
        limits = resource_limits if resource_limits is not None else getattr(engine, "_resource_limits", {})
        runtime.configure_limits(limits)
        engine._resource_limits = dict(limits)
        self.writer = writer
        self.target_ticks = target_ticks
        self.brains = brains or create_population_brains(
            engine, self.population_spec, runtime
        )
        self.max_workers = max_workers or max(
            group.brain.max_workers or 1 for group in self.population_spec.groups
        )
        self.provider_max_workers = dict(provider_max_workers or {})
        self.decision_mode = decision_mode
        from agent_world.observation_policy import HISTORY_POLICIES
        history_policy = observation_history_policy or getattr(engine, "_observation_history_policy", "full-v1")
        if history_policy not in HISTORY_POLICIES:
            raise ValueError("Invalid observation history policy")
        engine._observation_history_policy = history_policy
        self.log_agent_io = log_agent_io
        self.concurrent_decisions = (
            self.max_workers > 1
            if concurrent_decisions is None
            else concurrent_decisions
        )
        self.lifecycle_metadata = dict(lifecycle_metadata or {})
        self.lifecycle_metadata["observation_history_policy"] = history_policy
        self.resumed = resumed
        self.checkpoint_extra_factory = checkpoint_extra
        self.before_tick = before_tick
        self.on_tick = on_tick
        self.on_terminal = on_terminal
        self.report_stem = report_stem
        self.plan_usage_path = plan_usage_path
        self.plan_usage_checkpoints = list(plan_usage_checkpoints or [])
        self.benchmark_checkpoint_ticks = tuple(
            sorted(set(int(tick) for tick in benchmark_checkpoint_ticks))
        )
        if startup_health_check_tick is not None and startup_health_check_tick < 1:
            raise ValueError("startup health-check tick must be positive or None")
        if not 0 <= startup_health_max_failure_rate <= 1:
            raise ValueError("startup health failure rate must be between 0 and 1")
        self.startup_health_check_tick = startup_health_check_tick
        self.startup_health_max_failure_rate = startup_health_max_failure_rate
        if quota_wait_max_seconds < 0:
            raise ValueError("quota wait budget cannot be negative")
        self.quota_wait_max_seconds = float(quota_wait_max_seconds)
        self.quota_wait_poll_max_seconds = float(quota_wait_poll_max_seconds)
        self._sleep = sleep
        saved_quota = getattr(engine, "_session_quota_state", {})
        self._quota_wait_used = float(saved_quota.get("reserved_seconds", 0.0))
        self._quota_backoff_seconds = float(saved_quota.get("backoff_seconds", 300.0))
        self._quota_resume_until = float(saved_quota.get("resume_at", 0.0))
        self.pending_tick_path = pending_tick_path or pending_tick_path_for_artifacts(
            writer.events_path, writer.checkpoint_path
        )
        if provider_retry_rounds is None:
            provider_retry_rounds = int(
                os.environ.get(
                    "AGENT_WORLD_PROVIDER_RETRY_ROUNDS",
                    "2" if self.pending_tick_path is not None else "0",
                )
            )
        self.runner = SimulationRunner(
            engine,
            self.brains,
            log_agent_io=log_agent_io,
            concurrent_decisions=self.concurrent_decisions,
            max_workers=self.max_workers,
            provider_max_workers=self.provider_max_workers,
            decision_mode=self.decision_mode,
            observation_history_policy=history_policy,
            pending_tick_path=self.pending_tick_path,
            provider_retry_rounds=provider_retry_rounds,
            provider_retry_backoff_seconds=provider_retry_backoff_seconds,
            sleep=self._sleep,
        )
        self.capture_plan_usage = next(
            (
                capture
                for brain in self.brains.values()
                if callable(capture := getattr(brain, "capture_plan_usage", None))
            ),
            None,
        )
        self._started = False
        self.preflight_error: str | None = None

    def run(self) -> SessionResult:
        self.start()
        status = "running"
        stop_reason: str | None = None
        error: str | None = None
        if self.preflight_error:
            status = "stopped"
            stop_reason = (
                "authentication_required"
                if is_authentication_detail(self.preflight_error)
                else "provider_unavailable"
            )
        try:
            if status == "running" and self._quota_resume_until > time.time():
                self._sleep_for_quota(self._quota_resume_until - time.time())
                self.runtime.clear_quota_unavailable()
            while status == "running" and self.engine.state.tick < self.target_ticks:
                if self.before_tick is not None and self.before_tick():
                    status = "stopped"
                    stop_reason = "stop_requested"
                    break
                usage_checkpoint = self.runtime.usage_checkpoint()
                try:
                    events = self.runner.step()
                except RunBudgetExceeded as exc:
                    self._rollback_uncached_usage(usage_checkpoint)
                    status, stop_reason = "paused_checkpoint", "resource_budget_exhausted"
                    self.engine.log_event(
                        "run_paused", message=str(exc),
                        data={"reason": stop_reason, "limits": self.engine._resource_limits},
                        scope="public",
                    )
                    self.flush()
                    break
                except ModelAuthenticationRequiredError as exc:
                    partial_usage_path = self._rollback_uncached_usage(usage_checkpoint)
                    status = "paused_checkpoint"
                    stop_reason = "authentication_required"
                    self.engine.log_event(
                        "run_paused",
                        message=(
                            "A model connector requires authentication; the world remains "
                            "frozen and this completed-tick checkpoint can resume using every "
                            "accepted cached decision after login."
                        ),
                        data={
                            "reason": stop_reason,
                            "target_ticks": self.target_ticks,
                            "completed_tick": self.engine.state.tick,
                            "provider_messages": exc.messages,
                            "affected_agent_ids": sorted(exc.failures),
                            "affected_agent_count": len(exc.failures),
                            "cached_agent_ids": exc.cached_agents,
                            "cached_decision_count": len(exc.cached_agents),
                            "provider_event_counts": self.runtime.provider_event_summary(),
                            "partial_usage_path": (
                                str(partial_usage_path.resolve())
                                if partial_usage_path
                                else None
                            ),
                        },
                        scope="public",
                    )
                    self.flush()
                    break
                except ModelQuotaUnavailableError as exc:
                    partial_usage_path = self._rollback_uncached_usage(usage_checkpoint)
                    # The world is back at a completed-tick boundary, so waiting
                    # for the cap to lift and retrying the same tick is exactly
                    # a checkpoint resume without the process restart.
                    if self._wait_for_quota_reset(exc.messages):
                        continue
                    status = "paused_checkpoint"
                    stop_reason = "insufficient_quota"
                    self.engine.log_event(
                        "run_paused",
                        message=(
                            "Model quota became unavailable during decision collection; "
                            "the world remains frozen and this completed-tick checkpoint can "
                            "resume using every accepted cached decision."
                        ),
                        data={
                            "reason": stop_reason,
                            "target_ticks": self.target_ticks,
                            "completed_tick": self.engine.state.tick,
                            "provider_messages": exc.messages,
                            "affected_agent_ids": sorted(exc.failures),
                            "affected_agent_count": len(exc.failures),
                            "cached_agent_ids": exc.cached_agents,
                            "cached_decision_count": len(exc.cached_agents),
                            "provider_event_counts": self.runtime.provider_event_summary(),
                            "quota_wait_seconds_used": round(self._quota_wait_used, 1),
                            "partial_usage_path": (
                                str(partial_usage_path.resolve()) if partial_usage_path else None
                            ),
                        },
                        scope="public",
                    )
                    self.flush()
                    break
                except ModelDecisionsUnusableError as exc:
                    partial_usage_path = self.runtime.rollback_usage(
                        usage_checkpoint, attempted_tick=self.engine.state.tick
                    )
                    self.reset_brain_conversations("discarded_partial_tick")
                    self.runner.discard_pending_tick()
                    status = "paused_checkpoint"
                    stop_reason = "decisions_unusable"
                    self.engine.log_event(
                        "run_paused",
                        message=(
                            "Every living agent failed identically at the model boundary, so the "
                            "fault is external; the incomplete tick was discarded and this "
                            "completed-tick checkpoint can be resumed."
                        ),
                        data={
                            "reason": stop_reason,
                            "target_ticks": self.target_ticks,
                            "completed_tick": self.engine.state.tick,
                            "provider_messages": exc.messages,
                            "affected_agents": exc.agents,
                            "consecutive_ticks": exc.consecutive_ticks,
                            "partial_usage_path": (
                                str(partial_usage_path.resolve()) if partial_usage_path else None
                            ),
                        },
                        scope="public",
                    )
                    self.flush()
                    break
                except ModelProviderUnavailableError as exc:
                    partial_usage_path = self._rollback_uncached_usage(usage_checkpoint)
                    status = "paused_checkpoint"
                    stop_reason = "provider_unavailable"
                    self.engine.log_event(
                        "run_paused",
                        message=(
                            "A model provider became unavailable during decision collection; "
                            "the world remains frozen and this completed-tick checkpoint can "
                            "resume using every accepted cached decision."
                        ),
                        data={
                            "reason": stop_reason,
                            "target_ticks": self.target_ticks,
                            "completed_tick": self.engine.state.tick,
                            "provider_messages": exc.messages,
                            "affected_agent_ids": sorted(exc.failures),
                            "affected_agent_count": len(exc.failures),
                            "cached_agent_ids": exc.cached_agents,
                            "cached_decision_count": len(exc.cached_agents),
                            "provider_retry_rounds": exc.retry_rounds,
                            "provider_event_counts": self.runtime.provider_event_summary(),
                            "partial_usage_path": (
                                str(partial_usage_path.resolve()) if partial_usage_path else None
                            ),
                        },
                        scope="public",
                    )
                    self.flush()
                    break
                if any(
                    event.data.get("failure_kind") == "quota"
                    for event in events
                ):
                    status = "stopped"
                    stop_reason = "insufficient_quota"
                    self.engine.log_event(
                        "run_stopped",
                        message="Model quota is unavailable; stopped early so the run is not mistaken for agent behavior.",
                        data={"reason": stop_reason, "target_ticks": self.target_ticks},
                        scope="public",
                    )
                elif any(
                    event.data.get("failure_kind") == "provider"
                    for event in events
                ):
                    status = "stopped"
                    stop_reason = "provider_unavailable"
                    self.engine.log_event(
                        "run_stopped",
                        message="A requested model provider became unavailable; stopped before producing misleading behavior.",
                        data={"reason": stop_reason, "target_ticks": self.target_ticks},
                        scope="public",
                    )
                elif self._should_run_startup_health_check():
                    health = self._startup_health_report()
                    unhealthy = [
                        cohort for cohort in health["cohorts"] if cohort["unhealthy"]
                    ]
                    if unhealthy:
                        status = "stopped"
                        stop_reason = "startup_health_check_failed"
                        self.engine.log_event(
                            "run_health_check",
                            message=(
                                "Startup model-health check found systematic decision failures; "
                                "stopped early so the run is not mistaken for agent behavior."
                            ),
                            data={**health, "status": "failed", "reason": stop_reason},
                            scope="public",
                        )
                    else:
                        self.engine.log_event(
                            "run_health_check",
                            message="Startup model-health check passed.",
                            data={**health, "status": "passed"},
                            scope="public",
                        )
                if self._should_capture_plan_usage(self.engine.state.tick, bool(stop_reason)):
                    self._capture_plan_usage(self.engine.state.tick)
                if self.engine.state.tick in self.benchmark_checkpoint_ticks:
                    self._capture_benchmark_checkpoint(self.engine.state.tick)
                if self.on_tick is not None:
                    self.on_tick(self, events)
                self.flush()
                self.runner.commit_pending_tick()
                if stop_reason:
                    break

            if status == "running":
                status = "completed"
            if status == "completed":
                self.engine.log_event(
                    "run_completed",
                    message=f"Completed {self.target_ticks} target ticks.",
                    data={
                        "target_ticks": self.target_ticks,
                        "provider_event_counts": self.runtime.provider_event_summary(),
                    },
                    scope="public",
                )
            elif stop_reason == "stop_requested":
                self.engine.log_event(
                    "run_stopped",
                    message=f"Simulation stopped at tick {self.engine.state.tick}.",
                    data={"reason": stop_reason, "target_ticks": self.target_ticks},
                    scope="public",
                )
        except Exception as exc:  # Preserve a replayable failure artifact.
            self.reset_brain_conversations("run_failure")
            status = "failed"
            stop_reason = "run_failed"
            error = f"{type(exc).__name__}: {exc}"
            self.engine.log_event(
                "run_failed",
                message=error,
                data={"error": error, "target_ticks": self.target_ticks},
                scope="public",
            )

        if (
            self.capture_plan_usage is not None
            and (
                not self.plan_usage_checkpoints
                or self.plan_usage_checkpoints[-1].get("simulation_tick") != self.engine.state.tick
            )
        ):
            self._capture_plan_usage(self.engine.state.tick)
        self.flush()
        plan_usage = (
            summarize_plan_usage(self.plan_usage_checkpoints)
            if self.plan_usage_checkpoints
            else None
        )
        usage_records = self.runtime.usage_records()
        report = None
        if self.report_stem is not None:
            report = write_report(
                [event.to_dict() for event in self.engine.state.events],
                self.engine.snapshot(),
                self.runtime.attempted_usage_records(),
                self.report_stem,
                target_ticks=self.target_ticks,
                plan_usage=plan_usage,
            )
        result = SessionResult(
            status=status,
            final_tick=self.engine.state.tick,
            target_ticks=self.target_ticks,
            stop_reason=stop_reason,
            error=error,
            usage_records=usage_records,
            plan_usage=plan_usage,
            report=report,
        )
        if self.on_terminal is not None:
            self.on_terminal(self, result)
        return result

    def _rollback_uncached_usage(self, usage_checkpoint: int) -> Path | None:
        """Keep usage for cached decisions; quarantine only discarded work."""

        if self.pending_tick_path is not None and self.runner.cached_decision_count:
            return None
        partial_usage_path = self.runtime.rollback_usage(
            usage_checkpoint, attempted_tick=self.engine.state.tick
        )
        self.reset_brain_conversations("discarded_partial_tick")
        self.runner.discard_pending_tick()
        return partial_usage_path

    def _wait_for_quota_reset(self, messages: list[str]) -> bool:
        """Sleep until the provider cap lifts. Return whether to retry the tick.

        Waiting is the correct response to a rate limit: the run is not broken,
        it is early. The alternative the harness used to take - substituting
        wait actions and advancing the world - destroys the trial, and simply
        exiting throws away a run that only needed patience.

        When the provider states a reset time the wait is a single sleep to
        that instant. Otherwise it backs off, because every probe costs one
        real failed call per agent.
        """

        if self.quota_wait_max_seconds <= 0:
            return False
        remaining = self.quota_wait_max_seconds - self._quota_wait_used
        if remaining <= 0:
            return False

        now = datetime.now(timezone.utc)
        reset_at = next(
            (
                parsed
                for message in messages
                if (parsed := quota_reset_at(message, now=now)) is not None
            ),
            None,
        )
        if reset_at is not None:
            # A minute of slack: provider clocks and ours are not identical,
            # and retrying one second early wastes the whole wait.
            delay = (reset_at - now).total_seconds() + 60
            source = "provider_reset_time"
        else:
            delay = min(self._quota_backoff_seconds, self.quota_wait_poll_max_seconds)
            self._quota_backoff_seconds = min(
                self._quota_backoff_seconds * 2, self.quota_wait_poll_max_seconds
            )
            source = "backoff"
        delay = min(remaining, max(60.0, delay))
        self._quota_wait_used += delay
        self._quota_resume_until = time.time() + delay
        self.engine._session_quota_state = {
            "reserved_seconds": self._quota_wait_used,
            "backoff_seconds": self._quota_backoff_seconds,
            "resume_at": self._quota_resume_until,
        }

        self.engine.log_event(
            "run_quota_wait",
            message=(
                f"Model quota is exhausted; waiting {round(delay / 60)} minute(s) for it to "
                "reset, then retrying the same tick. The world has not advanced."
            ),
            data={
                "reason": "insufficient_quota",
                "completed_tick": self.engine.state.tick,
                "target_ticks": self.target_ticks,
                "wait_seconds": round(delay, 1),
                "wait_source": source,
                "provider_reset_at_utc": reset_at.isoformat() if reset_at else None,
                "waited_seconds_total": round(self._quota_wait_used, 1),
                "resume_at_unix": self._quota_resume_until,
                "wait_budget_seconds": self.quota_wait_max_seconds,
                "provider_messages": messages,
            },
            scope="public",
        )
        self.flush()
        self._sleep_for_quota(delay)
        self._quota_resume_until = 0.0
        self.engine._session_quota_state["resume_at"] = 0.0
        # Clear the cached quota flag so the retry makes a real call instead of
        # short-circuiting on the message that triggered this wait.
        self.runtime.clear_quota_unavailable()
        self.engine.log_event(
            "run_quota_retry",
            message="Retrying the tick after the quota wait.",
            data={
                "completed_tick": self.engine.state.tick,
                "waited_seconds_total": round(self._quota_wait_used, 1),
            },
            scope="public",
        )
        self.flush()
        return True

    def _sleep_for_quota(self, seconds: float) -> None:
        # Check operator stop requests between bounded waits; preserve reserved
        # budget before sleeping so crashes cannot reset the quota allowance.
        remaining = seconds
        while remaining > 0:
            if self.before_tick is not None and self.before_tick():
                return
            delay = min(30.0, remaining)
            self._sleep(delay)
            remaining -= delay

    def start(self) -> None:
        if self._started:
            return
        self._log_start()
        self.preflight_error = self._provider_preflight_error()
        if self.preflight_error:
            reason = (
                "authentication_required"
                if is_authentication_detail(self.preflight_error)
                else "provider_unavailable"
            )
            self.engine.log_event(
                "run_stopped",
                message=self.preflight_error,
                data={"reason": reason, "target_ticks": self.target_ticks},
                scope="public",
            )
        self._capture_plan_usage(self.engine.state.tick)
        self.flush()
        self._started = True

    def _provider_preflight_error(self) -> str | None:
        checked: dict[tuple[type[Any], str, str, str, str, str], Any] = {}
        for brain in self.brains.values():
            preflight = getattr(brain, "preflight", None)
            if not callable(preflight):
                continue
            scope = str(getattr(getattr(brain, "runtime", None), "scope", "default"))
            key = (
                type(brain),
                scope,
                str(getattr(brain, "model", "")),
                str(getattr(brain, "reasoning_effort", "")),
                str(getattr(brain, "connector_profile", "")),
                str(getattr(brain, "conversation_mode", "")),
            )
            representative = checked.get(key)
            if representative is not None:
                copy_state = getattr(brain, "copy_preflight_state_from", None)
                if callable(copy_state):
                    copy_state(representative)
                continue
            error = preflight()
            if error:
                return str(error)
            checked[key] = brain
        return None

    def _should_run_startup_health_check(self) -> bool:
        return (
            not self.resumed
            and self.startup_health_check_tick is not None
            and self.engine.state.tick == self.startup_health_check_tick
        )

    def _startup_health_report(self) -> dict[str, Any]:
        """Summarize harness/provider response failures without judging actions."""

        check_tick = int(self.startup_health_check_tick or self.engine.state.tick)
        assignments = self.population_spec.assignments(self.engine.state.agents)
        attempts: Counter[str] = Counter()
        failures: Counter[str] = Counter()
        for event in self.engine.state.events:
            if (
                event.type != "agent_response"
                or event.actor_id not in assignments
                or not 0 <= event.tick < check_tick
            ):
                continue
            cohort_id = assignments[event.actor_id].id
            attempts[cohort_id] += 1
            if event_matches_failure(event, is_decision_failure_message):
                failures[cohort_id] += 1

        cohorts: list[dict[str, Any]] = []
        for group in self.population_spec.groups:
            if not group.brain.model_backed:
                continue
            attempt_count = attempts[group.id]
            failure_count = failures[group.id]
            failure_rate = failure_count / attempt_count if attempt_count else 1.0
            cohorts.append(
                {
                    "cohort": group.id,
                    "brain": group.brain.type,
                    "model": group.brain.model,
                    "reasoning_effort": group.brain.reasoning_effort,
                    "attempts": attempt_count,
                    "decision_failures": failure_count,
                    "failure_rate": round(failure_rate, 4),
                    "unhealthy": (
                        attempt_count == 0
                        or (
                            failure_count >= 2
                            and failure_rate > self.startup_health_max_failure_rate
                        )
                    ),
                }
            )
        return {
            "check_tick": check_tick,
            "max_failure_rate": self.startup_health_max_failure_rate,
            "minimum_failures": 2,
            "cohorts": cohorts,
        }

    def flush(self) -> None:
        extra = dict(self.checkpoint_extra_factory(self) or {}) if self.checkpoint_extra_factory else {}
        rows = self.runtime.usage_records()
        extra["usage_commit"] = {
            "records": len(rows),
            "last_record_id": rows[-1].get("record_id") if rows else None,
            "run_identity": self.runtime.run_identity,
        }
        self.writer.flush(self.engine, checkpoint_extra=extra)

    def export_brain_states(self) -> dict[str, Any]:
        states: dict[str, Any] = {}
        for agent_id, brain in self.brains.items():
            export = getattr(brain, "export_checkpoint_state", None)
            if callable(export):
                states[agent_id] = export()
        return states

    def reset_brain_conversations(self, reason: str) -> None:
        for brain in self.brains.values():
            reset = getattr(brain, "reset_conversation", None)
            if callable(reset):
                reset(reason)

    def _log_start(self) -> None:
        population = self.population_spec.to_dict(self.engine.state.agents)
        uniform = not self.population_spec.mixed
        first_spec = self.population_spec.groups[0].brain
        data = {
            "brain": self.population_spec.run_type,
            "agents": len(self.engine.state.agents),
            "seed": self.engine.state.config.seed,
            "target_ticks": self.target_ticks,
            "model": first_spec.model if uniform else None,
            "reasoning_effort": first_spec.reasoning_effort if uniform else None,
            "provider": first_spec.provider if uniform else "mixed",
            "billing_mode": first_spec.billing_mode if uniform else "mixed",
            "population": population,
            **self.lifecycle_metadata,
        }
        if self.resumed:
            self.engine.log_event(
                "run_resumed",
                message=f"Resumed {self.population_spec.run_type} run from tick {self.engine.state.tick}.",
                data=data,
                scope="public",
            )
        else:
            self.engine.log_event(
                "run_started",
                message=f"Started {self.population_spec.run_type} run with {len(self.engine.state.agents)} agents.",
                data=data,
                scope="public",
            )

    def _capture_plan_usage(self, tick: int) -> None:
        if self.capture_plan_usage is None:
            return
        snapshot = self.capture_plan_usage()
        snapshot["simulation_tick"] = tick
        self.plan_usage_checkpoints.append(snapshot)
        if self.plan_usage_path is not None:
            atomic_write_json(
                self.plan_usage_path,
                {
                    "schema_version": 1,
                    "checkpoints": self.plan_usage_checkpoints,
                    "summary": summarize_plan_usage(self.plan_usage_checkpoints),
                },
            )

    def _capture_benchmark_checkpoint(self, tick: int) -> None:
        if any(
            event.type == "benchmark_checkpoint"
            and (event.data or {}).get("tick") == tick
            for event in self.engine.state.events
        ):
            return
        report = build_report(
            [event.to_dict() for event in self.engine.state.events],
            self.engine.snapshot(),
            self.runtime.usage_records(),
            target_ticks=tick,
        )
        benchmark = report.get("benchmarks") or {}
        cohorts = {
            cohort_id: {
                "brain": cohort.get("brain"),
                "model": cohort.get("model"),
                "reasoning_effort": cohort.get("reasoning_effort"),
                "provider": cohort.get("provider"),
                "raw": cohort.get("raw") or {},
                "scores": cohort.get("scores") or {},
            }
            for cohort_id, cohort in (benchmark.get("cohorts") or {}).items()
        }
        self.engine.log_event(
            "benchmark_checkpoint",
            message=f"Captured benchmark score trajectory at tick {tick}.",
            data={
                "schema_version": 1,
                "suite_id": benchmark.get("suite_id"),
                "protocol_id": (benchmark.get("protocol") or {}).get("id"),
                "tick": tick,
                "target_ticks": self.target_ticks,
                "score_horizon_ticks": tick,
                "cohorts": cohorts,
            },
            scope="private",
        )

    def _should_capture_plan_usage(self, tick: int, stopping: bool) -> bool:
        interval = max(0, int(os.environ.get("CODEX_PLAN_SNAPSHOT_INTERVAL_TICKS", "0")))
        return stopping or tick == self.target_ticks or (interval > 0 and tick % interval == 0)
