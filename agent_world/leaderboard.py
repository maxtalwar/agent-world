"""Automatically refreshed leaderboards and fixed-recipe benchmark launches.

Run with python -m agent_world.leaderboard --root /path/to/agent-world.
Benchmark launches require a reviewed configuration and same-origin page action.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

try:
    from .leaderboard_launch import LaunchService, LaunchError
    from .benchmark_acceptance import accepted_report
    from .gemini_pricing import historical_cost
    from .astra_pricing import historical_cost as astra_historical_cost
    from .world_viewer import WorldViewer, SnapshotUnavailable
    from .capability_reanalysis import policies as scoring_policies, rescore, formula as reanalysis_formula
except ImportError:
    from leaderboard_launch import LaunchService, LaunchError
    from benchmark_acceptance import accepted_report
    from gemini_pricing import historical_cost
    from astra_pricing import historical_cost as astra_historical_cost
    from world_viewer import WorldViewer, SnapshotUnavailable
    from capability_reanalysis import policies as scoring_policies, rescore, formula as reanalysis_formula

LOG = logging.getLogger(__name__)
STATIC = Path(__file__).with_name("static")
# Model identity determines the lab, never the harness/provider transport.
LABS = {
    "openai": ("OpenAI", r"gpt|chatgpt|codex|o[134](?:$|[-.])"),
    "anthropic": ("Anthropic", r"anthropic|claude|opus|sonnet|haiku|fable"),
    "meta": ("Meta", r"meta|llama|muse"),
    "xai": ("xAI", r"xai|x-ai|grok"),
    "alibabacloud": ("Alibaba Cloud", r"alibaba|qwen|qwq"),
    "google": ("Google", r"google|gemini|gemma"),
    "deepseek": ("DeepSeek", r"deepseek"),
    "zai": ("Z.ai", r"z-ai|zai|zhipu|glm|chatglm"),
    "mistral": ("Mistral AI", r"mistral|mixtral|magistral|devstral|codestral"),
    "moonshot": ("Moonshot AI", r"moonshot|kimi"),
    "cohere": ("Cohere", r"cohere|command-r|command-a"),
    "minimax": ("MiniMax", r"minimax"),
}


def quota_schedule(path: Path) -> dict:
    """Read recent quota timing without loading a simulation's entire event log."""
    try:
        with path.open("rb") as handle:
            start = max(0, path.stat().st_size - 256 * 1024)
            handle.seek(start)
            if start:
                handle.readline()
            lines = handle.read().splitlines()
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if event.get("type") in {"run_quota_retry", "run_completed", "run_failed", "run_stopped"}:
                return {}
            if event.get("type") != "run_quota_wait":
                continue
            data = event.get("data") or {}
            retry = data.get("resume_at_unix")
            retry_at = None
            if isinstance(retry, (int, float)) and not isinstance(retry, bool):
                try:
                    retry_at = datetime.fromtimestamp(retry, timezone.utc).isoformat()
                except (ValueError, OverflowError, OSError):
                    pass
            return {"retry_at": retry_at, "reset_at": data.get("provider_reset_at_utc")}
    except OSError:
        pass
    return {}


def model_lab(model: str) -> dict:
    for key, (name, pattern) in LABS.items():
        if re.search(r"(?:^|[/ :_-])(?:" + pattern + r")", model.lower()):
            return {"id": key, "name": name}
    return {"id": "unknown", "name": "Lab unspecified"}

CLASSIC_COLUMNS = [
    ["sustained_competence", "Competence"],
    ["effective_execution", "Execution"],
    ["entrepreneurial_agency", "Entrepreneurship"],
]

# Run the existing aggregator in the retained source checkout. Never import a
# different recipe's scoring implementation into the dashboard process.
AGGREGATE_SCRIPT = """
import json, sys
from agent_world.benchmarks import aggregate_benchmark_reports
from agent_world.protocols import get_recipe
p = json.load(sys.stdin)
recipe = get_recipe(p['recipe'])
if p['digest'] and recipe.digest != p['digest']:
    raise ValueError('Frozen recipe fingerprint mismatch')
reports = p['reports']
for r in reports:
    protocol = r['benchmarks']['protocol']
    if protocol['id'] != recipe.id:
        raise ValueError('Mixed recipes')
    if protocol.get('recipe_fingerprint_sha256') not in (None, recipe.digest):
        raise ValueError('Report recipe fingerprint mismatch')
print(json.dumps(aggregate_benchmark_reports(reports, recipe.id)))
"""


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def within(root: Path, value: str) -> Path:
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Evidence path is outside the repository")
    return path


