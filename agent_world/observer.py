"""Local web observatory for Agent World runs."""

from __future__ import annotations

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

from agent_world.agents import AgentBrain, SurvivalBrain
from agent_world.env import load_dotenv
from agent_world.metrics import compute_metrics, is_decision_failure_message, is_quota_failure_message
from agent_world.models import WorldConfig
from agent_world.openai_brain import OpenAIBrain
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


AGENT_IO_EVENT_TYPES = {"agent_observation", "agent_prompt"}

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


@dataclass(frozen=True)
class RunConfig:
    ticks: int = 25
    agents: int = 5
    brain: str = "survival"
    model: str | None = None
    reasoning_effort: str | None = None
    log_agent_io: bool = True
    max_workers: int = 1
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
    max_workers: int = 1
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
        self.snapshot_path = snapshot_path
        self.events_path = events_path
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._pause_event = threading.Event()
        self._status = RunStatus()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status.to_dict()

    def start(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        load_dotenv()
        try:
            config = _parse_run_config(payload)
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc), "run": self.status()}

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return 409, {"ok": False, "error": "A simulation is already running.", "run": self._status.to_dict()}
            self._stop_event = threading.Event()
            self._pause_event.clear()
            if config.brain == "llm":
                OpenAIBrain.reset_runtime_state()
                usage_path = self.events_path.with_name(self.events_path.stem + "-usage.jsonl")
                usage_path.parent.mkdir(parents=True, exist_ok=True)
                usage_path.write_text("", encoding="utf-8")
                os.environ["AGENT_WORLD_USAGE_LOG"] = str(usage_path)
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

    def _run(self, config: RunConfig, stop_event: threading.Event) -> None:
        engine: WorldEngine | None = None
        try:
            agent_names = [f"Agent {index + 1}" for index in range(config.agents)]
            engine = WorldEngine.create(config=config.world_config, agent_names=agent_names)
            engine.log_event(
                "run_started",
                message=f"Started {config.brain} run with {config.agents} agents for {config.ticks} ticks.",
                data={"config": config.public_dict()},
                scope="public",
            )
            self._write_engine(engine)

            brains = _make_brains(engine, config)
            runner = SimulationRunner(
                engine,
                brains,
                log_agent_io=config.log_agent_io,
                concurrent_decisions=config.max_workers > 1,
                max_workers=config.max_workers,
            )

            stopped_reason: str | None = None
            for _ in range(config.ticks):
                while self._pause_event.is_set() and not stop_event.is_set():
                    time.sleep(0.2)
                if stop_event.is_set():
                    break
                events = runner.step()
                if _contains_quota_failure(events):
                    stopped_reason = "OpenAI quota is unavailable; stopped early so the run is not mistaken for agent behavior."
                    engine.log_event(
                        "run_stopped",
                        message=stopped_reason,
                        data={"reason": "insufficient_quota", "target_ticks": config.ticks},
                        scope="public",
                    )
                    stop_event.set()
                self._write_engine(engine)
                self._update_running_status(engine)
                if stopped_reason:
                    break

            final_state = "stopped" if stop_event.is_set() else "completed"
            if stopped_reason is None:
                engine.log_event(
                    "run_stopped" if final_state == "stopped" else "run_completed",
                    message=f"Simulation {final_state} at tick {engine.state.tick}.",
                    data={"target_ticks": config.ticks},
                    scope="public",
                )
            self._write_engine(engine)
            metrics = compute_metrics(engine.state)
            with self._lock:
                self._status.state = final_state
                self._status.current_tick = engine.state.tick
                self._status.finished_at = time.time()
                self._status.stop_requested = False
                self._status.metrics = _status_metrics(metrics)
        except Exception as exc:  # The observatory should survive a failed run.
            if engine is not None:
                engine.log_event(
                    "run_failed",
                    message=f"Simulation failed: {exc}",
                    data={"error": str(exc)},
                    scope="public",
                )
                self._write_engine(engine)
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

    def _write_engine(self, engine: WorldEngine) -> None:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        events_jsonl = engine.export_events_jsonl()
        _atomic_write_text(self.events_path, events_jsonl + ("\n" if events_jsonl else ""))
        _atomic_write_text(self.snapshot_path, json.dumps(engine.snapshot(), indent=2, sort_keys=True))


def _parse_run_config(payload: dict[str, Any]) -> RunConfig:
    brain = str(payload.get("brain", TUNED_OBSERVATORY_DEFAULTS["brain"])).strip().lower()
    if brain not in {"survival", "llm"}:
        raise ValueError("brain must be survival or llm.")
    model = str(payload.get("model") or os.environ.get("OPENAI_MODEL") or TUNED_OBSERVATORY_DEFAULTS["model"]).strip()
    reasoning_effort = _parse_reasoning_effort(
        payload.get("reasoning_effort")
        or os.environ.get("OPENAI_REASONING_EFFORT", TUNED_OBSERVATORY_DEFAULTS["reasoning_effort"])
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
            payload.get("geography_mode", "shared_oasis"), "geography_mode", {"shared_oasis", "dispersed"}
        ),
        economy_mode=_bounded_choice(
            payload.get("economy_mode", "baseline"), "economy_mode", {"baseline", "commerce"}
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
        model=model if brain == "llm" else None,
        reasoning_effort=reasoning_effort if brain == "llm" else None,
        log_agent_io=bool(payload.get("log_agent_io", TUNED_OBSERVATORY_DEFAULTS["log_agent_io"])),
        max_workers=_bounded_int(payload.get("max_workers", TUNED_OBSERVATORY_DEFAULTS["max_workers"]), "max_workers", minimum=1, maximum=20),
        world_config=world_config,
    )


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
    allowed = {"minimal", "low", "medium", "high"}
    if effort not in allowed:
        raise ValueError(f"reasoning_effort must be one of: {', '.join(sorted(allowed))}.")
    return effort


def _make_brains(engine: WorldEngine, config: RunConfig) -> dict[str, AgentBrain]:
    if config.brain == "llm":
        return {
            agent_id: OpenAIBrain(model=config.model, reasoning_effort=config.reasoning_effort)
            for agent_id in engine.state.agents
        }
    return {agent_id: SurvivalBrain() for agent_id in engine.state.agents}


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


def _contains_quota_failure(events: list[Any]) -> bool:
    return any(is_quota_failure_message(getattr(event, "type", None), getattr(event, "message", None)) for event in events)


