"""Offline matched pre/post feedback analysis; never modifies run evidence."""
import argparse
from collections import Counter, defaultdict
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PIN = "783341aad5cf195209091652f6eb25420f4af0b8"
ENGINE = ROOT / ".worktrees/run-cohorts/gpt-5-6-luna-v8-revised-20260905-seed-11-783341aad5cf"
MODELS = ["gpt-5-6-terra", "gpt-5-6-luna", "gpt-5-5", "gpt-5-4-mini"]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert subprocess.check_output(["git", "-C", str(ENGINE), "rev-parse", "HEAD"], text=True).strip() == PIN
    assert not subprocess.check_output(["git", "-C", str(ENGINE), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
    sys.path.insert(0, str(ENGINE))
    from agent_world.models import WorldConfig, AgentDecision
    from agent_world.world import WorldEngine
    from agent_world.outcome_scoring import derive_action_execution_counts, derive_outcome_counts
    from agent_world.production_scoring import score_outcome_production_counts
    result = {"evidence_class": "offline_matched_before_after", "replay_engine_commit": PIN,
              "note": "Fixed recorded decisions; replay recovers outcomes, not counterfactual model decisions.",
              "models": {}, "exclusions": {
                  "GPT-5.6 Sol": "No original-v8 pre-fix study; v6 differs in horizon and prompts.",
                  "Muse Spark 1.2": "Original-v8 readiness diagnostic_only; revised study lacks ready status.",
                  "Gemini 3.6/3.7": "No matched pre-fix v8 studies; revised jobs flagged needs_provenance_review."}}
    decision_keys = {f.name for f in fields(AgentDecision)}
    for model in MODELS:
        arms = {}
        for arm in ("pre", "post"):
            suffix = "v8-20260905" if arm == "pre" else (
                "v8-revised-20260906" if model == "gpt-5-5" else "v8-revised-20260905")
            jid = model + "-" + suffix
            jp = ROOT / "runs/jobs" / jid / "job.json"
            job = json.loads(jp.read_text())
            ready = job["analysis_readiness"]
            assert ready["status"] == "ready" and ready["integrity"] == "clean"
            assert ready["completed_seeds"] == [11, 41] and ready["usage_coverage_pct"] == 100
            assert not ready["blockers"] and ready["transfer_accounting"]["complete"]
            pooled = Counter()
            cells = []
            for seed in (11, 41):
                folder = ROOT / "runs/managed" / jid / f"seed-{seed}"
                rp = folder / "run-report.json"
                report = json.loads(rp.read_text())
                snap = json.loads((folder / "run-snapshot.json").read_text())
                cohort = next(iter(report["benchmarks"]["cohorts"].values()))
                assert cohort["protocol_compliant"] and report["reliability"]["benchmark_integrity_status"] == "clean"
                events = [json.loads(line) for line in (folder / "run.jsonl").open()]
                observations = {(e["tick"], e["actor_id"]): e["data"]["observation"]["self"]
                                for e in events if e["type"] == "agent_observation"}
                decisions = defaultdict(dict)
                original_responses = {}
                for e in events:
                    if e["type"] == "agent_response":
                        key = (e["tick"], e["actor_id"])
                        assert key not in original_responses
                        original_responses[key] = e
                        decisions[e["tick"]][e["actor_id"]] = AgentDecision(
                            **{k: v for k, v in e["data"].items() if k in decision_keys})
                engine = WorldEngine.create(WorldConfig(**report["config"]),
                    [snap["agents"][f"agent-{i}"]["name"] for i in range(1, 11)])
                replay_responses = {}
                capacity = []
                health = []
                for tick in range(60):
                    living = {aid for aid, a in engine.state.agents.items() if a.alive}
                    assert set(decisions[tick]) == living
                    for aid in living:
                        assert engine.state.agents[aid].health == observations[tick, aid]["health"]
                    emitted = engine.tick(decisions[tick])
                    health.append(sum(a.health for a in engine.state.agents.values() if a.alive)/10)
                    for e in emitted:
                        if e.type == "agent_response":
                            row = e.to_dict()
                            key = (e.tick, e.actor_id)
                            replay_responses[key] = row
                            if arm == "post":
                                assert row["data"]["execution"] == original_responses[key]["data"]["execution"]
                        if e.type == "invalid_action" and "Not enough carrying capacity" in e.message:
                            capacity.append({"tick": e.tick, "actor": e.actor_id,
                                             "resource": e.data["action"].get("resource")})
                actual = engine.snapshot()
                assert all(actual[k] == snap[k] for k in actual), "Replay state diverged"
                raw = derive_outcome_counts(events, snap, member_ids=cohort["agents"],
                                            target_ticks=60, tail_ticks=12)
                raw.update(derive_action_execution_counts(replay_responses))
                for k, v in cohort["raw"].items():
                    if k.startswith("production_") and isinstance(v, (int, float)):
                        raw[k] = v
                assert abs(sum(health)*10 - raw["health_point_ticks"]) < 1e-8
                scores = score_outcome_production_counts(raw, execution_unit="action",
                                                        capability_aggregation="full_horizon_mean")
                if arm == "post":
                    for k in ("capability", "execution", "production"):
                        assert scores[k]["score"] == cohort["scores"][k]["score"]
                assert scores["production"]["score"] == cohort["scores"]["production"]["score"]
                pooled.update(raw)
                usage = [json.loads(line) for line in (folder/"run-usage.jsonl").open()]
                invalid = Counter(e["data"]["action"].get("type", "message") for e in events
                                  if e["type"] == "invalid_action")
                cell = {"seed": seed, "report": str(rp.relative_to(ROOT)),
                        "source": job["launch_commit"], "config": report["config"],
                        "model": cohort["model"], "provider": cohort["provider"], "effort": cohort["reasoning_effort"],
                        "readiness": ready["status"], "raw": dict(raw),
                        "scores": {k:v["score"] for k,v in scores.items()},
                        "original_scores": {k:v["score"] for k,v in cohort["scores"].items()},
                        "legacy_decision_execution": 100*raw["execution_valid_decisions"]/raw["execution_decisions"],
                        "replay_final_state_exact": True, "replay_health_trajectory_exact": True,
                        "health_by_completed_tick": health, "survivors": sum(a["alive"] for a in snap["agents"].values()),
                        "capacity_failures": len(capacity),
                        "capacity_affected_agents": len({x["actor"] for x in capacity}),
                        "capacity_failures_per_100_decisions": 100*len(capacity)/raw["execution_decisions"],
                        "invalid_actions_by_type": dict(invalid),
                        "production_by_source": cohort["raw"].get("production_by_source", {}),
                        "completed_structures": report["structures"]["complete"],
                        "static_prompt_hashes": sorted({u.get("static_prompt_sha256", "missing") for u in usage}),
                        "hashes": {f.name:digest(f) for f in [rp,folder/"run.jsonl",folder/"run-usage.jsonl",
                                                            folder/"run-snapshot.json",folder/"run-manifest.json"]}}
                assert cell["static_prompt_hashes"] and "missing" not in cell["static_prompt_hashes"]
                cells.append(cell)
            scores = score_outcome_production_counts(dict(pooled), execution_unit="action",
                                                    capability_aggregation="full_horizon_mean")
            arms[arm] = {"job": jid, "job_sha256": digest(jp), "cells":cells, "raw":dict(pooled),
                         "scores": {k:v["score"] for k,v in scores.items()},
                         "capacity_failures":sum(c["capacity_failures"] for c in cells),
                         "survivors":sum(c["survivors"] for c in cells),
                         "legacy_decision_execution":100*pooled["execution_valid_decisions"]/pooled["execution_decisions"]}
        for before, after in zip(arms["pre"]["cells"], arms["post"]["cells"]):
            assert before["config"] == after["config"]
            for k in ("model", "provider", "effort", "static_prompt_hashes"):
                assert before[k] == after[k], (model, k)
        arms["delta"] = {k:arms["post"]["scores"][k]-arms["pre"]["scores"][k]
                         for k in ("capability", "execution", "production")}
        result["models"][model] = arms
        print(model, "pre",arms["pre"]["scores"],"post",arms["post"]["scores"],
              "capacity",arms["pre"]["capacity_failures"],"->",arms["post"]["capacity_failures"],
              "survivors",arms["pre"]["survivors"],"->",arms["post"]["survivors"],flush=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n")

if __name__ == "__main__":
    main()
