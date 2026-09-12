"""Read-only world snapshots for the Laboratory viewer.

Discovery reads managed job manifests, never checkpoints or provider processes.
The demo and managed cells expose the same WorldEngine.snapshot() shape.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

STATIC = Path(__file__).with_name("static")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}\Z")
TERMINAL = {"completed", "failed", "stopped", "invalid", "cancelled"}
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024


class SnapshotUnavailable(ValueError):
    pass


def _read(path: Path, limit: int = MAX_SNAPSHOT_BYTES) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise SnapshotUnavailable("This world is too large to display.")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SnapshotUnavailable("The world snapshot is not ready.")
    return value


def _contained(root: Path, value: str) -> Path:
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise FileNotFoundError("World not found.")
    return path


def _optional(path: Path) -> dict:
    try:
        return _read(path)
    except (OSError, ValueError):
        return {}


def display_snapshot(snapshot: dict) -> dict:
    """Keep native spatial fields and exclude prompts, memories, and diagnostics."""
    config = snapshot.get("config", {})
    width, height = config.get("width"), config.get("height")
    if (type(width) is not int or type(height) is not int
            or not 1 <= width <= 128 or not 1 <= height <= 128):
        raise SnapshotUnavailable("Unsupported world dimensions.")
    tiles = snapshot.get("tiles", [])
    if len(tiles) != height or any(len(row) != width for row in tiles):
        raise SnapshotUnavailable("The world snapshot is incomplete.")
    if not isinstance(snapshot.get("agents"), dict) or not isinstance(snapshot.get("structures"), dict):
        raise SnapshotUnavailable("The world snapshot is incomplete.")
    return {
        "tick": snapshot["tick"], "config": config, "tiles": tiles,
        "agents": {key: {field: value for field, value in agent.items()
                        if field in {"id", "name", "position", "health", "alive", "specialty",
                                     "inventory", "equipped", "needs", "reserves"}}
                   for key, agent in snapshot["agents"].items()},
        "structures": snapshot["structures"], "item_piles": snapshot.get("item_piles", {}),
    }


class WorldViewer:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _job(self, run_id: str) -> tuple[dict, Path]:
        if not IDENTIFIER.fullmatch(run_id):
            raise FileNotFoundError("World not found.")
        path = _contained(self.root, str(self.root / "runs/jobs" / run_id / "job.json"))
        return _read(path), path

    def _meta(self, job: dict, job_path: Path, cell: dict) -> dict:
        heartbeat = _optional(job_path.with_name("controller-heartbeat.json"))
        latest = next((c for c in heartbeat.get("cells", []) if c.get("id") == cell["id"]), {})
        state = latest.get("controller_state") or cell.get("controller_state") or latest.get("state") or "unknown"
        manifest = _optional(_contained(self.root, cell["run_manifest"])) if cell.get("run_manifest") else {}
        if manifest.get("status") in TERMINAL:
            state = manifest["status"]
        elif state != "waiting_quota" and manifest.get("status") not in (None, "running"):
            state = manifest["status"]
        checked = heartbeat.get("checked_at_utc")
        try:
            stale = (datetime.now(timezone.utc) - datetime.fromisoformat(checked.replace("Z", "+00:00"))).total_seconds() > 120
        except (AttributeError, ValueError, TypeError):
            stale = True
        if stale and state not in TERMINAL:
            state = "status_stale"
        return {
            "run_id": job["run_id"], "cell_id": cell["id"],
            "title": job.get("config", {}).get("model", {}).get("id") or job["run_id"],
            "seed": cell.get("seed"), "target_ticks": cell.get("target_ticks"),
            "recipe": job.get("config", {}).get("protocol", ""),
            "state": state, "demo": False, "checked_at": checked,
            "created_at": job.get("created_at_utc", ""),
        }

    def worlds(self) -> dict:
        worlds = []
        archive = _optional(STATIC / "leaderboard-activity-archive.json")
        for job_path in (self.root / "runs/jobs").glob("*/job.json"):
            try:
                job = _read(_contained(self.root, str(job_path)))
                if not IDENTIFIER.fullmatch(job.get("run_id", "")):
                    continue
                archived = archive.get(job["run_id"], {})
                if isinstance(archived, dict) and archived.get("hidden"):
                    continue
                for cell in job.get("cells", []):
                    if not IDENTIFIER.fullmatch(cell.get("id", "")) or not cell.get("snapshot"):
                        continue
                    if _contained(self.root, cell["snapshot"]).is_file():
                        worlds.append(self._meta(job, job_path, cell))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        worlds.sort(key=lambda world: (world["state"] in TERMINAL, -_timestamp(world["created_at"]), world["run_id"], world["cell_id"]))
        return {"worlds": worlds, "refresh_seconds": 30}

    def snapshot(self, run_id: str = "demo", cell_id: str | None = None) -> dict:
        if run_id == "demo":
            result = _read(STATIC / "world-demo.json")
            return {**result, "snapshot": display_snapshot(result["snapshot"])}
        job, job_path = self._job(run_id)
        cells = job.get("cells", [])
        cell = next((c for c in cells if c.get("id") == cell_id), None) if cell_id else next(iter(cells), None)
        if cell is None or not cell.get("snapshot"):
            raise FileNotFoundError("World not found.")
        path = _contained(self.root, cell["snapshot"])
        try:
            snapshot = display_snapshot(_read(path))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SnapshotUnavailable("The next world snapshot is not available yet.") from exc
        return {"world": {**self._meta(job, job_path, cell),
                          "snapshot_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()},
                "snapshot": snapshot, "refresh_seconds": 30}


def _timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, TypeError, ValueError):
        return 0