def model_label(model: str) -> str:
    display_model = re.sub(r"-20\d{6}$", "", model) if model.startswith("claude-") else model
    if display_model.lower().startswith("gemini-"):
        display_model = re.sub(r"-(?:low|medium|high|max)$", "", display_model, flags=re.IGNORECASE)
    name = re.sub(r"(?<=\d)-(?=\d)", ".", display_model.removeprefix("claude-"))
    return name.replace("-", " ").title().replace("Gpt ", "GPT-").replace("Glm", "GLM")


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def board_title(recipe: str) -> str:
    return "v8.1" if recipe == "participant-v8-revised" else recipe.replace("participant-", "").replace("-", " ")


def new_board(recipe: str, digest: str = "") -> dict:
    return {
        "id": recipe + ("@" + digest if digest else ""),
        "recipe": recipe, "digest": digest, "title": board_title(recipe),
        "columns": CLASSIC_COLUMNS, "rows": [], "runs": [], "warnings": [],
        "source": "Managed benchmark reports", "method": "",
    }


class LeaderboardStore:
    def __init__(self, root: Path, refresh_seconds: int = 30):
        self.root = root.resolve()
        self.refresh_seconds = refresh_seconds
        self.lock = threading.Lock()
        self.payload = None
        self.next_refresh = 0.0
        self.aggregates = {}

    def canonical_boards(self) -> list[dict]:
        database = self.root / "data/model-benchmarks.sqlite"
        # Open each refresh afresh: the builder atomically replaces the database.
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            models = conn.execute("""
                SELECT m.*, r.* FROM models m JOIN model_results r USING(model_key)
                WHERE m.leaderboard_eligible = 1 ORDER BY r.rank
            """).fetchall()
            boards = {}
            for result in models:
                r = dict(result)
                recipe = r["suite"]
                board = boards.setdefault(recipe, new_board(recipe))
                board["source"] = "Canonical metrics database"
                board["method"] = (
                    "Frozen scores pooled from required seed counts. Controlled reasoning "
                    "variants retain their analytical positions and are labeled separately. "
                    "Cost is the mean API-list-price equivalent per run."
                )
                board["updated_at"] = datetime.fromtimestamp(
                    database.stat().st_mtime, timezone.utc).isoformat()
                scores = json.loads(r["scores_json"])
                reanalysis = None
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='model_score_reanalyses'").fetchone():
                    revised = conn.execute("SELECT result_json FROM model_score_reanalyses WHERE model_key=?", (r["model_key"],)).fetchone()
                    if revised:
                        reanalysis = json.loads(revised[0])
                board["columns"] = ([["capability", "Capability"], ["execution", "Execution"], ["production", "Production"]]
                                    if "capability" in scores else CLASSIC_COLUMNS)
                seeds = [x[0] for x in conn.execute("""
                    SELECT DISTINCT runs.seed FROM runs
                    JOIN run_cohorts USING(run_id) JOIN benchmark_trials USING(run_id)
                    WHERE run_cohorts.model = ? AND included_in_model_result = 1
                    ORDER BY runs.seed
                """, (r["model_key"],))]
                board["rows"].append({
                    "id": r["model_key"], "model": ("Grok 4.6" if r["label"] == "Grok 4.6 Build via Grok CLI" else r["label"]), "rank": r["rank"],
                    "lab": model_lab(r["model_key"]),
                    "scores": {k: v.get("score") for k, v in scores.items()},
                    "formulas": {k: v.get("formula", "") for k, v in scores.items()},
                    "status": "Controlled variant" if r["controlled_variant"] else "Replicated",
                    "note": r["variant_note"], "seeds": seeds,
                    "cost": r["api_list_cost_per_run_usd"],
                    "reasoning": r["reasoning_tokens_per_decision"],
                    "reasoning_estimated": bool(r["reasoning_tokens_estimated"]),
                    "latency": r["latency_median_seconds"],
                    "seed_scores": [], "commit": None, "reanalysis": reanalysis,
                })
        return list(boards.values())

    def aggregate(self, job: dict, reports: list[dict], signatures: tuple) -> dict:
        key = (job["run_id"], job.get("recipe_fingerprint_sha256"), signatures,
               json.dumps([r.get("owner_acceptance") for r in reports], sort_keys=True))
        if key in self.aggregates:
            return self.aggregates[key]
        candidates = [job.get("execution_root")]
        candidates += [cell.get("worktree") for cell in job["cells"]]
        candidates += [str(self.root)]
        errors = []
        for candidate in dict.fromkeys(x for x in candidates if x):
            source = within(self.root, candidate)
            if not (source / "agent_world/benchmarks.py").is_file():
                continue
            try:
                result = subprocess.run(
                    [sys.executable, "-c", AGGREGATE_SCRIPT],
                    cwd=source, input=json.dumps({
                        "recipe": job.get("recipe") or job["protocol"],
                        "digest": job.get("recipe_fingerprint_sha256"),
                        "reports": reports,
                    }), capture_output=True, text=True, timeout=30, check=True,
                )
                aggregate = json.loads(result.stdout)
                # A valid aggregate can explicitly reject evidence. Keep those
                # decisions; do not retry another source to obtain a better rank.
                self.aggregates = {k: v for k, v in self.aggregates.items() if k[0] != job["run_id"]}
                self.aggregates[key] = aggregate
                return aggregate
            except (subprocess.SubprocessError, ValueError) as exc:
                errors.append(type(exc).__name__)
        raise ValueError("Original scoring source is unavailable or incompatible (" + ", ".join(errors) + ")")

    def managed_run(self, job: dict, job_path: Path) -> tuple[dict, list[dict], dict | None]:
        heartbeat_path = job_path.with_name("controller-heartbeat.json")
        try:
            heartbeat = read_json(heartbeat_path)
        except (OSError, ValueError):
            heartbeat = {}
        checked = heartbeat.get("checked_at_utc")
        stale = True
        if checked:
            try:
                stale = (datetime.now(timezone.utc) - datetime.fromisoformat(
                    checked.replace("Z", "+00:00"))).total_seconds() > 120
            except (ValueError, TypeError):
                pass
        heartbeat_cells = {c["id"]: c for c in heartbeat.get("cells", [])}
        run = {
            "id": job["run_id"], "model": model_label(job["config"]["model"].get("id", "Mixed population")),
            "effort": job["config"]["model"].get("reasoning_effort"),
            "created_at": job.get("created_at_utc"), "commit": job.get("launch_commit"),
            "connector": job["config"]["model"].get("brain"),
            "connector_label": {"antigravity": "Antigravity", "muse": "Muse Code", "claude": "Claude Code",
                                "codex": "Codex", "grok": "Grok CLI", "openrouter": "OpenRouter",
                                "cursor": "Cursor", "devin": "Devin", "zcode": "ZCode"}.get(job["config"]["model"].get("brain"), job["config"]["model"].get("brain")),
            "checked_at": checked, "cells": [], "warnings": [],
            "readiness_status": (job.get("analysis_readiness") or {}).get("status"),
        }
        reports, signatures = [], []
        missing_costs = {}
        for cell in job["cells"]:
            latest = heartbeat_cells.get(cell["id"], {})
            state = (latest.get("controller_state") or cell.get("controller_state")
                     or latest.get("state") or "unknown")
            tick = latest.get("tick", cell.get("controller_last_tick"))
            try:
                manifest = read_json(within(self.root, cell["run_manifest"]))
                if (manifest.get("status") in {"completed", "failed", "stopped", "invalid", "cancelled"}
                        or (state != "waiting_quota" and manifest.get("status") not in (None, "running"))):
                    state = manifest["status"]
                    tick = manifest.get("final_tick", tick)
            except (OSError, ValueError, KeyError):
                pass
            stop_reason = latest.get("stop_reason") or cell.get("controller_stop_reason")
            attention = latest.get("attention") or cell.get("controller_attention")
            if state == "running" and (tick or 0) > 0:
                attention = None  # Completed progress supersedes historical startup attention.
            quota_blocked = (state not in {"completed", "running"} and (
                stop_reason in {"insufficient_quota", "quota_exhausted"}
                or attention == "quota_wait_budget_exhausted"))
            if quota_blocked:
                state = "waiting_quota"
            terminal = state in {"completed", "failed", "stopped", "invalid", "cancelled"}
            display_state = "status_stale" if stale and not terminal else state
            schedule = {}
            if state == "waiting_quota" and cell.get("events"):
                try:
                    schedule = quota_schedule(within(self.root, cell["events"]))
                except ValueError:
                    pass
            run["cells"].append({
                "seed": cell["seed"], "tick": tick, "target": cell.get("target_ticks"),
                "state": display_state, "operational_state": state,
                "attention": attention,
                "quota_wait_exhausted": attention == "quota_wait_budget_exhausted",
                "retry_at": ((latest.get("next_auto_resume_at_utc") or cell.get("next_auto_resume_at_utc")
                              or (schedule.get("retry_at") if attention != "quota_wait_budget_exhausted" else None)) if state == "waiting_quota" else None),
                "reset_at": schedule.get("reset_at"),
            })
            if job.get("kind") == "experiment":
                continue
            report_path = within(self.root, cell["output_dir"]) / "run-report.json"
            if not report_path.is_file():
                continue
            try:
                report = accepted_report(self.root, report_path, read_json(report_path))
                if report.get("owner_acceptance"):
                    run["readiness_status"] = "owner_accepted"
                    run["owner_acceptance"] = report["owner_acceptance"]
                # Only final reports may contribute to ranking, including early
                # population extinction when the report declares completion.
                if not report.get("run", {}).get("completed"):
                    continue
                protocol = report.get("benchmarks", {}).get("protocol", {})
                if protocol.get("id") != (job.get("recipe") or job.get("protocol")):
                    raise ValueError("Report and job recipe identities differ")
                report_digest = protocol.get("recipe_fingerprint_sha256")
                if report_digest and report_digest != job.get("recipe_fingerprint_sha256"):
                    raise ValueError("Report and job recipe fingerprints differ")
                missing_costs[cell["seed"]] = historical_cost(
                    report.get("usage", {}).get("estimated_cost"), job["config"]["model"]["id"])
                if missing_costs[cell["seed"]] is None:
                    missing_costs[cell["seed"]] = astra_historical_cost(
                        report.get("usage", {}).get("attempted_token_cost") or report.get("usage", {}).get("estimated_cost"),
                        job["config"]["model"]["id"], report_path)
                reports.append(report)
                stat = report_path.stat()
                signatures.append((str(report_path), stat.st_mtime_ns, stat.st_size))
            except (OSError, ValueError) as exc:
                run["warnings"].append(f"Seed {cell['seed']}: {exc}")
        aggregate = None
        if reports:
            try:
                aggregate = self.aggregate(job, reports, tuple(signatures))
            except ValueError as exc:
                run["warnings"].append(str(exc))
        rows = []
        if aggregate:
            for rejected in aggregate.get("rejected", []):
                run["warnings"].append(rejected.get("reason", "Evidence excluded").replace("_", " "))
            for r in aggregate["results"]:
                if not r.get("certified"):
                    run["warnings"].append("Awaiting a complete, unique set of required seeds; no replicated rank yet.")
                    continue
                costs = [x.get("api_list_cost_usd") if x.get("api_list_cost_usd") is not None
                         else missing_costs.get(x["seed"]) for x in r["required_replications"]]
                rows.append({
                    "id": job["run_id"] + ":" + r["model"], "model": model_label(r["model"]),
                    "report_paths": [signature[0] for signature in signatures],
                    "lab": model_lab(r["model"]),
                    "scores": {k: v.get("score") for k, v in r["scores"].items()},
                    "formulas": {k: v.get("formula", "") for k, v in r["scores"].items()},
                    "status": "Certified" if run.get("owner_acceptance") else r["status"].replace("_", " ").capitalize(),
                    "seeds": r["required_seeds"], "note": ("Owner-approved provenance override: source migration and incomplete native trace retention accepted on 2026-09-07." if run.get("owner_acceptance") else "; ".join(r.get("certification_flags", []))),
                    "cost": sum(costs) / len(costs) if costs and all(x is not None for x in costs) else None,
                    "reasoning": r.get("mean_reasoning_tokens_per_call"),
                    "reasoning_estimated": r.get("reasoning_tokens_estimated", False),
                    "latency": None, "commit": job.get("launch_commit"),
                    "seed_scores": [{"seed": s["seed"], "scores": {
                        k: v.get("score") for k, v in s["scores"].items()
                    }} for s in r["required_replications"]],
                })
        run["ranked"] = bool(rows)
        return run, rows, aggregate

    def build(self) -> dict:
        warnings = []
        experiments = []
        try:
            canonical = self.canonical_boards()
        except (OSError, sqlite3.Error, ValueError) as exc:
            LOG.exception("Cannot read canonical leaderboard")
            canonical = []
            warnings.append("Canonical database unavailable; managed results are still shown.")
        archive_path = STATIC / "leaderboard-activity-archive.json"
        archived = read_json(archive_path) if archive_path.exists() else {}
        boards = {}
        for path in sorted((self.root / "runs/jobs").glob("*/job.json")):
            try:
                job = read_json(path)
                recipe = job.get("recipe") or job.get("protocol")
                if job.get("kind") == "experiment":
                    if job.get("deferral", {}).get("status") == "deferred":
                        continue
                    run, _, _ = self.managed_run(job, path)
                    run.update(is_experiment=True, question=job.get("question") or job.get("config", {}).get("question", ""),
                               recipe=recipe, lab=model_lab(job["config"]["model"].get("id", "")),
                               agents=job.get("config", {}).get("runtime", {}).get("agents"),
                               world_overrides=job.get("config", {}).get("world", {}).get("overrides", {}))
                    experiments.append(run)
                    continue
                if job.get("kind") != "benchmark" or not recipe:
                    continue
                digest = job.get("recipe_fingerprint_sha256") or ""
                board = boards.setdefault(
                    recipe + ("@" + digest if digest else ""), new_board(recipe, digest))
                run, rows, aggregate = self.managed_run(job, path)
                run["archived"] = run["id"] in archived
                board["runs"].append(run)
                board["rows"].extend(rows)
                if aggregate:
                    protocol = aggregate["protocol"]
                    board["columns"] = protocol.get("score_columns") or CLASSIC_COLUMNS
                    board["method"] = protocol.get("aggregation", "Scores pool raw counts across required seeds.")
                    board["trial"] = {
                        "ticks": protocol.get("trial", {}).get("ticks"),
                        "agents": protocol.get("trial", {}).get("agents"),
                        "seeds": protocol.get("replications", {}).get("required_seeds", []),
                    }
                board["updated_at"] = max(board.get("updated_at", ""),
                                          run.get("checked_at") or job.get("created_at_utc", ""))
            except (OSError, ValueError, KeyError, TypeError):
                LOG.exception("Cannot read managed job %s", path.parent.name)
                warnings.append(f"Could not read study {path.parent.name}; it has been omitted.")
        # Database backfills are a fallback, not a signal to close a live
        # recipe pool. Prefer its validated managed results when available.
        # Keep distinct managed fingerprints separate; never pool them here.
        for catalog_board in canonical:
            matching = [b for b in boards.values() if b["recipe"] == catalog_board["recipe"]]
            if any(b["rows"] for b in matching):
                continue
            for empty in matching:
                catalog_board["runs"].extend(empty["runs"])
                del boards[empty["id"]]
            boards[catalog_board["id"]] = catalog_board
        revisions = scoring_policies(self.root)
        for board in boards.values():
            policy = revisions.get(board["recipe"])
            if policy:
                board["scoring_revision"] = policy["id"]
                board["scoring_caption"] = f"Final health · {policy['season_name']} damage counts {policy['season_damage_multiplier']:g}×"
                board["method"] = (reanalysis_formula(policy) + ". Dead original agents contribute zero. "
                                   "Scoring is revised after the run; source recipes, original scores and admission remain unchanged.")
                for row in board["rows"]:
                    try:
                        result = (rescore(self.root, row["report_paths"], policy) if row.get("report_paths") else row.get("reanalysis"))
                        if not result or result["policy_id"] != policy["id"]:
                            raise ValueError("Matching capability reanalysis is unavailable")
                        row["reanalysis"] = result
                        row["original_capability"] = row["scores"].get("capability")
                        row["scores"]["capability"] = result["capability"]["score"]
                        row["formulas"]["capability"] = result["capability"]["formula"]
                        per_seed = {c["seed"]: c["capability"]["score"] for c in result["cells"]}
                        for seed in row["seed_scores"]:
                            seed["scores"]["capability"] = per_seed[seed["seed"]]
                    except (OSError, ValueError, KeyError) as exc:
                        row["scores"]["capability"] = None
                        board["warnings"].append(row["model"] + ": capability rescoring unavailable — " + str(exc))
            if board["source"] != "Canonical metrics database" or policy:
                primary = board["columns"][0][0]
                board["rows"].sort(key=lambda row: (
                    -(row["scores"].get(primary) if row["scores"].get(primary) is not None else -1),
                    row["model"], row["id"]))
                for rank, row in enumerate(board["rows"], 1):
                    row["rank"] = rank
            board["runs"].sort(key=lambda run: (run["ranked"], run["model"]))
            board["active_count"] = sum(
                any(c["state"] not in {"completed", "failed", "stopped", "invalid", "cancelled"}
                    for c in run["cells"]) for run in board["runs"] if not run.get("archived"))
            board["state"] = "In progress" if board["active_count"] else (
                "Established" if board["source"] == "Canonical metrics database" else "Completed studies")
        recipe_counts = {}
        for b in boards.values():
            recipe_counts[b["recipe"]] = recipe_counts.get(b["recipe"], 0) + 1
        for b in boards.values():
            if recipe_counts[b["recipe"]] > 1:
                suffix = ("Canonical" if b["source"] == "Canonical metrics database"
                          else b["digest"][:8] or "Other studies")
                b["title"] += " · " + suffix
        # Recipe IDs supply display order only; never choose scoring by version.
        ordered = sorted(boards.values(), key=lambda b: (
            int(re.search(r"v(\d+)", b["recipe"])[1]) if re.search(r"v(\d+)", b["recipe"]) else 0,
            "revised" in b["recipe"], b["source"] == "Canonical metrics database"), reverse=True)
        return {"updated_at": stamp(), "refresh_seconds": self.refresh_seconds,
                "boards": ordered, "experiments": sorted(experiments, key=lambda r: r.get("created_at") or "", reverse=True), "warnings": warnings}

    def get(self) -> dict:
        with self.lock:
            if self.payload is None or time.monotonic() >= self.next_refresh:
                self.payload = self.build()
                self.next_refresh = time.monotonic() + self.refresh_seconds
            return self.payload


