"""Offline factory, supervisor-identity, provenance, and accounting probes.

Run from the repository root:
PYTHONPATH=. python3 reports/infrastructure-audit-2026-09-04/probe_boundaries.py
No provider executable is launched.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from agent_world.brain_factory import BrainSpec, create_brains
from agent_world.brain_runtime import BrainRuntime
from agent_world.world import WorldEngine
from agent_world.models import WorldConfig, AgentDecision
from agent_world.managed_runs import _session_name, load_run_config
from agent_world.run_finalization import _audit_report
from agent_world.run_report import build_report

results = {}
engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A"])
spec = BrainSpec.resolve(
    "zcode", model="glm-5.3", reasoning_effort="max", connector_profile="connector-v3"
)
with patch.dict("os.environ", {"ZCODE_EXECUTABLE": "synthetic-not-executed"}):
    try:
        create_brains(engine, spec, BrainRuntime())
        error = None
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
results["zcode_factory"] = {
    "profile": spec.connector_profile, "conversation": spec.conversation_mode,
    "error": error,
}
results["session_collision"] = {
    "id_a": _session_name("audit.x", "seed-11", 0),
    "id_b": _session_name("audit-x", "seed-11", 0),
}
with tempfile.TemporaryDirectory(prefix="aw-audit-boundaries-") as directory:
    path = Path(directory)
    manifest = path / "manifest.json"
    manifest.write_text(json.dumps({
        "resolved_models": {"requested-model": 1, "unexpected-model": 99}
    }))
    job = {
        "config": {"model": {"id": "requested-model"}}, "protocol": "participant-v7"
    }
    cell = {"seed": 11, "target_ticks": 50, "run_manifest": str(manifest)}
    report = {
        "run": {"completed": True, "final_tick": 50},
        "reliability": {
            "benchmark_integrity_status": "clean", "usage_record_coverage_pct": 100.0
        },
        "benchmarks": {"trial": {"protocol_compliant": True}},
    }
    audit = _audit_report(job, cell, report)
    results["provenance_membership_check"] = {
        "provenance": audit["model_provenance"], "blockers": audit["blockers"]
    }
    config = {
        "schema_version": 1, "run_id": "probe", "kind": "experiment",
        "question": "Synthetic validation probe",
        "model": {"brain": "codex", "id": "synthetic"}, "runtime": {"ticks": True},
    }
    config_path = path / "config.json"
    config_path.write_text(json.dumps(config))
    results["config_boolean_ticks_accepted"] = load_run_config(config_path)["runtime"]["ticks"]
    engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A", "B"])
    engine.tick({
        agent_id: AgentDecision(intent="wait", actions=[{"type": "wait"}])
        for agent_id in engine.state.agents
    })
    row = {
        "agent_id": "agent-1", "tick": 0, "model": "synthetic",
        "prompt_tokens": 1, "completion_tokens": 1, "cost": 0,
    }
    report = build_report(
        [event.to_dict() for event in engine.state.events],
        engine.snapshot(), [row, row], target_ticks=1,
    )
    results["duplicate_coverage"] = {
        key: report["reliability"][key] for key in [
            "usage_record_coverage_pct", "benchmark_integrity_status", "quality_flags"
        ]
    }
    bad_usage_path = path / "bad-usage"
    bad_usage_path.mkdir()
    runtime = BrainRuntime(bad_usage_path)  # Intentionally a directory.
    runtime.record_usage(row)
    results["usage_write_failure"] = {
        "in_memory_rows": len(runtime.usage_records()),
        "write_error_raised": False, "usage_file_created": bad_usage_path.is_file(),
    }
print(json.dumps(results, indent=2))
