"""Typed brain configuration and the single brain-construction path."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import os
import random
from typing import Any, Iterable

from agent_world.agents import AgentBrain, SurvivalBrain
from agent_world.brain_boundary import (
    CONNECTOR_PROFILES,
    CONVERSATION_MODES,
    DEFAULT_SESSION_MAX_TURNS,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.claude_brain import ClaudeBrain
from agent_world.codex_brain import CodexBrain
from agent_world.cursor_brain import CursorBrain
from agent_world.openrouter_brain import OpenRouterBrain
from agent_world.devin_brain import DevinBrain
from agent_world.grok_brain import GrokBrain
from agent_world.world import WorldEngine


ALLOWED_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh", "max"})
DEFAULT_MODEL_MAX_WORKERS = 4
SUPPORTED_BRAIN_TYPES = frozenset(
    {"survival", "openrouter", "codex", "claude", "cursor", "devin", "grok"}
)
BRAIN_TYPE_PROVIDERS: dict[str, str] = {
    "openrouter": "openrouter",
    "codex": "codex_cli",
    "claude": "claude_cli",
    "cursor": "cursor_cli",
    "devin": "devin_cli",
    "grok": "grok_cli",
}


@dataclass(frozen=True)
class BrainSpec:
    type: str = "survival"
    model: str | None = None
    reasoning_effort: str | None = None
    max_workers: int | None = None
    connector_profile: str = "stateless-v1"
    conversation_mode: str = "stateless"
    session_max_turns: int = DEFAULT_SESSION_MAX_TURNS

    @classmethod
    def resolve(
        cls,
        brain_type: str,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_workers: int | None = None,
        connector_profile: str = "stateless-v1",
        conversation_mode: str = "stateless",
        session_max_turns: int = DEFAULT_SESSION_MAX_TURNS,
    ) -> "BrainSpec":
        # Read old manifests/checkpoints, but never emit the ambiguous legacy name.
        brain_type = "openrouter" if brain_type == "llm" else brain_type
        if brain_type not in SUPPORTED_BRAIN_TYPES:
            raise ValueError(
                "brain type must be survival, openrouter, codex, claude, cursor, devin, or grok"
            )
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if reasoning_effort is not None and reasoning_effort not in ALLOWED_EFFORTS:
            raise ValueError("unsupported reasoning effort")
        if connector_profile not in CONNECTOR_PROFILES:
            raise ValueError(
                "connector profile must be stateless-v1, stateless-v2, or stateless-v3"
            )
        if conversation_mode not in CONVERSATION_MODES:
            raise ValueError("conversation mode must be stateless or bounded-session-v1")
        if session_max_turns < 1:
            raise ValueError("session_max_turns must be at least 1")
        if conversation_mode != "stateless" and brain_type not in {
            "codex",
            "claude",
            "cursor",
            "devin",
        }:
            raise ValueError(
                "bounded-session-v1 is supported only by codex, claude, cursor, and devin brains"
            )
        defaults = {
            "openrouter": (
                "OPENROUTER_MODEL",
                "z-ai/glm-5.2",
                "OPENROUTER_REASONING_EFFORT",
                "medium",
            ),
            "codex": ("CODEX_MODEL", "gpt-5.6-luna", "CODEX_REASONING_EFFORT", "low"),
            "claude": ("CLAUDE_MODEL", "claude-sonnet-5", "CLAUDE_REASONING_EFFORT", "low"),
            "cursor": ("CURSOR_MODEL", "cursor-grok-4.5", "CURSOR_REASONING_EFFORT", "low"),
            "grok": ("GROK_MODEL", "grok-4.6", "GROK_REASONING_EFFORT", "medium"),
            "devin": (
                "DEVIN_MODEL",
                "swe-1-6-fast",
                "DEVIN_REASONING_EFFORT",
                "low",
            ),
        }
        if brain_type == "survival":
            return cls(
                type=brain_type,
                max_workers=max_workers or 1,
                connector_profile=connector_profile,
                conversation_mode=conversation_mode,
                session_max_turns=session_max_turns,
            )
        model_env, model_default, effort_env, effort_default = defaults[brain_type]
        worker_env = {
            "openrouter": "OPENROUTER_MAX_PARALLEL_AGENTS",
            "codex": "CODEX_MAX_PARALLEL_AGENTS",
            "claude": "CLAUDE_MAX_PARALLEL_AGENTS",
            "cursor": "CURSOR_MAX_PARALLEL_AGENTS",
            "devin": "DEVIN_MAX_PARALLEL_AGENTS",
            "grok": "GROK_MAX_PARALLEL_AGENTS",
        }[brain_type]
        workers = max_workers if max_workers is not None else int(
            os.environ.get(worker_env, str(DEFAULT_MODEL_MAX_WORKERS))
        )
        resolved_effort = reasoning_effort or os.environ.get(effort_env, effort_default)
        if resolved_effort not in ALLOWED_EFFORTS:
            raise ValueError(f"unsupported reasoning effort: {resolved_effort}")
        return cls(
            type=brain_type,
            model=model or os.environ.get(model_env, model_default),
            reasoning_effort=resolved_effort,
            max_workers=max(1, workers),
            connector_profile=connector_profile,
            conversation_mode=conversation_mode,
            session_max_turns=session_max_turns,
        )

    @property
    def model_backed(self) -> bool:
        return self.type in {"openrouter", "codex", "claude", "cursor", "devin", "grok"}

    @property
    def provider(self) -> str | None:
        return BRAIN_TYPE_PROVIDERS.get(self.type)

    @property
    def billing_mode(self) -> str | None:
        return {
            "openrouter": "api",
            "codex": "chatgpt_plan",
            "claude": "claude_plan",
            "cursor": "cursor_subscription",
            "devin": "devin_subscription",
            "grok": "grok_subscription",
        }.get(self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "max_workers": self.max_workers,
            "connector_profile": self.connector_profile,
            "conversation_mode": self.conversation_mode,
            "session_max_turns": self.session_max_turns,
            "provider": self.provider,
            "billing_mode": self.billing_mode,
        }


@dataclass(frozen=True)
class PopulationGroup:
    count: int
    brain: BrainSpec
    id: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "count": self.count, **self.brain.to_dict()}


@dataclass(frozen=True)
class PopulationSpec:
    """Ordered model cohorts and their deterministic agent assignments."""

    groups: tuple[PopulationGroup, ...]
    assignment_strategy: str = "ordered"
    assignment_seed: int = 0
    assigned_groups: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.groups:
            raise ValueError("population must contain at least one group")
        if any(group.count < 1 for group in self.groups):
            raise ValueError("population group counts must be at least 1")
        ids = [group.id for group in self.groups]
        if len(ids) != len(set(ids)):
            raise ValueError("population group ids must be unique")
        if self.assignment_strategy not in {"ordered", "stratified"}:
            raise ValueError("assignment strategy must be ordered or stratified")

    @property
    def total_agents(self) -> int:
        return sum(group.count for group in self.groups)

    @property
    def mixed(self) -> bool:
        signatures = {
            (group.brain.type, group.brain.model, group.brain.reasoning_effort)
            for group in self.groups
        }
        return len(signatures) > 1

    @property
    def run_type(self) -> str:
        return "mixed" if self.mixed else self.groups[0].brain.type

    @property
    def model_backed(self) -> bool:
        return any(group.brain.model_backed for group in self.groups)

    @classmethod
    def uniform(cls, count: int, brain: BrainSpec) -> "PopulationSpec":
        return cls((PopulationGroup(count=count, brain=brain, id="cohort-1"),))

    @classmethod
    def parse_many(
        cls,
        values: Iterable[str],
        *,
        reasoning_effort: str | None = None,
        max_workers: int | None = None,
        connector_profile: str = "stateless-v1",
        conversation_mode: str = "stateless",
        session_max_turns: int = DEFAULT_SESSION_MAX_TURNS,
    ) -> "PopulationSpec":
        groups = tuple(
            _parse_population_group(
                value,
                index=index,
                default_effort=reasoning_effort,
                max_workers=max_workers,
                connector_profile=connector_profile,
                conversation_mode=conversation_mode,
                session_max_turns=session_max_turns,
            )
            for index, value in enumerate(values, start=1)
        )
        return cls(groups)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PopulationSpec":
        raw_groups = value.get("groups")
        if not isinstance(raw_groups, list):
            raise ValueError("saved population is missing groups")
        groups: list[PopulationGroup] = []
        for index, raw in enumerate(raw_groups, start=1):
            if not isinstance(raw, dict):
                raise ValueError("saved population group must be an object")
            brain = BrainSpec.resolve(
                str(raw.get("type") or "survival"),
                model=raw.get("model"),
                reasoning_effort=raw.get("reasoning_effort"),
                max_workers=raw.get("max_workers"),
                connector_profile=str(raw.get("connector_profile") or "stateless-v1"),
                conversation_mode=str(raw.get("conversation_mode") or "stateless"),
                session_max_turns=int(
                    raw.get("session_max_turns") or DEFAULT_SESSION_MAX_TURNS
                ),
            )
            groups.append(
                PopulationGroup(
                    count=int(raw.get("count") or 0),
                    brain=brain,
                    id=str(raw.get("id") or f"cohort-{index}"),
                )
            )
        raw_assignments = value.get("assignments")
        assigned_groups = (
            tuple(sorted((str(agent_id), str(group_id)) for agent_id, group_id in raw_assignments.items()))
            if isinstance(raw_assignments, dict)
            else ()
        )
        return cls(
            tuple(groups),
            assignment_strategy=str(value.get("assignment_strategy") or "ordered"),
            assignment_seed=int(value.get("assignment_seed") or 0),
            assigned_groups=assigned_groups,
        )

    def bind_assignments(
        self,
        engine: WorldEngine,
        *,
        strategy: str,
        seed: int,
    ) -> "PopulationSpec":
        """Freeze a reproducible assignment before any model decisions occur."""

        agent_ids = list(engine.state.agents)
        if strategy == "ordered":
            ordered = agent_ids
        elif strategy == "stratified":
            rng = random.Random(seed)
            strata: dict[str, list[str]] = {}
            for agent_id in agent_ids:
                agent = engine.state.agents[agent_id]
                strata.setdefault(agent.specialty or "generalist", []).append(agent_id)
            stratum_names = sorted(strata)
            rng.shuffle(stratum_names)
            remaining = {group.id: group.count for group in self.groups}
            remaining_agents = len(agent_ids)
            assigned_pairs: list[tuple[str, str]] = []
            for stratum_index, stratum_name in enumerate(stratum_names):
                members = strata[stratum_name]
                rng.shuffle(members)
                if stratum_index == len(stratum_names) - 1:
                    allocations = dict(remaining)
                else:
                    raw = {
                        group.id: remaining[group.id] * len(members) / remaining_agents
                        for group in self.groups
                    }
                    allocations = {group_id: int(value) for group_id, value in raw.items()}
                    unfilled = len(members) - sum(allocations.values())
                    ranked = sorted(
                        self.groups,
                        key=lambda group: (raw[group.id] - allocations[group.id], remaining[group.id], group.id),
                        reverse=True,
                    )
                    for group in ranked[:unfilled]:
                        allocations[group.id] += 1
                slots = [
                    group.id
                    for group in self.groups
                    for _ in range(allocations[group.id])
                ]
                rng.shuffle(slots)
                assigned_pairs.extend(zip(members, slots))
                for group_id, count in allocations.items():
                    remaining[group_id] -= count
                remaining_agents -= len(members)
            assigned = tuple(sorted(assigned_pairs))
        else:
            raise ValueError("assignment strategy must be ordered or stratified")
        if strategy == "ordered":
            group_slots: list[PopulationGroup] = []
            for group in self.groups:
                group_slots.extend([group] * group.count)
            assigned = tuple(
                sorted((agent_id, group.id) for agent_id, group in zip(ordered, group_slots))
            )
        return PopulationSpec(
            self.groups,
            assignment_strategy=strategy,
            assignment_seed=seed,
            assigned_groups=assigned,
        )

    def assignments(self, agent_ids: Iterable[str]) -> dict[str, PopulationGroup]:
        ordered_ids = list(agent_ids)
        if len(ordered_ids) != self.total_agents:
            raise ValueError(
                f"population describes {self.total_agents} agents but world contains {len(ordered_ids)}"
            )
        groups_by_id = {group.id: group for group in self.groups}
        if self.assigned_groups:
            assignments = {
                agent_id: groups_by_id[group_id] for agent_id, group_id in self.assigned_groups
            }
            if set(assignments) != set(ordered_ids):
                raise ValueError("saved population assignments do not match world agents")
            return assignments
        assignments: dict[str, PopulationGroup] = {}
        cursor = 0
        for group in self.groups:
            for agent_id in ordered_ids[cursor : cursor + group.count]:
                assignments[agent_id] = group
            cursor += group.count
        return assignments

    def to_dict(self, agent_ids: Iterable[str] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.run_type,
            "total_agents": self.total_agents,
            "groups": [group.to_dict() for group in self.groups],
            "assignment_strategy": self.assignment_strategy,
            "assignment_seed": self.assignment_seed,
        }
        if agent_ids is not None:
            result["assignments"] = {
                agent_id: group.id for agent_id, group in self.assignments(agent_ids).items()
            }
        return result


def _parse_population_group(
    value: str,
    *,
    index: int,
    default_effort: str | None,
    max_workers: int | None,
    connector_profile: str,
    conversation_mode: str,
    session_max_turns: int,
) -> PopulationGroup:
    try:
        raw_count, raw_target = value.split("@", 1)
        count = int(raw_count)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"invalid population {value!r}; expected COUNT@MODEL or COUNT@BRAIN:MODEL"
        ) from exc
    if count < 1 or not raw_target.strip():
        raise ValueError("population group count must be at least 1 and model cannot be empty")
    parts = raw_target.strip().split(":")
    if parts[0] in SUPPORTED_BRAIN_TYPES:
        brain_type = parts.pop(0)
    elif parts[0] == "llm":
        brain_type = "openrouter"
        parts.pop(0)
    else:
        brain_type = _infer_brain_type(parts[0])
    effort = default_effort
    if len(parts) > 1 and parts[-1] in ALLOWED_EFFORTS:
        effort = parts.pop()
    model = ":".join(parts) or None
    if brain_type == "codex" and model and model.lower().startswith("openai/"):
        model = model.split("/", 1)[1]
    if brain_type == "survival" and model not in {None, "survival"}:
        raise ValueError("survival population groups do not accept a model")
    brain = BrainSpec.resolve(
        brain_type,
        model=None if brain_type == "survival" else model,
        reasoning_effort=effort,
        max_workers=max_workers,
        connector_profile=connector_profile,
        conversation_mode=conversation_mode,
        session_max_turns=session_max_turns,
    )
    return PopulationGroup(count=count, brain=brain, id=f"cohort-{index}")


def _infer_brain_type(model: str) -> str:
    normalized = model.lower()
    if normalized.startswith("grok-"):
        return "grok"
    if normalized.startswith("swe-") or normalized.startswith("devin-"):
        return "devin"
    if normalized.startswith("cursor-") or normalized.startswith("composer-"):
        return "cursor"
    if normalized.startswith("claude-"):
        return "claude"
    if normalized.startswith("gpt-") or normalized.startswith("openai/gpt-"):
        return "codex"
    if normalized == "survival":
        return "survival"
    return "openrouter"


def create_brains(
    engine: WorldEngine,
    spec: BrainSpec,
    runtime: BrainRuntime,
) -> dict[str, AgentBrain]:
    return create_population_brains(
        engine,
        PopulationSpec.uniform(len(engine.state.agents), spec),
        runtime,
    )


def create_population_brains(
    engine: WorldEngine,
    population: PopulationSpec,
    runtime: BrainRuntime,
    *,
    checkpoint_brain_states: dict[str, Any] | None = None,
) -> dict[str, AgentBrain]:
    constructors = {
        "openrouter": OpenRouterBrain,
        "codex": CodexBrain,
        "claude": ClaudeBrain,
        "cursor": CursorBrain,
        "devin": DevinBrain,
        "grok": GrokBrain,
    }
    brains: dict[str, AgentBrain] = {}
    scoped_runtimes: dict[str, Any] = {}
    for agent_id, group in population.assignments(engine.state.agents).items():
        spec = group.brain
        if spec.type == "survival":
            brains[agent_id] = SurvivalBrain()
            continue
        brain_class = constructors[spec.type]
        scope = spec.provider or spec.type
        scoped_runtime = scoped_runtimes.setdefault(scope, runtime.scoped(scope))
        kwargs: dict[str, Any] = {
            "model": spec.model,
            "reasoning_effort": spec.reasoning_effort,
            "runtime": scoped_runtime,
        }
        if spec.type in {"codex", "claude", "cursor", "devin", "grok"}:
            boundary_kwargs = {
                "agent_id": agent_id,
                "connector_profile": spec.connector_profile,
                "conversation_mode": spec.conversation_mode,
                "session_max_turns": spec.session_max_turns,
            }
            accepted = inspect.signature(brain_class).parameters
            kwargs.update(
                {
                    key: value
                    for key, value in boundary_kwargs.items()
                    if key in accepted
                }
            )
        brain = brain_class(**kwargs)
        saved_state = (checkpoint_brain_states or {}).get(agent_id)
        restore = getattr(brain, "restore_checkpoint_state", None)
        if isinstance(saved_state, dict) and callable(restore):
            restore(saved_state)
        brains[agent_id] = brain
    return brains
