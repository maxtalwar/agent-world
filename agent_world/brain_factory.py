"""Typed brain configuration and the single brain-construction path."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Iterable

from agent_world.agents import AgentBrain, SurvivalBrain
from agent_world.brain_runtime import BrainRuntime
from agent_world.claude_brain import ClaudeBrain
from agent_world.codex_brain import CodexBrain
from agent_world.openai_brain import OpenAIBrain
from agent_world.world import WorldEngine


ALLOWED_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh", "max"})
SUPPORTED_BRAIN_TYPES = frozenset({"survival", "llm", "codex", "claude"})


@dataclass(frozen=True)
class BrainSpec:
    type: str = "survival"
    model: str | None = None
    reasoning_effort: str | None = None
    max_workers: int | None = None

    @classmethod
    def resolve(
        cls,
        brain_type: str,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_workers: int | None = None,
    ) -> "BrainSpec":
        if brain_type not in SUPPORTED_BRAIN_TYPES:
            raise ValueError("brain type must be survival, llm, codex, or claude")
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if reasoning_effort is not None and reasoning_effort not in ALLOWED_EFFORTS:
            raise ValueError("unsupported reasoning effort")
        defaults = {
            "llm": ("OPENAI_MODEL", "z-ai/glm-5.2", "OPENAI_REASONING_EFFORT", "medium"),
            "codex": ("CODEX_MODEL", "gpt-5.6-luna", "CODEX_REASONING_EFFORT", "low"),
            "claude": ("CLAUDE_MODEL", "claude-sonnet-5", "CLAUDE_REASONING_EFFORT", "low"),
        }
        if brain_type == "survival":
            return cls(type=brain_type, max_workers=max_workers or 1)
        model_env, model_default, effort_env, effort_default = defaults[brain_type]
        worker_env = {
            "llm": "OPENAI_MAX_PARALLEL_AGENTS",
            "codex": "CODEX_MAX_PARALLEL_AGENTS",
            "claude": "CLAUDE_MAX_PARALLEL_AGENTS",
        }[brain_type]
        workers = max_workers if max_workers is not None else int(os.environ.get(worker_env, "1"))
        resolved_effort = reasoning_effort or os.environ.get(effort_env, effort_default)
        if resolved_effort not in ALLOWED_EFFORTS:
            raise ValueError(f"unsupported reasoning effort: {resolved_effort}")
        return cls(
            type=brain_type,
            model=model or os.environ.get(model_env, model_default),
            reasoning_effort=resolved_effort,
            max_workers=max(1, workers),
        )

    @property
    def model_backed(self) -> bool:
        return self.type in {"llm", "codex", "claude"}

    @property
    def provider(self) -> str | None:
        return {"llm": "openai_compatible", "codex": "codex_cli", "claude": "claude_cli"}.get(self.type)

    @property
    def billing_mode(self) -> str | None:
        return {"llm": "api", "codex": "chatgpt_plan", "claude": "claude_plan"}.get(self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "max_workers": self.max_workers,
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

    def __post_init__(self) -> None:
        if not self.groups:
            raise ValueError("population must contain at least one group")
        if any(group.count < 1 for group in self.groups):
            raise ValueError("population group counts must be at least 1")
        ids = [group.id for group in self.groups]
        if len(ids) != len(set(ids)):
            raise ValueError("population group ids must be unique")

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
    ) -> "PopulationSpec":
        groups = tuple(
            _parse_population_group(
                value,
                index=index,
                default_effort=reasoning_effort,
                max_workers=max_workers,
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
            )
            groups.append(
                PopulationGroup(
                    count=int(raw.get("count") or 0),
                    brain=brain,
                    id=str(raw.get("id") or f"cohort-{index}"),
                )
            )
        return cls(tuple(groups))

    def assignments(self, agent_ids: Iterable[str]) -> dict[str, PopulationGroup]:
        ordered_ids = list(agent_ids)
        if len(ordered_ids) != self.total_agents:
            raise ValueError(
                f"population describes {self.total_agents} agents but world contains {len(ordered_ids)}"
            )
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
    else:
        brain_type = _infer_brain_type(parts[0])
    effort = default_effort
    if len(parts) > 1 and parts[-1] in ALLOWED_EFFORTS:
        effort = parts.pop()
    model = ":".join(parts) or None
    if brain_type == "survival" and model not in {None, "survival"}:
        raise ValueError("survival population groups do not accept a model")
    brain = BrainSpec.resolve(
        brain_type,
        model=None if brain_type == "survival" else model,
        reasoning_effort=effort,
        max_workers=max_workers,
    )
    return PopulationGroup(count=count, brain=brain, id=f"cohort-{index}")


def _infer_brain_type(model: str) -> str:
    normalized = model.lower()
    if normalized.startswith("claude-"):
        return "claude"
    if normalized.startswith("gpt-5.6-"):
        return "codex"
    if normalized == "survival":
        return "survival"
    return "llm"


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
) -> dict[str, AgentBrain]:
    constructors = {
        "llm": OpenAIBrain,
        "codex": CodexBrain,
        "claude": ClaudeBrain,
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
        brains[agent_id] = brain_class(
            model=spec.model,
            reasoning_effort=spec.reasoning_effort,
            runtime=scoped_runtime,
        )
    return brains
