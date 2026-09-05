"""Local web observatory for Agent World runs."""

from __future__ import annotations

from agent_world.jsonl_tail import tail_for
from agent_world.managed_observer import ManagedObserverClient

from collections import Counter
from dataclasses import asdict, dataclass, field
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from agent_world.brain_boundary import (
    normalize_connector_profile,
    normalize_conversation_mode,
)
from agent_world.brain_factory import BrainSpec, DEFAULT_MODEL_MAX_WORKERS
from agent_world.brain_runtime import BrainRuntime
from agent_world.env import load_dotenv
from agent_world.metrics import compute_metrics, is_decision_failure_message, is_quota_failure_message
from agent_world.models import WorldConfig
from agent_world.persistence import IncrementalRunWriter
from agent_world.session import SimulationSession
from agent_world.world import WorldEngine


AGENT_IO_EVENT_TYPES = {"agent_observation", "agent_prompt", "agent_prompt_context"}

TUNED_OBSERVATORY_DEFAULTS = {
    "ticks": 20,
    "agents": 5,
    "brain": "openrouter",
    "seed": 11,
    "model": "z-ai/glm-5.2",
    "reasoning_effort": "medium",
    "log_agent_io": True,
    "max_workers": DEFAULT_MODEL_MAX_WORKERS,
}