def _atomic_write_text(path: Path, text: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


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
                self._send_json(
                    load_observer_state(
                        snapshot_path,
                        events_path,
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


def load_observer_state(
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
            events = [event for event in events if event.get("tick", 0) <= at_tick]
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


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent World Observatory</title>
  <style>
    :root {
      color-scheme: light;
      --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
      --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
      --bg: #f3efe3;
      --panel: #fdfcf6;
      --panel-2: #f7f3e7;
      --board: #efe9d8;
      --line: #e5decb;
      --line-strong: #d5ccb2;
      --ink: #3a352a;
      --muted: #746d5b;
      --faint: #a49b85;
      --green: #3f6d4e;
      --green-bright: #57854f;
      --green-soft: #e5eede;
      --terra: #b3593f;
      --gold: #8a6516;
      --violet: #6f4f8f;
      --sky: #4a7fa5;
      --danger: #a8402a;
      --radius: 14px;
      --shadow: 0 16px 40px -30px rgba(90, 70, 30, 0.55);
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      height: 100dvh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      font-family: var(--sans);
      font-size: 13.5px;
      color: var(--ink);
      background:
        radial-gradient(1000px 500px at 90% -10%, rgba(140, 170, 110, 0.10), transparent 60%),
        radial-gradient(900px 500px at -10% 0%, rgba(190, 150, 80, 0.08), transparent 55%),
        var(--bg);
      -webkit-font-smoothing: antialiased;
    }
    button, input, select { font-family: var(--sans); }

    /* ---------- Topbar ---------- */
    .topbar {
      position: sticky;
      top: 0;
      z-index: 30;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 12px 22px;
      background: rgba(253, 252, 246, 0.92);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--line);
    }
    .runline { position: absolute; left: 0; right: 0; bottom: -1px; height: 3px; pointer-events: none; }
    .runline i { display: block; height: 100%; width: 0%; background: linear-gradient(90deg, #8db877, var(--green)); transition: width .4s ease; border-radius: 0 2px 2px 0; }
    .brand { display: flex; align-items: center; gap: 11px; min-width: 0; }
    .brand-mark { flex: none; display: grid; place-items: center; }
    .brand-text h1 {
      margin: 0;
      font-family: var(--serif);
      font-size: 19px;
      font-weight: 600;
      letter-spacing: 0.01em;
      color: var(--ink);
      line-height: 1.1;
    }
    .brand-sub {
      margin: 0;
      font-size: 9.5px;
      font-weight: 700;
      letter-spacing: 0.24em;
      text-transform: uppercase;
      color: var(--faint);
    }
    .topbar-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .tick-chip {
      display: inline-flex;
      align-items: baseline;
      gap: 6px;
      height: 30px;
      align-items: center;
      padding: 0 12px;
      border-radius: 999px;
      border: 1px solid var(--line-strong);
      background: var(--panel);
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .tick-chip b { font-size: 14px; color: var(--ink); font-variant-numeric: tabular-nums; letter-spacing: 0; }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      height: 30px;
      padding: 0 12px;
      border-radius: 999px;
      border: 1px solid var(--line-strong);
      background: var(--panel);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .status-pill .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint); }
    .status-pill.running { background: var(--green-soft); border-color: #b7cfa8; color: var(--green); }
    .status-pill.running .dot { background: var(--green); animation: pulse 1.8s ease-out infinite; }
    .status-pill.completed { background: #e3edf4; border-color: #b6cddd; color: var(--sky); }
    .status-pill.completed .dot { background: var(--sky); }
    .status-pill.stopped { background: #f4e8cf; border-color: #dcc793; color: var(--gold); }
    .status-pill.stopped .dot { background: var(--gold); }
    .status-pill.failed { background: #f6e0d8; border-color: #ddab99; color: var(--danger); }
    .status-pill.failed .dot { background: var(--danger); }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(63, 109, 78, 0.4); }
      70% { box-shadow: 0 0 0 7px rgba(63, 109, 78, 0); }
      100% { box-shadow: 0 0 0 0 rgba(63, 109, 78, 0); }
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      height: 34px;
      padding: 0 16px;
      border-radius: 9px;
      border: 1px solid var(--line-strong);
      background: var(--panel);
      color: var(--ink);
      font-size: 12.5px;
      font-weight: 650;
      cursor: pointer;
      transition: border-color .15s ease, background .15s ease, transform .1s ease, filter .15s ease;
    }
    .btn:hover { border-color: var(--green); color: var(--green); }
    .btn:active { transform: translateY(1px); }
    .btn.primary {
      background: linear-gradient(180deg, var(--green-bright), var(--green));
      border-color: transparent;
      color: #fdfcf6;
      box-shadow: 0 8px 18px -10px rgba(63, 109, 78, 0.8);
    }
    .btn.primary:hover { filter: brightness(1.06); color: #fdfcf6; }
    .btn.danger { color: var(--danger); border-color: #ddab99; }
    .btn.danger:hover { background: #f6e0d8; border-color: var(--danger); }
    .btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none; filter: none; box-shadow: none; }

    /* ---------- Ticker ---------- */
    .ticker {
      display: flex;
      flex-wrap: wrap;
      padding: 0 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(250, 247, 236, 0.8);
    }
    .stat {
      display: flex;
      align-items: baseline;
      gap: 7px;
      padding: 9px 16px 9px 0;
      margin-right: 16px;
      border-right: 1px solid var(--line);
    }
    .stat:last-child { border-right: none; }
    .stat .v { font-size: 15px; font-weight: 700; color: var(--ink); font-variant-numeric: tabular-nums; }
    .stat .k { font-size: 9.5px; font-weight: 650; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); }

    /* ---------- Full-map viewport with floating windows ---------- */
    .viewport { position: relative; flex: 1; min-height: 0; }
    .map-stage {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      padding: 12px 96px 12px 16px;
    }
    .map-board { width: 100%; height: 100%; min-height: 0; }
    .map-note-chip {
      position: absolute;
      left: 14px;
      top: 12px;
      z-index: 20;
      padding: 4px 11px;
      border-radius: 999px;
      border: 1px solid var(--line-strong);
      background: rgba(253, 252, 246, 0.9);
      color: var(--muted);
      font-size: 11px;
      font-variant-numeric: tabular-nums;
    }
    .map-note-chip:empty { display: none; }
    .dock {
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 26;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .dock-btn {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      width: 68px;
      padding: 9px 4px 7px;
      border-radius: 13px;
      border: 1px solid var(--line-strong);
      background: rgba(253, 252, 246, 0.92);
      backdrop-filter: blur(6px);
      color: var(--muted);
      font-size: 8.5px;
      font-weight: 700;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      cursor: pointer;
      box-shadow: var(--shadow);
      transition: border-color .15s ease, color .15s ease, background .15s ease;
    }
    .dock-btn:hover { border-color: var(--green); color: var(--green); }
    .dock-btn.active { background: var(--green-soft); border-color: var(--green); color: var(--green); }
    .dock-btn svg { display: block; }
    .dock-badge {
      position: absolute;
      top: -6px;
      right: -6px;
      min-width: 19px;
      height: 19px;
      padding: 0 5px;
      border-radius: 999px;
      background: var(--green);
      border: 1.5px solid var(--panel);
      color: #fdfcf6;
      font-size: 10px;
      font-weight: 700;
      font-style: normal;
      display: grid;
      place-items: center;
      font-variant-numeric: tabular-nums;
    }
    .float-win {
      position: absolute;
      top: 12px;
      right: 92px;
      z-index: 25;
      width: min(410px, calc(100vw - 120px));
      max-height: calc(100% - 24px);
      display: flex;
      flex-direction: column;
      background: var(--panel);
      border: 1px solid var(--line-strong);
      border-radius: var(--radius);
      box-shadow: 0 26px 60px -30px rgba(90, 70, 30, 0.6);
      padding: 15px 17px;
    }
    .float-win[hidden] { display: none; }
    .win-body { min-height: 0; overflow: auto; margin: 0 -6px; padding: 0 6px; }
    .win-body::-webkit-scrollbar { width: 9px; }
    .win-body::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 999px; border: 2px solid transparent; background-clip: padding-box; }
    #inspector {
      top: auto;
      right: auto;
      left: 14px;
      bottom: 14px;
      width: min(370px, calc(100vw - 120px));
      max-height: min(58%, 480px);
    }
    .panel-head {
      flex: none;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 13px;
    }
    .panel-head h2 {
      margin: 0 auto 0 0;
      font-family: var(--serif);
      font-size: 16px;
      font-weight: 600;
      color: var(--ink);
      letter-spacing: 0.01em;
    }
    .panel-note { color: var(--faint); font-size: 11.5px; font-variant-numeric: tabular-nums; }

    /* ---------- Map ---------- */
    #map { width: 100%; height: 100%; }
    #map svg { display: block; width: 100%; height: 100%; }
    .map-empty { height: 100%; display: grid; place-items: center; color: var(--faint); font-size: 13px; }
    .map-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 15px;
      margin-top: 2px;
    }
    .lg { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; color: var(--muted); }
    .lg .sw { width: 12px; height: 12px; border-radius: 4px; box-shadow: inset 0 0 0 1px rgba(60, 50, 20, 0.15); }
    .lg svg { display: block; }

    /* ---------- Tooltip ---------- */
    .tt {
      position: fixed;
      z-index: 70;
      max-width: 250px;
      background: #fffef9;
      border: 1px solid var(--line-strong);
      border-radius: 10px;
      padding: 9px 11px;
      font-size: 11.5px;
      color: var(--ink);
      box-shadow: 0 14px 34px -14px rgba(90, 70, 30, 0.5);
      pointer-events: none;
    }
    .tt-head { font-weight: 700; margin-bottom: 4px; }
    .tt-row { display: flex; flex-wrap: wrap; gap: 4px 8px; margin-top: 3px; color: var(--muted); }
    .tt-res { display: inline-flex; align-items: center; gap: 4px; }
    .tt-res i { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
    .tt-foot { margin-top: 6px; font-size: 10px; color: var(--faint); }

    /* ---------- Roster ---------- */
    .roster { display: grid; grid-template-columns: repeat(auto-fill, minmax(225px, 1fr)); gap: 11px; }
    .card {
      position: relative;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 11px 12px;
      background: var(--panel-2);
      cursor: pointer;
      transition: border-color .15s ease, transform .12s ease, box-shadow .15s ease;
    }
    .card:hover { border-color: var(--line-strong); transform: translateY(-1px); }
    .card.selected { border-color: var(--green); box-shadow: 0 0 0 2px var(--green-soft); }
    .card.dead { opacity: 0.55; }
    .card.dead::after {
      content: "deceased";
      position: absolute;
      top: 11px;
      right: 12px;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--danger);
    }
    .card-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
    .card-dot { flex: none; width: 12px; height: 12px; border-radius: 50%; box-shadow: inset 0 0 0 1.5px rgba(0, 0, 0, 0.18); }
    .card-name { font-weight: 700; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .card-pos { margin-left: auto; color: var(--faint); font-size: 11px; font-variant-numeric: tabular-nums; }
    .card-inv { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin: 9px 0; }
    .inv-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 1.5px 7px;
      border-radius: 999px;
      background: #efe9d8;
      color: var(--muted);
      font-size: 10.5px;
      font-weight: 600;
    }
    .inv-chip i { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
    .inv-chip.empty { background: transparent; border: 1px dashed var(--line-strong); color: var(--faint); font-weight: 500; }
    .card-inv .carry { margin-left: auto; color: var(--faint); font-size: 10.5px; font-variant-numeric: tabular-nums; }
    .meters { display: grid; gap: 5px; }
    .meter { display: grid; grid-template-columns: 44px 1fr 30px; align-items: center; gap: 8px; }
    .meter .ml { font-size: 9.5px; color: var(--muted); text-transform: capitalize; }
    .meter .mv { font-size: 9.5px; color: var(--faint); text-align: right; font-variant-numeric: tabular-nums; }
    .track { height: 6.5px; border-radius: 999px; background: #e8e2d0; overflow: hidden; }
    .track i { display: block; height: 100%; border-radius: 999px; }
    .meter-health .track i { background: linear-gradient(90deg, #d98a5e, #c2693f); }
    .meter-food .track i { background: linear-gradient(90deg, #8cb872, #6f9e57); }
    .meter-water .track i { background: linear-gradient(90deg, #7bb4d6, #5b96bd); }
    .meter-energy .track i { background: linear-gradient(90deg, #c1a3d8, #9c7bbd); }

    /* ---------- Civilization panel ---------- */
    .civ-chips { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
    .chip {
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 11px;
    }
    .chip b { display: block; font-size: 17px; font-weight: 700; color: var(--ink); font-variant-numeric: tabular-nums; line-height: 1.2; }
    .chip b .dim { color: var(--faint); font-weight: 600; font-size: 13px; }
    .chip span { color: var(--muted); font-size: 10px; font-weight: 650; letter-spacing: 0.06em; text-transform: uppercase; }
    .chart { border: 1px solid var(--line); border-radius: 10px; background: #fffef9; padding: 8px 8px 4px; }
    .chart svg { display: block; width: 100%; height: 96px; }
    .chart-empty { padding: 26px 10px; text-align: center; color: var(--faint); font-size: 12px; }
    .chart-legend { display: flex; flex-wrap: wrap; gap: 5px 14px; margin-top: 8px; }
    .cl-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--muted); }
    .cl-item i { width: 9px; height: 3.5px; border-radius: 2px; display: inline-block; }
    .cl-item b { color: var(--ink); font-variant-numeric: tabular-nums; }
    .struct-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; margin-top: 12px; }
    .struct-chip {
      display: grid;
      justify-items: center;
      gap: 1px;
      padding: 8px 4px 6px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel-2);
      text-align: center;
    }
    .struct-chip.zero { opacity: 0.4; }
    .struct-chip b { font-size: 13px; font-variant-numeric: tabular-nums; }
    .struct-chip span { font-size: 9px; color: var(--muted); letter-spacing: 0.03em; text-transform: uppercase; font-weight: 650; }

    /* ---------- Inspector ---------- */
    .mini-close {
      width: 24px; height: 24px;
      border-radius: 7px;
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--muted);
      font-size: 14px;
      line-height: 1;
      cursor: pointer;
    }
    .mini-close:hover { color: var(--ink); border-color: var(--line-strong); }
    .ins-res { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
    .ins-block { border: 1px solid var(--line); border-radius: 10px; background: var(--panel-2); padding: 9px 11px; margin-bottom: 8px; }
    .ins-block-head { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
    .ins-block-head b { font-size: 12.5px; }
    .ins-icon { flex: none; display: grid; place-items: center; }
    .badge {
      margin-left: auto;
      padding: 1.5px 7px;
      border-radius: 999px;
      font-size: 9.5px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .badge.ok { background: var(--green-soft); color: var(--green); }
    .badge.warn { background: #f4e8cf; color: var(--gold); }
    .mini { color: var(--muted); font-size: 11px; line-height: 1.5; }
    .ins-agent { display: flex; align-items: center; gap: 7px; padding: 5px 0; font-size: 12px; }
    .ins-agent .card-dot { width: 10px; height: 10px; }
    .ins-agent .mini { margin-left: auto; }

    /* ---------- Chronicle ---------- */
    .console-filters { display: flex; gap: 8px; margin-bottom: 10px; }
    .picker { flex: 1; min-width: 0; display: grid; gap: 4px; }
    .picker .pk { font-size: 9.5px; color: var(--faint); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; }
    .picker select {
      width: 100%;
      height: 30px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: #fffef9;
      color: var(--ink);
      padding: 0 8px;
      font-size: 12px;
      cursor: pointer;
    }
    .picker select:focus { outline: none; border-color: var(--green); box-shadow: 0 0 0 3px var(--green-soft); }
    .console-filters { flex: none; }
    .console-body { flex: 1; min-height: 140px; overflow: auto; margin: 0 -6px; padding: 0 6px; }
    .console-body::-webkit-scrollbar { width: 9px; }
    .console-body::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 999px; border: 2px solid transparent; background-clip: padding-box; }
    .logline {
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr);
      gap: 9px;
      padding: 8px 4px;
      border-bottom: 1px solid var(--line);
      font-size: 12.5px;
    }
    .logline:last-child { border-bottom: none; }
    .logline .lt {
      align-self: start;
      display: inline-grid;
      place-items: center;
      min-width: 28px;
      height: 20px;
      border-radius: 6px;
      background: var(--panel-2);
      border: 1px solid var(--line);
      color: var(--muted);
      font-weight: 700;
      font-size: 10.5px;
      font-variant-numeric: tabular-nums;
    }
    .log-main { min-width: 0; display: grid; gap: 3px; }
    .log-meta { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
    .tag {
      display: inline-flex;
      align-items: center;
      height: 18px;
      padding: 0 7px;
      border-radius: 999px;
      font-size: 9.5px;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      background: #eee9db;
      color: #6f695c;
      white-space: nowrap;
    }
    .tag.invalid { background: #f6e0d8; color: var(--danger); }
    .tag.move { background: #e2ecf3; color: #3f6c8a; }
    .tag.resource { background: #e3edda; color: #44703f; }
    .tag.social { background: #ece4f1; color: var(--violet); }
    .tag.trade { background: #f4ead0; color: var(--gold); }
    .tag.body { background: #f0e8d6; color: #7a6a3a; }
    .tag.system { background: #edeade; color: #6b6a5d; }
    .actor { color: var(--faint); font-weight: 650; font-size: 11px; }
    .msg { color: var(--ink); line-height: 1.45; overflow-wrap: anywhere; }
    .msg.speech { font-family: var(--serif); font-style: italic; color: #4a4335; }
    .empty-note { color: var(--faint); padding: 18px 6px; font-size: 12px; }

    /* ---------- Drawer ---------- */
    .drawer-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(60, 50, 25, 0.35);
      backdrop-filter: blur(2px);
      opacity: 0;
      pointer-events: none;
      transition: opacity .18s ease;
      z-index: 40;
    }
    .drawer-backdrop.open { opacity: 1; pointer-events: auto; }
    .drawer {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: min(460px, 100vw);
      background: var(--panel);
      border-left: 1px solid var(--line-strong);
      display: flex;
      flex-direction: column;
      transform: translateX(102%);
      transition: transform .22s ease;
      z-index: 41;
      box-shadow: -18px 0 44px -26px rgba(90, 70, 30, 0.5);
    }
    .drawer.open { transform: translateX(0); }
    .drawer-head {
      flex: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 18px 13px;
      border-bottom: 1px solid var(--line);
    }
    .drawer-title { font-family: var(--serif); font-size: 17px; font-weight: 600; }
    .drawer-close {
      width: 30px; height: 30px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--muted);
      cursor: pointer;
      display: grid;
      place-items: center;
      font-size: 15px;
    }
    .drawer-close:hover { color: var(--ink); border-color: var(--line-strong); }
    .drawer-tabs { flex: none; display: flex; gap: 6px; padding: 13px 18px 0; }
    .dtab {
      flex: 1;
      height: 32px;
      border: 1px solid var(--line);
      border-radius: 9px;
      background: var(--panel-2);
      color: var(--muted);
      font-size: 11.5px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      cursor: pointer;
    }
    .dtab:hover { color: var(--ink); border-color: var(--line-strong); }
    .dtab.active { background: var(--green-soft); color: var(--green); border-color: #b7cfa8; }
    .drawer-body { flex: 1; min-height: 0; overflow: auto; padding: 16px 18px; }
    .drawer-body::-webkit-scrollbar { width: 9px; }
    .drawer-body::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 999px; border: 2px solid transparent; background-clip: padding-box; }
    .dpanel[hidden] { display: none; }
    .dform { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 14px; align-items: end; }
    .field { min-width: 0; display: grid; gap: 5px; }
    .field label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.07em; font-weight: 700; }
    .field input, .field select {
      width: 100%;
      min-width: 0;
      height: 34px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: #fffef9;
      color: var(--ink);
      padding: 0 10px;
      font-size: 13px;
    }
    .field select { cursor: pointer; }
    .field input:focus, .field select:focus { outline: none; border-color: var(--green); box-shadow: 0 0 0 3px var(--green-soft); }
    .field input:disabled, .field select:disabled { color: var(--faint); background: var(--panel-2); cursor: not-allowed; }
    .field.check { display: flex; align-items: center; gap: 8px; height: 34px; }
    .field.check input { width: 16px; height: 16px; accent-color: var(--green); }
    .field.check label { text-transform: none; font-size: 12.5px; color: var(--ink); letter-spacing: 0; font-weight: 550; }
    .section { grid-column: 1 / -1; padding-top: 14px; margin-top: 4px; border-top: 1px dashed var(--line-strong); }
    .section-title {
      grid-column: 1 / -1;
      color: var(--green);
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    .terrain-grid { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .terrain-block {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 11px;
      display: grid;
      gap: 9px;
      background: var(--panel-2);
      margin: 0;
    }
    .terrain-block .tb-title {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--gold);
      padding: 0 4px;
    }
    .drawer-footer { flex: none; padding: 13px 18px 16px; border-top: 1px solid var(--line); display: grid; gap: 8px; }
    .drawer-footer .btn { width: 100%; }
    .drawer-foot-note { margin: 0; font-size: 11px; color: var(--faint); line-height: 1.4; text-align: center; }
    .drawer-foot-note strong { color: var(--muted); }
    .run-stack { display: grid; gap: 12px; }
    .run-meta { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 11.5px; color: var(--muted); }
    .run-meta strong { color: var(--ink); font-size: 12.5px; }
    .footer-actions { display: flex; gap: 8px; }
    .footer-actions .btn { flex: 1; }
    .progress { height: 6px; border-radius: 999px; background: #e8e2d0; overflow: hidden; }
    .timeline { display: grid; gap: 4px; }
    .timeline-row { display: flex; align-items: center; gap: 6px; }
    .timeline-row input[type="range"] {
      flex: 1;
      min-width: 0;
      height: 5px;
      appearance: none;
      -webkit-appearance: none;
      border-radius: 999px;
      background: #e8e2d0;
      accent-color: var(--accent, #c15f3c);
      cursor: pointer;
    }
    .timeline-row input[type="range"]:disabled { cursor: not-allowed; opacity: .5; }
    .btn.tiny { flex: none; height: 26px; padding: 0 8px; font-size: 11px; }
    .btn.tiny.live.viewing-history { background: var(--accent, #c15f3c); color: #fff; border-color: transparent; }
    .timeline-label { font-size: 11px; color: #8a857a; font-variant-numeric: tabular-nums; }
    .timeline-label.history { color: var(--accent, #c15f3c); font-weight: 640; }
    .progress i { display: block; height: 100%; width: 0%; background: linear-gradient(90deg, #8db877, var(--green)); transition: width .3s ease; }

    @media (max-width: 760px) {
      .topbar { flex-wrap: wrap; }
      .topbar-right { width: 100%; justify-content: space-between; }
      .ticker { padding: 0 14px; flex-wrap: nowrap; overflow-x: auto; }
      .stat { flex: none; }
      .map-stage { padding: 44px 10px 92px; place-items: start center; }
      .map-note-chip { top: 10px; left: 10px; }
      .dock { top: auto; bottom: 10px; left: 10px; right: 10px; flex-direction: row; justify-content: center; }
      .dock-btn { flex: 1; max-width: 88px; }
      .float-win { top: auto; bottom: 88px; left: 10px; right: 10px; width: auto; max-height: 58dvh; }
      #inspector { left: 10px; right: 10px; bottom: 88px; width: auto; max-height: 58dvh; }
      .dform, .terrain-grid { grid-template-columns: 1fr; }
      .roster { grid-template-columns: minmax(0, 1fr); }
      .drawer { width: 100vw; }
      .struct-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 26 26" width="30" height="30">
          <circle cx="17.5" cy="8" r="4.2" fill="#e0b84f"/>
          <path d="M1 22 Q8 9 14 22 Z" fill="#7fa663"/>
          <path d="M10 22 Q18 7 25 22 Z" fill="#3f6d4e"/>
        </svg>
      </span>
      <div class="brand-text">
        <h1>Agent World</h1>
        <p class="brand-sub">Observatory</p>
      </div>
    </div>
    <div class="topbar-right">
      <span class="tick-chip">Tick <b id="tick-readout">0</b></span>
      <span class="status-pill" id="status-pill"><span class="dot"></span><span id="status-text">idle</span></span>
      <button class="btn primary" id="open-drawer" type="button">Configure Run</button>
    </div>
    <div class="runline" aria-hidden="true"><i id="runline-bar"></i></div>
  </header>

  <section class="ticker" id="ticker" aria-label="Run summary"></section>

  <div class="viewport">
    <div class="map-stage">
      <div class="map-board"><div id="map"></div></div>
    </div>
    <span class="map-note-chip" id="map-note"></span>

    <nav class="dock" aria-label="Panels">
      <button class="dock-btn" id="dock-run" type="button" data-window="win-run">
        <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><polygon points="4,3.5 4,16.5 15,10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><line x1="17" y1="3.5" x2="17" y2="16.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        Run
      </button>
      <button class="dock-btn" id="dock-civ" type="button" data-window="win-civ">
        <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><polyline points="2,15 7,9 11,12 18,3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><line x1="2" y1="18" x2="18" y2="18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity="0.5"/></svg>
        Civilization
      </button>
      <button class="dock-btn" id="dock-agents" type="button" data-window="win-agents">
        <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><circle cx="7" cy="6.5" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M2 17 q0 -5 5 -5 q5 0 5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="14.5" cy="7.5" r="2.4" fill="none" stroke="currentColor" stroke-width="1.6" opacity="0.7"/><path d="M12.5 16.5 q0.2 -3.8 4 -3.8 q2 0 2 2.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity="0.7"/></svg>
        Agents
        <em class="dock-badge" id="dock-agents-badge" hidden></em>
      </button>
      <button class="dock-btn" id="dock-chronicle" type="button" data-window="win-chronicle">
        <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><rect x="4" y="2.5" width="12" height="15" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><line x1="7" y1="7" x2="13" y2="7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="7" y1="10.5" x2="13" y2="10.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="7" y1="14" x2="10.5" y2="14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
        Chronicle
      </button>
      <button class="dock-btn" id="dock-legend" type="button" data-window="win-legend">
        <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><circle cx="10" cy="10" r="7.5" fill="none" stroke="currentColor" stroke-width="1.8"/><polygon points="10,4.5 12,10 10,15.5 8,10" fill="currentColor"/></svg>
        Legend
      </button>
    </nav>

    <section class="float-win" id="win-civ" hidden aria-label="Civilization">
      <div class="panel-head">
        <h2>Civilization</h2>
        <span class="panel-note">trends over ticks</span>
        <button class="mini-close win-close" type="button" data-window="win-civ" aria-label="Close">&#10005;</button>
      </div>
      <div class="win-body">
        <div class="civ-chips" id="civ-chips"></div>
        <div class="chart" id="civ-chart"></div>
        <div class="chart-legend" id="civ-legend"></div>
        <div class="struct-row" id="civ-structures"></div>
      </div>
    </section>

    <section class="float-win" id="win-agents" hidden aria-label="Agents">
      <div class="panel-head">
        <h2>Agents</h2>
        <span class="panel-note" id="agent-count"></span>
        <button class="mini-close win-close" type="button" data-window="win-agents" aria-label="Close">&#10005;</button>
      </div>
      <div class="win-body">
        <div class="roster" id="agents"></div>
      </div>
    </section>

    <section class="float-win" id="win-chronicle" hidden aria-label="Chronicle">
      <div class="panel-head">
        <h2>Chronicle</h2>
        <span class="panel-note" id="event-count"></span>
        <button class="mini-close win-close" type="button" data-window="win-chronicle" aria-label="Close">&#10005;</button>
      </div>
      <div class="console-filters">
        <label class="picker"><span class="pk">Agent</span><select id="filter-agent"></select></label>
        <label class="picker"><span class="pk">Action</span><select id="filter-type"></select></label>
      </div>
      <div class="console-body" id="events"></div>
    </section>

    <section class="float-win" id="win-legend" hidden aria-label="Map legend">
      <div class="panel-head">
        <h2>Legend</h2>
        <button class="mini-close win-close" type="button" data-window="win-legend" aria-label="Close">&#10005;</button>
      </div>
      <div class="win-body">
        <div class="map-legend" id="map-legend"></div>
      </div>
    </section>

    <section class="float-win" id="win-run" hidden aria-label="Run control">
      <div class="panel-head">
        <h2>Run</h2>
        <span class="panel-note" id="run-state-detail"></span>
        <button class="mini-close win-close" type="button" data-window="win-run" aria-label="Close">&#10005;</button>
      </div>
      <div class="win-body">
        <div class="run-stack">
          <div class="run-meta"><strong id="run-state-label">Idle</strong></div>
          <div class="progress"><i id="progress-bar"></i></div>
          <div class="timeline" id="timeline" aria-label="Tick timeline">
            <div class="timeline-row">
              <button class="btn tiny" id="tick-back" type="button" title="Back one tick" disabled>&#9664;</button>
              <input type="range" id="timeline-slider" min="0" max="0" value="0" step="1" disabled>
              <button class="btn tiny" id="tick-forward" type="button" title="Forward one tick" disabled>&#9654;</button>
              <button class="btn tiny live" id="tick-live" type="button" disabled>Live</button>
            </div>
            <div class="timeline-label" id="timeline-label">no history yet</div>
          </div>
          <div class="footer-actions">
            <button class="btn primary" id="start-run" type="submit" form="panel-launch">Start</button>
            <button class="btn" id="pause-run" type="button" disabled>Pause</button>
            <button class="btn danger" id="stop-run" type="button" disabled>Stop</button>
          </div>
        </div>
      </div>
    </section>

    <section class="float-win" id="inspector" hidden aria-label="Tile inspector">
      <div class="panel-head">
        <h2 id="inspector-title">Tile</h2>
        <button class="mini-close" id="inspector-close" type="button" aria-label="Close inspector">&#10005;</button>
      </div>
      <div class="win-body" id="inspector-body"></div>
    </section>
  </div>

  <div id="tt" class="tt" hidden></div>

  <div class="drawer-backdrop" id="drawer-backdrop"></div>
  <aside class="drawer" id="drawer" aria-label="Run control">
    <div class="drawer-head">
      <span class="drawer-title">Run Control</span>
      <button class="drawer-close" id="close-drawer" type="button" aria-label="Close">&#10005;</button>
    </div>
    <div class="drawer-tabs">
      <button class="dtab active" id="tab-launch" type="button" data-panel="panel-launch">Launch</button>
      <button class="dtab" id="tab-config" type="button" data-panel="panel-config">World Config</button>
    </div>
    <div class="drawer-body">
      <form class="dform dpanel" id="panel-launch">
        <label class="field">
          <label for="run-brain">Brain</label>
          <select id="run-brain" class="lock">
            <option value="survival">survival</option>
            <option value="llm" selected>llm</option>
          </select>
        </label>
        <label class="field">
          <label for="run-agents">Agents</label>
          <input id="run-agents" class="lock" type="number" min="1" max="20" value="5">
        </label>
        <label class="field">
          <label for="run-ticks">Ticks</label>
          <input id="run-ticks" class="lock" type="number" min="1" max="1000" value="20">
        </label>
        <label class="field">
          <label for="run-seed">Seed</label>
          <input id="run-seed" class="lock" type="number" min="0" value="11">
        </label>
        <label class="field">
          <label for="run-model">Model</label>
          <select id="run-model" class="lock">
            <option value="z-ai/glm-5.2" selected>GLM-5.2</option>
            <option value="z-ai/glm-5.1">GLM-5.1</option>
            <option value="z-ai/glm-4.7">GLM-4.7</option>
            <option value="z-ai/glm-4.5-air">GLM-4.5 Air</option>
          </select>
        </label>
        <label class="field">
          <label for="run-reasoning">Reasoning</label>
          <select id="run-reasoning" class="lock">
            <option value="minimal">minimal</option>
            <option value="low">low</option>
            <option value="medium" selected>medium</option>
            <option value="high">high</option>
          </select>
        </label>
        <label class="field">
          <label for="run-workers">Max workers</label>
          <input id="run-workers" class="lock" type="number" min="1" max="20" value="1">
        </label>
        <label class="field check">
          <input id="run-io" class="lock" type="checkbox" checked>
          <label for="run-io">Log agent IO</label>
        </label>
      </form>
      <div class="dform dpanel" id="panel-config" hidden>
        <div class="section-title">Experiment Treatment</div>
        <label class="field"><label for="cfg-objective-mode">Objective</label><select id="cfg-objective-mode" class="lock"><option value="neutral" selected>neutral emergence</option><option value="collective">collective welfare</option><option value="individual">individual utility</option></select></label>
        <label class="field"><label for="cfg-economy-mode">Economy</label><select id="cfg-economy-mode" class="lock"><option value="baseline" selected>baseline</option><option value="commerce">commerce</option></select></label>
        <label class="field"><label for="cfg-geography-mode">Geography</label><select id="cfg-geography-mode" class="lock"><option value="shared_oasis" selected>shared oasis</option><option value="dispersed">dispersed specialists</option></select></label>

        <div class="section-title">Agents</div>
        <label class="field"><label for="cfg-carry-capacity">Inventory limit</label><input id="cfg-carry-capacity" class="lock" type="number" min="1" max="100" value="10"></label>
        <label class="field"><label for="cfg-action-points">Action points</label><input id="cfg-action-points" class="lock" type="number" min="1" max="20" value="4"></label>
        <label class="field"><label for="cfg-storage-capacity">Storage capacity</label><input id="cfg-storage-capacity" class="lock" type="number" min="1" max="1000" value="120"></label>

        <div class="section-title section">Starting Reserves</div>
        <label class="field"><label for="cfg-food-start">Food start</label><input id="cfg-food-start" class="lock" type="number" min="0" max="100" value="10"></label>
        <label class="field"><label for="cfg-food-max">Food max</label><input id="cfg-food-max" class="lock" type="number" min="1" max="100" value="20"></label>
        <label class="field"><label for="cfg-water-start">Water start</label><input id="cfg-water-start" class="lock" type="number" min="0" max="100" value="10"></label>
        <label class="field"><label for="cfg-water-max">Water max</label><input id="cfg-water-max" class="lock" type="number" min="1" max="100" value="20"></label>
        <label class="field"><label for="cfg-energy-start">Energy start</label><input id="cfg-energy-start" class="lock" type="number" min="0" max="200" value="25"></label>
        <label class="field"><label for="cfg-energy-max">Energy max</label><input id="cfg-energy-max" class="lock" type="number" min="1" max="200" value="30"></label>

        <div class="section-title section">Survival Pressure</div>
        <label class="field"><label for="cfg-food-decay">Food decay</label><input id="cfg-food-decay" class="lock" type="number" min="0" max="20" value="1"></label>
        <label class="field"><label for="cfg-water-decay">Water decay</label><input id="cfg-water-decay" class="lock" type="number" min="0" max="20" value="2"></label>
        <label class="field"><label for="cfg-energy-decay">Energy decay</label><input id="cfg-energy-decay" class="lock" type="number" min="0" max="20" value="1"></label>
        <label class="field"><label for="cfg-exhaustion">Exhaustion damage</label><input id="cfg-exhaustion" class="lock" type="number" min="0" max="50" value="2"></label>
        <label class="field"><label for="cfg-food-spoil-interval">Food spoil ticks</label><input id="cfg-food-spoil-interval" class="lock" type="number" min="0" max="1000" value="6"></label>
        <label class="field"><label for="cfg-food-spoil-qty">Food spoil amount</label><input id="cfg-food-spoil-qty" class="lock" type="number" min="0" max="100" value="1"></label>

        <div class="section-title section">Resource Production</div>
        <label class="field"><label for="cfg-resource-base">Initial resources</label><input id="cfg-resource-base" class="lock" type="number" min="0" max="5" step="0.1" value="1"></label>
        <label class="field"><label for="cfg-starter-radius">Starter radius</label><input id="cfg-starter-radius" class="lock" type="number" min="0" max="10" value="1"></label>
        <label class="field"><label for="cfg-wild-food">Wild food density</label><input id="cfg-wild-food" class="lock" type="number" min="0" max="1" step="0.01" value="0.35"></label>
        <label class="field"><label for="cfg-wild-fiber">Wild fiber density</label><input id="cfg-wild-fiber" class="lock" type="number" min="0" max="1" step="0.01" value="0.85"></label>
        <label class="field"><label for="cfg-farm-food-added">Farm action food</label><input id="cfg-farm-food-added" class="lock" type="number" min="0" max="50" value="5"></label>
        <label class="field"><label for="cfg-farm-food-cap">Farm food cap</label><input id="cfg-farm-food-cap" class="lock" type="number" min="0" max="100" value="24"></label>
        <label class="field"><label for="cfg-farm-passive">Farm passive food</label><input id="cfg-farm-passive" class="lock" type="number" min="0" max="20" value="2"></label>

        <div class="section-title section">Terrain Regrowth</div>
        <div class="terrain-grid">
          <fieldset class="terrain-block">
            <legend class="tb-title">Plains</legend>
            <label class="field"><label for="cfg-plains-food">Food</label><input id="cfg-plains-food" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.01"></label>
            <label class="field"><label for="cfg-plains-fiber">Fiber</label><input id="cfg-plains-fiber" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.03"></label>
          </fieldset>
          <fieldset class="terrain-block">
            <legend class="tb-title">Forest</legend>
            <label class="field"><label for="cfg-forest-wood">Wood</label><input id="cfg-forest-wood" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.14"></label>
            <label class="field"><label for="cfg-forest-food">Food</label><input id="cfg-forest-food" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.02"></label>
            <label class="field"><label for="cfg-forest-fiber">Fiber</label><input id="cfg-forest-fiber" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.03"></label>
          </fieldset>
          <fieldset class="terrain-block">
            <legend class="tb-title">Mountain</legend>
            <label class="field"><label for="cfg-mountain-stone">Stone</label><input id="cfg-mountain-stone" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.04"></label>
            <label class="field"><label for="cfg-mountain-ore">Ore</label><input id="cfg-mountain-ore" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.01"></label>
          </fieldset>
          <fieldset class="terrain-block">
            <legend class="tb-title">Water</legend>
            <label class="field"><label for="cfg-water-water">Water</label><input id="cfg-water-water" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.7"></label>
            <label class="field"><label for="cfg-water-food">Food / fish</label><input id="cfg-water-food" class="lock terrain-input" type="number" min="0" max="1" step="0.01" value="0.02"></label>
          </fieldset>
        </div>
      </div>
    </div>
    <div class="drawer-footer">
      <button class="btn primary" id="drawer-start" type="submit" form="panel-launch">Start run</button>
      <p class="drawer-foot-note">Playback &amp; Start/Pause/Stop also live in the <strong>Run</strong> panel on the map.</p>
    </div>
  </aside>

  <script>
    /* ---------- Constants ---------- */
    const TILE = 40;
    const TERRAIN_FILLS = {
      plains: ["#d3e4a3", "#cbdd97", "#dae9ad"],
      forest: ["#aecf87", "#a6c67e", "#b6d691"],
      mountain: ["#d9d4c5", "#d2ccbb", "#e0dbcc"],
      water: ["#92c6e6", "#89bfe2", "#9bcdeb"],
    };
    const RESOURCE_COLORS = {
      water: "#5b96bd", food: "#c99a3f", wood: "#8a6540",
      stone: "#8d8d8d", ore: "#c98f4e", ingot: "#8f7863", fiber: "#7fa05a",
      tool: "#6f4f8f", advanced_tool: "#48345f",
    };
    const AGENT_COLORS = [
      "#c15f3c", "#3f6d8a", "#6f4f8f", "#8a6516", "#3c6b60",
      "#a84d68", "#4f6d3f", "#7a5230", "#356e73", "#8f5f8f",
    ];
    const STRUCTURE_NAMES = {
      farm_plot: "farm", storage: "storage", shelter: "shelter",
      house: "house", workshop: "workshop", well: "well",
    };
    const standardActionTypes = [
      "wait", "move", "inspect", "gather", "chop", "mine", "harvest", "fish", "farm",
      "craft", "repair", "pick_up", "drop", "claim_item", "consume", "equip", "store",
      "retrieve", "say", "whisper", "broadcast", "offer_trade", "accept_trade",
      "reject_trade", "offer_contract", "accept_contract", "repay_contract", "gift",
      "claim_tile", "contest_claim", "build", "contribute", "set_access_fee",
      "claim_dividend", "maintain_structure", "grant_access",
      "revoke_access", "create_group", "invite_member", "join_group", "leave_group",
      "publish_rule", "record_agreement",
    ];
    const TERRAIN_STORAGE_KEY = "agentWorldObservatory.terrainRegrowth";

    let latestSnapshot = {};
    let latestEvents = [];
    let latestAgents = {};
    let selectedTile = null;
    let selectedAgentId = null;
    let lastMapKey = "";
    let viewTick = null;  // null = live; a number = viewing that historical tick
    let historyRange = { min_tick: null, max_tick: null, count: 0, live_tick: 0 };

    /* ---------- Deterministic per-tile variation ---------- */
    function hash(x, y, salt = 0) {
      let h = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791);
      h = (h ^ (h >> 13)) >>> 0;
      return h;
    }
    function pick(list, x, y, salt = 0) { return list[hash(x, y, salt) % list.length]; }

    /* ---------- Terrain decoration ---------- */
    function treeShape(px, py, scale) {
      return `<g transform="translate(${px},${py}) scale(${scale})">
        <rect x="-1.3" y="1.5" width="2.6" height="5" rx="1.2" fill="#7d5f3d"/>
        <circle cx="0" cy="-0.5" r="5" fill="#4e8a52"/>
        <circle cx="0" cy="-4" r="3.4" fill="#5c9a5f"/>
      </g>`;
    }

    const TREE_SLOTS = [[11, 15], [27, 12], [15, 29], [29, 28]];
    function forestDecor(tile) {
      const wood = (tile.resources || {}).wood || 0;
      if (wood <= 0) {
        return `<ellipse cx="13" cy="16" rx="3" ry="2" fill="#b09067" stroke="#8a6540" stroke-width="0.7"/>
          <ellipse cx="26" cy="27" rx="3" ry="2" fill="#b09067" stroke="#8a6540" stroke-width="0.7"/>`;
      }
      const count = Math.min(4, 1 + Math.floor(wood / 4));
      let out = "";
      for (let i = 0; i < count; i++) {
        const [sx, sy] = TREE_SLOTS[i];
        const jx = (hash(tile.x, tile.y, i) % 5) - 2;
        const jy = (hash(tile.x, tile.y, i + 9) % 5) - 2;
        const scale = 0.85 + (hash(tile.x, tile.y, i + 17) % 30) / 100;
        out += treeShape(sx + jx, sy + jy, scale);
      }
      return out;
    }

    function mountainDecor(tile) {
      const flip = hash(tile.x, tile.y, 3) % 2 === 0;
      let out = `<g ${flip ? 'transform="translate(40,0) scale(-1,1)"' : ""}>
        <polygon points="7,33 19,10 32,33" fill="#b7af9b" stroke="#968d77" stroke-width="1" stroke-linejoin="round"/>
        <polygon points="14,33 19,10 24,21 20,33" fill="#cec7b3" opacity="0.75"/>
        <polygon points="15.5,16.5 19,10 22.5,16.5" fill="#f2efe6"/>
      </g>`;
      const res = tile.resources || {};
      if ((res.stone || 0) > 8) out += `<circle cx="8" cy="30" r="2.6" fill="#a49b87" stroke="#8b8270" stroke-width="0.7"/>`;
      if ((res.ore || 0) > 0) out += `<circle cx="33" cy="29" r="1.6" fill="#c98f4e"/>`;
      return out;
    }

    function waterDecor(tile) {
      const y1 = 8 + (hash(tile.x, tile.y, 5) % 10);
      const y2 = 23 + (hash(tile.x, tile.y, 6) % 8);
      let out = `<path d="M7 ${y1} q5 -3 10 0" fill="none" stroke="#d6ecfa" stroke-width="1.6" stroke-linecap="round"/>
        <path d="M22 ${y2} q5 -3 10 0" fill="none" stroke="#c4e2f5" stroke-width="1.4" stroke-linecap="round"/>`;
      if (((tile.resources || {}).food || 0) > 0) {
        const fx = 12 + (hash(tile.x, tile.y, 7) % 14);
        const fy = 16 + (hash(tile.x, tile.y, 8) % 10);
        out += `<g transform="translate(${fx},${fy})">
          <ellipse cx="0" cy="0" rx="3" ry="1.6" fill="#4f7d9b"/>
          <polygon points="2.4,0 5,-2 5,2" fill="#4f7d9b"/>
        </g>`;
      }
      return out;
    }

    function plainsDecor(tile) {
      let out = "";
      const tufts = 2 + (hash(tile.x, tile.y, 1) % 2);
      for (let i = 0; i < tufts; i++) {
        const px = 6 + (hash(tile.x, tile.y, 20 + i) % 28);
        const py = 9 + (hash(tile.x, tile.y, 30 + i) % 25);
        out += `<path d="M${px} ${py} q1.2 -4 2.4 0" fill="none" stroke="#9fbd72" stroke-width="1.2" stroke-linecap="round"/>`;
      }
      const flowers = Math.min(3, (tile.resources || {}).food || 0);
      for (let i = 0; i < flowers; i++) {
        const px = 8 + (hash(tile.x, tile.y, 40 + i) % 24);
        const py = 8 + (hash(tile.x, tile.y, 50 + i) % 24);
        out += `<circle cx="${px}" cy="${py}" r="1.4" fill="#dcb23e"/>`;
      }
      return out;
    }

    function tileDecor(tile) {
      if (tile.terrain === "forest") return forestDecor(tile);
      if (tile.terrain === "mountain") return mountainDecor(tile);
      if (tile.terrain === "water") return waterDecor(tile);
      return plainsDecor(tile);
    }

    /* ---------- Structures ---------- */
    function drawStructure(type, cx, cy, s, opts = {}) {
      let body = "";
      switch (type) {
        case "farm_plot": {
          const w = s, h = s * 0.72;
          const x0 = cx - w / 2, y0 = cy - h / 2;
          body = `<rect x="${x0}" y="${y0}" width="${w}" height="${h}" rx="3" fill="#b08a55" stroke="#8a6540" stroke-width="1.2"/>`;
          for (let i = 0; i < 3; i++) {
            const ry = y0 + (i + 0.5) * (h / 3);
            body += `<line x1="${x0 + 3}" y1="${ry + 1.6}" x2="${x0 + w - 3}" y2="${ry + 1.6}" stroke="#97744a" stroke-width="1.2"/>`;
            for (let j = 0; j < 3; j++) {
              const rx = x0 + (j + 0.5) * (w / 3);
              body += `<circle cx="${rx}" cy="${ry - 0.6}" r="1.7" fill="#5d9b46"/>`;
            }
          }
          break;
        }
        case "well": {
          const r = s * 0.3;
          body = `
            <polygon points="${cx - s * 0.44},${cy - s * 0.18} ${cx},${cy - s * 0.52} ${cx + s * 0.44},${cy - s * 0.18}" fill="#b3593f" stroke="#8e4530" stroke-width="1" stroke-linejoin="round"/>
            <line x1="${cx}" y1="${cy - s * 0.18}" x2="${cx}" y2="${cy + s * 0.02}" stroke="#6b5232" stroke-width="1.1"/>
            <rect x="${cx - s * 0.38}" y="${cy - s * 0.2}" width="2.4" height="${s * 0.34}" fill="#7d5f3d"/>
            <rect x="${cx + s * 0.38 - 2.4}" y="${cy - s * 0.2}" width="2.4" height="${s * 0.34}" fill="#7d5f3d"/>
            <circle cx="${cx}" cy="${cy + s * 0.16}" r="${r}" fill="#c9ccd2" stroke="#8b9098" stroke-width="1.5"/>
            <circle cx="${cx}" cy="${cy + s * 0.16}" r="${r * 0.52}" fill="#5a6572"/>`;
          break;
        }
        case "shelter": {
          const w = s * 0.9, h = s * 0.66;
          const base = cy + h * 0.38;
          body = `
            <polygon points="${cx - w / 2},${base} ${cx},${base - h} ${cx + w / 2},${base}" fill="#c9a36b" stroke="#a37f4b" stroke-width="1.3" stroke-linejoin="round"/>
            <polygon points="${cx - w * 0.16},${base} ${cx},${base - h * 0.55} ${cx + w * 0.16},${base}" fill="#8a6540"/>`;
          break;
        }
        case "house": {
          const w = s * 0.8, h = s * 0.52;
          const x0 = cx - w / 2, y0 = cy - h / 2 + s * 0.1;
          body = `
            <rect x="${x0}" y="${y0}" width="${w}" height="${h}" rx="1.5" fill="#eed9ae" stroke="#bfa276" stroke-width="1.2"/>
            <polygon points="${x0 - 3},${y0} ${cx},${y0 - s * 0.34} ${x0 + w + 3},${y0}" fill="#b3593f" stroke="#8e4530" stroke-width="1.2" stroke-linejoin="round"/>
            <rect x="${cx - 3}" y="${y0 + h - 8.5}" width="6" height="8.5" rx="1" fill="#7d5f3d"/>
            <rect x="${x0 + 3.5}" y="${y0 + 4}" width="5.5" height="5" fill="#f8f2de" stroke="#bfa276" stroke-width="0.8"/>`;
          break;
        }
        case "storage": {
          const w = s * 0.74, h = s * 0.58;
          const x0 = cx - w / 2, y0 = cy - h / 2 + 2;
          const lid = y0 + h * 0.34;
          body = `
            <rect x="${x0}" y="${y0}" width="${w}" height="${h}" rx="2.5" fill="#b28a58" stroke="#7d5f3d" stroke-width="1.4"/>
            <line x1="${x0}" y1="${lid}" x2="${x0 + w}" y2="${lid}" stroke="#7d5f3d" stroke-width="1.3"/>
            <rect x="${cx - 2.4}" y="${lid - 2.4}" width="4.8" height="4.8" rx="1" fill="#e3c26b" stroke="#7d5f3d" stroke-width="0.9"/>`;
          break;
        }
        case "workshop": {
          const w = s * 0.82, h = s * 0.5;
          const x0 = cx - w / 2, y0 = cy - h / 2 + s * 0.1;
          body = `
            <rect x="${x0}" y="${y0}" width="${w}" height="${h}" rx="1.5" fill="#d9d2c2" stroke="#9d9480" stroke-width="1.2"/>
            <polygon points="${x0 - 3},${y0} ${x0 + w * 0.6},${y0 - s * 0.28} ${x0 + w + 3},${y0}" fill="#6d6858" stroke="#57534a" stroke-width="1.1" stroke-linejoin="round"/>
            <rect x="${x0 + w - 9}" y="${y0 - s * 0.26}" width="3.6" height="${s * 0.26}" fill="#8b8270"/>
            <rect x="${x0 + 4}" y="${y0 + 4}" width="6" height="5.5" fill="#e8a34a" stroke="#b47b2e" stroke-width="0.8"/>`;
          break;
        }
        default: {
          const w = s * 0.6, h = s * 0.5;
          body = `<rect x="${cx - w / 2}" y="${cy - h / 2}" width="${w}" height="${h}" rx="2" fill="#c4b591" stroke="#93855f" stroke-width="1.2"/>`;
        }
      }
      if (opts.under) {
        return `<g>
          <rect x="${cx - s / 2 - 2.5}" y="${cy - s / 2 - 1.5}" width="${s + 5}" height="${s + 4}" rx="4"
            fill="rgba(214,196,160,0.35)" stroke="#a08a5f" stroke-width="1.3" stroke-dasharray="5 4"/>
          <g opacity="0.5">${body}</g>
        </g>`;
      }
      return `<g>${body}</g>`;
    }

    function structureIcon(type, size = 22, under = false) {
      return `<svg viewBox="0 0 40 40" width="${size}" height="${size}" aria-hidden="true">${drawStructure(type, 20, 21, 30, { under })}</svg>`;
    }

    function structureName(type) {
      return STRUCTURE_NAMES[type] || String(type || "").replaceAll("_", " ");
    }

    /* ---------- Figures ---------- */
    function agentColor(id) {
      const n = parseInt(String(id).replace("agent-", ""), 10);
      const idx = Number.isFinite(n) && n > 0 ? (n - 1) % AGENT_COLORS.length : 0;
      return AGENT_COLORS[idx];
    }

    function agentFigure(agent, cx, cy, selected) {
      const color = agentColor(agent.id);
      const label = String(agent.id).replace("agent-", "");
      const ring = selected
        ? `<circle cx="${cx}" cy="${cy + 1}" r="13" fill="none" stroke="${color}" stroke-width="2" stroke-dasharray="4 3">
             <animate attributeName="opacity" values="1;0.35;1" dur="1.6s" repeatCount="indefinite"/>
           </circle>`
        : "";
      return `<g>
        ${ring}
        <ellipse cx="${cx}" cy="${cy + 8.5}" rx="6" ry="2" fill="rgba(70,55,30,0.25)"/>
        <rect x="${cx - 4}" y="${cy - 3}" width="8" height="11" rx="4" fill="${color}" stroke="rgba(0,0,0,0.28)" stroke-width="1"/>
        <circle cx="${cx}" cy="${cy - 7}" r="4.3" fill="#f2cda4" stroke="#c9996b" stroke-width="1"/>
        <g transform="translate(${cx},${cy - 16.5})">
          <rect x="-6.5" y="-5" width="13" height="9.5" rx="4.75" fill="#fffdf7" stroke="#d8d0bc" stroke-width="0.9"/>
          <text x="0" y="2.4" text-anchor="middle" font-size="7" font-weight="700" fill="#5b5546" font-family="ui-sans-serif, system-ui, sans-serif">${escapeHtml(label)}</text>
        </g>
      </g>`;
    }

    function graveFigure(cx, cy) {
      return `<g transform="translate(${cx},${cy})" opacity="0.9">
        <ellipse cx="0" cy="6.5" rx="6.5" ry="2" fill="rgba(70,55,30,0.18)"/>
        <path d="M-5 6 L-5 -2 Q-5 -8 0 -8 Q5 -8 5 -2 L5 6 Z" fill="#c5bfae" stroke="#8f897a" stroke-width="1"/>
        <line x1="0" y1="-5.5" x2="0" y2="1.5" stroke="#8f897a" stroke-width="1.2"/>
        <line x1="-2.6" y1="-3.2" x2="2.6" y2="-3.2" stroke="#8f897a" stroke-width="1.2"/>
      </g>`;
    }

    function pileFigure(cx, cy) {
      return `<g transform="translate(${cx},${cy})">
        <path d="M-4.5 4 Q-5.5 -2 -1.5 -3.5 L1.5 -3.5 Q5.5 -2 4.5 4 Q0 6.5 -4.5 4 Z" fill="#cfa66b" stroke="#9e7a45" stroke-width="1"/>
        <path d="M-1.8 -3.5 Q0 -6 1.8 -3.5" fill="none" stroke="#9e7a45" stroke-width="1"/>
      </g>`;
    }

    /* ---------- Map ---------- */
    const STRUCT_OFFSETS = { 1: [[0, 0]], 2: [[-9, 0], [9, 0]], 3: [[-9, -8], [9, -8], [0, 9]], 4: [[-9, -8], [9, -8], [-9, 9], [9, 9]] };
    const AGENT_OFFSETS = { 1: [[0, 2]], 2: [[-9, 2], [9, 2]], 3: [[-9, -4], [9, -4], [0, 10]], 4: [[-9, -4], [9, -4], [-9, 10], [9, 10]] };

    function renderMap(snapshot, force = false) {
      const holder = document.getElementById("map");
      const tiles = snapshot.tiles || [];
      const key = JSON.stringify([
        snapshot.tick,
        selectedTile,
        selectedAgentId,
        tiles.length,
        Object.values(snapshot.agents || {}).map(a => [a.id, a.position, a.alive]),
        Object.keys(snapshot.structures || {}),
        Object.keys(snapshot.item_piles || {}),
      ]);
      if (!force && key === lastMapKey) return;
      lastMapKey = key;

      if (!tiles.length) {
        holder.innerHTML = '<div class="map-empty">No world yet — press Configure Run to launch a simulation.</div>';
        document.getElementById("map-note").textContent = "";
        return;
      }
      const rows = tiles.length, cols = tiles[0].length;
      document.getElementById("map-note").textContent = `${cols}×${rows} tiles · tick ${snapshot.tick ?? 0}`;

      const agentsByPos = {};
      Object.values(snapshot.agents || {}).forEach(agent => {
        const k = `${agent.position.x},${agent.position.y}`;
        (agentsByPos[k] ||= []).push(agent);
      });
      const structuresByPos = {};
      Object.values(snapshot.structures || {}).forEach(structure => {
        const k = `${structure.position.x},${structure.position.y}`;
        (structuresByPos[k] ||= []).push(structure);
      });
      const pilesByPos = {};
      Object.values(snapshot.item_piles || {}).forEach(pile => {
        if (!pile.position) return;
        const k = `${pile.position.x},${pile.position.y}`;
        (pilesByPos[k] ||= []).push(pile);
      });

      let base = "", deco = "", claims = "", structs = "", piles = "", figures = "", labels = "", hits = "";
      for (const tile of tiles.flat()) {
        const tx = tile.x * TILE, ty = tile.y * TILE;
        const fill = pick(TERRAIN_FILLS[tile.terrain] || TERRAIN_FILLS.plains, tile.x, tile.y);
        base += `<rect x="${tx}" y="${ty}" width="${TILE}" height="${TILE}" fill="${fill}" stroke="rgba(70,60,30,0.06)" stroke-width="0.6"/>`;
        const d = tileDecor(tile);
        if (d) deco += `<g transform="translate(${tx},${ty})">${d}</g>`;
        if (tile.claimed_by) {
          claims += `<rect x="${tx + 1.5}" y="${ty + 1.5}" width="${TILE - 3}" height="${TILE - 3}" rx="3" fill="rgba(220,180,90,0.10)" stroke="rgba(154,110,40,0.8)" stroke-width="1.2" stroke-dasharray="5 4"/>`;
        }
        hits += `<rect x="${tx}" y="${ty}" width="${TILE}" height="${TILE}" fill="transparent" data-tx="${tile.x}" data-ty="${tile.y}"/>`;
      }
      Object.entries(structuresByPos).forEach(([k, list]) => {
        const [x, y] = k.split(",").map(Number);
        const offsets = STRUCT_OFFSETS[Math.min(list.length, 4)];
        const size = list.length > 1 ? 19 : 30;
        list.slice(0, 4).forEach((structure, i) => {
          const [ox, oy] = offsets[i];
          structs += drawStructure(structure.type, x * TILE + 20 + ox, y * TILE + 21 + oy, size, {
            under: structure.status === "under_construction",
          });
        });
      });
      Object.entries(pilesByPos).forEach(([k]) => {
        const [x, y] = k.split(",").map(Number);
        piles += pileFigure(x * TILE + 8, y * TILE + 32);
      });
      Object.entries(agentsByPos).forEach(([k, list]) => {
        const [x, y] = k.split(",").map(Number);
        const alive = list.filter(a => a.alive);
        const dead = list.filter(a => !a.alive);
        dead.forEach((agent, i) => {
          figures += graveFigure(x * TILE + 30 - i * 9, y * TILE + 12);
        });
        const offsets = AGENT_OFFSETS[Math.min(alive.length, 4)] || AGENT_OFFSETS[4];
        alive.slice(0, 4).forEach((agent, i) => {
          const [ox, oy] = offsets[i];
          figures += agentFigure(agent, x * TILE + 20 + ox, y * TILE + 18 + oy, agent.id === selectedAgentId);
        });
      });
      for (let x = 0; x < cols; x++) {
        labels += `<text x="${x * TILE + TILE / 2}" y="-5" text-anchor="middle" font-size="7.5" fill="#a89f8a" font-family="ui-monospace, monospace">${x}</text>`;
      }
      for (let y = 0; y < rows; y++) {
        labels += `<text x="-6" y="${y * TILE + TILE / 2 + 2.5}" text-anchor="end" font-size="7.5" fill="#a89f8a" font-family="ui-monospace, monospace">${y}</text>`;
      }
      const sel = selectedTile
        ? `<rect x="${selectedTile.x * TILE + 1}" y="${selectedTile.y * TILE + 1}" width="${TILE - 2}" height="${TILE - 2}" rx="3" fill="none" stroke="#3f6d4e" stroke-width="2.5"/>`
        : "";
      holder.innerHTML = `<svg viewBox="-18 -16 ${cols * TILE + 26} ${rows * TILE + 24}" xmlns="http://www.w3.org/2000/svg">
        ${base}${deco}${claims}${piles}${structs}${figures}${sel}
        <rect id="hover-rect" x="0" y="0" width="${TILE}" height="${TILE}" rx="3" fill="none" stroke="rgba(63,109,78,0.55)" stroke-width="2" visibility="hidden" pointer-events="none"/>
        ${labels}
        <g id="hit-layer">${hits}</g>
      </svg>`;
    }

    function buildLegend() {
      const terrains = [["plains", "#cfe19d"], ["forest", "#aecf87"], ["mountain", "#d9d4c5"], ["water", "#92c6e6"]];
      const structures = ["house", "farm_plot", "well", "storage", "shelter", "workshop"];
      let out = terrains.map(([name, color]) =>
        `<span class="lg"><i class="sw" style="background:${color}"></i>${name}</span>`
      ).join("");
      out += structures.map(type =>
        `<span class="lg">${structureIcon(type, 18)}${structureName(type)}</span>`
      ).join("");
      out += `<span class="lg">${structureIcon("house", 18, true)}under construction</span>`;
      out += `<span class="lg"><svg viewBox="0 0 20 20" width="16" height="16">${graveFigure(10, 11)}</svg>grave</span>`;
      document.getElementById("map-legend").innerHTML = out;
    }

    /* ---------- Tooltip & inspector ---------- */
    function agentsAt(x, y) {
      return Object.values(latestSnapshot.agents || {}).filter(a => a.position.x === x && a.position.y === y);
    }
    function structuresAt(x, y) {
      return Object.values(latestSnapshot.structures || {}).filter(s => s.position.x === x && s.position.y === y);
    }
    function pilesAt(x, y) {
      return Object.values(latestSnapshot.item_piles || {}).filter(p => p.position && p.position.x === x && p.position.y === y);
    }

    function tipContent(x, y) {
      const tiles = latestSnapshot.tiles || [];
      const tile = tiles[y] && tiles[y][x];
      if (!tile) return "";
      const res = Object.entries(tile.resources || {}).filter(([, v]) => v > 0)
        .map(([k, v]) => `<span class="tt-res"><i style="background:${RESOURCE_COLORS[k] || "#999"}"></i>${escapeHtml(k)} ${v}</span>`)
        .join("");
      const structureText = structuresAt(x, y)
        .map(s => escapeHtml(structureName(s.type)) + (s.status === "under_construction" ? " (building)" : ""))
        .join(", ");
      const agentText = agentsAt(x, y).map(a => escapeHtml(a.name) + (a.alive ? "" : " †")).join(", ");
      const pileText = pilesAt(x, y).map(p => `${escapeHtml(p.item)} ×${p.quantity}`).join(", ");
      return `<div class="tt-head">(${x}, ${y}) · ${escapeHtml(tile.terrain)}${tile.claimed_by ? " · claimed" : ""}</div>`
        + (res ? `<div class="tt-row">${res}</div>` : "")
        + (structureText ? `<div class="tt-row">structures: ${structureText}</div>` : "")
        + (agentText ? `<div class="tt-row">agents: ${agentText}</div>` : "")
        + (pileText ? `<div class="tt-row">dropped: ${pileText}</div>` : "")
        + `<div class="tt-foot">click to inspect</div>`;
    }

    function moveHover(x, y) {
      const hover = document.querySelector("#map #hover-rect");
      if (!hover) return;
      hover.setAttribute("x", x * TILE);
      hover.setAttribute("y", y * TILE);
      hover.setAttribute("visibility", "visible");
    }

    function hideTip() {
      document.getElementById("tt").hidden = true;
      const hover = document.querySelector("#map #hover-rect");
      if (hover) hover.setAttribute("visibility", "hidden");
    }

    function showTip(html, cx, cy) {
      const tip = document.getElementById("tt");
      if (!html) { tip.hidden = true; return; }
      tip.innerHTML = html;
      tip.hidden = false;
      const pad = 14;
      const rect = tip.getBoundingClientRect();
      let left = cx + pad, top = cy + pad;
      if (left + rect.width > window.innerWidth - 8) left = cx - rect.width - pad;
      if (top + rect.height > window.innerHeight - 8) top = cy - rect.height - pad;
      tip.style.left = `${Math.max(8, left)}px`;
      tip.style.top = `${Math.max(8, top)}px`;
    }

    function selectTile(x, y) {
      if (selectedTile && selectedTile.x === x && selectedTile.y === y) selectedTile = null;
      else selectedTile = { x, y };
      renderMap(latestSnapshot, true);
      renderInspector();
    }

    function renderInspector() {
      const card = document.getElementById("inspector");
      const tiles = latestSnapshot.tiles || [];
      if (!selectedTile || !tiles.length) { card.hidden = true; return; }
      const { x, y } = selectedTile;
      const tile = tiles[y] && tiles[y][x];
      if (!tile) { card.hidden = true; return; }
      card.hidden = false;
      document.getElementById("inspector-title").textContent = `Tile ${x}, ${y} — ${tile.terrain}`;
      const res = Object.entries(tile.resources || {}).filter(([, v]) => v > 0)
        .map(([k, v]) => `<span class="inv-chip"><i style="background:${RESOURCE_COLORS[k] || "#999"}"></i>${escapeHtml(k)} ${v}</span>`)
        .join("") || '<span class="inv-chip empty">no resources</span>';
      const claim = tile.claimed_by ? `<div class="mini">claimed by ${escapeHtml(tile.claimed_by)}</div>` : "";
      const structureBlocks = structuresAt(x, y).map(s => {
        const status = s.status === "under_construction"
          ? '<span class="badge warn">building</span>'
          : '<span class="badge ok">complete</span>';
        const remaining = s.remaining_inputs && Object.keys(s.remaining_inputs).length
          ? `<div class="mini">still needs ${Object.entries(s.remaining_inputs).map(([k, v]) => `${escapeHtml(k)} ×${v}`).join(", ")}</div>`
          : "";
        const inv = s.inventory && Object.entries(s.inventory).filter(([, v]) => v > 0).map(([k, v]) => `${escapeHtml(k)} ${v}`).join(", ");
        const builders = (s.contributors || []).length > 1
          ? `<div class="mini">built by ${s.contributors.length} agents together</div>`
          : "";
        const fee = s.public_access
          ? `<div class="mini">public access · fee ${Object.entries(s.access_fee || {}).map(([k, v]) => `${escapeHtml(k)} ×${v}`).join(", ") || "free"}</div>`
          : "";
        const shares = Object.entries(s.contributor_shares || {}).length
          ? `<div class="mini">shares ${Object.entries(s.contributor_shares).map(([k, v]) => `${escapeHtml(k)} ${(Number(v) * 100).toFixed(0)}%`).join(", ")}</div>`
          : "";
        const treasury = Object.entries(s.treasury || {}).filter(([, v]) => v > 0)
          .map(([k, v]) => `${escapeHtml(k)} ${v}`).join(", ");
        const operations = s.upkeep_interval
          ? `<div class="mini">${s.active === false ? "inactive" : "active"} · capacity ${s.uses_remaining ?? "—"}/${s.uses_per_tick ?? "—"} · upkeep every ${s.upkeep_interval}t${treasury ? ` · treasury ${treasury}` : ""}</div>`
          : "";
        return `<div class="ins-block">
          <div class="ins-block-head"><span class="ins-icon">${structureIcon(s.type, 26)}</span><b>${escapeHtml(structureName(s.type))}</b>${status}</div>
          <div class="mini">owner ${escapeHtml(s.owner_id || "—")} · durability ${s.durability ?? "—"}</div>
          ${remaining}${inv ? `<div class="mini">stores ${inv}</div>` : ""}${builders}${fee}${shares}${operations}
        </div>`;
      }).join("");
      const agentRows = agentsAt(x, y).map(a => {
        const reserves = a.reserves || a.needs || {};
        return `<div class="ins-agent">
          <span class="card-dot" style="background:${agentColor(a.id)}"></span>
          <b>${escapeHtml(a.name)}</b>${a.alive ? "" : ' <span class="badge warn">deceased</span>'}
          <span class="mini">hp ${a.health} · food ${reserves.food ?? "?"} · water ${reserves.water ?? "?"} · energy ${reserves.energy ?? "?"}</span>
        </div>`;
      }).join("");
      const pileRows = pilesAt(x, y).map(p =>
        `<div class="mini">dropped: ${escapeHtml(p.item)} ×${p.quantity}${p.owner_id ? ` (claimed by ${escapeHtml(p.owner_id)})` : ""}</div>`
      ).join("");
      document.getElementById("inspector-body").innerHTML =
        `<div class="ins-res">${res}</div>${claim}${structureBlocks}${agentRows}${pileRows}`;
    }

    /* ---------- Civilization panel ---------- */
    function renderCiv(summary) {
      const agents = summary.agents || {};
      const chips = [
        [`${agents.living ?? 0}<span class="dim">/${agents.total ?? 0}</span>`, "Population"],
        [summary.median_lifespan ?? 0, "Median lifespan"],
        [summary.groups ?? 0, "Groups"],
        [summary.open_trades ?? 0, "Open trades"],
      ];
      document.getElementById("civ-chips").innerHTML = chips.map(([v, k]) =>
        `<div class="chip"><b>${v}</b><span>${escapeHtml(k)}</span></div>`
      ).join("");
      renderChart(summary.series || {});
      const byType = summary.structures_by_type || {};
      const sites = summary.sites_in_progress ?? 0;
      const types = ["house", "farm_plot", "well", "storage", "shelter", "workshop"];
      let out = types.map(type => {
        const count = byType[type] || 0;
        return `<div class="struct-chip ${count ? "" : "zero"}">${structureIcon(type, 24)}<b>${count}</b><span>${structureName(type)}</span></div>`;
      }).join("");
      out += `<div class="struct-chip ${sites ? "" : "zero"}">${structureIcon("house", 24, true)}<b>${sites}</b><span>in progress</span></div>`;
      document.getElementById("civ-structures").innerHTML = out;
    }

    function renderChart(series) {
      const holder = document.getElementById("civ-chart");
      const legend = document.getElementById("civ-legend");
      const ticks = series.ticks || [];
      if (ticks.length < 2) {
        holder.innerHTML = '<div class="chart-empty">Trends appear as a run progresses.</div>';
        legend.innerHTML = "";
        return;
      }
      const defs = [
        ["population", "Population", "#3f6d4e", true],
        ["structures", "Structures", "#b3593f", false],
        ["trades", "Trades", "#8a6516", false],
        ["messages", "Speech", "#6f4f8f", false],
      ];
      const w = 320, h = 92, p = 8;
      const n = ticks.length;
      const px = i => p + (w - 2 * p) * (i / (n - 1));
      let out = "";
      for (let g = 1; g <= 2; g++) {
        const gy = p + (h - 2 * p) * (g / 3);
        out += `<line x1="${p}" y1="${gy}" x2="${w - p}" y2="${gy}" stroke="#eee7d5" stroke-width="1"/>`;
      }
      out += `<line x1="${p}" y1="${h - p}" x2="${w - p}" y2="${h - p}" stroke="#e0d8c2" stroke-width="1"/>`;
      const legendParts = [];
      defs.forEach(([key, label, color, area]) => {
        const vals = series[key] || [];
        if (vals.length !== n) return;
        const maxVal = Math.max(1, ...vals);
        const py = v => h - p - (h - 2 * p) * (v / maxVal);
        const pts = vals.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(" ");
        if (area) out += `<polygon points="${p},${h - p} ${pts} ${w - p},${h - p}" fill="rgba(63,109,78,0.13)"/>`;
        out += `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>`;
        legendParts.push(`<span class="cl-item"><i style="background:${color}"></i>${label} <b>${vals[n - 1]}</b></span>`);
      });
      holder.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${out}</svg>`;
      legend.innerHTML = legendParts.join("");
    }

    /* ---------- Run status & ticker ---------- */
    async function refresh() {
      try {
        const url = viewTick === null ? "/api/state" : `/api/state?tick=${viewTick}`;
        const response = await fetch(url, { cache: "no-store" });
        const state = await response.json();
        render(state);
      } catch (error) {
        document.getElementById("status-text").textContent = "waiting";
      }
    }

    function render(state) {
      const snapshot = state.snapshot || {};
      latestSnapshot = snapshot;
      latestAgents = snapshot.agents || {};
      latestEvents = state.recent_events || [];
      renderRun(state.run || {}, state.summary || {});
      renderTimeline(state.history || {}, state.run || {});
      renderTicker(state.summary || {});
      renderCiv(state.summary || {});
      renderMap(snapshot);
      renderAgents(latestAgents, snapshot.config || {});
      renderEventFilters(latestEvents, latestAgents);
      renderEvents(latestEvents);
      renderInspector();
    }

    function renderTimeline(history, run) {
      historyRange = history || {};
      const slider = document.getElementById("timeline-slider");
      const label = document.getElementById("timeline-label");
      const liveBtn = document.getElementById("tick-live");
      const backBtn = document.getElementById("tick-back");
      const fwdBtn = document.getElementById("tick-forward");
      const hasHistory = (history.count || 0) > 1;
      slider.disabled = !hasHistory;
      liveBtn.disabled = !hasHistory;
      backBtn.disabled = !hasHistory;
      fwdBtn.disabled = !hasHistory || viewTick === null;
      if (!hasHistory) {
        label.textContent = "no history yet";
        label.className = "timeline-label";
        liveBtn.classList.remove("viewing-history");
        return;
      }
      slider.min = history.min_tick ?? 0;
      slider.max = history.max_tick ?? 0;
      const shown = viewTick === null ? (history.max_tick ?? 0) : viewTick;
      if (document.activeElement !== slider) slider.value = shown;
      if (viewTick === null) {
        label.textContent = `live · tick ${history.live_tick ?? 0}`;
        label.className = "timeline-label";
        liveBtn.classList.remove("viewing-history");
      } else {
        label.textContent = `viewing tick ${viewTick} of ${history.live_tick ?? "?"} — press Live to return`;
        label.className = "timeline-label history";
        liveBtn.classList.add("viewing-history");
      }
    }

    function setViewTick(value) {
      const min = historyRange.min_tick ?? 0;
      const max = historyRange.max_tick ?? 0;
      if (value === null || value >= max) {
        viewTick = null;
      } else {
        viewTick = Math.max(min, Math.min(max, value));
      }
      refresh();
    }

    function renderRun(run, summary = {}) {
      const state = run.state || "idle";
      const running = state === "running";
      const current = Number(run.current_tick || 0);
      const target = Number(run.target_ticks || 0);
      const percent = target > 0 ? Math.max(0, Math.min(100, (current / target) * 100)) : 0;
      const displayTick = running ? current : Number(summary.tick ?? current);

      document.getElementById("tick-readout").textContent = displayTick;
      const pill = document.getElementById("status-pill");
      pill.className = `status-pill ${state}`;
      document.getElementById("status-text").textContent = stateLabel(state, run.stop_requested, run.paused);
      document.getElementById("runline-bar").style.width = running ? `${percent}%` : "0%";

      document.getElementById("run-state-label").textContent = stateLabel(state, run.stop_requested, run.paused);
      const detail = running || state === "completed" || state === "stopped"
        ? `${current}/${target} ticks · ${run.agents || 0} agents · ${run.brain || "survival"}`
        : state === "failed"
          ? run.error || "failed"
          : "no active run";
      document.getElementById("run-state-detail").textContent = detail;
      document.getElementById("progress-bar").style.width = `${percent}%`;

      document.getElementById("start-run").disabled = running;
      document.getElementById("drawer-start").disabled = running;
      document.getElementById("stop-run").disabled = !running;
      const pauseBtn = document.getElementById("pause-run");
      pauseBtn.disabled = !running;
      pauseBtn.textContent = run.paused ? "Resume" : "Pause";
      document.querySelectorAll(".lock").forEach(el => { el.disabled = running; });
      syncModelControl(running);
    }

    function stateLabel(state, stopRequested, paused) {
      if (state === "running" && stopRequested) return "Stopping";
      if (state === "running" && paused) return "Paused";
      return String(state || "idle").replace(/^\w/, char => char.toUpperCase());
    }

    function renderTicker(summary) {
      const agents = summary.agents || {};
      const events = summary.events || {};
      const values = [
        ["Tick", summary.tick ?? 0],
        ["Living", `${agents.living ?? 0}/${agents.total ?? 0}`],
        ["Median life", summary.median_lifespan ?? 0],
        ["Builds", summary.builds ?? 0],
        ["In progress", summary.sites_in_progress ?? 0],
        ["Co-op builds", summary.cooperative_sites ?? 0],
        ["Trades", summary.accepted_trades ?? 0],
        ["LLM errors", summary.llm_failures ?? 0],
        ["Invalid", events.invalid_action ?? 0],
      ];
      document.getElementById("ticker").innerHTML = values.map(([label, value]) =>
        `<div class="stat"><span class="v">${escapeHtml(value)}</span><span class="k">${escapeHtml(label)}</span></div>`
      ).join("");
    }

    /* ---------- Roster ---------- */
    function renderAgents(agents, config = {}) {
      const entries = Object.values(agents).sort((a, b) => a.id.localeCompare(b.id));
      const living = entries.filter(agent => agent.alive).length;
      document.getElementById("agent-count").textContent = entries.length ? `${living}/${entries.length} alive` : "";
      const badge = document.getElementById("dock-agents-badge");
      badge.hidden = !entries.length;
      badge.textContent = living;
      document.getElementById("agents").innerHTML = entries.map(agent => {
        const reserves = agent.reserves || agent.needs || {};
        const inv = Object.entries(agent.inventory || {}).filter(([, v]) => v)
          .map(([k, v]) => `<span class="inv-chip"><i style="background:${RESOURCE_COLORS[k] || "#999"}"></i>${escapeHtml(k)} ${v}</span>`)
          .join("") || '<span class="inv-chip empty">empty-handed</span>';
        const role = agent.specialty ? `<span class="badge ok">${escapeHtml(agent.specialty)}</span>` : "";
        const equipment = Object.entries(agent.equipment_durability || {})
          .map(([item, durability]) => `${escapeHtml(item)} ${durability}`)
          .join(", ");
        return `<article class="card ${agent.alive ? "" : "dead"} ${selectedAgentId === agent.id ? "selected" : ""}" data-agent-id="${escapeHtml(agent.id)}">
          <div class="card-row">
            <span class="card-dot" style="background:${agentColor(agent.id)}"></span>
            <span class="card-name">${escapeHtml(agent.name)}</span>
            ${role}<span class="card-pos">${agent.position.x}, ${agent.position.y}</span>
          </div>
          <div class="card-inv">${inv}<span class="carry">${agent.carry_weight}/${agent.carry_capacity}</span></div>
          ${equipment ? `<div class="mini">equipped durability: ${equipment}</div>` : ""}
          <div class="meters">
            ${meter("health", agent.health, 100)}
            ${meter("food", reserves.food, config.food_reserve_max || 20)}
            ${meter("water", reserves.water, config.water_reserve_max || 20)}
            ${meter("energy", reserves.energy, config.energy_reserve_max || 30)}
          </div>
        </article>`;
      }).join("");
    }

    function meter(label, value, max = 100) {
      const numeric = Number(value || 0);
      const percentage = max > 0 ? Math.round(Math.max(0, Math.min(100, (numeric / max) * 100))) : 0;
      const kind = String(label).split(" ")[0];
      return `<div class="meter meter-${kind}"><span class="ml">${escapeHtml(label)}</span><span class="track"><i style="width:${percentage}%"></i></span><span class="mv">${percentage}%</span></div>`;
    }

    /* ---------- Chronicle ---------- */
    function renderEvents(events) {
      const filters = currentEventFilters();
      const filteredEvents = events.filter(event =>
        (filters.agent === "all" || (event.actor_id || "world") === filters.agent) &&
        eventMatchesTypeFilter(event, filters.type)
      );
      const countText = filteredEvents.length === events.length
        ? `${events.length} recent`
        : `${filteredEvents.length}/${events.length} recent`;
      document.getElementById("event-count").textContent = countText;
      const ordered = filteredEvents.map((event, index) => [event, index])
        .sort((a, b) => ((b[0].tick ?? 0) - (a[0].tick ?? 0)) || (b[1] - a[1]))
        .map(([event]) => event);
      document.getElementById("events").innerHTML = ordered.length
        ? ordered.map(event =>
        `<div class="logline">
          <span class="lt">${escapeHtml(event.tick)}</span>
          <div class="log-main">
            <div class="log-meta">
              <span class="tag ${eventClass(event.type)}">${escapeHtml(eventLabel(event.type))}</span>
              <span class="actor">${escapeHtml(actorName(event.actor_id))}</span>
            </div>
            <div class="msg ${isSpeech(event.type) ? "speech" : ""}">${escapeHtml(event.message || eventFallback(event))}</div>
          </div>
        </div>`
        ).join("")
        : '<div class="empty-note">No matching events</div>';
    }

    function actorName(id) {
      if (!id) return "world";
      return (latestAgents[id] && latestAgents[id].name) || id;
    }

    function isSpeech(type) {
      return ["say", "whisper", "broadcast"].includes(type);
    }

    function renderEventFilters(events, agents) {
      syncSelectOptions(document.getElementById("filter-agent"), eventAgentOptions(events, agents));
      syncSelectOptions(document.getElementById("filter-type"), eventTypeOptions(events));
    }

    function currentEventFilters() {
      return {
        agent: document.getElementById("filter-agent").value || "all",
        type: document.getElementById("filter-type").value || "all",
      };
    }

    function eventAgentOptions(events, agents) {
      const ids = new Set(events.map(event => event.actor_id || "world"));
      const options = [{ value: "all", label: "All agents" }];
      Array.from(ids).sort((a, b) => a.localeCompare(b)).forEach(id => {
        const name = id === "world" ? "World" : agents[id]?.name || id;
        options.push({ value: id, label: name });
      });
      return options;
    }

    function eventTypeOptions(events) {
      const types = Array.from(new Set([
        ...standardActionTypes,
        ...events.map(event => event.type).filter(Boolean),
      ])).sort();
      return [
        { value: "all", label: "All actions" },
        { value: "trade", label: "trade" },
        ...types.map(type => ({ value: type, label: eventLabel(type) })),
      ];
    }

    function eventMatchesTypeFilter(event, typeFilter) {
      if (typeFilter === "all") return true;
      if (typeFilter === "trade") return eventClass(event.type) === "trade";
      return event.type === typeFilter;
    }

    function syncSelectOptions(select, options) {
      const current = select.value || "all";
      const nextValues = options.map(option => option.value).join("|");
      if (select.dataset.values === nextValues) return;
      select.dataset.values = nextValues;
      select.innerHTML = options.map(option =>
        `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`
      ).join("");
      select.value = options.some(option => option.value === current) ? current : "all";
    }

    function eventLabel(type) {
      return String(type || "event").replaceAll("_", " ");
    }

    function eventClass(type) {
      if (type === "invalid_action") return "invalid";
      if (type === "move") return "move";
      if (["gather", "chop", "mine", "harvest", "fish", "farm", "craft", "build", "build_started", "contribute", "maintain_structure", "claim_dividend"].includes(type)) return "resource";
      if (["say", "whisper", "broadcast", "create_group", "invite_member", "join_group", "publish_rule"].includes(type)) return "social";
      if (["offer_trade", "accept_trade", "reject_trade", "expire_trade", "offer_contract", "accept_contract", "repay_contract", "contract_fulfilled", "contract_default", "set_access_fee"].includes(type)) return "trade";
      if (["consume", "wait", "survival_damage", "death"].includes(type)) return "body";
      if (["world_created", "agent_spawned", "run_started", "run_completed", "run_stopped", "run_failed"].includes(type)) return "system";
      return "";
    }

    function eventFallback(event) {
      const actions = event?.data?.actions;
      if (Array.isArray(actions) && actions.length) {
        return `planned ${actions.map(action => action.type || "action").join(", ")}`;
      }
      return "";
    }

    /* ---------- Run control ---------- */
    async function startRun(event) {
      event.preventDefault();
      const payload = {
        brain: document.getElementById("run-brain").value,
        agents: numberValue("run-agents"),
        ticks: numberValue("run-ticks"),
        seed: numberValue("run-seed"),
        model: document.getElementById("run-model").value.trim(),
        reasoning_effort: document.getElementById("run-reasoning").value,
        log_agent_io: document.getElementById("run-io").checked,
        max_workers: numberValue("run-workers"),
        objective_mode: document.getElementById("cfg-objective-mode").value,
        economy_mode: document.getElementById("cfg-economy-mode").value,
        geography_mode: document.getElementById("cfg-geography-mode").value,
        action_points_per_tick: numberValue("cfg-action-points"),
        default_carry_capacity: numberValue("cfg-carry-capacity"),
        storage_capacity: numberValue("cfg-storage-capacity"),
        food_reserve_start: numberValue("cfg-food-start"),
        food_reserve_max: numberValue("cfg-food-max"),
        water_reserve_start: numberValue("cfg-water-start"),
        water_reserve_max: numberValue("cfg-water-max"),
        energy_reserve_start: numberValue("cfg-energy-start"),
        energy_reserve_max: numberValue("cfg-energy-max"),
        survival_food_decay: numberValue("cfg-food-decay"),
        survival_water_decay: numberValue("cfg-water-decay"),
        survival_energy_decay: numberValue("cfg-energy-decay"),
        exhaustion_damage: numberValue("cfg-exhaustion"),
        carried_food_spoil_interval: numberValue("cfg-food-spoil-interval"),
        carried_food_spoil_quantity: numberValue("cfg-food-spoil-qty"),
        resource_base_multiplier: numberValue("cfg-resource-base"),
        starter_resource_radius: numberValue("cfg-starter-radius"),
        wild_food_density: numberValue("cfg-wild-food"),
        wild_fiber_density: numberValue("cfg-wild-fiber"),
        plains_food_regen: numberValue("cfg-plains-food"),
        plains_fiber_regen: numberValue("cfg-plains-fiber"),
        forest_wood_regen: numberValue("cfg-forest-wood"),
        forest_food_regen: numberValue("cfg-forest-food"),
        forest_fiber_regen: numberValue("cfg-forest-fiber"),
        mountain_stone_regen: numberValue("cfg-mountain-stone"),
        mountain_ore_regen: numberValue("cfg-mountain-ore"),
        water_water_regen: numberValue("cfg-water-water"),
        water_food_regen: numberValue("cfg-water-food"),
        farm_food_added: numberValue("cfg-farm-food-added"),
        farm_food_capacity: numberValue("cfg-farm-food-cap"),
        farm_passive_food_growth: numberValue("cfg-farm-passive"),
      };
      document.getElementById("run-state-label").textContent = "Starting";
      const result = await postJSON("/api/run/start", payload);
      if (!result.ok) {
        document.getElementById("run-state-label").textContent = "Start failed";
        document.getElementById("run-state-detail").textContent = result.error || "unknown error";
        return;
      }
      renderRun(result.run || {});
      closeDrawer();
      openWindow("win-run");
      await refresh();
    }

    async function stopRun() {
      document.getElementById("run-state-label").textContent = "Stopping";
      await postJSON("/api/run/stop", {});
      await refresh();
    }

    async function postJSON(path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      return { ...result, ok: response.ok && result.ok !== false };
    }

    function syncModelControl(forceDisabled = false) {
      const brain = document.getElementById("run-brain").value;
      document.getElementById("run-model").disabled = forceDisabled || brain !== "llm";
      document.getElementById("run-reasoning").disabled = forceDisabled || brain !== "llm";
    }

    function numberValue(id) {
      return Number(document.getElementById(id).value);
    }

    /* ---------- Terrain persistence ---------- */
    function loadTerrainConfig() {
      try {
        const stored = window.localStorage.getItem(TERRAIN_STORAGE_KEY);
        if (!stored) return;
        const values = JSON.parse(stored);
        if (!values || typeof values !== "object" || Array.isArray(values)) return;
        document.querySelectorAll(".terrain-input").forEach(input => {
          if (Object.prototype.hasOwnProperty.call(values, input.id)) {
            input.value = String(values[input.id]);
          }
        });
      } catch (error) {
        // Ignore unavailable or malformed browser storage and keep the defaults.
      }
    }

    function saveTerrainConfig() {
      try {
        const values = {};
        document.querySelectorAll(".terrain-input").forEach(input => { values[input.id] = input.value; });
        window.localStorage.setItem(TERRAIN_STORAGE_KEY, JSON.stringify(values));
      } catch (error) {
        // Browser storage is only a convenience; runs still use the visible values.
      }
    }

    function setupTerrainPersistence() {
      loadTerrainConfig();
      document.querySelectorAll(".terrain-input").forEach(input => {
        input.addEventListener("input", saveTerrainConfig);
        input.addEventListener("change", saveTerrainConfig);
      });
    }

    /* ---------- Floating windows ---------- */
    function toggleWindow(id) {
      document.querySelectorAll(".float-win").forEach(win => {
        if (win.id === "inspector") return;
        win.hidden = win.id === id ? !win.hidden : true;
      });
      syncDock();
    }

    function openWindow(id) {
      document.querySelectorAll(".float-win").forEach(win => {
        if (win.id === "inspector") return;
        win.hidden = win.id !== id;
      });
      syncDock();
    }

    function syncDock() {
      document.querySelectorAll(".dock-btn[data-window]").forEach(button => {
        const win = document.getElementById(button.dataset.window);
        button.classList.toggle("active", Boolean(win) && !win.hidden);
      });
    }

    /* ---------- Drawer ---------- */
    function switchDrawerTab(panelId) {
      document.querySelectorAll(".dpanel").forEach(panel => { panel.hidden = panel.id !== panelId; });
      document.querySelectorAll(".dtab").forEach(button => { button.classList.toggle("active", button.dataset.panel === panelId); });
    }

    function openDrawer() {
      toggleWindow(null);
      document.getElementById("drawer").classList.add("open");
      document.getElementById("drawer-backdrop").classList.add("open");
    }

    function closeDrawer() {
      document.getElementById("drawer").classList.remove("open");
      document.getElementById("drawer-backdrop").classList.remove("open");
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
    }

    /* ---------- Wiring ---------- */
    const mapHolder = document.getElementById("map");
    mapHolder.addEventListener("pointermove", event => {
      const target = event.target.closest("[data-tx]");
      if (!target) { hideTip(); return; }
      const x = Number(target.dataset.tx), y = Number(target.dataset.ty);
      moveHover(x, y);
      showTip(tipContent(x, y), event.clientX, event.clientY);
    });
    mapHolder.addEventListener("pointerleave", hideTip);
    mapHolder.addEventListener("click", event => {
      const target = event.target.closest("[data-tx]");
      if (!target) return;
      selectTile(Number(target.dataset.tx), Number(target.dataset.ty));
    });
    document.getElementById("inspector-close").addEventListener("click", () => {
      selectedTile = null;
      renderMap(latestSnapshot, true);
      renderInspector();
    });
    document.querySelectorAll(".dock-btn[data-window]").forEach(button => {
      button.addEventListener("click", () => toggleWindow(button.dataset.window));
    });
    document.querySelectorAll(".win-close").forEach(button => {
      button.addEventListener("click", () => toggleWindow(button.dataset.window));
    });
    document.getElementById("agents").addEventListener("click", event => {
      const card = event.target.closest("[data-agent-id]");
      if (!card) return;
      const id = card.dataset.agentId;
      selectedAgentId = selectedAgentId === id ? null : id;
      const filter = document.getElementById("filter-agent");
      const wanted = selectedAgentId || "all";
      if ([...filter.options].some(option => option.value === wanted)) filter.value = wanted;
      renderEvents(latestEvents);
      renderMap(latestSnapshot, true);
      renderAgents(latestAgents, latestSnapshot.config || {});
    });
    document.getElementById("panel-launch").addEventListener("submit", event => {
      startRun(event).catch(error => {
        document.getElementById("run-state-label").textContent = "Start failed";
        document.getElementById("run-state-detail").textContent = String(error);
      });
    });
    document.getElementById("stop-run").addEventListener("click", () => {
      stopRun().catch(error => {
        document.getElementById("run-state-label").textContent = "Stop failed";
        document.getElementById("run-state-detail").textContent = String(error);
      });
    });
    document.getElementById("pause-run").addEventListener("click", async () => {
      const resuming = document.getElementById("pause-run").textContent === "Resume";
      await postJSON(resuming ? "/api/run/resume" : "/api/run/pause", {});
      await refresh();
    });
    document.getElementById("timeline-slider").addEventListener("input", event => {
      setViewTick(Number(event.target.value));
    });
    document.getElementById("tick-back").addEventListener("click", () => {
      const current = viewTick === null ? (historyRange.max_tick ?? 0) : viewTick;
      setViewTick(current - 1);
    });
    document.getElementById("tick-forward").addEventListener("click", () => {
      if (viewTick !== null) setViewTick(viewTick + 1);
    });
    document.getElementById("tick-live").addEventListener("click", () => setViewTick(null));
    document.getElementById("run-brain").addEventListener("change", () => syncModelControl(false));
    document.querySelectorAll(".dtab").forEach(button => {
      button.addEventListener("click", () => switchDrawerTab(button.dataset.panel));
    });
    document.getElementById("open-drawer").addEventListener("click", openDrawer);
    document.getElementById("close-drawer").addEventListener("click", closeDrawer);
    document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      if (document.getElementById("drawer").classList.contains("open")) {
        closeDrawer();
        return;
      }
      toggleWindow(null);
      selectedTile = null;
      renderMap(latestSnapshot, true);
      renderInspector();
    });
    document.getElementById("filter-agent").addEventListener("change", () => {
      const value = document.getElementById("filter-agent").value;
      selectedAgentId = latestAgents[value] ? value : null;
      renderEvents(latestEvents);
      renderMap(latestSnapshot, true);
      renderAgents(latestAgents, latestSnapshot.config || {});
    });
    document.getElementById("filter-type").addEventListener("change", () => renderEvents(latestEvents));

    buildLegend();
    setupTerrainPersistence();
    syncModelControl(false);
    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""
