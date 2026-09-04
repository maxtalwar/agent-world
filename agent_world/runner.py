"""Simulation runner that connects brains to the world engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable

from agent_world.agents import AgentBrain
from agent_world.interface import (
    build_dynamic_observation,
    build_observation,
    build_static_context,
    parse_agent_response,
)
from agent_world.io import atomic_write_json
from agent_world.metrics import (
    is_auth_failure_message,
    is_ambiguous_boundary_failure_message,
    is_provider_failure_message,
    is_quota_failure_message,
)
from agent_world.models import AgentDecision
from agent_world.decision_outcome import restore_decision
from agent_world.world import WorldEngine


PENDING_TICK_SCHEMA_VERSION = 2
MAX_PENDING_TICK_BYTES = 1_000_000


def pending_tick_path_for_artifacts(
    events_path: Path | None, checkpoint_path: Path | None
) -> Path | None:
    """Return the single bounded journal beside a run's durable artifacts."""

    if events_path is not None:
        return events_path.with_name(f"{events_path.stem}-pending-tick.json")
    if checkpoint_path is None:
        return None
    stem = checkpoint_path.stem
    if stem.endswith("-checkpoint"):
        stem = stem[: -len("-checkpoint")]
    return checkpoint_path.with_name(f"{stem}-pending-tick.json")


def pending_tick_cached_agent_ids(path: Path | None, engine: WorldEngine) -> set[str]:
    """Identify cache-valid agents before resume reconciles their usage rows."""

    if path is None:
        return set()
    agent_ids = [
        agent_id
        for agent_id in sorted(engine.state.agents)
        if engine.state.agents[agent_id].alive
    ]
    observations = {
        agent_id: build_observation(engine.state, agent_id) for agent_id in agent_ids
    }
    payload = _read_pending_payload(path)
    if payload is None or payload.get("tick") != engine.state.tick:
        return set()
    records = payload.get("decisions")
    if not isinstance(records, dict):
        return set()
    return {
        agent_id
        for agent_id, observation in observations.items()
        if isinstance(records.get(agent_id), dict)
        and records[agent_id].get("observation_sha256")
        == _observation_sha256(observation)
        and not _is_retryable_failure(
            restore_decision(records[agent_id].get("decision"))
        )
    }


class PendingTickJournal:
    """Bounded write-through cache for accepted decisions in one frozen tick."""

    def __init__(
        self,
        path: Path | None,
        *,
        tick: int,
        observations: dict[str, dict[str, Any]],
        brains: dict[str, AgentBrain],
    ):
        self.path = path
        self.tick = tick
        self.observation_hashes = {
            agent_id: _observation_sha256(observation)
            for agent_id, observation in observations.items()
        }
        self.brains = brains
        self.decisions: dict[str, AgentDecision] = {}
        self.records: dict[str, dict[str, Any]] = {}
        self.failures: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        payload = _read_pending_payload(self.path)
        if payload is None:
            return
        if (
            payload.get("schema_version") != PENDING_TICK_SCHEMA_VERSION
            or payload.get("tick") != self.tick
        ):
            self.clear()
            return
        raw_records = payload.get("decisions")
        raw_failures = payload.get("failures")
        if isinstance(raw_failures, list):
            self.failures = [
                dict(row) for row in raw_failures if isinstance(row, dict)
            ][-100:]
        if not isinstance(raw_records, dict):
            self.clear()
            return
        changed = False
        for agent_id, record in raw_records.items():
            if (
                agent_id not in self.observation_hashes
                or not isinstance(record, dict)
                or record.get("observation_sha256") != self.observation_hashes[agent_id]
            ):
                changed = True
                continue
            decision = restore_decision(record.get("decision"))
            if _is_retryable_failure(decision):
                changed = True
                continue
            brain_state = record.get("brain_state")
            restore = getattr(self.brains.get(agent_id), "restore_checkpoint_state", None)
            if isinstance(brain_state, dict) and callable(restore):
                try:
                    restore(brain_state)
                except (TypeError, ValueError):
                    changed = True
                    continue
            self.decisions[agent_id] = decision
            self.records[agent_id] = dict(record)
        if changed:
            self._write()

    def record_decision(self, agent_id: str, decision: AgentDecision) -> None:
        brain_state = None
        export = getattr(self.brains.get(agent_id), "export_checkpoint_state", None)
        if callable(export):
            candidate = export()
            if isinstance(candidate, dict):
                brain_state = candidate
        record = {
            "observation_sha256": self.observation_hashes[agent_id],
            "decision": asdict(decision),
            "brain_state": brain_state,
        }
        self.decisions[agent_id] = decision
        self.records[agent_id] = record
        self._write()

    def record_failure(
        self, agent_id: str, decision: AgentDecision, *, retry_round: int
    ) -> None:
        self.failures.append(
            {
                "agent_id": agent_id,
                "intent": decision.intent,
                "retry_round": retry_round,
                "time": time.time(),
            }
        )
        self.failures = self.failures[-100:]
        self._write()

    def _write(self) -> None:
        if self.path is None:
            return
        payload = {
            "schema_version": PENDING_TICK_SCHEMA_VERSION,
            "tick": self.tick,
            "decisions": self.records,
            "failures": self.failures,
        }
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > MAX_PENDING_TICK_BYTES:
            raise ValueError(
                f"Pending-tick journal exceeded {MAX_PENDING_TICK_BYTES} bytes"
            )
        atomic_write_json(self.path, payload, fsync=True)

    def clear(self) -> None:
        self.decisions.clear()
        self.records.clear()
        self.failures.clear()
        if self.path is not None:
            self.path.unlink(missing_ok=True)


