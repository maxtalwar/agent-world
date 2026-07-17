"""Local web observatory for Agent World runs."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from agent_world.brain_factory import (
    ALLOWED_EFFORTS,
    BrainSpec,
    PopulationGroup,
    PopulationSpec,
    create_population_brains,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.env import load_dotenv
from agent_world.interface import OBSERVATION_MODES
from agent_world.io import atomic_write_json
from agent_world.metrics import compute_metrics, is_decision_failure_message, is_quota_failure_message
from agent_world.models import WorldConfig
from agent_world.persistence import IncrementalRunWriter
from agent_world.run_catalog import refresh_catalog_for_output, write_run_catalog
from agent_world.session import SimulationSession
from agent_world.world import DEFAULT_TURN_MODE, TURN_MODES, WorldEngine


AGENT_IO_EVENT_TYPES = {
    "agent_observation",
    "agent_prompt",
    "agent_prompt_context",
    "agent_activation",
    "tick_activation_order",
}

TUNED_OBSERVATORY_DEFAULTS = {
    "ticks": 20,
    "agents": 5,
    "brain": "llm",
    "seed": 11,
    "model": "z-ai/glm-5.2",
    "reasoning_effort": "medium",
    "log_agent_io": True,
    "max_workers": 1,
}

OBSERVATORY_PRESETS = {
    "baseline": {
        "label": "Common Ground",
        "description": "Shared oasis, generalists, and the simplest world rules.",
        "economy_mode": "baseline",
        "geography_mode": "shared_oasis",
        "objective_mode": "neutral",
        "specialization_mode": "generalists",
    },
    "organic-generalists": {
        "label": "Open Frontier",
        "description": "Dispersed starts and physical exchange without assigned economic roles.",
        "economy_mode": "organic",
        "geography_mode": "dispersed",
        "objective_mode": "neutral",
        "specialization_mode": "generalists",
    },
    "experimental-organic-specialists": {
        "label": "Specialist Provinces",
        "description": "Experimental comparative advantages across a dispersed organic world.",
        "economy_mode": "organic",
        "geography_mode": "dispersed",
        "objective_mode": "neutral",
        "specialization_mode": "specialists",
    },
}

MODEL_LIBRARY = {
    "codex": ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"],
    "claude": ["claude-sonnet-5", "claude-opus-4-8", "fable"],
    "llm": ["z-ai/glm-5.2", "gpt-5.4-mini"],
    "survival": ["survival"],
}


@dataclass(frozen=True)
class RunConfig:
    ticks: int = 25
    agents: int = 5
    brain: str = "survival"
    model: str | None = None
    reasoning_effort: str | None = None
    log_agent_io: bool = True
    max_workers: int = 1
    turn_mode: str = DEFAULT_TURN_MODE
    preset: str = "organic-generalists"
    decision_mode: str = "raw"
    observation_mode: str = "compact-v2"
    assignment_strategy: str = "ordered"
    assignment_seed: int = 0
    provider_max_workers: dict[str, int] = field(default_factory=dict)
    population: PopulationSpec | None = None
    name: str = ""
    world_config: WorldConfig = field(default_factory=WorldConfig)

    def public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["population"] = self.population.to_dict() if self.population else None
        return result


@dataclass
class RunStatus:
    state: str = "idle"
    current_tick: int = 0
    target_ticks: int = 0
    agents: int = 0
    brain: str = ""
    seed: int = 1
    model: str | None = None
    reasoning_effort: str | None = None
    log_agent_io: bool = True
    max_workers: int = 1
    turn_mode: str = DEFAULT_TURN_MODE
    started_at: float | None = None
    finished_at: float | None = None
    stop_requested: bool = False
    paused: bool = False
    error: str = ""
    run_id: str | None = None
    output_dir: str | None = None
    files: dict[str, str] = field(default_factory=dict)
    population: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunController:
    """Owns one background simulation launched from the observatory UI."""

    def __init__(
        self,
        snapshot_path: Path,
        events_path: Path,
        *,
        runs_root: Path | None = None,
    ):
        self.snapshot_path = snapshot_path
        self.events_path = events_path
        self.checkpoint_path = events_path.with_name(events_path.stem + "-checkpoint.pkl")
        self.runs_root = runs_root.resolve() if runs_root is not None else None
        self._path_listener: Any = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._pause_event = threading.Event()
        self._status = RunStatus()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status.to_dict()

    def paths(self) -> tuple[Path, Path]:
        with self._lock:
            return self.snapshot_path, self.events_path

    def set_path_listener(self, listener: Any) -> None:
        self._path_listener = listener

    def start(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        load_dotenv()
        try:
            config = _parse_run_config(payload)
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc), "run": self.status()}

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return 409, {"ok": False, "error": "A simulation is already running.", "run": self._status.to_dict()}
            snapshot_path, events_path, run_id = self._paths_for_new_run(config)
            self.snapshot_path = snapshot_path
            self.events_path = events_path
            self.checkpoint_path = events_path.with_name(events_path.stem + "-checkpoint.pkl")
            self._stop_event = threading.Event()
            self._pause_event.clear()
            self._status = RunStatus(
                state="running",
                current_tick=0,
                target_ticks=config.ticks,
                agents=config.agents,
                brain=config.brain,
                seed=config.world_config.seed,
                model=config.model,
                reasoning_effort=config.reasoning_effort,
                log_agent_io=config.log_agent_io,
                max_workers=config.max_workers,
                turn_mode=config.turn_mode,
                started_at=time.time(),
                run_id=run_id,
                output_dir=str(events_path.parent),
                files={
                    "events": str(events_path),
                    "snapshot": str(snapshot_path),
                    "report": str(events_path.with_name(events_path.stem + "-report.json")),
                    "manifest": str(events_path.with_name(events_path.stem + "-manifest.json")),
                },
                population=config.population.to_dict() if config.population else {},
                config=config.public_dict(),
            )
            thread = threading.Thread(
                target=self._run,
                args=(config, self._stop_event, snapshot_path, events_path),
                name="agent-world-observer-run",
                daemon=True,
            )
            self._thread = thread
            thread.start()
            response = {"ok": True, "run": self._status.to_dict()}
        if self._path_listener is not None:
            self._path_listener(snapshot_path)
        return 202, response

    def _paths_for_new_run(self, config: RunConfig) -> tuple[Path, Path, str | None]:
        if self.runs_root is None:
            return self.snapshot_path, self.events_path, None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name = _slug(config.name) or config.preset
        relative = Path("observatory") / f"{timestamp}-{name}"
        run_dir = self.runs_root / relative
        suffix = 1
        while run_dir.exists():
            run_dir = self.runs_root / f"{relative}-{suffix}"
            suffix += 1
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir / "run-snapshot.json", run_dir / "run.jsonl", str(run_dir.relative_to(self.runs_root))

    def stop(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            if self._thread is None or not self._thread.is_alive() or self._stop_event is None:
                return 200, {"ok": True, "run": self._status.to_dict()}
            self._stop_event.set()
            self._pause_event.clear()
            self._status.stop_requested = True
            self._status.paused = False
            return 202, {"ok": True, "run": self._status.to_dict()}

    def pause(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                return 409, {"ok": False, "error": "No simulation is running.", "run": self._status.to_dict()}
            self._pause_event.set()
            self._status.paused = True
            return 200, {"ok": True, "run": self._status.to_dict()}

    def resume(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            self._pause_event.clear()
            self._status.paused = False
            return 200, {"ok": True, "run": self._status.to_dict()}

    def _run(
        self,
        config: RunConfig,
        stop_event: threading.Event,
        snapshot_path: Path,
        events_path: Path,
    ) -> None:
        engine: WorldEngine | None = None
        manifest_path = events_path.with_name(events_path.stem + "-manifest.json")
        manifest: dict[str, Any] | None = None
        try:
            population = config.population
            if population is None:
                raise RuntimeError("Run population was not resolved.")
            agent_names = [f"Agent {index + 1}" for index in range(population.total_agents)]
            engine = WorldEngine.create(config=config.world_config, agent_names=agent_names)
            if not population.assigned_groups:
                population = population.bind_assignments(
                    engine,
                    strategy=config.assignment_strategy,
                    seed=config.assignment_seed,
                )
            writer = IncrementalRunWriter(
                events_path,
                snapshot_path,
                checkpoint_path=events_path.with_name(events_path.stem + "-checkpoint.pkl"),
            )
            brain_spec = population.groups[0].brain
            usage_path = events_path.with_name(events_path.stem + "-usage.jsonl")
            if population.model_backed:
                usage_path.parent.mkdir(parents=True, exist_ok=True)
                usage_path.write_text("", encoding="utf-8")
            runtime = BrainRuntime(usage_path if population.model_backed else None)
            manifest = _observer_manifest(
                config=config,
                engine=engine,
                population=population,
                events_path=events_path,
                snapshot_path=snapshot_path,
            )
            atomic_write_json(manifest_path, manifest)

            def before_tick() -> bool:
                while self._pause_event.is_set() and not stop_event.is_set():
                    time.sleep(0.2)
                return stop_event.is_set()

            def on_tick(current: SimulationSession, _events: list[Any]) -> None:
                self._update_running_status(current.engine)

            def checkpoint_extra(current: SimulationSession) -> dict[str, Any]:
                return {
                    "run": {
                        **config.public_dict(),
                        "population": population.to_dict(current.engine.state.agents),
                        "target_ticks": config.ticks,
                        "events_path": str(events_path.resolve()),
                        "snapshot_path": str(snapshot_path.resolve()),
                        "sequential_decisions": config.max_workers <= 1,
                    },
                    "plan_usage_checkpoints": current.plan_usage_checkpoints,
                }

            stem = events_path.with_name(events_path.stem)
            session = SimulationSession(
                engine=engine,
                brain_spec=brain_spec,
                runtime=runtime,
                writer=writer,
                target_ticks=config.ticks,
                brains=create_population_brains(engine, population, runtime),
                population_spec=population,
                max_workers=config.max_workers,
                provider_max_workers=config.provider_max_workers,
                decision_mode=config.decision_mode,
                observation_mode=config.observation_mode,
                log_agent_io=config.log_agent_io,
                concurrent_decisions=config.max_workers > 1,
                turn_mode=config.turn_mode,
                lifecycle_metadata={
                    "config": config.public_dict(),
                    "preset": config.preset,
                    "decision_mode": config.decision_mode,
                    "observation_mode": config.observation_mode,
                    "turn_mode": config.turn_mode,
                    "population": population.to_dict(engine.state.agents),
                },
                checkpoint_extra=checkpoint_extra,
                before_tick=before_tick,
                on_tick=on_tick,
                report_stem=stem,
                plan_usage_path=(
                    events_path.with_name(events_path.stem + "-plan-usage.json")
                    if any(group.brain.type == "codex" for group in population.groups)
                    else None
                ),
            )
            result = session.run()
            if manifest is not None:
                manifest.update(
                    {
                        "status": result.status,
                        "final_tick": result.final_tick,
                        "stop_reason": result.stop_reason,
                        "error": result.error,
                        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
                atomic_write_json(manifest_path, manifest)
            refresh_catalog_for_output(events_path)
            metrics = compute_metrics(engine.state)
            with self._lock:
                self._status.state = result.status
                self._status.current_tick = engine.state.tick
                self._status.finished_at = time.time()
                self._status.stop_requested = False
                self._status.metrics = _status_metrics(metrics)
                self._status.error = result.error or ""
        except Exception as exc:  # The observatory should survive a failed run.
            if engine is not None:
                if not engine.state.events or engine.state.events[-1].type != "run_failed":
                    engine.log_event(
                        "run_failed",
                        message=f"Simulation failed: {exc}",
                        data={"error": str(exc)},
                        scope="public",
                    )
            if manifest is not None:
                manifest.update(
                    {
                        "status": "failed",
                        "final_tick": engine.state.tick if engine is not None else 0,
                        "error": str(exc),
                        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
                atomic_write_json(manifest_path, manifest)
            with self._lock:
                self._status.state = "failed"
                self._status.finished_at = time.time()
                self._status.stop_requested = False
                self._status.error = str(exc)

    def _update_running_status(self, engine: WorldEngine) -> None:
        metrics = compute_metrics(engine.state)
        with self._lock:
            self._status.current_tick = engine.state.tick
            self._status.metrics = _status_metrics(metrics)


def _parse_run_config(payload: dict[str, Any]) -> RunConfig:
    preset_name = str(payload.get("preset") or "organic-generalists").strip()
    if preset_name not in OBSERVATORY_PRESETS:
        raise ValueError(f"preset must be one of: {', '.join(sorted(OBSERVATORY_PRESETS))}.")
    preset = OBSERVATORY_PRESETS[preset_name]
    max_workers = _bounded_int(
        payload.get("max_workers", TUNED_OBSERVATORY_DEFAULTS["max_workers"]),
        "max_workers",
        minimum=1,
        maximum=100,
    )
    brain = str(payload.get("brain", TUNED_OBSERVATORY_DEFAULTS["brain"])).strip().lower()
    if brain not in {"survival", "llm", "codex", "claude"}:
        raise ValueError("brain must be survival, llm, codex, or claude.")
    if brain == "codex":
        model = str(payload.get("model") or os.environ.get("CODEX_MODEL") or "gpt-5.6-luna").strip()
        default_effort = os.environ.get("CODEX_REASONING_EFFORT", "low")
    elif brain == "claude":
        model = str(payload.get("model") or os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5").strip()
        default_effort = os.environ.get("CLAUDE_REASONING_EFFORT", "low")
    else:
        model = str(payload.get("model") or os.environ.get("OPENAI_MODEL") or TUNED_OBSERVATORY_DEFAULTS["model"]).strip()
        default_effort = os.environ.get("OPENAI_REASONING_EFFORT", TUNED_OBSERVATORY_DEFAULTS["reasoning_effort"])
    reasoning_effort = _parse_reasoning_effort(
        payload.get("reasoning_effort") or default_effort
    )
    world_config = WorldConfig(
        width=16,
        height=16,
        seed=_bounded_int(payload.get("seed", TUNED_OBSERVATORY_DEFAULTS["seed"]), "seed", minimum=0, maximum=2_147_483_647),
        action_points_per_tick=_bounded_int(payload.get("action_points_per_tick", 4), "action_points_per_tick", minimum=1, maximum=20),
        default_carry_capacity=_bounded_int(payload.get("default_carry_capacity", 10), "default_carry_capacity", minimum=1, maximum=100),
        storage_capacity=_bounded_int(payload.get("storage_capacity", 120), "storage_capacity", minimum=1, maximum=1000),
        food_reserve_start=_bounded_int(payload.get("food_reserve_start", 10), "food_reserve_start", minimum=0, maximum=100),
        food_reserve_max=_bounded_int(payload.get("food_reserve_max", 20), "food_reserve_max", minimum=1, maximum=100),
        water_reserve_start=_bounded_int(payload.get("water_reserve_start", 10), "water_reserve_start", minimum=0, maximum=100),
        water_reserve_max=_bounded_int(payload.get("water_reserve_max", 20), "water_reserve_max", minimum=1, maximum=100),
        energy_reserve_start=_bounded_int(payload.get("energy_reserve_start", 25), "energy_reserve_start", minimum=0, maximum=200),
        energy_reserve_max=_bounded_int(payload.get("energy_reserve_max", 30), "energy_reserve_max", minimum=1, maximum=200),
        survival_food_decay=_bounded_int(payload.get("survival_food_decay", 1), "survival_food_decay", minimum=0, maximum=20),
        survival_water_decay=_bounded_int(payload.get("survival_water_decay", 2), "survival_water_decay", minimum=0, maximum=20),
        survival_energy_decay=_bounded_int(payload.get("survival_energy_decay", 1), "survival_energy_decay", minimum=0, maximum=20),
        exhaustion_damage=_bounded_int(payload.get("exhaustion_damage", 2), "exhaustion_damage", minimum=0, maximum=50),
        carried_food_spoil_interval=_bounded_int(payload.get("carried_food_spoil_interval", 6), "carried_food_spoil_interval", minimum=0, maximum=1000),
        carried_food_spoil_quantity=_bounded_int(payload.get("carried_food_spoil_quantity", 1), "carried_food_spoil_quantity", minimum=0, maximum=100),
        resource_base_multiplier=_bounded_float(payload.get("resource_base_multiplier", 1.0), "resource_base_multiplier", minimum=0.0, maximum=5.0),
        plains_food_regen=_bounded_float(payload.get("plains_food_regen", 0.01), "plains_food_regen", minimum=0.0, maximum=1.0),
        plains_fiber_regen=_bounded_float(payload.get("plains_fiber_regen", 0.03), "plains_fiber_regen", minimum=0.0, maximum=1.0),
        forest_wood_regen=_bounded_float(payload.get("forest_wood_regen", 0.14), "forest_wood_regen", minimum=0.0, maximum=1.0),
        forest_food_regen=_bounded_float(payload.get("forest_food_regen", 0.02), "forest_food_regen", minimum=0.0, maximum=1.0),
        forest_fiber_regen=_bounded_float(payload.get("forest_fiber_regen", 0.03), "forest_fiber_regen", minimum=0.0, maximum=1.0),
        mountain_stone_regen=_bounded_float(payload.get("mountain_stone_regen", 0.04), "mountain_stone_regen", minimum=0.0, maximum=1.0),
        mountain_ore_regen=_bounded_float(payload.get("mountain_ore_regen", 0.01), "mountain_ore_regen", minimum=0.0, maximum=1.0),
        water_water_regen=_bounded_float(payload.get("water_water_regen", 0.7), "water_water_regen", minimum=0.0, maximum=1.0),
        water_food_regen=_bounded_float(payload.get("water_food_regen", 0.02), "water_food_regen", minimum=0.0, maximum=1.0),
        wild_food_density=_bounded_float(payload.get("wild_food_density", 0.35), "wild_food_density", minimum=0.0, maximum=1.0),
        wild_fiber_density=_bounded_float(payload.get("wild_fiber_density", 0.85), "wild_fiber_density", minimum=0.0, maximum=1.0),
        starter_resource_radius=_bounded_int(payload.get("starter_resource_radius", 1), "starter_resource_radius", minimum=0, maximum=10),
        farm_food_added=_bounded_int(payload.get("farm_food_added", 5), "farm_food_added", minimum=0, maximum=50),
        farm_food_capacity=_bounded_int(payload.get("farm_food_capacity", 24), "farm_food_capacity", minimum=0, maximum=100),
        farm_passive_food_growth=_bounded_int(payload.get("farm_passive_food_growth", 2), "farm_passive_food_growth", minimum=0, maximum=20),
        geography_mode=_bounded_choice(
            payload.get("geography_mode", preset["geography_mode"]),
            "geography_mode",
            {"shared_oasis", "dispersed"},
        ),
        specialization_mode=_bounded_choice(
            payload.get("specialization_mode", preset["specialization_mode"]),
            "specialization_mode",
            {"generalists", "specialists"},
        ),
        economy_mode=_bounded_choice(
            payload.get("economy_mode", preset["economy_mode"]),
            "economy_mode",
            {"baseline", "commerce", "organic"},
        ),
        objective_mode=_bounded_choice(
            payload.get("objective_mode", preset["objective_mode"]),
            "objective_mode",
            {"neutral", "collective", "individual"},
        ),
    )
    _validate_reserve_pair("food", world_config.food_reserve_start, world_config.food_reserve_max)
    _validate_reserve_pair("water", world_config.water_reserve_start, world_config.water_reserve_max)
    _validate_reserve_pair("energy", world_config.energy_reserve_start, world_config.energy_reserve_max)
    agents = _bounded_int(
        payload.get("agents", TUNED_OBSERVATORY_DEFAULTS["agents"]),
        "agents",
        minimum=1,
        maximum=100,
    )
    population = _parse_observer_population(
        payload.get("population"),
        fallback_count=agents,
        fallback_brain=brain,
        fallback_model=model,
        fallback_effort=reasoning_effort,
        max_workers=max_workers,
    )
    if population.total_agents > 100:
        raise ValueError("population cannot exceed 100 agents.")
    assignment_strategy = str(
        payload.get("assignment_strategy") or ("stratified" if population.mixed else "ordered")
    ).strip().lower()
    if assignment_strategy not in {"ordered", "stratified"}:
        raise ValueError("assignment_strategy must be ordered or stratified.")
    assignment_seed = _bounded_int(
        payload.get("assignment_seed", world_config.seed),
        "assignment_seed",
        minimum=0,
        maximum=2_147_483_647,
    )
    population = PopulationSpec(
        population.groups,
        assignment_strategy=assignment_strategy,
        assignment_seed=assignment_seed,
    )
    provider_max_workers = {
        "codex_cli": _bounded_int(
            payload.get("codex_max_workers", min(max_workers, 4)),
            "codex_max_workers",
            1,
            100,
        ),
        "claude_cli": _bounded_int(
            payload.get("claude_max_workers", min(max_workers, 4)),
            "claude_max_workers",
            1,
            100,
        ),
        "openai_compatible": _bounded_int(
            payload.get("llm_max_workers", min(max_workers, 2)),
            "llm_max_workers",
            1,
            100,
        ),
    }
    return RunConfig(
        ticks=_bounded_int(payload.get("ticks", TUNED_OBSERVATORY_DEFAULTS["ticks"]), "ticks", minimum=1, maximum=1000),
        agents=population.total_agents,
        brain=population.run_type,
        model=(population.groups[0].brain.model if not population.mixed else None),
        reasoning_effort=(population.groups[0].brain.reasoning_effort if not population.mixed else None),
        log_agent_io=bool(payload.get("log_agent_io", TUNED_OBSERVATORY_DEFAULTS["log_agent_io"])),
        max_workers=max_workers,
        turn_mode=_bounded_choice(
            payload.get("turn_mode", DEFAULT_TURN_MODE), "turn_mode", set(TURN_MODES)
        ),
        preset=preset_name,
        decision_mode=_bounded_choice(
            payload.get("decision_mode", "raw"), "decision_mode", {"raw", "validated"}
        ),
        observation_mode=_bounded_choice(
            payload.get("observation_mode", "compact-v2"),
            "observation_mode",
            set(OBSERVATION_MODES),
        ),
        assignment_strategy=assignment_strategy,
        assignment_seed=assignment_seed,
        provider_max_workers=provider_max_workers,
        population=population,
        name=str(payload.get("name") or "").strip()[:80],
        world_config=world_config,
    )


def _parse_observer_population(
    value: Any,
    *,
    fallback_count: int,
    fallback_brain: str,
    fallback_model: str | None,
    fallback_effort: str | None,
    max_workers: int,
) -> PopulationSpec:
    raw_groups = value.get("groups") if isinstance(value, dict) else value
    if raw_groups is None or raw_groups == "":
        spec = BrainSpec.resolve(
            fallback_brain,
            model=fallback_model,
            reasoning_effort=fallback_effort,
            max_workers=max_workers,
        )
        return PopulationSpec.uniform(fallback_count, spec)
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("population must be a non-empty list of cohort objects.")
    groups: list[PopulationGroup] = []
    for index, raw in enumerate(raw_groups, start=1):
        if not isinstance(raw, dict):
            raise ValueError("each population cohort must be an object.")
        brain_type = str(raw.get("brain") or raw.get("type") or "").strip().lower()
        if brain_type not in {"survival", "llm", "codex", "claude"}:
            raise ValueError(f"population cohort {index} has an unsupported brain.")
        count = _bounded_int(raw.get("count", 0), f"population[{index}].count", 1, 100)
        effort = None
        if brain_type != "survival":
            effort = _parse_reasoning_effort(raw.get("reasoning_effort") or fallback_effort or "low")
        thinking_budget = None
        if brain_type == "claude":
            thinking_budget = _bounded_int(
                raw.get("thinking_budget_tokens", 0),
                f"population[{index}].thinking_budget_tokens",
                0,
                200000,
            )
        model = str(raw.get("model") or "").strip() or None
        spec = BrainSpec.resolve(
            brain_type,
            model=None if brain_type == "survival" else model,
            reasoning_effort=effort,
            thinking_budget_tokens=thinking_budget,
            max_workers=max_workers,
        )
        groups.append(PopulationGroup(count=count, brain=spec, id=f"cohort-{index}"))
    return PopulationSpec(tuple(groups))


def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def _bounded_float(value: Any, name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def _bounded_choice(value: Any, name: str, allowed: set[str]) -> str:
    parsed = str(value).strip().lower()
    if parsed not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}.")
    return parsed


def _validate_reserve_pair(name: str, start: int, maximum: int) -> None:
    if start > maximum:
        raise ValueError(f"{name}_reserve_start must be less than or equal to {name}_reserve_max.")


def _parse_reasoning_effort(value: Any) -> str:
    effort = str(value or "medium").strip().lower()
    allowed = {"minimal", "low", "medium", "high", "xhigh", "max"}
    if effort not in allowed:
        raise ValueError(f"reasoning_effort must be one of: {', '.join(sorted(allowed))}.")
    return effort


def _status_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "agents": metrics.get("agents", {}),
        "trade": metrics.get("trade", {}),
        "economic_flows": metrics.get("economic_flows", {}),
        "specialization": metrics.get("specialization", {}),
        "productive_assets": metrics.get("productive_assets", {}),
        "infrastructure": metrics.get("infrastructure", {}),
        "invalid_actions": metrics.get("invalid_actions", {}),
        "llm": metrics.get("llm", {}),
        "wealth_gini": metrics.get("wealth_gini", 0),
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48]


def _observer_manifest(
    *,
    config: RunConfig,
    engine: WorldEngine,
    population: PopulationSpec,
    events_path: Path,
    snapshot_path: Path,
) -> dict[str, Any]:
    try:
        git_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        git_sha, dirty = None, None
    checkpoint_path = events_path.with_name(events_path.stem + "-checkpoint.pkl")
    report_stem = events_path.with_name(events_path.stem)
    return {
        "schema_version": 1,
        "status": "running",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_ticks": config.ticks,
        "final_tick": engine.state.tick,
        "preset": config.preset,
        "decision_mode": config.decision_mode,
        "observation_mode": config.observation_mode,
        "turn_mode": config.turn_mode,
        "command": ["agent-world", "view", "browser-launched-run"],
        "config": asdict(engine.state.config),
        "population": population.to_dict(engine.state.agents),
        "assignment_source_manifest": None,
        "concurrency": {
            "global": config.max_workers,
            "providers": config.provider_max_workers,
        },
        "provider_settings": {
            "claude_cli": {
                "thinking_budget_tokens": sorted(
                    {
                        int(group.brain.thinking_budget_tokens or 0)
                        for group in population.groups
                        if group.brain.type == "claude"
                    }
                )
            }
        },
        "provenance": {"git_sha": git_sha, "dirty_worktree": dirty, "surface": "observatory"},
        "outputs": {
            "events": str(events_path),
            "snapshot": str(snapshot_path),
            "checkpoint": str(checkpoint_path),
            "report_json": f"{report_stem}-report.json",
            "report_markdown": f"{report_stem}-report.md",
        },
    }


class SnapshotHistory:
    """Per-tick snapshot archive so the UI can scrub back through a run.

    A watcher thread samples the snapshot file and stores one copy per tick. Works for
    observatory-launched and CLI-launched runs alike, since both write the same file.
    Restarting a run (tick moves backwards) clears the archive.
    """

    def __init__(self, snapshot_path: Path, max_ticks: int = 2000):
        self.snapshot_path = snapshot_path
        self.max_ticks = max_ticks
        self._lock = threading.Lock()
        self._snapshots: dict[int, dict[str, Any]] = {}
        self._last_mtime: float = 0.0

    def set_path(self, snapshot_path: Path) -> None:
        with self._lock:
            self.snapshot_path = snapshot_path
            self._snapshots.clear()
            self._last_mtime = 0.0

    def record(self, snapshot: dict[str, Any]) -> None:
        tick = snapshot.get("tick")
        if not isinstance(tick, int):
            return
        with self._lock:
            latest = max(self._snapshots) if self._snapshots else -1
            if tick < latest:
                self._snapshots.clear()
            if tick not in self._snapshots and len(self._snapshots) < self.max_ticks:
                self._snapshots[tick] = snapshot

    def get(self, tick: int) -> dict[str, Any] | None:
        with self._lock:
            return self._snapshots.get(tick)

    def tick_range(self) -> dict[str, int | None]:
        with self._lock:
            if not self._snapshots:
                return {"min_tick": None, "max_tick": None, "count": 0}
            return {"min_tick": min(self._snapshots), "max_tick": max(self._snapshots), "count": len(self._snapshots)}

    def poll_file(self) -> None:
        try:
            mtime = self.snapshot_path.stat().st_mtime
        except OSError:
            return
        if mtime == self._last_mtime:
            return
        self._last_mtime = mtime
        snapshot = _read_json(self.snapshot_path)
        if snapshot:
            self.record(snapshot)

    def start_watcher(self, interval_seconds: float = 0.5) -> None:
        def _watch() -> None:
            while True:
                self.poll_file()
                time.sleep(interval_seconds)

        threading.Thread(target=_watch, name="agent-world-snapshot-history", daemon=True).start()


def _find_runs_root(path: Path) -> Path | None:
    resolved = path.expanduser().resolve()
    for candidate in (resolved.parent, *resolved.parents):
        if candidate.name == "runs":
            return candidate
    return None


def _observer_config_payload() -> dict[str, Any]:
    return {
        "presets": OBSERVATORY_PRESETS,
        "models": MODEL_LIBRARY,
        "reasoning_efforts": sorted(ALLOWED_EFFORTS),
        "observation_modes": list(OBSERVATION_MODES),
        "turn_modes": sorted(TURN_MODES),
        "decision_modes": ["raw", "validated"],
        "limits": {"agents": 100, "ticks": 1000, "workers": 100},
        "defaults": {
            **TUNED_OBSERVATORY_DEFAULTS,
            "preset": "organic-generalists",
            "observation_mode": "compact-v2",
            "turn_mode": DEFAULT_TURN_MODE,
            "decision_mode": "raw",
        },
    }


def _load_catalog(runs_root: Path | None, active_run: dict[str, Any]) -> dict[str, Any]:
    if runs_root is None:
        return {"ok": True, "run_count": 0, "runs": [], "active_run": active_run}
    catalog_path = runs_root / "catalog.json"
    catalog = _read_json(catalog_path)
    if not catalog:
        catalog = write_run_catalog(runs_root)
    return {"ok": True, **catalog, "active_run": active_run}


def _resolve_catalog_ref(runs_root: Path | None, run_ref: str) -> tuple[Path, Path | None]:
    if runs_root is None or not run_ref.strip():
        raise ValueError("A run reference is required.")
    candidate = (runs_root / run_ref).resolve()
    root = runs_root.resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("Run reference is outside the run catalog.")
    if candidate.is_file():
        if not candidate.name.endswith("-report.json"):
            raise ValueError("Run reference must identify a report or run directory.")
        return candidate.parent, candidate
    if candidate.is_dir():
        return candidate, None
    raise FileNotFoundError(f"Run not found: {run_ref}")


def _first_path(directory: Path, preferred: list[str], pattern: str) -> Path | None:
    for name in preferred:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return next(iter(sorted(directory.glob(pattern))), None)


def _catalog_run_paths(runs_root: Path | None, run_ref: str) -> dict[str, Path | None]:
    run_dir, exact_report = _resolve_catalog_ref(runs_root, run_ref)
    report_stem = (
        exact_report.name[: -len("-report.json")]
        if exact_report is not None
        else "run"
    )
    exact_artifact = exact_report is not None
    event_names = [f"{report_stem}.jsonl"]
    snapshot_names = [f"{report_stem}-snapshot.json"]
    manifest_names = [f"{report_stem}-manifest.json"]
    if report_stem == "run":
        manifest_names.append("manifest.json")
    events = _first_path(run_dir, event_names, "__no_fallback__" if exact_artifact else "*.jsonl")
    if events is not None and ("usage" in events.name or "plan" in events.name):
        events = next(
            (
                path
                for path in sorted(run_dir.glob("*.jsonl"))
                if "usage" not in path.name and "plan" not in path.name
            ),
            None,
        )
    return {
        "directory": run_dir,
        "events": events,
        "snapshot": _first_path(
            run_dir,
            snapshot_names,
            "__no_fallback__" if exact_artifact else "*-snapshot.json",
        ),
        "report": exact_report
        or _first_path(run_dir, ["run-report.json"], "*-report.json"),
        "manifest": _first_path(
            run_dir,
            manifest_names,
            "__no_fallback__" if exact_artifact else "*-manifest.json",
        ),
    }


def load_catalog_run_state(runs_root: Path | None, run_id: str) -> dict[str, Any]:
    paths = _catalog_run_paths(runs_root, run_id)
    snapshot_path = paths["snapshot"]
    events_path = paths["events"]
    report = _read_json(paths["report"]) if paths["report"] else {}
    manifest = _read_json(paths["manifest"]) if paths["manifest"] else {}
    if snapshot_path is None and not report:
        raise FileNotFoundError(f"Run has no readable snapshot or report: {run_id}")
    state = load_observer_state(
        snapshot_path or Path("/nonexistent"),
        events_path or Path("/nonexistent"),
        run_status={
            "state": manifest.get("status") or (report.get("run") or {}).get("status") or "archived",
            "current_tick": (report.get("run") or {}).get("final_tick") or 0,
            "target_ticks": (report.get("run") or {}).get("target_ticks") or 0,
            "run_id": run_id,
            "paused": False,
            "stop_requested": False,
            "error": manifest.get("error") or "",
            "config": manifest.get("config") or report.get("config") or {},
            "population": manifest.get("population") or report.get("population") or {},
        },
        report_path=paths["report"],
        manifest_path=paths["manifest"],
    )
    state["source"] = "archive"
    state["selected_run"] = run_id
    state["available"] = {
        key: bool(path and path.exists()) for key, path in paths.items() if key != "directory"
    }
    return state


def load_catalog_run_detail(runs_root: Path | None, run_id: str) -> dict[str, Any]:
    paths = _catalog_run_paths(runs_root, run_id)
    return {
        "ok": True,
        "id": run_id,
        "report": _read_json(paths["report"]) if paths["report"] else {},
        "manifest": _read_json(paths["manifest"]) if paths["manifest"] else {},
        "available": {
            key: bool(path and path.exists()) for key, path in paths.items() if key != "directory"
        },
    }


def serve_observer(
    snapshot_path: Path,
    events_path: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    runs_root = _find_runs_root(events_path)
    controller = RunController(
        snapshot_path=snapshot_path,
        events_path=events_path,
        runs_root=runs_root,
    )
    history = SnapshotHistory(snapshot_path)
    controller.set_path_listener(history.set_path)
    history.poll_file()
    history.start_watcher()
    if runs_root is not None:
        write_run_catalog(runs_root)
    handler = _handler(
        snapshot_path=snapshot_path,
        events_path=events_path,
        controller=controller,
        history=history,
        runs_root=runs_root,
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Agent World observatory: http://{host}:{port}")
    print(f"Watching snapshot: {snapshot_path}")
    print(f"Watching events:   {events_path}")
    server.serve_forever()


def _handler(
    snapshot_path: Path,
    events_path: Path,
    controller: RunController,
    history: SnapshotHistory | None = None,
    runs_root: Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    class ObserverHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path in {"/", "/runs"}:
                self._send_text(HTML, "text/html; charset=utf-8")
            elif path == "/static/observer.css":
                self._send_text(CSS, "text/css; charset=utf-8")
            elif path == "/static/observer.js":
                self._send_text(JAVASCRIPT, "text/javascript; charset=utf-8")
            elif path == "/api/config":
                self._send_json(_observer_config_payload())
            elif path == "/api/runs":
                self._send_json(_load_catalog(runs_root, controller.status()))
            elif path == "/api/runs/state":
                run_id = (query.get("id") or [""])[0]
                try:
                    self._send_json(load_catalog_run_state(runs_root, run_id))
                except (ValueError, FileNotFoundError) as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=404)
            elif path == "/api/runs/detail":
                run_id = (query.get("id") or [""])[0]
                try:
                    self._send_json(load_catalog_run_detail(runs_root, run_id))
                except (ValueError, FileNotFoundError) as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=404)
            elif path == "/api/state":
                at_tick = _parse_tick_param(query)
                active_snapshot, active_events = controller.paths()
                self._send_json(
                    load_observer_state(
                        active_snapshot,
                        active_events,
                        run_status=controller.status(),
                        at_tick=at_tick,
                        history=history,
                    )
                )
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/run/start":
                try:
                    payload = self._read_json_body()
                except ValueError as exc:
                    self._send_json({"ok": False, "error": str(exc), "run": controller.status()}, status=400)
                    return
                status, response = controller.start(payload)
                self._send_json(response, status=status)
            elif path == "/api/run/stop":
                status, response = controller.stop()
                self._send_json(response, status=status)
            elif path == "/api/run/pause":
                status, response = controller.pause()
                self._send_json(response, status=status)
            elif path == "/api/run/resume":
                status, response = controller.resume()
                self._send_json(response, status=status)
            else:
                self.send_error(404)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("Request body must be valid JSON.") from exc
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def _send_text(self, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: Any, status: int = 200) -> None:
            data = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ObserverHandler


def _parse_tick_param(query: dict[str, list[str]]) -> int | None:
    values = query.get("tick") or []
    if not values:
        return None
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return None


def load_observer_state(
    snapshot_path: Path,
    events_path: Path,
    recent_limit: int = 120,
    run_status: dict[str, Any] | None = None,
    at_tick: int | None = None,
    history: SnapshotHistory | None = None,
    report_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = _read_json(snapshot_path)
    events = _read_events(events_path)
    live_tick = snapshot.get("tick", 0)
    viewing_tick = None
    if at_tick is not None and history is not None:
        historical = history.get(at_tick)
        if historical is not None:
            snapshot = historical
            events = [event for event in events if event.get("tick", 0) <= at_tick]
            viewing_tick = at_tick
    visible_events = [event for event in events if event.get("type") not in AGENT_IO_EVENT_TYPES]
    resolved_report = report_path or events_path.with_name(events_path.stem + "-report.json")
    resolved_manifest = manifest_path or events_path.with_name(events_path.stem + "-manifest.json")
    return {
        "snapshot": snapshot,
        "recent_events": visible_events[-recent_limit:],
        "summary": summarize(snapshot, visible_events),
        "report": _read_json(resolved_report) if resolved_report else {},
        "manifest": _read_json(resolved_manifest) if resolved_manifest else {},
        "run": run_status or RunStatus().to_dict(),
        "history": (history.tick_range() if history else {"min_tick": None, "max_tick": None, "count": 0})
        | {"live_tick": live_tick, "viewing_tick": viewing_tick},
        "files": {
            "snapshot": str(snapshot_path),
            "events": str(events_path),
            "snapshot_exists": snapshot_path.exists(),
            "events_exists": events_path.exists(),
            "events_size": events_path.stat().st_size if events_path.exists() else 0,
        },
    }


def summarize(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    agents = snapshot.get("agents", {})
    living = [agent for agent in agents.values() if agent.get("alive")]
    event_counts = Counter(event.get("type") for event in events)
    diagnostics = snapshot.get("diagnostics", {})
    build_readiness = diagnostics.get("build_readiness", {})
    current_tick = snapshot.get("tick", 0)
    structures = snapshot.get("structures", {})
    complete_structures = [s for s in structures.values() if s.get("status", "complete") == "complete"]
    sites_in_progress = sum(1 for s in structures.values() if s.get("status") == "under_construction")
    cooperative_sites = sum(1 for s in structures.values() if len(s.get("contributors", [])) > 1)
    death_ticks = {event.get("actor_id"): event.get("tick", 0) for event in events if event.get("type") == "death"}
    lifespans = sorted(death_ticks.get(agent_id, current_tick) for agent_id in agents) if agents else []
    llm_failures = [
        event
        for event in events
        if is_decision_failure_message(event.get("type"), str(event.get("message", "")))
    ]
    return {
        "tick": current_tick,
        "agents": {
            "total": len(agents),
            "living": len(living),
            "dead": len(agents) - len(living),
        },
        "median_lifespan": lifespans[len(lifespans) // 2] if lifespans else 0,
        "builds": event_counts.get("build", 0),
        "sites_in_progress": sites_in_progress,
        "cooperative_sites": cooperative_sites,
        "ever_buildable": diagnostics.get("build_ready_ever", []),
        "events": dict(sorted(event_counts.items())),
        "structures": len(complete_structures),
        "structures_by_type": dict(sorted(Counter(structure.get("type") for structure in complete_structures).items())),
        "build_ready": build_readiness.get("ready_counts", {}),
        "open_trades": sum(1 for trade in snapshot.get("trades", {}).values() if trade.get("status") == "open"),
        "accepted_trades": sum(1 for trade in snapshot.get("trades", {}).values() if trade.get("status") == "accepted"),
        "groups": len(snapshot.get("groups", {})),
        "llm_failures": len(llm_failures),
        "quota_failures": sum(is_quota_failure_message(event.get("type"), str(event.get("message", ""))) for event in events),
        "rate_limit_failures": sum(
            ("429" in str(event.get("message", "")) or "rate_limit" in str(event.get("message", "")))
            and not is_quota_failure_message(event.get("type"), str(event.get("message", "")))
            for event in llm_failures
        ),
        "series": _civilization_series(snapshot, events),
    }


def _civilization_series(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Per-tick cumulative civilization trends derived from the event log."""

    current_tick = int(snapshot.get("tick", 0) or 0)
    agents = snapshot.get("agents", {})
    if not agents and not events:
        return {"ticks": [], "population": [], "structures": [], "trades": [], "messages": []}
    deaths: Counter[int] = Counter()
    builds: Counter[int] = Counter()
    trades: Counter[int] = Counter()
    messages: Counter[int] = Counter()
    for event in events:
        tick = int(event.get("tick", 0) or 0)
        event_type = event.get("type")
        if event_type == "death":
            deaths[tick] += 1
        elif event_type == "build":
            builds[tick] += 1
        elif event_type == "accept_trade":
            trades[tick] += 1
        elif event_type in {"say", "whisper", "broadcast"}:
            messages[tick] += 1
    ticks = list(range(current_tick + 1))
    alive = len(agents)
    built = traded = spoken = 0
    population_series: list[int] = []
    structure_series: list[int] = []
    trade_series: list[int] = []
    message_series: list[int] = []
    for tick in ticks:
        alive -= deaths.get(tick, 0)
        built += builds.get(tick, 0)
        traded += trades.get(tick, 0)
        spoken += messages.get(tick, 0)
        population_series.append(max(alive, 0))
        structure_series.append(built)
        trade_series.append(traded)
        message_series.append(spoken)
    return {
        "ticks": ticks,
        "population": population_series,
        "structures": structure_series,
        "trades": trade_series,
        "messages": message_series,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


STATIC_DIR = Path(__file__).with_name("static")
HTML = (STATIC_DIR / "observer.html").read_text(encoding="utf-8")
CSS = (STATIC_DIR / "observer.css").read_text(encoding="utf-8")
JAVASCRIPT = (STATIC_DIR / "observer.js").read_text(encoding="utf-8")
