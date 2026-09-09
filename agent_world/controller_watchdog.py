"""Token-free recovery of lost controller sessions, owned by the portal service."""
from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from agent_world.managed_runs import _job_lock, _launch_job_controller, _tmux_active
from agent_world.io import atomic_write_json

LOG = logging.getLogger(__name__)
ACTIVE_CELLS = {"running", "waiting_quota", "launching", "resume_scheduled", "stalled_process_reaped"}


def eligible(job):
    # An attention state, deliberate deferral, or completed job needs a different
    # workflow. In particular, a seed waiting behind a failed startup gate is
    # not permission to restart a historical study.
    return (
        (job.get("controller") or {}).get("status") == "running"
        and (job.get("deferral") or {}).get("status") != "deferred"
        and any(c.get("controller_state") in ACTIVE_CELLS
                and not c.get("controller_attention") for c in job.get("cells", []))
    )


def recover_controllers(root, *, now=None):
    """Revive controllers only; their pinned code enforces quota/checkpoint rules.

    Never kill sessions or directly resume cells here. The job lock prevents
    competing portal instances or an explicit resume from creating duplicates.
    """
    now = time.time() if now is None else now
    active = False
    for path in sorted((Path(root) / "runs/jobs").glob("*/job.json")):
        try:
            job = json.loads(path.read_text())
            if not eligible(job):
                continue
            active = True
            if _tmux_active(job["controller"].get("session")):
                continue
            with _job_lock(path.parent):
                job = json.loads(path.read_text())
                if not eligible(job) or _tmux_active(job["controller"].get("session")):
                    continue
                record = path.parent / "controller-recovery.json"
                previous = json.loads(record.read_text()) if record.exists() else {}
                if now < previous.get("retry_at", 0):
                    continue
                attempts = int(previous.get("attempts", 0)) + 1
                # Persist before launch, including a bounded cooldown for failures.
                result = {"attempts": attempts, "attempted_at": now,
                          "retry_at": now + min(1800, 60 * 2 ** min(attempts - 1, 5))}
                atomic_write_json(record, result)
                try:
                    _launch_job_controller(job)
                except Exception as exc:
                    result["error"] = str(exc)
                    # The launcher marks startup failures; retain recovery intent.
                    job["controller"]["status"] = "running"
                    atomic_write_json(path, job)
                    raise
                else:
                    result["recovered_at"] = now
                finally:
                    atomic_write_json(record, result)
        except Exception:
            LOG.exception("Controller recovery failed for %s", path.parent.name)
    return active


if __name__ == "__main__":
    import sys
    print(json.dumps({"active": recover_controllers(Path(sys.argv[1]))}))
