"""The observer is a client of durable managed jobs for model-backed runs."""
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from agent_world.io import atomic_write_json


def read_control(path: Path) -> str:
    try:
        return str(json.loads(path.read_text()).get("action", "run"))
    except FileNotFoundError:
        return "run"


def stop_requested(events_path: Path | None) -> bool:
    if events_path is None:
        return False
    path = events_path.parent / "operator-control.json"
    while read_control(path) == "pause":
        time.sleep(0.2)
    return read_control(path) == "stop"


class ManagedObserverClient:
    def __init__(self, snapshot_path: Path, events_path: Path):
        self.pointer = events_path.with_name(events_path.stem + "-managed-selection.json")
        self.selection = None
        if self.pointer.is_file():
            self.selection = json.loads(self.pointer.read_text())

    def clear(self):
        self.selection = None
        self.pointer.unlink(missing_ok=True)

    def paths(self):
        return (Path(self.selection["snapshot"]), Path(self.selection["events"]))

    def status(self):
        from agent_world.managed_runs import job_status
        status = job_status(self.selection["run_id"])
        cell = status["cells"][0]
        control = read_control(Path(self.selection["events"]).parent / "operator-control.json")
        return {
            **self.selection["display"],
            "state": cell["state"], "current_tick": cell.get("tick") or 0,
            "paused": control == "pause", "stop_requested": control == "stop",
            "error": cell.get("controller_attention") or "",
            "managed_run_id": self.selection["run_id"],
        }

    def start(self, config):
        from agent_world.managed_runs import launch_config
        run_id = "observer-" + uuid.uuid4().hex
        payload = {
            "schema_version": 1, "run_id": run_id, "kind": "experiment",
            "question": "Interactive world experiment configured in the observer.",
            "model": {"brain": config.brain, "id": config.model, "reasoning_effort": config.reasoning_effort},
            "seeds": [config.world_config.seed],
            "world": {"overrides": asdict(config.world_config)},
            "runtime": {"ticks": config.ticks, "agents": config.agents, "max_workers": config.max_workers},
            "harness": {"connector_profile": config.connector_profile,
                        "conversation_mode": config.conversation_mode, "session_max_turns": config.session_max_turns,
                        "no_agent_io_log": not config.log_agent_io},
        }
        config_path = self.pointer.parent / (run_id + ".json")
        atomic_write_json(config_path, payload, fsync=True)
        job = launch_config(config_path)
        cell = job["cells"][0]
        self.selection = {"run_id": run_id, "snapshot": cell["snapshot"], "events": cell["events"],
                          "display": {"target_ticks": config.ticks, "agents": config.agents,
                                      "brain": config.brain, "seed": config.world_config.seed,
                                      "model": config.model, "reasoning_effort": config.reasoning_effort,
                                      "started_at": time.time(), "config": config.public_dict()}}
        atomic_write_json(self.pointer, self.selection, fsync=True)
        return 202, {"ok": True, "run": self.status()}

    def control(self, action):
        from agent_world.managed_runs import resume_job
        atomic_write_json(Path(self.selection["events"]).parent / "operator-control.json",
                          {"action": action}, fsync=True)
        if action == "run" and self.status()["state"] in {"interrupted", "paused_checkpoint", "stopped", "failed"}:
            resume_job(self.selection["run_id"])
        return 202, {"ok": True, "run": self.status()}
