"""Read-only retention inventory and verified, portable run evidence exports."""
import hashlib
import json
import shutil
from pathlib import Path

from agent_world.io import atomic_write_json
from agent_world.managed_runs import load_job, _tmux_active


def inventory_job(run_id):
    job = load_job(run_id)
    source = Path(job["source_root"]).resolve()
    catalog = source / "data/run-sources.json"
    catalog_text = catalog.read_text() if catalog.is_file() else ""
    owned = [Path(job["job_dir"])] + [Path(cell["output_dir"]) for cell in job["cells"]]
    sessions = [cell.get("session") for cell in job["cells"]]
    sessions += [(job.get(key) or {}).get("session") for key in ("controller", "finalization_supervisor")]
    active = [session for session in sessions if _tmux_active(session)]
    files = []
    seen = set()
    for directory in owned:
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.is_symlink() or path in seen:
                continue
            if any(part.startswith(".") for part in path.relative_to(directory).parts) or path.suffix not in {".json", ".jsonl", ".md", ".log", ".pkl"}:
                continue
            if any(word in path.name.lower() for word in ("credential", "secret", "token")):
                continue
            seen.add(path)
            try:
                relative = path.resolve().relative_to(source).as_posix()
            except ValueError:
                relative = "external/" + directory.name + "/" + path.relative_to(directory).as_posix()
            files.append({"path": str(path), "export_path": relative, "bytes": path.stat().st_size,
                          "sha256": _digest(path), "trusted_local_pickle": path.suffix == ".pkl"})
    referenced = any(str(directory) in catalog_text or directory.name in catalog_text for directory in owned)
    return {
        "schema_version": 1, "run_id": run_id, "active_sessions": active,
        "catalog_referenced": referenced, "files": files,
        "worktrees": sorted({path for path in [
            *(cell.get("worktree") for cell in job["cells"]),
            (job.get("orchestration_source") or {}).get("worktree"),
        ] if path}),
        "retention": "retain" if active or referenced else "review_after_verified_export",
        "deletion_performed": False,
    }


def _digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def export_job(run_id, destination):
    inventory = inventory_job(run_id)
    if inventory["active_sessions"]:
        raise ValueError("Pause/stop all owned processes before exporting consistent evidence")
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(f"Export destination already exists: {destination}")
    destination.mkdir(parents=True)
    exported = []
    targets = [row["export_path"] for row in inventory["files"]]
    if len(targets) != len(set(targets)):
        raise ValueError("Export paths collide; evidence requires distinct source directories")
    for row in inventory["files"]:
        target = (destination / row["export_path"]).resolve()
        if not target.is_relative_to(destination):
            raise ValueError("Unsafe export path")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row["path"], target)
        if _digest(target) != row["sha256"]:
            raise ValueError("Evidence changed during export; export is incomplete")
        exported.append({key: value for key, value in row.items() if key != "path"})
    manifest = {**inventory, "files": exported, "worktrees": [],
                "portability": "JSON/JSONL are portable; pickle checkpoints require trusted compatible Python source."}
    atomic_write_json(destination / "export-manifest.json", manifest, fsync=True)
    return manifest