def make_server(root: Path, host: str = "127.0.0.1", port: int = 8091, launch_service=None) -> ThreadingHTTPServer:
    store = LeaderboardStore(root)
    viewer = WorldViewer(root)
    launches = launch_service or LaunchService(root)
    csrf_token = secrets.token_urlsafe(32)
    allowed_hosts = {"127.0.0.1", "localhost", "::1", socket.gethostname().lower()}
    allowed_hosts.update(h.lower() for h in launches.settings.get("allowed_hosts", []))
    if launches.settings.get("launch_enabled"):
        threading.Thread(target=launches.recovery_loop, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def json_response(self, value, status=200):
            body = json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def trusted_host(self):
            try:
                return urlsplit("//" + self.headers.get("Host", "")).hostname in allowed_hosts
            except ValueError:
                return False

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in {"/api/launch/preview", "/api/launch/start", "/api/launch/start-batch", "/api/launch/reconnect"}:
                self.send_error(404)
                return
            origin = urlsplit(self.headers.get("Origin", ""))
            if (not self.trusted_host() or origin.scheme not in {"http", "https"}
                    or origin.netloc.lower() != self.headers.get("Host", "").lower()
                    or self.headers.get("Sec-Fetch-Site") == "cross-site"
                    or not secrets.compare_digest(self.headers.get("X-Leaderboard-Token", ""), csrf_token)):
                self.json_response({"error": "Launch requests must come from this leaderboard page."}, 403)
                return
            if self.headers.get_content_type() != "application/json":
                self.json_response({"error": "Expected a JSON launch request."}, 415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise LaunchError("Invalid launch request size")
                values = json.loads(self.rfile.read(length))
                if not isinstance(values, dict):
                    raise LaunchError("Expected a launch request object")
                if path.endswith("/preview"):
                    result = launches.preview(values)
                elif path.endswith("/start-batch"):
                    result = launches.start_batch(values)
                elif path.endswith("/reconnect"):
                    result = launches.reconnect(values)
                else:
                    result = launches.start(values)
                self.json_response(result, 200 if path.endswith("/preview") else 202)
            except (LaunchError, ValueError, TypeError) as exc:
                self.json_response({"error": str(exc)}, 400)
            except Exception:
                LOG.exception("Benchmark launch request failed")
                self.json_response({"error": "Launch could not be completed. Check the recorded request state before retrying."}, 503)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in {"/api/worlds", "/api/world"}:
                try:
                    query = parse_qs(urlsplit(self.path).query)
                    result = viewer.worlds() if path == "/api/worlds" else viewer.snapshot(
                        query.get("run", ["demo"])[0], query.get("cell", [None])[0])
                    self.json_response(result)
                except FileNotFoundError:
                    self.json_response({"error": "World not found."}, 404)
                except (SnapshotUnavailable, OSError, ValueError, KeyError, TypeError):
                    self.json_response({"error": "World snapshot temporarily unavailable."}, 503)
                return
            if path == "/api/launch/options":
                if not self.trusted_host():
                    self.json_response({"error": "Unrecognized leaderboard hostname"}, 403)
                    return
                try:
                    self.json_response({**launches.public_options(), "token": csrf_token})
                except Exception:
                    LOG.exception("Launch options unavailable")
                    self.json_response({"error": "Launch options are temporarily unavailable"}, 503)
                return
            if path in {"/api/leaderboards", "/api/experiments"}:
                try:
                    body = json.dumps({**store.get(), "launches": launches.recent()}, allow_nan=False).encode()
                except Exception:
                    LOG.exception("Leaderboard request failed")
                    self.send_error(503, "Leaderboard data temporarily unavailable")
                    return
                content_type = "application/json"
            elif path == "/healthz":
                body, content_type = b'{"ok":true}', "application/json"
            elif path in {"/", "/laboratory", "/laboratory/", "/experiments", "/experiments/", "/leaderboard.js", "/leaderboard-launch.js", "/leaderboard.css", "/inter-latin.woff2", "/leaderboards", "/leaderboards/", "/world", "/world/", "/world-renderer.js", "/world-viewer.js", "/world-preview.js", "/world-viewer.css"} | {
                "/labs/" + lab + ".svg" for lab in (*LABS, "unknown")
            }:
                filenames = {"/world": "world-viewer.html", "/world/": "world-viewer.html", "/leaderboards": "leaderboard.html", "/leaderboards/": "leaderboard.html", "/": "leaderboard.html", "/laboratory": "leaderboard.html", "/laboratory/": "leaderboard.html", "/experiments": "leaderboard.html", "/experiments/": "leaderboard.html"}
                file = STATIC / filenames.get(path, path[1:])
                try:
                    body = file.read_bytes()
                except OSError:
                    self.send_error(404)
                    return
                content_type = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
                                ".css": "text/css", ".woff2": "font/woff2",
                                ".svg": "image/svg+xml"}[file.suffix]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if path.startswith("/api") else "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self'; script-src 'self'; "
                             "font-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    server = make_server(args.root, args.host, args.port)
    print(f"Agent World leaderboard: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
