"""Shared lifecycle owner for CLI, experiment, and observatory simulations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable

from agent_world.agents import AgentBrain
from agent_world.brain_factory import BrainSpec, PopulationSpec, create_population_brains
from agent_world.brain_runtime import BrainRuntime
from agent_world.codex_brain import summarize_plan_usage
from agent_world.io import atomic_write_json
from agent_world.metrics import is_provider_failure_message, is_quota_failure_message
from agent_world.persistence import IncrementalRunWriter
from agent_world.run_report import write_report
from agent_world.runner import (
    ModelProviderUnavailableError,
    ModelQuotaUnavailableError,
    SimulationRunner,
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
        self.log_agent_io = log_agent_io
        self.concurrent_decisions = (
            self.max_workers > 1
            if concurrent_decisions is None
            else concurrent_decisions
        )
        self.lifecycle_metadata = dict(lifecycle_metadata or {})
        self.resumed = resumed
        self.checkpoint_extra_factory = checkpoint_extra
        self.before_tick = before_tick
        self.on_tick = on_tick
        self.on_terminal = on_terminal
        self.report_stem = report_stem
        self.plan_usage_path = plan_usage_path
        self.plan_usage_checkpoints = list(plan_usage_checkpoints or [])
        self.runner = SimulationRunner(
            engine,
            self.brains,
            log_agent_io=log_agent_io,
            concurrent_decisions=self.concurrent_decisions,
            max_workers=self.max_workers,
            provider_max_workers=self.provider_max_workers,
            decision_mode=self.decision_mode,
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
            stop_reason = "provider_unavailable"
        try:
            while status == "running" and self.engine.state.tick < self.target_ticks:
                if self.before_tick is not None and self.before_tick():
                    status = "stopped"
                    stop_reason = "stop_requested"
                    break
                usage_checkpoint = self.runtime.usage_checkpoint()
                try:
                    events = self.runner.step()
                except ModelQuotaUnavailableError as exc:
                    partial_usage_path = self.runtime.rollback_usage(
                        usage_checkpoint, attempted_tick=self.engine.state.tick
                    )
                    status = "paused_checkpoint"
                    stop_reason = "insufficient_quota"
                    self.engine.log_event(
                        "run_paused",
                        message=(
                            "Model quota became unavailable during decision collection; "
                            "the incomplete tick was discarded and this completed-tick checkpoint can be resumed."
                        ),
                        data={
                            "reason": stop_reason,
                            "target_ticks": self.target_ticks,
                            "completed_tick": self.engine.state.tick,
                            "provider_messages": exc.messages,
                            "partial_usage_path": (
                                str(partial_usage_path.resolve()) if partial_usage_path else None
                            ),
                        },
                        scope="public",
                    )
                    self.flush()
                    break
                except ModelProviderUnavailableError as exc:
                    partial_usage_path = self.runtime.rollback_usage(
                        usage_checkpoint, attempted_tick=self.engine.state.tick
                    )
                    status = "paused_checkpoint"
                    stop_reason = "provider_unavailable"
                    self.engine.log_event(
                        "run_paused",
                        message=(
                            "A model provider became unavailable during decision collection; "
                            "the incomplete tick was discarded and this completed-tick checkpoint can be resumed."
                        ),
                        data={
                            "reason": stop_reason,
                            "target_ticks": self.target_ticks,
                            "completed_tick": self.engine.state.tick,
                            "provider_messages": exc.messages,
                            "partial_usage_path": (
                                str(partial_usage_path.resolve()) if partial_usage_path else None
                            ),
                        },
                        scope="public",
                    )
                    self.flush()
                    break
                if any(
                    is_quota_failure_message(
                        getattr(event, "type", None), getattr(event, "message", None)
                    )
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
                    is_provider_failure_message(
                        getattr(event, "type", None), getattr(event, "message", None)
                    )
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
                if self._should_capture_plan_usage(self.engine.state.tick, bool(stop_reason)):
                    self._capture_plan_usage(self.engine.state.tick)
                if self.on_tick is not None:
                    self.on_tick(self, events)
                self.flush()
                if stop_reason:
                    break

            if status == "running":
                status = "completed"
            if status == "completed":
                self.engine.log_event(
                    "run_completed",
                    message=f"Completed {self.target_ticks} target ticks.",
                    data={"target_ticks": self.target_ticks},
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
                usage_records,
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

    def start(self) -> None:
        if self._started:
            return
        self._log_start()
        self.preflight_error = self._provider_preflight_error()
        if self.preflight_error:
            self.engine.log_event(
                "run_stopped",
                message=self.preflight_error,
                data={"reason": "provider_unavailable", "target_ticks": self.target_ticks},
                scope="public",
            )
        self._capture_plan_usage(self.engine.state.tick)
        self.flush()
        self._started = True

    def _provider_preflight_error(self) -> str | None:
        checked: set[tuple[type[Any], str]] = set()
        for brain in self.brains.values():
            preflight = getattr(brain, "preflight", None)
            if not callable(preflight):
                continue
            scope = str(getattr(getattr(brain, "runtime", None), "scope", "default"))
            key = (type(brain), scope)
            if key in checked:
                continue
            checked.add(key)
            error = preflight()
            if error:
                return str(error)
        return None

    def flush(self) -> None:
        extra = self.checkpoint_extra_factory(self) if self.checkpoint_extra_factory else None
        self.writer.flush(self.engine, checkpoint_extra=extra)

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

    def _should_capture_plan_usage(self, tick: int, stopping: bool) -> bool:
        interval = max(0, int(os.environ.get("CODEX_PLAN_SNAPSHOT_INTERVAL_TICKS", "0")))
        return stopping or tick == self.target_ticks or (interval > 0 and tick % interval == 0)
