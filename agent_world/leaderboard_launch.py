"""Fixed-recipe benchmark launch queue; only invoked after an explicit page action."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import sqlite3
import subprocess
import sys
import threading
import time

try:
    from .leaderboard_models import model_catalog, for_recipe, recipe_label
    from .leaderboard_supervisor import AstraClient, SupervisorError, MODEL, EFFORT
except ImportError:
    from leaderboard_models import model_catalog, for_recipe, recipe_label
    from leaderboard_supervisor import AstraClient, SupervisorError, MODEL, EFFORT

ACTIVE = {"queued", "launching", "supervising"}
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+\[\]\-]{0,127}\Z")
INFO = """
import json,sys
from agent_world.protocols import get_recipe
from agent_world.managed_runs import _MODEL_BACKED_BRAINS
r=get_recipe(sys.argv[1])
print(json.dumps({'recipe':r.to_dict(),'digest':r.digest,'brains':sorted(_MODEL_BACKED_BRAINS)}))
"""


class LaunchError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                   stderr=subprocess.DEVNULL, timeout=15).strip()


def study_model_identity(model):
    """Tier aliases share duplicate-launch identity, but retain original evidence IDs."""
    if isinstance(model, str) and re.fullmatch(r"(?:meta/)?muse-spark-[0-9.]+(?:-contributor)?", model):
        return model.removeprefix("meta/").removesuffix("-contributor")
    return model


def env():
    return {**os.environ, "PATH": str(Path.home() / ".local/bin") + ":" + os.environ.get("PATH", "")}


def contained(root, value):
    path = Path(value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise LaunchError("Launch source must be retained inside this repository")
    return path


class LaunchService:
    def __init__(self, root, settings=None):
        self.root = Path(root).resolve()
        self.folder = self.root / ".local/leaderboard-launches"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.database = self.folder / "requests.sqlite"
        self.settings_path = self.root / ".local/leaderboard-settings.json"
        self.settings = settings if settings is not None else (
            read(self.settings_path) if self.settings_path.exists() else {})
        self.cache = None
        self.cache_until = 0
        self.lock = threading.Lock()
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL, state TEXT NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL, payload TEXT NOT NULL)""")

    def connection(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def sources(self):
        candidates = []
        jobs = []
        for path in (self.root / "runs/jobs").glob("*/job.json"):
            try:
                job = read(path)
                if job.get("kind") == "benchmark" and job.get("protocol"):
                    jobs.append(job)
            except (OSError, ValueError):
                continue
        jobs.sort(key=lambda j: j.get("created_at_utc", ""), reverse=True)
        for job in jobs:
            for location in [job.get("execution_root")] + [c.get("worktree") for c in job["cells"]]:
                if location:
                    candidates.append((job["protocol"], job.get("recipe_fingerprint_sha256"), location))
        for path in (self.root / "agent_world/recipes").glob("*.json"):
            candidates.append((path.stem, None, str(self.root)))
        result = {}
        checked = set()
        for recipe, expected_digest, location in candidates:
            if (recipe, expected_digest) in checked:
                continue
            try:
                source = contained(self.root, location)
                commit = git(source, "rev-parse", "HEAD")
                # Pinned source must be clean. Do not launch from live edits or
                # relabel a retained recipe using the current branch's settings.
                if git(source, "status", "--porcelain", "--untracked-files=all", "--",
                       "agent_world", "scripts", ".agents", "docs"):
                    continue
                info = json.loads(subprocess.check_output(
                    [sys.executable, "-c", INFO, recipe], cwd=source, text=True,
                    stderr=subprocess.DEVNULL, timeout=20, env=env()))
                if expected_digest and info["digest"] != expected_digest:
                    continue
                identifier = recipe + "@" + info["digest"]
                if identifier in result:
                    checked.add((recipe, expected_digest))
                    continue
                defaults = info["recipe"]["defaults"]
                result[identifier] = {
                    "id": identifier, "recipe_id": recipe, "digest": info["digest"],
                    "source": str(source), "commit": commit, "brains": info["brains"],
                    "defaults": defaults,
                    "seeds": info["recipe"]["replications"]["required_seeds"],
                }
                checked.add((recipe, expected_digest))
            except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError):
                continue
        return result

    def catalog(self, force=False):
        with self.lock:
            if force or self.cache is None or time.monotonic() > self.cache_until:
                sources = self.sources()
                blocker = None
                models, warnings = [], []
                binary = self.settings.get("supervisor_binary")
                if not self.settings.get("launch_enabled"):
                    blocker = "Benchmark launches have not been enabled on this host."
                elif not self.settings.get("monitor_thread_id"):
                    blocker = "The shared Run Monitoring task is not configured."
                elif not binary or not Path(binary).is_file():
                    blocker = "The Astra supervisor runtime is not configured."
                elif not shutil.which("tmux", path=env()["PATH"]):
                    blocker = "The detached run supervisor is unavailable."
                else:
                    client = None
                    try:
                        client = AstraClient(binary, self.root)
                        client.verify()
                        models, warnings = model_catalog(sources, client, env())
                    except (OSError, RuntimeError) as exc:
                        blocker = str(exc)
                    finally:
                        if client:
                            client.close()
                if not models:
                    models, warnings = model_catalog(sources, environment=env())
                self.cache = {"sources": sources, "blocker": blocker, "models": models, "warnings": warnings}
                self.cache_until = time.monotonic() + 60
            return self.cache

    def public_options(self):
        c = self.catalog()
        return {
            "enabled": not c["blocker"], "blocker": c["blocker"],
            "supervisor": {"model": MODEL, "effort": EFFORT},
            "warnings": c.get("warnings", []),
            "recipes": [{**{k: v for k, v in s.items() if k not in {"source", "models"}},
                         "title": recipe_label(s["recipe_id"]),
                         "models": [{k: v for k, v in m.items() if k not in {"model", "variants", "efforts"}}
                                    for m in for_recipe(c.get("models", []), s)]}
                        for s in c["sources"].values()],
        }

    def get(self, identifier):
        with self.connection() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise LaunchError("Launch request not found")
        return {**json.loads(row["payload"]), "id": row["id"], "state": row["state"]}

    def update(self, identifier, **changes):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM requests WHERE id=?", (identifier,)).fetchone()
            payload = json.loads(row["payload"])
            state = changes.pop("state", row["state"])
            payload.update(changes)
            payload["updated_at"] = now()
            db.execute("UPDATE requests SET state=?,updated=?,payload=? WHERE id=?",
                       (state, time.time(), json.dumps(payload), identifier))

    def public_request(self, request):
        request = {**request, "can_reconnect": request.get("state") == "needs_attention" and
                   (self.root / "runs/jobs" / request["run_id"] / "job.json").exists()}
        return {k: v for k, v in request.items() if k in {
            "id", "run_id", "state", "recipe_id", "recipe_title", "model", "model_name", "lab", "brain", "seeds", "defaults",
            "commit", "created_at", "updated_at", "error", "supervisor_thread_id",
            "supervisor_state", "supervisor_message", "supervisor_model", "supervisor_effort", "can_reconnect",
            "monitor_reviewed", "monitor_resolution", "monitor_resolution_reason",
        }}

    def monitoring_worklist(self):
        with self.connection() as db:
            rows = db.execute("SELECT id FROM requests WHERE state != 'review' ORDER BY created").fetchall()
        work = []
        for row in rows:
            request = self.get(row["id"])
            if request.get("monitor_reviewed"):
                continue
            path = self.root / "runs/jobs" / request["run_id"] / "job.json"
            job = read(path) if path.exists() else {}
            work.append({"request_id": request["id"], "run_id": request["run_id"],
                         "model": request["model"], "recipe": request["recipe_id"],
                         "source": request["source"], "state": request["state"],
                         "error": request.get("error"), "job_path": str(path),
                         "controller_status": (job.get("controller") or {}).get("status"),
                         "readiness": job.get("analysis_readiness"),
                         "cells": [{k: c.get(k) for k in ["id", "controller_state", "controller_attention"]}
                                   for c in job.get("cells", [])]})
        return work

    def monitoring_ack(self, identifier, resolution=None, reason=None):
        request = self.get(identifier)
        path = self.root / "runs/jobs" / request["run_id"] / "job.json"
        job = read(path) if path.exists() else {}
        status = (job.get("controller") or {}).get("status")
        if status not in {"completed", "completed_with_blockers", "needs_attention", "failed", "stopped", "cancelled"} and request["state"] != "needs_attention":
            raise LaunchError("A healthy active run cannot leave the monitoring worklist")
        ready = status == "completed" and (job.get("analysis_readiness") or {}).get("status") == "ready"
        if not ready and (resolution not in {"external_blocker", "evidence_decision"} or not reason or not reason.strip()):
            raise LaunchError("Repairable faults stay on the worklist; an unresolved handoff requires a named external blocker or evidence decision")
        self.update(identifier, monitor_reviewed=True, state="completed" if ready else "needs_attention",
                    monitor_resolution="verified_complete" if ready else resolution,
                    monitor_resolution_reason=reason)

    def recent(self):
        with self.connection() as db:
            rows = db.execute("SELECT id FROM requests WHERE state != 'review' ORDER BY created DESC LIMIT 20").fetchall()
        result = []
        for row in rows:
            request = self.get(row["id"])
            if request["state"] in {"queued", "launching"} and not self.alive(request):
                request["supervisor_state"] = "reconnecting"
            result.append(self.public_request(request))
        return result

    def launch_checkout(self, source):
        # A linked worktree shares the main checkout's HEAD for _canonical_root
        # operations in historical managers. An independent local source clone
        # keeps both launch_commit and orchestrator_commit pinned without editing
        # historical code. The managed manager still owns all cell worktrees.
        target = self.root / ".local/leaderboard-sources" / source["commit"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            if not (target / ".git").exists():
                subprocess.run(["git", "-c", "core.autocrlf=false", "clone", "--shared",
                                "--no-checkout", str(self.root), str(target)],
                               check=True, capture_output=True, timeout=60)
                subprocess.run(["git", "-C", str(target), "-c", "core.autocrlf=false",
                                "checkout", "--detach", source["commit"]],
                               check=True, capture_output=True, timeout=60)
            if git(target, "rev-parse", "HEAD") != source["commit"]:
                raise LaunchError("Pinned launch checkout changed")
            for name in ("jobs", "managed"):
                shared = self.root / "runs" / name
                shared.mkdir(parents=True, exist_ok=True)
                link = target / "runs" / name
                link.parent.mkdir(parents=True, exist_ok=True)
                if not link.exists() and not link.is_symlink():
                    link.symlink_to(shared, target_is_directory=True)
                if link.resolve() != shared.resolve():
                    raise LaunchError("Pinned launch checkout has a conflicting run registry")
            dotenv = target / ".env"
            if (self.root / ".env").is_file() and not dotenv.exists():
                dotenv.symlink_to(self.root / ".env")
        return target

    def preview(self, values):
        selected = None
        if set(values) == {"recipe", "model_key"}:
            catalog = self.catalog()
            source = catalog["sources"].get(values["recipe"])
            if not source:
                raise LaunchError("This recipe has no clean retained launch source")
            selected = next((m for m in for_recipe(catalog.get("models", []), source)
                             if m["key"] == values["model_key"]), None)
            if not selected:
                raise LaunchError("This model is unavailable for the selected recipe. Refresh the catalog.")
            values = {"recipe": values["recipe"], "brain": selected["brain"], "model": selected["model"]}
        if set(values) != {"recipe", "brain", "model"}:
            raise LaunchError("Choose a recipe, connector, and exact model ID")
        catalog = self.catalog()
        if catalog["blocker"]:
            raise LaunchError(catalog["blocker"])
        source = catalog["sources"].get(values["recipe"])
        if not source:
            raise LaunchError("This recipe has no clean retained launch source")
        brain, model = values["brain"], values["model"]
        if brain not in source["brains"] or not isinstance(model, str) or not MODEL_ID.fullmatch(model):
            raise LaunchError("Invalid connector or model ID")
        origin_source = source["source"]
        source = {**source, "source": str(self.launch_checkout(source))}
        token = secrets.token_hex(16)
        run_id = "web-" + re.sub(r"[^a-z0-9]+", "-", model.lower())[:42].strip("-") + "-" + token[:12]
        request_dir = self.folder / token
        request_dir.mkdir()
        config = {
            "schema_version": 1, "run_id": run_id, "kind": "benchmark",
            "protocol": source["recipe_id"], "model": {
                "brain": brain, "id": model, "reasoning_effort": source["defaults"]["reasoning_effort"],
            }, "seeds": source["seeds"], "source": {"commit": source["commit"]},
        }
        config_path = request_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2))
        # The existing managed CLI validates fixed recipe conditions without
        # model calls or detached processes.
        command = [sys.executable, "-m", "agent_world.cli", "run", "--config", str(config_path), "--dry-run"]
        try:
            checked = subprocess.run(command, cwd=source["source"], env=env(), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
            plan = json.loads(checked.stdout)
            if plan["launch_commit"] != source["commit"] or plan["orchestrator_commit"] != source["commit"]:
                raise LaunchError("Managed launcher did not preserve the reviewed source commits")
        except subprocess.CalledProcessError as exc:
            raise LaunchError("Managed launch validation failed: " + exc.stderr[-800:])
        except subprocess.TimeoutExpired:
            raise LaunchError("Managed launch validation timed out")
        request = {
            "run_id": run_id, "recipe_id": source["recipe_id"], "recipe_key": source["id"],
            "digest": source["digest"], "source": source["source"], "origin_source": origin_source, "commit": source["commit"],
            "brain": brain, "model": model, "model_name": selected["name"] if selected else model,
            "lab": selected["lab"] if selected else "unknown", "recipe_title": recipe_label(source["recipe_id"]),
            "seeds": source["seeds"], "defaults": source["defaults"],
            "config_path": str(config_path), "config_hash": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "created_at": now(), "updated_at": now(), "supervisor_model": MODEL,
            "supervisor_effort": EFFORT, "supervisor_state": "pending",
            "session": "aw-web-" + token, "supervisor_thread_id": None,
        }
        with self.connection() as db:
            db.execute("INSERT INTO requests VALUES (?,?,?,?,?,?)",
                       (token, run_id, "review", time.time(), time.time(), json.dumps(request)))
        return self.public_request({**request, "id": token, "state": "review"})

    def start(self, values, dispatch=True):
        if set(values) != {"request_id"}:
            raise LaunchError("Submit the reviewed launch request")
        identifier = values["request_id"]
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM requests WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise LaunchError("Review this benchmark before starting it")
            request = json.loads(row["payload"])
            if row["state"] != "review":
                return self.public_request(self.get(identifier))
            if time.time() - row["created"] > 600:
                raise LaunchError("This review expired. Review the current settings again.")
            for other in db.execute("SELECT payload FROM requests WHERE state IN ('queued','launching','supervising')"):
                p = json.loads(other["payload"])
                if (p["recipe_key"], p["brain"], study_model_identity(p["model"])) == (request["recipe_key"], request["brain"], study_model_identity(request["model"])):
                    raise LaunchError("This model already has an active launch in this recipe: " + p["run_id"])
            for path in (self.root / "runs/jobs").glob("*/job.json"):
                try:
                    job = read(path)
                    model = job.get("config", {}).get("model", {})
                    same = (job.get("protocol"), model.get("brain"), study_model_identity(model.get("id"))) == (
                        request["recipe_id"], request["brain"], study_model_identity(request["model"]))
                    if same and job.get("controller", {}).get("status") not in {
                        "completed", "completed_with_blockers", "failed", "stopped", "cancelled"
                    }:
                        raise LaunchError("This model already has an unfinished study: " + job["run_id"])
                except (OSError, json.JSONDecodeError):
                    continue
            self.validate_source(request)
            db.execute("UPDATE requests SET state='queued',updated=? WHERE id=?", (time.time(), identifier))
        if dispatch:
            self.ensure_worker(identifier)
        return self.public_request(self.get(identifier))

    def start_batch(self, values):
        identifiers = values.get("request_ids")
        if (set(values) != {"request_ids"} or not isinstance(identifiers, list)
                or not 1 <= len(identifiers) <= 20
                or any(not isinstance(i, str) for i in identifiers)
                or len(set(identifiers)) != len(identifiers)):
            raise LaunchError("Submit up to 20 distinct reviewed requests")
        results = []
        # Hold review members so a running dispatcher cannot pick up half a batch.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for identifier in identifiers:
                row = db.execute("SELECT state,payload FROM requests WHERE id=?", (identifier,)).fetchone()
                if row and row["state"] == "review":
                    payload = json.loads(row["payload"])
                    payload["dispatch_ready"] = False
                    db.execute("UPDATE requests SET payload=? WHERE id=?", (json.dumps(payload), identifier))
        # Do not dispatch until all members have been accepted/rejected.
        # A singleton dispatcher sends one assignment for the accepted batch.
        for identifier in identifiers:
            try:
                request = self.start({"request_id": identifier}, dispatch=False)
                results.append({"id": identifier, "request": request})
            except LaunchError as exc:
                results.append({"id": identifier, "error": str(exc)})
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for result in results:
                if result.get("request"):
                    row = db.execute("SELECT payload FROM requests WHERE id=?", (result["id"],)).fetchone()
                    payload = json.loads(row["payload"])
                    payload["dispatch_ready"] = True
                    db.execute("UPDATE requests SET payload=? WHERE id=?", (json.dumps(payload), result["id"]))
        if any(r.get("request", {}).get("state") == "queued" for r in results):
            self.ensure_worker(identifiers[0])
        return {"results": results}

    def reconnect(self, values):
        if set(values) != {"request_id"}:
            raise LaunchError("Choose an existing supervisor request")
        identifier = values["request_id"]
        request = self.get(identifier)
        if request["state"] in ACTIVE:
            return self.public_request(request)
        if request["state"] != "needs_attention" or not (
            self.root / "runs/jobs" / request["run_id"] / "job.json"
        ).exists():
            raise LaunchError("No existing run needs a supervisor reconnection")
        self.update(identifier, state="queued", last_event_signature=None, monitor_reviewed=False, error=None)
        self.ensure_worker(identifier)
        return self.public_request(self.get(identifier))

    def validate_source(self, request):
        source = contained(self.root, request["source"])
        if git(source, "rev-parse", "HEAD") != request["commit"]:
            raise LaunchError("Launch source changed; review the benchmark again")
        if git(source, "status", "--porcelain", "--untracked-files=all", "--",
               "agent_world", "scripts", ".agents", "docs"):
            raise LaunchError("Launch source has uncommitted changes")
        config = contained(self.root, request["config_path"])
        if hashlib.sha256(config.read_bytes()).hexdigest() != request["config_hash"]:
            raise LaunchError("Reviewed launch configuration changed")

    def alive(self, request=None):
        return subprocess.run(["tmux", "has-session", "-t", "aw-leaderboard-dispatch"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env()).returncode == 0

    def ensure_worker(self, identifier=None):
        if self.alive():
            return
        log = self.folder / "dispatcher.log"
        command = shlex.join([sys.executable, str(Path(__file__).resolve()), "worker",
                             "--root", str(self.root)])
        result = subprocess.run(["tmux", "new-session", "-d", "-s", "aw-leaderboard-dispatch",
                                 "-c", str(self.root), "exec " + command + " >> " + shlex.quote(str(log)) + " 2>&1"],
                                capture_output=True, text=True, env=env())
        if result.returncode and not self.alive():
            raise LaunchError("Could not start the detached launch dispatcher")

    def recover(self):
        with self.connection() as db:
            rows = db.execute("SELECT id FROM requests WHERE state IN ('queued','launching')").fetchall()
        if rows:
            self.ensure_worker()

    def recovery_loop(self):
        while True:
            self.recover()
            time.sleep(30)


def assignment_prompt(requests):
    return (
        "Consolidated leaderboard handoff to this existing Run Monitoring task. "
        "You are GPT-6 Astra at low effort for ALL runs below, alongside your existing worklist. "
        "The deterministic dispatcher owns initial launch after this acknowledgment; do not launch anything yourself. "
        "Acknowledge this batch briefly in one response, without tool calls, polling, or a separate per-model task. "
        "Your existing monitoring heartbeat discovers these requests from "
        ".local/leaderboard-launches/requests.sqlite. Controllers own startup gates, healthy progress, quota waits, "
        "bounded checkpoint recovery and finalization. Do not repeat these instructions on routine transitions. "
        "After launch, attention means you own diagnosis, scoped connector/infrastructure repair, validation, "
        "and managed resumption of the existing checkpoint. Do not stop at diagnosis for a repairable fault. "
        "Record any required source migration; never silently edit pinned source or weaken integrity guards. "
        "Keep repairable faults on the worklist; escalate only a concrete user/external/evidence dependency. "
        "At attention or completion follow each run's pinned benchmark skill and recipe, preserve provenance, "
        "never restart to evade quota, and do not admit results to the leaderboard. "
        "Only meaningful blockers or verified completion warrant an update. Batch:\n" +
        json.dumps([{k: r.get(k) for k in ["run_id", "model", "brain", "recipe_id", "seeds", "defaults",
                                          "source", "commit", "config_path"]} for r in requests])
    )


def dispatch_once(service):
    with service.connection() as db:
        rows = db.execute("SELECT id FROM requests WHERE state IN ('queued','launching') ORDER BY created").fetchall()
    requests = [service.get(row["id"]) for row in rows]
    requests = [r for r in requests if r.get("dispatch_ready", True)]
    if not requests:
        return False
    thread = service.settings.get("monitor_thread_id")
    if not thread:
        raise LaunchError("The shared Run Monitoring task is not configured")
    client = None
    try:
        pending = [r for r in requests if not r.get("assignment_ready")]
        # If the process died during an acknowledged turn, do not send it again.
        ambiguous = [r for r in pending if r.get("supervisor_turn_id")]
        for r in ambiguous:
            service.update(r["id"], state="needs_attention",
                           error="Monitoring handoff was interrupted; inspect Run Monitoring before retrying.")
        requests = [r for r in requests if r not in ambiguous]
        pending = [r for r in pending if r not in ambiguous]
        if pending:
            client = AstraClient(service.settings["supervisor_binary"], service.root)
            client.verify()
            state = client.rpc("thread/read", {"threadId": thread, "includeTurns": True})
            if any(t.get("status") == "inProgress" for t in state.get("thread", {}).get("turns", [])):
                return True  # Leave queued; never overlap an existing monitoring turn.
            client.attach(thread)
            for r in pending:
                service.validate_source(r)
                service.update(r["id"], supervisor_thread_id=thread, supervisor_state="assigning")
            def update_all(changes):
                for r in pending:
                    service.update(r["id"], **changes)
            client.turn(thread, assignment_prompt(pending), update_all)
            for r in pending:
                service.update(r["id"], assignment_ready=True, supervisor_state="watching")
        for original in requests:
            request = service.get(original["id"])
            job_path = service.root / "runs/jobs" / request["run_id"] / "job.json"
            try:
                if not job_path.exists():
                    service.validate_source(request)
                    service.update(request["id"], state="launching")
                    subprocess.run([sys.executable, "-m", "agent_world.cli", "run", "--config",
                                    request["config_path"]], cwd=request["source"], env=env(), check=True, timeout=180)
                service.update(request["id"], state="supervising", supervisor_thread_id=thread,
                               supervisor_state="watching", error=None)
            except Exception as exc:
                service.update(request["id"], state="needs_attention", supervisor_thread_id=thread,
                               error=str(exc)[-1000:])
        return True
    except Exception as exc:
        for r in requests:
            service.update(r["id"], state="needs_attention", supervisor_state="needs_attention",
                           error=str(exc)[-1000:])
        return True
    finally:
        if client:
            client.close()


def worker(root, identifier=None):
    # One durable dispatcher serializes consolidated handoffs. It never watches
    # healthy runs or opens a new Codex task. The existing heartbeat owns monitoring.
    service = LaunchService(root)
    while True:
        dispatch_once(service)
        time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["worker", "monitor-list", "monitor-ack"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--request")
    parser.add_argument("--resolution", choices=["external_blocker", "evidence_decision"])
    parser.add_argument("--reason")
    args = parser.parse_args()
    if args.command == "worker":
        worker(args.root, args.request)
    elif args.command == "monitor-list":
        print(json.dumps(LaunchService(args.root).monitoring_worklist(), indent=2))
    else:
        LaunchService(args.root).monitoring_ack(args.request, args.resolution, args.reason)