@dataclass(frozen=True)
class RunConfig:
    ticks: int = 25
    agents: int = 5
    brain: str = "survival"
    model: str | None = None
    reasoning_effort: str | None = None
    log_agent_io: bool = True
    max_workers: int = DEFAULT_MODEL_MAX_WORKERS
    connector_profile: str = "connector-v1"
    conversation_mode: str = "fresh-conversation"
    session_max_turns: int = 10
    world_config: WorldConfig = field(default_factory=WorldConfig)

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    max_workers: int = DEFAULT_MODEL_MAX_WORKERS
    started_at: float | None = None
    finished_at: float | None = None
    stop_requested: bool = False
    paused: bool = False
    error: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunController:
    """Owns one background simulation launched from the observatory UI."""

    def __init__(self, snapshot_path: Path, events_path: Path):
        self.snapshot_path = self._free_snapshot_path = snapshot_path
        self.events_path = self._free_events_path = events_path
        self.checkpoint_path = events_path.with_name(events_path.stem + "-checkpoint.pkl")
        self._lock = threading.Lock()
        self._launch_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._pause_event = threading.Event()
        self._status = RunStatus()
        self._managed = ManagedObserverClient(snapshot_path, events_path)
        if self._managed.selection:
            self.snapshot_path, self.events_path = self._managed.paths()

    def status(self) -> dict[str, Any]:
        if self._managed.selection:
            return self._managed.status()
        with self._lock:
            return self._status.to_dict()

    def start(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with self._launch_lock:
            return self._start_locked(payload)

    def _start_locked(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        load_dotenv()
        try:
            config = _parse_run_config(payload)
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc), "run": self.status()}

        if self._managed.selection and self._managed.status()["state"] == "running":
            return 409, {"ok": False, "error": "A simulation is already running.", "run": self.status()}
        if config.brain != "survival":
            if self._thread is not None and self._thread.is_alive():
                return 409, {"ok": False, "error": "A simulation is already running.", "run": self.status()}
            try:
                result = self._managed.start(config)
            except (ValueError, OSError, RuntimeError) as exc:
                return 400, {"ok": False, "error": str(exc)}
            self.snapshot_path, self.events_path = self._managed.paths()
            return result
        self._managed.clear()
        self.snapshot_path, self.events_path = self._free_snapshot_path, self._free_events_path
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return 409, {"ok": False, "error": "A simulation is already running.", "run": self._status.to_dict()}
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
                started_at=time.time(),
                config=config.public_dict(),
            )
            thread = threading.Thread(
                target=self._run,
                args=(config, self._stop_event),
                name="agent-world-observer-run",
                daemon=True,
            )
            self._thread = thread
            thread.start()
            return 202, {"ok": True, "run": self._status.to_dict()}

    def stop(self) -> tuple[int, dict[str, Any]]:
        if self._managed.selection:
            return self._managed.control("stop")
        with self._lock:
            if self._thread is None or not self._thread.is_alive() or self._stop_event is None:
                return 200, {"ok": True, "run": self._status.to_dict()}
            self._stop_event.set()
            self._pause_event.clear()
            self._status.stop_requested = True
            self._status.paused = False
            return 202, {"ok": True, "run": self._status.to_dict()}

    def pause(self) -> tuple[int, dict[str, Any]]:
        if self._managed.selection:
            return self._managed.control("pause")
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                return 409, {"ok": False, "error": "No simulation is running.", "run": self._status.to_dict()}
            self._pause_event.set()
            self._status.paused = True
            return 200, {"ok": True, "run": self._status.to_dict()}

    def resume(self) -> tuple[int, dict[str, Any]]:
        if self._managed.selection:
            return self._managed.control("run")
        with self._lock:
            self._pause_event.clear()
            self._status.paused = False
            return 200, {"ok": True, "run": self._status.to_dict()}

    def _run(self, config: RunConfig, stop_event: threading.Event) -> None:
        engine: WorldEngine | None = None
        try:
            agent_names = [f"Agent {index + 1}" for index in range(config.agents)]
            engine = WorldEngine.create(config=config.world_config, agent_names=agent_names)
            writer = IncrementalRunWriter(
                self.events_path,
                self.snapshot_path,
                checkpoint_path=self.checkpoint_path,
            )
            brain_spec = BrainSpec.resolve(
                config.brain,
                model=config.model,
                reasoning_effort=config.reasoning_effort,
                max_workers=config.max_workers,
                connector_profile=config.connector_profile,
                conversation_mode=config.conversation_mode,
                session_max_turns=config.session_max_turns,
            )
            usage_path = self.events_path.with_name(self.events_path.stem + "-usage.jsonl")
            if brain_spec.model_backed:
                usage_path.parent.mkdir(parents=True, exist_ok=True)
                usage_path.write_text("", encoding="utf-8")
            runtime = BrainRuntime(usage_path if brain_spec.model_backed else None)

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
                        "target_ticks": config.ticks,
                        "events_path": str(self.events_path.resolve()),
                        "snapshot_path": str(self.snapshot_path.resolve()),
                        "sequential_decisions": config.max_workers <= 1,
                    },
                    "plan_usage_checkpoints": current.plan_usage_checkpoints,
                    "brain_states": current.export_brain_states(),
                }

            stem = self.events_path.with_name(self.events_path.stem)
            session = SimulationSession(
                engine=engine,
                brain_spec=brain_spec,
                runtime=runtime,
                writer=writer,
                target_ticks=config.ticks,
                log_agent_io=config.log_agent_io,
                concurrent_decisions=config.max_workers > 1,
                lifecycle_metadata={"config": config.public_dict()},
                checkpoint_extra=checkpoint_extra,
                before_tick=before_tick,
                on_tick=on_tick,
                report_stem=stem,
                plan_usage_path=(
                    self.events_path.with_name(self.events_path.stem + "-plan-usage.json")
                    if brain_spec.type == "codex"
                    else None
                ),
            )
            result = session.run()
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
    brain = str(payload.get("brain", TUNED_OBSERVATORY_DEFAULTS["brain"])).strip().lower()
    if brain == "llm":
        brain = "openrouter"
    if brain not in {
        "survival",
        "openrouter",
        "codex",
        "claude",
        "cursor",
        "devin",
        "grok",
        "zcode",
        "antigravity",
        "muse",
    }:
        raise ValueError(
            "brain must be survival, openrouter, codex, claude, cursor, devin, grok, zcode, antigravity, or muse."
        )
    spec = BrainSpec.resolve(
        brain, model=payload.get("model"), reasoning_effort=payload.get("reasoning_effort"),
        connector_profile=str(payload.get("connector_profile", "connector-v1")),
        conversation_mode=str(payload.get("conversation_mode", "fresh-conversation")),
        session_max_turns=_bounded_int(payload.get("session_max_turns", 10), "session_max_turns", 1, 100),
    )
    model, reasoning_effort = spec.model, spec.reasoning_effort
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
            payload.get("geography_mode", "shared_oasis"), "geography_mode", {"shared_oasis", "dispersed"}
        ),
        economy_mode=_bounded_choice(
            payload.get("economy_mode", "baseline"), "economy_mode", {"baseline", "commerce", "organic"}
        ),
        objective_mode=_bounded_choice(
            payload.get("objective_mode", "neutral"), "objective_mode", {"neutral", "collective", "individual"}
        ),
    )
    _validate_reserve_pair("food", world_config.food_reserve_start, world_config.food_reserve_max)
    _validate_reserve_pair("water", world_config.water_reserve_start, world_config.water_reserve_max)
    _validate_reserve_pair("energy", world_config.energy_reserve_start, world_config.energy_reserve_max)
    return RunConfig(
        ticks=_bounded_int(payload.get("ticks", TUNED_OBSERVATORY_DEFAULTS["ticks"]), "ticks", minimum=1, maximum=1000),
        agents=_bounded_int(payload.get("agents", TUNED_OBSERVATORY_DEFAULTS["agents"]), "agents", minimum=1, maximum=20),
        brain=brain,
        model=(
            model
            if brain in {"openrouter", "codex", "claude", "cursor", "devin", "grok", "zcode", "antigravity", "muse"}
            else None
        ),
        reasoning_effort=(
            reasoning_effort
            if brain in {"openrouter", "codex", "claude", "cursor", "devin", "grok", "zcode", "antigravity", "muse"}
            else None
        ),
        log_agent_io=bool(payload.get("log_agent_io", TUNED_OBSERVATORY_DEFAULTS["log_agent_io"])),
        max_workers=_bounded_int(payload.get("max_workers", TUNED_OBSERVATORY_DEFAULTS["max_workers"]), "max_workers", minimum=1, maximum=40),
        connector_profile=_bounded_choice(
            normalize_connector_profile(
                str(payload.get("connector_profile", "connector-v1"))
            ),
            "connector_profile",
            {"connector-v1", "connector-v2", "connector-v3"},
        ),
        conversation_mode=_bounded_choice(
            normalize_conversation_mode(
                str(payload.get("conversation_mode", "fresh-conversation"))
            ),
            "conversation_mode",
            {"fresh-conversation", "persistent-conversation-v1"},
        ),
        session_max_turns=_bounded_int(
            payload.get("session_max_turns", 10),
            "session_max_turns",
            minimum=1,
            maximum=100,
        ),
        world_config=world_config,
    )


