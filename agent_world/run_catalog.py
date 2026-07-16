"""Rebuildable index of local run artifacts.

Raw run outputs remain canonical. The catalog is deliberately derived so it can
be regenerated after interruption, concurrent runs, or manual artifact moves.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_world.io import atomic_write_json, atomic_write_text


def write_run_catalog(
    runs_root: Path,
    *,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> dict[str, Any]:
    root = runs_root.expanduser().resolve()
    reports = sorted({*root.rglob("run-report.json"), *root.rglob("*-report.json")})
    records = [_catalog_record(root, report_path) for report_path in reports]
    records.sort(
        key=lambda row: (str(row.get("started_at_utc") or ""), str(row.get("report") or "")),
        reverse=True,
    )
    payload = {
        "schema_version": 1,
        "root": _portable_path(root),
        "run_count": len(records),
        "runs": records,
        "note": (
            "Derived index only. Event JSONL, snapshots, manifests, reports, usage logs, "
            "and checkpoints in each run directory are the canonical evidence."
        ),
    }
    atomic_write_json(json_path or root / "catalog.json", payload)
    atomic_write_text(markdown_path or root / "catalog.md", _render_catalog(payload))
    return payload


def refresh_catalog_for_output(output_path: Path | None) -> dict[str, Any] | None:
    if output_path is None:
        return None
    resolved = output_path.expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        if candidate.name == "runs":
            return write_run_catalog(candidate)
    return None


def _catalog_record(root: Path, report_path: Path) -> dict[str, Any]:
    report = _read_json(report_path)
    manifest_path = _matching_manifest(report_path)
    manifest = _read_json(manifest_path) if manifest_path else {}
    run = report.get("run") or {}
    reliability = report.get("reliability") or {}
    usage = report.get("usage") or {}
    credits = (usage.get("simulation_credits") or {}).get("credits") or {}
    population = report.get("population") or manifest.get("population") or {}
    cohort_models = sorted(
        {
            str(group.get("model") or group.get("brain") or group.get("type"))
            for group in (population.get("cohorts") or {}).values()
            if isinstance(group, dict)
        }
    )
    if not cohort_models:
        cohort_models = sorted(
            {
                str(group.get("model") or group.get("type"))
                for group in population.get("groups") or []
                if isinstance(group, dict)
            }
        )
    return {
        "id": str(report_path.parent.relative_to(root)),
        "report": str(report_path.relative_to(root)),
        "manifest": str(manifest_path.relative_to(root)) if manifest_path else None,
        "status": manifest.get("status") or ("completed" if run.get("completed") else "stopped"),
        "started_at_utc": manifest.get("started_at_utc") or manifest.get("created_at_utc"),
        "final_tick": run.get("final_tick"),
        "target_ticks": run.get("target_ticks"),
        "seed": (report.get("config") or {}).get("seed"),
        "preset": manifest.get("preset"),
        "observation_mode": manifest.get("observation_mode"),
        "turn_mode": manifest.get("turn_mode") or (report.get("turn_dynamics") or {}).get("mode"),
        "models": cohort_models,
        "quality_status": reliability.get("quality_status"),
        "invalid_actions_per_proposed_action_pct": reliability.get(
            "invalid_actions_per_proposed_action_pct"
        ),
        "llm_calls": usage.get("calls"),
        "api_cost_usd": usage.get("total_cost_usd"),
        "codex_simulation_credits": credits.get("total"),
    }


def _matching_manifest(report_path: Path) -> Path | None:
    candidates = [
        report_path.with_name(report_path.name.replace("-report.json", "-manifest.json")),
        report_path.parent / "manifest.json",
        report_path.parent / "run-manifest.json",
    ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _portable_path(path: Path) -> str:
    """Prefer a repository-relative catalog root over one user's absolute path."""

    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _render_catalog(payload: dict[str, Any]) -> str:
    lines = [
        "# Local run catalog",
        "",
        payload["note"],
        "",
        f"Indexed runs: {payload['run_count']}",
        "",
        "| Run | Status | Ticks | Turn mode | Observation | Models | Quality | Invalid | Credits |",
        "|---|---:|---:|---|---|---|---:|---:|---:|",
    ]
    for run in payload["runs"]:
        lines.append(
            "| {id} | {status} | {final}/{target} | {turn} | {observation} | {models} | "
            "{quality} | {invalid} | {credits} |".format(
                id=run.get("id"),
                status=run.get("status") or "?",
                final=run.get("final_tick") if run.get("final_tick") is not None else "?",
                target=run.get("target_ticks") if run.get("target_ticks") is not None else "?",
                turn=run.get("turn_mode") or "legacy",
                observation=run.get("observation_mode") or "legacy",
                models=", ".join(run.get("models") or []) or "unknown",
                quality=run.get("quality_status") or "?",
                invalid=run.get("invalid_actions_per_proposed_action_pct")
                if run.get("invalid_actions_per_proposed_action_pct") is not None
                else "?",
                credits=run.get("codex_simulation_credits")
                if run.get("codex_simulation_credits") is not None
                else "-",
            )
        )
    lines.extend(["", "Regenerate with `python3 -m agent_world.cli catalog-runs`.", ""])
    return "\n".join(lines)
