"""Declarative, durable launcher for model-backed Agent World run cells."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
from typing import Any

from agent_world.benchmarks import (
    BENCHMARK_PROTOCOL_ID,
    BENCHMARK_QUOTA_WAIT_HOURS,
)
from agent_world.protocols import RECIPES, get_recipe, recipe_from_dict
from agent_world.jsonl_tail import tail_for
from agent_world.io import atomic_write_json


CONFIG_SCHEMA_VERSION = 1
JOB_SCHEMA_VERSION = 1
DEFAULT_JOB_ROOT = Path("runs/jobs")
DEFAULT_OUTPUT_ROOT = Path("runs/managed")
CONTROLLER_POLL_SECONDS = 30.0
CONTROLLER_PROGRESS_INTERVAL_TICKS = 10
CONTROLLER_STALL_SECONDS = 3600.0

_TOP_LEVEL_KEYS = {
    "schema_version", "run_id", "kind", "question", "protocol", "recipe", "model",
    "seeds", "world", "runtime", "harness", "output_dir", "source",
}
_MODEL_KEYS = {"brain", "id", "reasoning_effort", "population"}
_WORLD_OPTIONS = {
    "overrides", "preset", "width", "height", "world_variant", "objective_mode", "economy_mode",
    "geography_mode", "specialization_mode", "action_feedback_mode", "transfer_kind_mode",
    "communication_action_cost", "town_ledger_action_cost",
    "town_ledger_prompt_mode", "town_ledger_seed_mode",
    "town_ledger_output_mode", "codex_action_max_items",
}
_RUNTIME_OPTIONS = {
    "max_run_calls", "max_run_tokens", "max_run_cost_usd",
    "ticks", "agents", "max_workers", "quota_wait_hours", "progress",
    "sequential_decisions", "provider_max_workers",
}
_HARNESS_OPTIONS = {
    "connector_profile", "conversation_mode", "session_max_turns",
    "observation_history_policy", "decision_mode", "assignment_strategy", "assignment_seed",
    "startup_health_check_tick", "startup_health_max_failure_rate",
    "no_agent_io_log", "claude_thinking_budget_tokens",
}
_PROVIDER_WORKER_FLAGS = {
    "openrouter": "openrouter-max-workers", "codex": "codex-max-workers",
    "claude": "claude-max-workers", "cursor": "cursor-max-workers",
    "devin": "devin-max-workers", "grok": "grok-max-workers",
    "zcode": "zcode-max-workers",
    "antigravity": "antigravity-max-workers", "muse": "muse-max-workers",
}
_MODEL_BACKED_BRAINS = set(_PROVIDER_WORKER_FLAGS)
_REASONING_EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError(
            f"{label} may contain only letters, numbers, dots, underscores, and hyphens"
        )
    return value


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"Unknown {label} config field(s): {', '.join(unknown)}")


def load_run_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Run config must be a JSON object")
    _reject_unknown(value, _TOP_LEVEL_KEYS, "top-level")
    if value.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {CONFIG_SCHEMA_VERSION}")
    kind = value.get("kind")
    if kind not in {"benchmark", "experiment"}:
        raise ValueError("kind must be 'benchmark' or 'experiment'")
    _safe_id(str(value.get("run_id") or ""), label="run_id")

    model = _require_mapping(value.get("model"), "model")
    world = _require_mapping(value.get("world"), "world")
    runtime = _require_mapping(value.get("runtime"), "runtime")
    harness = _require_mapping(value.get("harness"), "harness")
    source = _require_mapping(value.get("source"), "source")
    _reject_unknown(model, _MODEL_KEYS, "model")
    _reject_unknown(world, _WORLD_OPTIONS, "world")
    _reject_unknown(runtime, _RUNTIME_OPTIONS, "runtime")
    _reject_unknown(harness, _HARNESS_OPTIONS, "harness")
    _reject_unknown(source, {"commit"}, "source")

    population = model.get("population")
    if population is not None:
        if kind == "benchmark":
            raise ValueError("Benchmark configs require one uniform model; population is experimental")
        if model.get("brain") or model.get("id"):
            raise ValueError("Use model.population or model.brain/model.id, not both")
        if not isinstance(population, list) or not population or not all(
            isinstance(item, str) and item for item in population
        ):
            raise ValueError("model.population must be a non-empty array of COUNT@BRAIN:MODEL strings")
    elif not model.get("brain") or not model.get("id"):
        raise ValueError("model.brain and model.id are required")
    if population is None:
        if model["brain"] not in _MODEL_BACKED_BRAINS:
            raise ValueError(
                "model.brain must be openrouter, codex, claude, cursor, devin, grok, zcode, antigravity, or muse"
            )
        effort = model.get("reasoning_effort")
        if effort is not None and effort not in _REASONING_EFFORTS:
            raise ValueError(f"Unsupported model.reasoning_effort: {effort!r}")

    benchmark_recipe = get_recipe(value.get("protocol")) if kind == "benchmark" else None
    seeds = value.get("seeds", list(benchmark_recipe.required_seeds) if benchmark_recipe else [11])
    if not isinstance(seeds, list) or not seeds or not all(
        isinstance(seed, int) and not isinstance(seed, bool) for seed in seeds
    ):
        raise ValueError("seeds must be a non-empty array of integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must not contain duplicates")
    value["seeds"] = seeds

    if kind == "benchmark":
        protocol = value.get("protocol") or BENCHMARK_PROTOCOL_ID
        recipe = get_recipe(protocol)
        if value.get("recipe") not in {None, recipe.id}:
            raise ValueError("Benchmark protocol and recipe must agree")
        value["protocol"] = protocol
        undeclared = sorted(set(seeds) - recipe.allowed_seeds)
        if undeclared:
            raise ValueError(f"Benchmark seeds are not declared by {protocol}: {undeclared}")
        incompatible_blocks = {
            "world": sorted(world),
            "runtime": sorted(
                set(runtime)
                - {
                    "max_workers", "provider_max_workers",
                    "quota_wait_hours", "progress",
                }
            ),
            "harness": sorted(harness),
        }
        configured = [
            f"{block}.{name}"
            for block, names in incompatible_blocks.items()
            for name in names
        ]
        if configured:
            raise ValueError(
                "Benchmark protocol owns these settings; omit them from the config: "
                + ", ".join(configured)
            )
        if model.get("reasoning_effort") not in {None, recipe.reasoning_effort}:
            raise ValueError(
                f"{protocol} requires model.reasoning_effort={recipe.reasoning_effort!r} "
                f"for brain={model['brain']!r}"
            )
        model["reasoning_effort"] = recipe.reasoning_effort
    elif value.get("protocol") is not None:
        raise ValueError("Experiment configs must omit protocol")
    if value.get("recipe") is not None:
        recipe = get_recipe(value["recipe"])
        if model.get("reasoning_effort") is None:
            model["reasoning_effort"] = recipe.reasoning_effort
    if kind == "experiment" and not str(value.get("question") or "").strip():
        raise ValueError("Experiment configs require a concrete question")

    for key in ("ticks", "agents", "max_workers"):
        if key in runtime and (not isinstance(runtime[key], int) or isinstance(runtime[key], bool) or runtime[key] < 1):
            raise ValueError(f"runtime.{key} must be a positive integer")
    thinking_budget = harness.get("claude_thinking_budget_tokens")
    if thinking_budget is not None and (
        not isinstance(thinking_budget, int) or isinstance(thinking_budget, bool) or thinking_budget < 0
    ):
        raise ValueError("harness.claude_thinking_budget_tokens must be a non-negative integer")
    quota_wait = runtime.get("quota_wait_hours")
    if quota_wait is not None and (
        not isinstance(quota_wait, (int, float))
        or isinstance(quota_wait, bool)
        or not __import__("math").isfinite(quota_wait)
        or quota_wait < 0
    ):
        raise ValueError("runtime.quota_wait_hours must be a non-negative number")
    workers = runtime.get("provider_max_workers")
    if workers is not None:
        workers = _require_mapping(workers, "runtime.provider_max_workers")
        _reject_unknown(workers, set(_PROVIDER_WORKER_FLAGS), "provider worker")
        if any(not isinstance(count, int) or isinstance(count, bool) or count < 1 for count in workers.values()):
            raise ValueError("Every provider worker limit must be a positive integer")
    from agent_world.request_context import validate_limits
    validate_limits({key: runtime[name] for name, key in (
        ("max_run_calls", "calls"), ("max_run_tokens", "tokens"), ("max_run_cost_usd", "cost_usd")
    ) if name in runtime})
    from agent_world.brain_factory import BrainSpec, PopulationSpec
    from agent_world.models import WorldConfig
    from agent_world.cli import build_parser
    selected_recipe = value.get("protocol") or value.get("recipe")
    defaults = get_recipe(selected_recipe).defaults() if selected_recipe else {}
    shared = {
        "reasoning_effort": model.get("reasoning_effort"),
        "max_workers": runtime.get("max_workers"),
        "connector_profile": harness.get("connector_profile", defaults.get("connector_profile", "connector-v1")),
        "conversation_mode": harness.get("conversation_mode", "fresh-conversation"),
        "session_max_turns": harness.get("session_max_turns", 10),
    }
    if population:
        resolved = PopulationSpec.parse_many(population, **shared)
        if runtime.get("agents") is not None and runtime["agents"] != resolved.total_agents:
            raise ValueError("runtime.agents conflicts with model.population")
    else:
        spec = BrainSpec.resolve(model["brain"], model=model["id"], **shared)
        model["reasoning_effort"] = spec.reasoning_effort
    overrides = world.get("overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError("world.overrides must be an object")
    if kind == "benchmark" and overrides:
        raise ValueError("world.overrides is experiment-only")
    try:
        WorldConfig(**overrides)
    except TypeError as exc:
        raise ValueError(f"Invalid world overrides: {exc}") from exc
    import contextlib
    import io
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            arguments = build_cell_command(value, seeds[0], Path("/dry-run"))[3:]
            build_parser().parse_args(arguments)
        except SystemExit as exc:
            raise ValueError("Run configuration contains invalid CLI option values") from exc
    return value


def _append_option(command: list[str], name: str, value: Any) -> None:
    flag = f"--{name.replace('_', '-')}"
    if isinstance(value, bool):
        if value:
            command.append(flag)
    elif value is not None:
        command.extend([flag, str(value)])


def build_cell_command(config: dict[str, Any], seed: int, output: Path) -> list[str]:
    command = ["python3", "-m", "agent_world.cli", "run"]
    if config["kind"] == "benchmark":
        command.extend(["--benchmark-protocol", config["protocol"]])
    if config.get("recipe") and config["kind"] != "benchmark":
        command.extend(["--recipe", config["recipe"]])
    model = config["model"]
    if model.get("population"):
        for population in model["population"]:
            command.extend(["--population", population])
    else:
        command.extend(["--brain", str(model["brain"]), "--model", str(model["id"])])
    _append_option(command, "reasoning_effort", model.get("reasoning_effort"))
    command.extend(["--seed", str(seed)])
    for block_name, allowed in (
        ("world", _WORLD_OPTIONS - {"overrides"}), ("runtime", _RUNTIME_OPTIONS - {"provider_max_workers"}),
        ("harness", _HARNESS_OPTIONS),
    ):
        block = config.get(block_name) or {}
        for name in sorted(allowed):
            if name in block:
                _append_option(command, name, block[name])
    for provider, count in (config.get("runtime", {}).get("provider_max_workers") or {}).items():
        command.extend([f"--{_PROVIDER_WORKER_FLAGS[provider]}", str(count)])
    if (config.get("world") or {}).get("overrides"):
        command.extend(["--world-config-json", json.dumps(config["world"]["overrides"], separators=(",", ":"))])
    command.extend(
        ["--out", str(output / "run.jsonl"), "--snapshot", str(output / "run-snapshot.json")]
    )
    if "--progress" not in command:
        command.append("--progress")
    return command


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _canonical_root() -> Path:
    # A controller/finalizer may execute inside a pinned linked worktree.
    # The common Git directory identifies the shared canonical job store.
    common = Path(_git(Path.cwd(), "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common.parent


def build_launch_plan(config: dict[str, Any], root: Path, *, run_id: str | None = None) -> dict[str, Any]:
    resolved_id = _safe_id(run_id or str(config["run_id"]), label="run_id")
    requested_commit = str((config.get("source") or {}).get("commit") or "HEAD")
    commit = _git(root, "rev-parse", f"{requested_commit}^{{commit}}")
    if requested_commit == "HEAD" and _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Refusing to launch from dirty tracked source; commit it or set source.commit")
    if requested_commit == "HEAD" and _git(root, "status", "--porcelain", "--untracked-files=all", "--", "agent_world/recipes"):
        raise ValueError("Commit recipe files before launching from HEAD")
    selected_recipe = config.get("protocol") or config.get("recipe")
    if requested_commit != "HEAD" and selected_recipe:
        try:
            definition = _git(root, "show", f"{commit}:agent_world/recipes/{selected_recipe}.json")
            pinned_recipe = recipe_from_dict(json.loads(definition))
        except (subprocess.CalledProcessError, ValueError) as exc:
            raise ValueError(
                "source.commit must contain the selected JSON recipe; launch older "
                "pre-recipe studies through their original checkout"
            ) from exc
        if pinned_recipe.digest != get_recipe(selected_recipe).digest:
            raise ValueError("Selected recipe differs in source.commit; use that checkout's definition")
    output_root = Path(config.get("output_dir") or DEFAULT_OUTPUT_ROOT / resolved_id)
    if not output_root.is_absolute():
        output_root = root / output_root
    job_dir = root / DEFAULT_JOB_ROOT / resolved_id
    target_ticks = (
        get_recipe(config["protocol"]).defaults()["ticks"]
        if config["kind"] == "benchmark"
        else int((config.get("runtime") or {}).get("ticks",
            get_recipe(config["recipe"]).defaults()["ticks"] if config.get("recipe") else 25))
    )
    cells = []
    for seed in config["seeds"]:
        cell_id = f"seed-{seed}"
        cell_output = output_root / cell_id
        cohort = f"{resolved_id}-{cell_id}"
        cells.append(
            {
                "id": cell_id, "seed": seed, "cohort_id": cohort,
                "target_ticks": target_ticks,
                "output_dir": str(cell_output),
                "events": str(cell_output / "run.jsonl"),
                "snapshot": str(cell_output / "run-snapshot.json"),
                "checkpoint": str(cell_output / "run-checkpoint.pkl"),
                "run_manifest": str(cell_output / "run-manifest.json"),
                "log": str(job_dir / f"{cell_id}.log"),
                "command": build_cell_command(config, seed, cell_output),
                "session": None, "resume_count": 0,
                "worktree": None,
            }
        )
    return {
        "schema_version": JOB_SCHEMA_VERSION, "run_id": resolved_id,
        "kind": config["kind"], "question": config.get("question"),
        "protocol": config.get("protocol"), "launch_commit": commit,
        "recipe": config.get("protocol") or config.get("recipe"),
        "recipe_fingerprint_sha256": (get_recipe(config.get("protocol") or config.get("recipe")).digest
            if config.get("protocol") or config.get("recipe") else None),
        "orchestrator_commit": commit if requested_commit == "HEAD" else _git(root, "rev-parse", "HEAD"),
        "source_root": str(root), "job_dir": str(job_dir),
        "config": config, "created_at_utc": utc_now(), "cells": cells,
    }


def _session_name(run_id: str, cell_id: str, resume_count: int) -> str:
    raw = f"aw-{run_id}-{cell_id}" + (f"-r{resume_count}" if resume_count else "")
    digest = __import__("hashlib").sha256(raw.encode()).hexdigest()[:16]
    return re.sub(r"[^A-Za-z0-9_-]", "-", raw)[:61] + "-" + digest


def _tmux_active(session: str | None) -> bool:
    if not session or shutil.which("tmux") is None:
        return False
    return subprocess.run(
        ["tmux", "has-session", "-t", session], capture_output=True
    ).returncode == 0


@contextmanager
def _job_lock(job_dir: str | Path):
    """Serialize controller, manual-resume, and finalization job mutations."""

    path = Path(job_dir) / ".job.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_launcher(job: dict[str, Any], cell: dict[str, Any], *, resume: bool) -> Path:
    job_dir = Path(job["job_dir"])
    suffix = f"-resume-{cell['resume_count']}" if resume else ""
    path = job_dir / f"launch-{cell['id']}{suffix}.sh"
    inner = (
        ["python3", "-m", "agent_world.cli", "run", "--resume-checkpoint", cell["checkpoint"],
         "--ticks", str(cell["target_ticks"]), "--progress"]
        if resume else cell["command"]
    )
    if resume:
        config = job["config"]
        quota_wait_hours = (config.get("runtime") or {}).get("quota_wait_hours")
        if quota_wait_hours is None:
            quota_wait_hours = (
                BENCHMARK_QUOTA_WAIT_HOURS if config["kind"] == "benchmark" else 0.0
            )
        inner.extend(["--quota-wait-hours", str(quota_wait_hours)])
    if resume and cell.get("source_recovery_record"):
        inner.extend(["--source-recovery-record", cell["source_recovery_record"]])
    isolated = [
        str(Path(cell.get("worktree") or job["source_root"]) / "scripts/run-isolated-cohort"),
        "--cohort", cell["cohort_id"], "--commit", cell.get("execution_commit", job["launch_commit"]), "--", *inner,
    ]
    content = (
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        f"export PATH={shlex.quote(os.environ.get('PATH', os.defpath))}\n"
        f"exec {shlex.join(isolated)} >> {shlex.quote(cell['log'])} 2>&1\n"
    )
    path.write_text(content, encoding="utf-8")
    path.chmod(0o700)
    return path


def _prepare_cell(job: dict[str, Any], cell: dict[str, Any]) -> None:
    if cell.get("worktree"):
        return
    launcher = Path(job["source_root"]) / "scripts/run-isolated-cohort"
    result = subprocess.run(
        [
            str(launcher), "--cohort", cell["cohort_id"], "--commit",
            cell.get("execution_commit", job["launch_commit"]), "--prepare-only", "--",
        ],
        cwd=job["source_root"],
        capture_output=True,
        text=True,
        check=True,
    )
    cell["worktree"] = result.stdout.strip().splitlines()[-1]


def _launch_cell(job: dict[str, Any], cell: dict[str, Any], *, resume: bool = False) -> None:
    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is required for durable managed runs")
    session = _session_name(job["run_id"], cell["id"], cell["resume_count"])
    if _tmux_active(session):
        raise RuntimeError(f"Supervisor session already exists: {session}")
    _prepare_cell(job, cell)
    launcher = _write_launcher(job, cell, resume=resume)
    if resume:
        manifest = Path(cell["run_manifest"])
        if manifest.exists():
            archived = manifest.with_name(
                f"run-manifest.before-resume-{cell['resume_count']}.json"
            )
            if archived.exists():
                raise FileExistsError(f"Resume manifest archive already exists: {archived}")
            manifest.replace(archived)
            cell.setdefault("previous_run_manifests", []).append(str(archived))
    cell["session"] = session
    cell["launch_state"] = "launching"
    cell["last_launched_at_utc"] = utc_now()
    atomic_write_json(Path(job["job_dir"]) / "job.json", job, fsync=True)
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-c", job["source_root"], str(launcher)],
        check=True,
    )
    if not _tmux_active(session):
        raise RuntimeError(f"Supervisor failed to remain active: {session}; inspect {cell['log']}")
    cell["session"] = session
    cell["launch_state"] = "running"
    cell["last_launched_at_utc"] = utc_now()


def _health_gate_status(cell: dict[str, Any]) -> str | None:
    rows = tail_for(str(Path(cell["events"]).resolve()), frozenset({"run_health_check"}), True).read()
    if not rows:
        return None
    status = (rows[-1].get("data") or {}).get("status")
    return status if status in {"passed", "failed"} else None


def _launch_gate_supervisor(job: dict[str, Any]) -> None:
    first = job["cells"][0]
    _prepare_cell(job, first)
    session = _session_name(job["run_id"], "startup-gate", 0)
    script = Path(job["job_dir"]) / "supervise-startup-gate.sh"
    script.write_text(
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        f"export PATH={shlex.quote(os.environ.get('PATH', os.defpath))}\n"
        f"cd {shlex.quote(job['source_root'])}\n"
        f"exec python3 -m agent_world.managed_runs supervise "
        f"{shlex.quote(str(Path(job['job_dir']) / 'job.json'))} "
        f">> {shlex.quote(str(Path(job['job_dir']) / 'supervisor.log'))} 2>&1\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-c", job["source_root"], str(script)],
        check=True,
    )
    if not _tmux_active(session):
        raise RuntimeError(f"Startup-gate supervisor failed to remain active: {session}")
    job["startup_gate"]["supervisor_session"] = session


def _launch_job_controller(job: dict[str, Any]) -> None:
    """Launch the durable lifecycle controller for every managed job."""

    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is required for the managed job controller")
    orchestrator_commit = job.get("orchestrator_commit", job.get("launch_commit"))
    if job["cells"] and orchestrator_commit != job.get("launch_commit"):
        orchestration = job.setdefault("orchestration_source", {
            "cohort_id": job["run_id"] + "-orchestrator", "worktree": None,
        })
        _prepare_cell({**job, "launch_commit": orchestrator_commit}, orchestration)
        execution_root = orchestration["worktree"]
    else:
        if job["cells"]:
            _prepare_cell(job, job["cells"][0])
        execution_root = (job["cells"][0].get("worktree") if job["cells"] else None) or job["source_root"]
    job["execution_root"] = execution_root
    job_dir = Path(job["job_dir"])
    session = _session_name(job["run_id"], "controller", 0)
    existing = job.get("controller") or {}
    if _tmux_active(existing.get("session")) or _tmux_active(session):
        raise RuntimeError(f"Job controller session already exists: {session}")
    script = job_dir / "supervise-job.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -uo pipefail\n"
        f"export PATH={shlex.quote(os.environ.get('PATH', os.defpath))}\n"
        f"cd {shlex.quote(execution_root)}\n"
        "attempt=0\n"
        "while true; do\n"
        f"  python3 -m agent_world.run_controller {shlex.quote(str(job_dir / 'job.json'))} "
        f">> {shlex.quote(str(job_dir / 'controller.log'))} 2>&1 && exit 0\n"
        "  attempt=$((attempt + 1))\n"
        "  delay=$((attempt * 30))\n"
        "  (( delay > 300 )) && delay=300\n"
        f"  echo \"Job controller crashed; restart $attempt follows in ${{delay}}s.\" >> "
        f"{shlex.quote(str(job_dir / 'controller.log'))}\n"
        "  sleep \"$delay\"\n"
        "done\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    job["controller"] = {
        "schema_version": 1,
        "status": "running",
        "session": session,
        "started_at_utc": utc_now(),
        "poll_seconds": CONTROLLER_POLL_SECONDS,
        "progress_interval_ticks": CONTROLLER_PROGRESS_INTERVAL_TICKS,
        "stall_seconds": CONTROLLER_STALL_SECONDS,
        "heartbeat": str(job_dir / "controller-heartbeat.json"),
        "events": str(job_dir / "controller-events.jsonl"),
        "log": str(job_dir / "controller.log"),
    }
    if isinstance(job.get("startup_gate"), dict):
        job["startup_gate"]["supervisor_session"] = session
    atomic_write_json(job_dir / "job.json", job)
    try:
        subprocess.run(
            [
                "tmux", "new-session", "-d", "-s", session,
                "-c", job["source_root"], str(script),
            ],
            check=True,
        )
    except Exception as exc:
        job["controller"].update(
            {"status": "failed", "ended_at_utc": utc_now(), "error": str(exc)}
        )
        atomic_write_json(job_dir / "job.json", job)
        raise
    if not _tmux_active(session):
        fresh = _read_json(str(job_dir / "job.json")) or {}
        state = (fresh.get("controller") or {}).get("status")
        if state in {"completed", "completed_with_blockers", "needs_attention"}:
            job.clear()
            job.update(fresh)
            return
        raise RuntimeError(
            f"Job controller failed to remain active: {session}; "
            f"inspect {job_dir / 'controller.log'}"
        )


def supervise_startup_gate(job_path: Path, *, poll_seconds: float = 5.0) -> None:
    while True:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        first = job["cells"][0]
        gate = _health_gate_status(first)
        if gate == "passed":
            job["startup_gate"].update({"status": "passed", "passed_at_utc": utc_now()})
            atomic_write_json(job_path, job)
            for cell in job["cells"][1:]:
                try:
                    Path(cell["output_dir"]).mkdir(parents=True, exist_ok=False)
                    _launch_cell(job, cell)
                except Exception as exc:
                    cell["launch_error"] = str(exc)
                    atomic_write_json(job_path, job)
                    raise
                else:
                    atomic_write_json(job_path, job)
            return
        if gate == "failed":
            job["startup_gate"].update(
                {"status": "failed", "failed_at_utc": utc_now(), "reason": "startup_health_check_failed"}
            )
            atomic_write_json(job_path, job)
            return
        first_status = cell_status(first)
        if not first_status["supervisor_active"] and first_status["state"] not in {"running", "not_started"}:
            job["startup_gate"].update(
                {"status": "blocked", "failed_at_utc": utc_now(), "reason": first_status["state"]}
            )
            atomic_write_json(job_path, job)
            return
        time.sleep(poll_seconds)


def launch_config(path: Path, *, run_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    config = load_run_config(path)
    root = _canonical_root()
    job = build_launch_plan(config, root, run_id=run_id)
    job_dir = Path(job["job_dir"])
    if job_dir.exists() or job_dir.is_symlink():
        raise FileExistsError(f"Managed run already exists: {job_dir}")
    # Validate every seed before any cell can consume provider usage.
    for cell in job["cells"]:
        destination = Path(cell["output_dir"])
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Run output already exists: {destination}")
        for parent in destination.parents:
            if parent.exists() and not parent.is_dir():
                raise NotADirectoryError(f"Run output parent is not a directory: {parent}")
    if dry_run:
        return job
    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is required for durable managed runs")
    job_dir.mkdir(parents=True)
    atomic_write_json(job_dir / "config.json", config)
    atomic_write_json(job_dir / "job.json", job)
    try:
        gated = job["kind"] == "benchmark" and len(job["cells"]) > 1
        if gated:
            job["startup_gate"] = {"status": "pending", "source_cell": job["cells"][0]["id"]}
        launch_cells = job["cells"][:1] if gated else job["cells"]
        for cell in launch_cells:
            Path(cell["output_dir"]).mkdir(parents=True, exist_ok=False)
            _launch_cell(job, cell)
            atomic_write_json(job_dir / "job.json", job)
        _launch_job_controller(job)
    except Exception:
        atomic_write_json(job_dir / "job.json", job, fsync=True)
        if any(cell.get("session") for cell in job["cells"]) and not job.get("controller"):
            _launch_job_controller(job)
        raise
    return job


def _job_path(run_id: str, root: Path | None = None) -> Path:
    return (root or _canonical_root()) / DEFAULT_JOB_ROOT / _safe_id(run_id, label="run_id") / "job.json"


def load_job(run_id: str, root: Path | None = None) -> dict[str, Any]:
    path = _job_path(run_id, root)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != JOB_SCHEMA_VERSION:
        raise ValueError(f"Unsupported managed job manifest: {path}")
    return value


def _read_json(path: str) -> dict[str, Any] | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def cell_status(cell: dict[str, Any]) -> dict[str, Any]:
    run_manifest = _read_json(cell["run_manifest"])
    snapshot = _read_json(cell["snapshot"])
    active = _tmux_active(cell.get("session"))
    manifest_status = run_manifest.get("status") if run_manifest else None
    # Durable terminal evidence wins over a stale supervisor. The old order
    # could report a completed run as running forever when a wrapper retained
    # the tmux session after the child process exited.
    if manifest_status and manifest_status != "running":
        state = manifest_status
    elif active:
        state = "running"
    elif Path(cell["checkpoint"]).exists():
        state = "interrupted"
    else:
        state = "not_started"
    tick = None
    if snapshot:
        tick = snapshot.get("tick")
    if tick is None and run_manifest:
        tick = run_manifest.get("final_tick")
    return {
        "id": cell["id"], "seed": cell["seed"], "state": state,
        "tick": tick, "target_ticks": cell.get("target_ticks"),
        "session": cell.get("session"),
        "supervisor_active": active and state == "running",
        "stale_supervisor": active and state != "running",
        "stop_reason": run_manifest.get("stop_reason") if run_manifest else None,
        "controller_state": cell.get("controller_state"),
        "controller_attention": cell.get("controller_attention"),
        "next_auto_resume_at_utc": cell.get("next_auto_resume_at_utc"),
        "auto_resume_count": int(cell.get("auto_resume_count") or 0),
        "log": cell["log"], "checkpoint": cell["checkpoint"],
    }


def job_status(run_id: str, root: Path | None = None) -> dict[str, Any]:
    job = load_job(run_id, root)
    cells = [cell_status(cell) for cell in job["cells"]]
    gate = dict(job.get("startup_gate") or {})
    if gate.get("supervisor_session"):
        gate["supervisor_active"] = _tmux_active(gate["supervisor_session"])
    finalization = dict(job.get("finalization_supervisor") or {})
    if finalization.get("session"):
        finalization["supervisor_active"] = _tmux_active(finalization["session"])
    controller = dict(job.get("controller") or {})
    if controller.get("session"):
        controller["supervisor_active"] = _tmux_active(controller["session"])
    heartbeat = _read_json(controller.get("heartbeat", "")) if controller else None
    if heartbeat:
        controller["heartbeat_state"] = heartbeat
    if gate.get("status") in {"pending", "failed", "blocked"}:
        deferred_state = (
            "waiting_startup_gate" if gate["status"] == "pending" else "blocked_startup_gate"
        )
        for index, cell in enumerate(cells):
            if index and cell["state"] == "not_started":
                cell["state"] = deferred_state
    return {
        "run_id": job["run_id"], "kind": job["kind"], "protocol": job.get("protocol"),
        "launch_commit": job["launch_commit"],
        "startup_gate": gate or None,
        "controller": controller or None,
        "finalization": finalization or None,
        "analysis_readiness": job.get("analysis_readiness"),
        "cells": cells,
    }


def resume_job(run_id: str) -> dict[str, Any]:
    initial = load_job(run_id)
    resumed = []
    with _job_lock(initial["job_dir"]):
        job = load_job(run_id)
        for cell in job["cells"]:
            status = cell_status(cell)
            if status["state"] == "completed":
                continue
            if status["supervisor_active"]:
                continue
            if status["state"] == "stopped" and status.get("stop_reason") == "startup_health_check_failed":
                continue
            if not Path(cell["checkpoint"]).exists() and cell.get("session") is None:
                continue
            if not Path(cell["checkpoint"]).exists():
                raise FileNotFoundError(f"No checkpoint available for {cell['id']}: {cell['checkpoint']}")
            cell["resume_count"] = int(cell.get("resume_count") or 0) + 1
            _launch_cell(job, cell, resume=True)
            resumed.append(cell["id"])
            atomic_write_json(Path(job["job_dir"]) / "job.json", job)
        controller = job.get("controller") or {}
        if not _tmux_active(controller.get("session")):
            _launch_job_controller(job)
    return {"run_id": run_id, "resumed": resumed, "status": job_status(run_id)}


def format_status(status: dict[str, Any]) -> str:
    lines = [
        f"Managed run {status['run_id']} | {status['kind']}"
        + (f" | {status['protocol']}" if status.get("protocol") else ""),
        f"launch commit: {status['launch_commit']}",
    ]
    if status.get("startup_gate"):
        gate = status["startup_gate"]
        supervisor = (
            f"; supervisor_active={str(gate['supervisor_active']).lower()}"
            if "supervisor_active" in gate else ""
        )
        lines.append(f"startup gate: {gate['status']}{supervisor}")
    if status.get("controller"):
        controller = status["controller"]
        heartbeat = controller.get("heartbeat_state") or {}
        checked = heartbeat.get("checked_at_utc")
        detail = f"; last_check={checked}" if checked else ""
        lines.append(
            f"controller: {controller.get('status', 'unknown')}; "
            f"supervisor_active={str(controller.get('supervisor_active', False)).lower()}"
            f"{detail}"
        )
    if status.get("finalization"):
        finalization = status["finalization"]
        lines.append(
            f"finalization: {finalization.get('status', 'unknown')}; "
            f"supervisor_active={str(finalization.get('supervisor_active', False)).lower()}"
        )
    if status.get("analysis_readiness"):
        lines.append(f"analysis readiness: {status['analysis_readiness'].get('status')}")
    for cell in status["cells"]:
        tick = "?" if cell["tick"] is None else cell["tick"]
        target = cell.get("target_ticks")
        progress = f"{tick}/{target}" if target is not None else str(tick)
        line = f"- {cell['id']}: {cell['state']} at tick {progress}"
        if cell.get("stop_reason"):
            line += f" ({cell['stop_reason']})"
        if cell.get("stale_supervisor"):
            line += "; stale_supervisor=true"
        if cell.get("controller_attention"):
            line += f"; attention={cell['controller_attention']}"
        if cell.get("next_auto_resume_at_utc"):
            line += f"; auto_resume_at={cell['next_auto_resume_at_utc']}"
        if cell.get("auto_resume_count"):
            line += f"; auto_resumes={cell['auto_resume_count']}"
        line += f"; log={cell['log']}"
        lines.append(line)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) == 2 and arguments[0] == "supervise":
        supervise_startup_gate(Path(arguments[1]))
        return
    raise SystemExit("Usage: python3 -m agent_world.managed_runs supervise JOB.json")


if __name__ == "__main__":
    main()