def _read_pending_payload(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            encoded = handle.read(MAX_PENDING_TICK_BYTES + 1)
        if len(encoded) > MAX_PENDING_TICK_BYTES:
            raise ValueError("Pending-tick journal exceeds its size limit")
        value = json.loads(encoded)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _observation_sha256(observation: dict[str, Any]) -> str:
    encoded = json.dumps(observation, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _is_retryable_failure(decision: AgentDecision) -> bool:
    return decision.failure_kind not in {None, "model_output"}


class SimulationRunner:
    """Orchestrates observe -> decide -> validate ticks.

    The runner logs observations and prompts as private events so a run can be
    audited without exposing one agent's private context to another agent.
    """

    def __init__(
        self,
        engine: WorldEngine,
        brains: dict[str, AgentBrain],
        log_agent_io: bool = True,
        concurrent_decisions: bool = False,
        max_workers: int | None = None,
        provider_max_workers: dict[str, int] | None = None,
        decision_mode: str = "raw",
        pending_tick_path: Path | None = None,
        provider_retry_rounds: int = 0,
        provider_retry_backoff_seconds: float = 15.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.engine = engine
        self.brains = brains
        self.log_agent_io = log_agent_io
        self.concurrent_decisions = concurrent_decisions
        self.max_workers = max_workers
        self.provider_max_workers = dict(provider_max_workers or {})
        self.decision_mode = decision_mode
        self.pending_tick_path = pending_tick_path
        self.provider_retry_rounds = max(0, int(provider_retry_rounds))
        self.provider_retry_backoff_seconds = max(
            0.0, float(provider_retry_backoff_seconds)
        )
        self._sleep = sleep
        self._active_journal: PendingTickJournal | None = None
        if decision_mode not in {"raw", "validated"}:
            raise ValueError("decision mode must be raw or validated")
        self._provider_semaphores = {
            provider: threading.BoundedSemaphore(limit)
            for provider, limit in self.provider_max_workers.items()
        }
        self._systemic_boundary_streak = 0
        self._logged_static_contexts: set[str] = {
            str(event.data.get("static_context_sha256"))
            for event in self.engine.state.events
            if event.type == "agent_prompt_context" and event.data.get("static_context_sha256")
        }

    def step(self) -> list[Any]:
        agent_ids = [
            agent_id
            for agent_id in sorted(self.engine.state.agents)
            if self.engine.state.agents[agent_id].alive and agent_id in self.brains
        ]
        observations = {agent_id: build_observation(self.engine.state, agent_id) for agent_id in agent_ids}
        journal = self._journal_for(agent_ids, observations)
        decisions = dict(journal.decisions)
        unresolved = [agent_id for agent_id in agent_ids if agent_id not in decisions]
        retry_round = 0
        while unresolved:
            authentication_failures: dict[str, str] = {}
            quota_failures: dict[str, str] = {}
            provider_failures: dict[str, str] = {}

            def record_completed(agent_id: str, decision: AgentDecision) -> None:
                decisions[agent_id] = decision
                if decision.failure_kind == "authentication":
                    authentication_failures[agent_id] = decision.intent
                    journal.record_failure(agent_id, decision, retry_round=retry_round)
                elif decision.failure_kind == "quota":
                    quota_failures[agent_id] = decision.intent
                    journal.record_failure(agent_id, decision, retry_round=retry_round)
                elif decision.failure_kind == "provider":
                    provider_failures[agent_id] = decision.intent
                    journal.record_failure(agent_id, decision, retry_round=retry_round)
                elif decision.failure_kind == "harness":
                    journal.record_failure(agent_id, decision, retry_round=retry_round)
                else:
                    journal.record_decision(agent_id, decision)

            self._collect_decisions(
                unresolved, observations, on_decision=record_completed
            )
            if authentication_failures:
                raise ModelAuthenticationRequiredError(
                    authentication_failures, cached_agents=sorted(journal.decisions)
                )
            if quota_failures:
                raise ModelQuotaUnavailableError(
                    quota_failures, cached_agents=sorted(journal.decisions)
                )
            if not provider_failures:
                break
            if retry_round >= self.provider_retry_rounds:
                raise ModelProviderUnavailableError(
                    provider_failures,
                    cached_agents=sorted(journal.decisions),
                    retry_rounds=retry_round,
                )
            unresolved = sorted(provider_failures)
            retry_round += 1
            if self.provider_retry_backoff_seconds:
                self._sleep(
                    self.provider_retry_backoff_seconds * (2 ** (retry_round - 1))
                )
        self._guard_systemic_boundary_failure(decisions)
        for agent_id, observation in observations.items():
            self._log_agent_input(agent_id, observation)
        return self.engine.tick(decisions)

    @property
    def cached_decision_count(self) -> int:
        return len(self._active_journal.decisions) if self._active_journal else 0

    def commit_pending_tick(self) -> None:
        """Delete cache only after the session durably flushes the advanced tick."""

        if (
            self._active_journal is not None
            and self.engine.state.tick > self._active_journal.tick
        ):
            self._active_journal.clear()
            self._active_journal = None

    def discard_pending_tick(self) -> None:
        if self._active_journal is not None:
            self._active_journal.clear()
            self._active_journal = None

    def _journal_for(
        self,
        agent_ids: list[str],
        observations: dict[str, dict[str, Any]],
    ) -> PendingTickJournal:
        if (
            self._active_journal is not None
            and self._active_journal.tick == self.engine.state.tick
        ):
            return self._active_journal
        if self._active_journal is not None:
            self._active_journal.clear()
        self._active_journal = PendingTickJournal(
            self.pending_tick_path,
            tick=self.engine.state.tick,
            observations={agent_id: observations[agent_id] for agent_id in agent_ids},
            brains=self.brains,
        )
        return self._active_journal

    def _guard_systemic_boundary_failure(
        self, decisions: dict[str, AgentDecision]
    ) -> None:
        """Any infrastructure failure freezes the tick, including a lone failure."""
        failures = [
            decision.intent for decision in decisions.values()
            if decision.failure_kind == "harness"
        ]
        if failures:
            raise ModelDecisionsUnusableError(
                sorted(set(failures)), agents=len(failures), consecutive_ticks=1
            )

    def _collect_decisions(
        self,
        agent_ids: list[str],
        observations: dict[str, dict[str, Any]],
        *,
        on_decision: Callable[[str, AgentDecision], None] | None = None,
    ) -> dict[str, AgentDecision]:
        if not self.concurrent_decisions or len(agent_ids) <= 1:
            decisions: dict[str, AgentDecision] = {}
            for agent_id in agent_ids:
                decision = self._decide(agent_id, observations[agent_id])
                decisions[agent_id] = decision
                if on_decision is not None:
                    on_decision(agent_id, decision)
            return decisions
        decisions: dict[str, AgentDecision] = {}
        worker_count = self.max_workers or len(agent_ids)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._decide, agent_id, observations[agent_id]): agent_id
                for agent_id in agent_ids
            }
            for future in as_completed(futures):
                agent_id = futures[future]
                decisions[agent_id] = parse_agent_response(future.result())
                if on_decision is not None:
                    on_decision(agent_id, decisions[agent_id])
        return decisions

    def _decide(self, agent_id: str, observation: dict[str, Any]) -> AgentDecision:
        brain = self.brains[agent_id]
        runtime = getattr(brain, "runtime", None)
        provider = getattr(runtime, "scope", None) or "default"
        semaphore = self._provider_semaphores.get(provider)
        if semaphore is None:
            decision = parse_agent_response(brain.decide(observation))
        else:
            with semaphore:
                decision = parse_agent_response(brain.decide(observation))
        if self.decision_mode == "validated":
            decision = _truncate_to_declared_action_budget(decision, observation)
        return decision

    def _log_agent_input(self, agent_id: str, observation: dict[str, Any]) -> None:
        if not self.log_agent_io:
            return
        agent = self.engine.state.agents[agent_id]
        static_context = build_static_context(observation.get("world", {}))
        static_hash = hashlib.sha256(static_context.encode("utf-8")).hexdigest()
        if static_hash not in self._logged_static_contexts:
            self.engine.log_event(
                "agent_prompt_context",
                actor_id=None,
                data={
                    "static_context": static_context,
                    "static_context_sha256": static_hash,
                    "format": "static_context_v2",
                },
                scope="private",
                recipients=set(self.engine.state.agents),
            )
            self._logged_static_contexts.add(static_hash)
        dynamic = build_dynamic_observation(observation)
        dynamic_json = json.dumps(dynamic, separators=(",", ":"), sort_keys=True)
        component_chars = {
            key: len(json.dumps(value, separators=(",", ":"), sort_keys=True))
            for key, value in dynamic.items()
        }
        self.engine.log_event(
            "agent_observation",
            actor_id=agent_id,
            position=agent.position,
            data={"observation": dynamic, "format": "compact_dynamic_v2"},
            scope="private",
            recipients={agent_id},
        )
        self.engine.log_event(
            "agent_prompt",
            actor_id=agent_id,
            position=agent.position,
            data={
                "static_context_sha256": static_hash,
                "dynamic_sha256": hashlib.sha256(dynamic_json.encode("utf-8")).hexdigest(),
                "dynamic_component_chars": component_chars,
                "format": "static_context_ref_plus_compact_dynamic_v2",
            },
            scope="private",
            recipients={agent_id},
        )


class ModelQuotaUnavailableError(RuntimeError):
    """Raised before world resolution when a provider exhausts its quota."""

    def __init__(
        self,
        failures: dict[str, str] | list[str],
        *,
        cached_agents: list[str] | None = None,
    ):
        self.failures = dict(failures) if isinstance(failures, dict) else {}
        messages = (
            sorted(set(self.failures.values())) if self.failures else list(failures)
        )
        super().__init__(messages[0] if messages else "Model quota unavailable")
        self.messages = messages
        self.cached_agents = list(cached_agents or [])


class ModelAuthenticationRequiredError(RuntimeError):
    """Raised before world resolution when a connector needs authentication."""

    def __init__(
        self,
        failures: dict[str, str] | list[str],
        *,
        cached_agents: list[str] | None = None,
    ):
        self.failures = dict(failures) if isinstance(failures, dict) else {}
        messages = (
            sorted(set(self.failures.values())) if self.failures else list(failures)
        )
        super().__init__(messages[0] if messages else "Model authentication required")
        self.messages = messages
        self.cached_agents = list(cached_agents or [])


class ModelProviderUnavailableError(RuntimeError):
    """Raised before world resolution when a model provider is unavailable."""

    def __init__(
        self,
        failures: dict[str, str] | list[str],
        *,
        cached_agents: list[str] | None = None,
        retry_rounds: int = 0,
    ):
        self.failures = dict(failures) if isinstance(failures, dict) else {}
        messages = (
            sorted(set(self.failures.values())) if self.failures else list(failures)
        )
        super().__init__(messages[0] if messages else "Model provider unavailable")
        self.messages = messages
        self.cached_agents = list(cached_agents or [])
        self.retry_rounds = retry_rounds


class ModelDecisionsUnusableError(RuntimeError):
    """Raised before world resolution when a whole population fails identically.

    The catch-all for external faults no message classifier recognizes. Handled
    exactly like a provider outage: discard the partial tick and pause to a
    resumable checkpoint rather than advance the world on fabricated actions.
    """

    def __init__(self, messages: list[str], *, agents: int, consecutive_ticks: int):
        super().__init__(messages[0] if messages else "Model decisions unusable")
        self.messages = list(messages)
        self.agents = agents
        self.consecutive_ticks = consecutive_ticks


def _truncate_to_declared_action_budget(
    decision: AgentDecision, observation: dict[str, Any]
) -> AgentDecision:
    """Optional assisted condition: remove only actions that exceed declared AP."""

    remaining = int((observation.get("world") or {}).get("action_points_per_tick") or 0)
    costs = {
        str(action.get("type")): (action.get("cost") or {}).get("action_points")
        for action in observation.get("valid_actions", [])
        if isinstance(action, dict)
    }
    kept: list[dict[str, Any]] = []
    for action in decision.actions:
        raw_cost = costs.get(str(action.get("type")), 1)
        cost = raw_cost if isinstance(raw_cost, int) else 1
        if cost > remaining:
            break
        kept.append(action)
        remaining -= cost
    decision.actions = kept or [{"type": "wait"}]
    return decision