def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def _bounded_float(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not __import__("math").isfinite(parsed) or parsed < minimum or parsed > maximum:
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
        "action_failures": metrics.get("action_failures", {}),
        "llm": metrics.get("llm", {}),
        "wealth_gini": metrics.get("wealth_gini", 0),
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

    def record(self, snapshot: dict[str, Any]) -> None:
        tick = snapshot.get("tick")
        if not isinstance(tick, int):
            return
        with self._lock:
            latest = max(self._snapshots) if self._snapshots else -1
            if tick < latest:
                self._snapshots.clear()
            self._snapshots.setdefault(tick, snapshot)
            while len(self._snapshots) > max(1, self.max_ticks):
                del self._snapshots[min(self._snapshots)]

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


def serve_observer(
    snapshot_path: Path,
    events_path: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    controller = RunController(snapshot_path=snapshot_path, events_path=events_path)
    history = SnapshotHistory(snapshot_path)
    history.poll_file()
    history.start_watcher()
    handler = _handler(snapshot_path=snapshot_path, events_path=events_path, controller=controller, history=history)
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
) -> type[BaseHTTPRequestHandler]:
    class ObserverHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/":
                self._send_text(HTML, "text/html; charset=utf-8")
            elif path == "/api/state":
                at_tick = _parse_tick_param(parse_qs(parsed.query))
                if history and history.snapshot_path != controller.snapshot_path:
                    with history._lock:
                        history.snapshot_path = controller.snapshot_path
                        history._snapshots.clear()
                        history._last_mtime = 0
                    history.poll_file()
                self._send_json(
                    load_observer_state(
                        controller.snapshot_path,
                        controller.events_path,
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

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
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


_PROJECTION_CACHE: dict[tuple, dict[str, Any]] = {}
_PROJECTION_LOCK = threading.Lock()


def load_observer_state(snapshot_path: Path, events_path: Path, recent_limit: int = 120,
                        run_status=None, at_tick=None, history=None) -> dict[str, Any]:
    def signature(path):
        try:
            info = path.stat()
            return (str(path.resolve()), info.st_ino, info.st_size, info.st_mtime_ns)
        except FileNotFoundError:
            return (str(path.resolve()), None)
    key = (signature(snapshot_path), signature(events_path), recent_limit, at_tick, id(history))
    with _PROJECTION_LOCK:
        if key not in _PROJECTION_CACHE:
            value = _load_observer_state(snapshot_path, events_path, recent_limit,
                                         None, at_tick, history)
            if len(_PROJECTION_CACHE) >= 8:
                del _PROJECTION_CACHE[next(iter(_PROJECTION_CACHE))]
            _PROJECTION_CACHE[key] = value
        result = dict(_PROJECTION_CACHE[key])
    result["run"] = run_status or RunStatus().to_dict()
    if history:
        result["history"] = {**result["history"], **history.tick_range()}
    return result


def _load_observer_state(
    snapshot_path: Path,
    events_path: Path,
    recent_limit: int = 120,
    run_status: dict[str, Any] | None = None,
    at_tick: int | None = None,
    history: SnapshotHistory | None = None,
) -> dict[str, Any]:
    snapshot = _read_json(snapshot_path)
    events = _read_events(events_path)
    live_tick = snapshot.get("tick", 0)
    viewing_tick = None
    if at_tick is not None and history is not None:
        historical = history.get(at_tick)
        if historical is not None:
            snapshot = historical
            events = [event for event in events if event.get("tick", 0) < at_tick]
            viewing_tick = at_tick
    visible_events = [event for event in events if event.get("type") not in AGENT_IO_EVENT_TYPES]
    return {
        "snapshot": snapshot,
        "recent_events": visible_events[-recent_limit:],
        "summary": summarize(snapshot, visible_events),
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
    return tail_for(str(path.resolve())).read()


HTML = (Path(__file__).with_name("static") / "observer.html").read_text(encoding="utf-8")
