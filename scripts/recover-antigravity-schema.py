#!/usr/bin/env python3
"""Record an explicitly authorized connector migration; then use managed resume.

Requires inactive, paused Antigravity cells. Never changes a checkpoint or the
original launch identity. Migrated evidence requires source provenance review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_world.managed_runs import _job_lock, load_job, cell_status, atomic_write_json, utc_now


def migrate(root, run_id, commit):
    root = root.resolve()
    job = load_job(run_id, root)
    with _job_lock(job["job_dir"]):
        job = load_job(run_id, root)
        if job["config"]["model"]["brain"] != "antigravity":
            raise ValueError("Only the audited Antigravity connector recovery is supported")
        if job.get("source_recoveries"):
            raise ValueError("Recovery already recorded; use managed resume")
        target = subprocess.check_output(["git", "-C", str(root), "rev-parse", commit], text=True).strip()
        for cell in job["cells"]:
            status = cell_status(cell)
            if status["supervisor_active"] or status["state"] != "paused_checkpoint" or status.get("stop_reason") != "decisions_unusable":
                raise ValueError("All cells must be inactive at decisions_unusable checkpoints")
        directory = Path(job["job_dir"]) / "source-recovery"
        directory.mkdir(exist_ok=False)
        shutil.copy2(Path(job["job_dir"]) / "job.json", directory / "job-before.json")
        records = []
        for cell in job["cells"]:
            checkpoint = Path(cell["checkpoint"]).resolve()
            archive = directory / (cell["id"] + "-checkpoint.pkl")
            shutil.copy2(checkpoint, archive)
            events = [json.loads(line) for line in Path(cell["events"]).read_text().splitlines()]
            start = next(e["data"] for e in events if e["type"] == "run_started")
            fingerprint = start["benchmark_code_fingerprint"]
            files = {}
            for file in Path(cell["output_dir"]).glob("*"):
                if file.is_file():
                    files[str(file.resolve())] = hashlib.sha256(file.read_bytes()).hexdigest()
            record = {
                "schema_version": 1, "at_utc": utc_now(), "run_id": run_id,
                "cell_id": cell["id"], "cohort_id": cell["cohort_id"],
                "from_commit": job["launch_commit"], "to_commit": target,
                "protocol": job["protocol"], "recipe_fingerprint_sha256": job.get("recipe_fingerprint_sha256"),
                "model": job["config"]["model"], "seed": cell["seed"],
                "from_fingerprint": fingerprint, "providers": ["antigravity_cli"],
                "checkpoint": str(checkpoint), "checkpoint_archive": str(archive),
                "checkpoint_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "evidence_before_sha256": files,
                "reason": "User-authorized Antigravity native finish/schema-event boundary correction; checkpoints and historical evidence retained.",
                "certification": "requires_source_migration_review",
            }
            record_path = directory / (cell["id"] + ".json")
            atomic_write_json(record_path, record)
            cell["historical_worktree"] = cell.get("worktree")
            cell["worktree"] = None
            cell["execution_commit"] = target
            cell["source_recovery_record"] = str(record_path)
            records.append(str(record_path))
        job["source_recoveries"] = records
        job["orchestrator_commit"] = target
        job["orchestration_source"] = {"cohort_id": run_id + "-schema-recovery-controller", "worktree": None}
        job["analysis_readiness"] = {"status": "needs_provenance_review", "blockers": ["Explicit connector source migration requires review after completion."]}
        atomic_write_json(Path(job["job_dir"]) / "job.json", job)
        print(json.dumps({"run_id": run_id, "records": records, "execution_commit": target}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    migrate(args.root, args.run_id, args.commit)
