"""Simulation runner that connects brains to the world engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import threading
from typing import Any

from agent_world.agents import AgentBrain
from agent_world.interface import (
    build_dynamic_observation,
    build_observation,
    build_static_context,
    parse_agent_response,
)
from agent_world.metrics import is_provider_failure_message, is_quota_failure_message
from agent_world.models import AgentDecision
from agent_world.world import WorldEngine


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
    ):
        self.engine = engine
        self.brains = brains
        self.log_agent_io = log_agent_io
        self.concurrent_decisions = concurrent_decisions
        self.max_workers = max_workers
        self.provider_max_workers = dict(provider_max_workers or {})
        self.decision_mode = decision_mode
        if decision_mode not in {"raw", "validated"}:
            raise ValueError("decision mode must be raw or validated")
        self._provider_semaphores = {
            provider: threading.BoundedSemaphore(limit)
            for provider, limit in self.provider_max_workers.items()
        }
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
        decisions = self._collect_decisions(agent_ids, observations)
        quota_messages = sorted(
            {
                decision.intent
                for decision in decisions.values()
                if is_quota_failure_message("agent_response", decision.intent)
            }
        )
        if quota_messages:
            raise ModelQuotaUnavailableError(quota_messages)
        provider_messages = sorted(
            {
                decision.intent
                for decision in decisions.values()
                if is_provider_failure_message("agent_response", decision.intent)
            }
        )
        if provider_messages:
            raise ModelProviderUnavailableError(provider_messages)
        for agent_id, observation in observations.items():
            self._log_agent_input(agent_id, observation)
        return self.engine.tick(decisions)

    def _collect_decisions(
        self,
        agent_ids: list[str],
        observations: dict[str, dict[str, Any]],
    ) -> dict[str, AgentDecision]:
        if not self.concurrent_decisions or len(agent_ids) <= 1:
            return {
                agent_id: self._decide(agent_id, observations[agent_id])
                for agent_id in agent_ids
            }
        decisions: dict[str, AgentDecision] = {}
        worker_count = self.max_workers or len(agent_ids)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._decide, agent_id, observations[agent_id]): agent_id
                for agent_id in agent_ids
            }
            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    decisions[agent_id] = parse_agent_response(future.result())
                except Exception as exc:  # Defensive shell around third-party brains.
                    decisions[agent_id] = AgentDecision(
                        intent=f"Agent brain failed: {exc}",
                        actions=[{"type": "wait"}],
                        messages=[],
                        memory_updates=[],
                    )
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

    def __init__(self, messages: list[str]):
        super().__init__(messages[0] if messages else "Model quota unavailable")
        self.messages = list(messages)


class ModelProviderUnavailableError(RuntimeError):
    """Raised before world resolution when a model provider is unavailable."""

    def __init__(self, messages: list[str]):
        super().__init__(messages[0] if messages else "Model provider unavailable")
        self.messages = list(messages)


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
