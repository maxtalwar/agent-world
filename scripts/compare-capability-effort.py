"""Audit matched seed-11 medium/high experiments without model calls."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("5.5", "medium", "gpt-5-5-v8-revised-20260906"),
    ("5.5", "high", "gpt-5-5-v81-high-capability-probe-20260906"),
    ("5.4 Mini", "medium", "gpt-5-4-mini-v8-revised-20260905"),
    ("5.4 Mini", "high", "gpt-5-4-mini-v81-high-capability-probe-20260906"),
]

def main():
    rows = []
    configs = []
    static_hashes = set()
    for label, effort, job_id in CASES:
        folder = ROOT / "runs/managed" / job_id / "seed-11"
        paths = [folder / n for n in ("run-report.json", "run-manifest.json",
                 "run-usage.jsonl", "run.jsonl", "run-snapshot.json")]
        report, manifest = [json.loads(p.read_text()) for p in paths[:2]]
        usage, events = [[json.loads(line) for line in p.open()] for p in paths[2:4]]
        snapshot = json.loads(paths[4].read_text())
        cohort = next(iter(report["benchmarks"]["cohorts"].values()))
        raw = cohort["raw"]
        reliability = report["reliability"]
        assert manifest["status"] == "completed" and manifest["final_tick"] == 60
        assert not manifest["provenance"]["dirty_worktree"]
        assert reliability["benchmark_integrity_status"] == "clean"
        assert reliability["usage_record_coverage_pct"] == 100
        assert raw["external_decision_failures"] == raw["model_output_failures"] == 0
        assert len(usage) == raw["decisions"] == len({(u["tick"],u["agent_id"]) for u in usage})
        assert report["usage"]["attempts_without_usage"] == 0
        assert report["usage"]["discarded_calls"] == 0
        assert not report["usage"]["unknown_charge_exposure"]
        assert {u["reasoning_effort"] for u in usage} == {effort}
        assert {u["model"] for u in usage} == {cohort["model"]}
        assert {u["cli_version"] for u in usage} == {"codex-cli 0.147.0"}
        assert report["benchmarks"]["protocol"]["recipe_fingerprint_sha256"] == "8de610d3cd050f86bf4fb5e16a04708e069d099435b41d2729b4717d9a0da006"
        static_hashes.update(u["static_prompt_sha256"] for u in usage)
        configs.append(report["config"])
        obs = {(e["tick"], e["actor_id"]):e["data"]["observation"]["self"]
               for e in events if e["type"] == "agent_observation"}
        health = [sum((obs.get((t+1,a),{}).get("health",0) if t<59 else
                    snapshot["agents"][a]["health"] if snapshot["agents"][a]["alive"] else 0)
                    for a in cohort["agents"])/10 for t in range(60)]
        assert abs(sum(health)*10 - raw["health_point_ticks"]) < 1e-7
        damage = Counter()
        for e in events:
            if e["type"] == "survival_damage":
                damage.update(e["data"]["causes"])
        reasoning = [u["reasoning_tokens"] for u in usage]
        token_cost = report["usage"]["attempted_token_cost"]
        assert token_cost["available"] and not token_cost["unknown_models"]
        rows.append({
            "model": label, "effort": effort, "job": job_id,
            "source": manifest["provenance"]["git_sha"],
            "evidence_class": report["benchmarks"]["trial"]["certification"],
            "capability":100*raw["health_point_ticks"]/raw["health_point_tick_capacity"],
            "execution":100*raw["execution_valid_actions"]/raw["execution_actions"],
            "production":100*raw["production_value_added"]/raw["production_possible_agent_ticks"],
            "survivors": raw["living_agents"], "endpoint_health": health[-1],
            "season_health":[statistics.mean(health[i:i+12]) for i in range(0,60,12)],
            "health_by_tick":health, "reasoning_mean":statistics.mean(reasoning),
            "zero_reasoning_pct":100*reasoning.count(0)/len(reasoning),
            "mean_decision_seconds":statistics.mean(u["duration_seconds"] for u in usage),
            "api_equivalent_cost_usd":token_cost["cost_usd"]["total"],
            "cost_per_decision_usd":token_cost["cost_usd"]["total"]/len(usage),
            "calls":len(usage), "damage_cause_events":dict(damage),
            "structures":report["structures"]["complete"],
            "production_by_source":raw["production_by_source"],
            "trades_accepted":cohort["diagnostics"]["trades_accepted"],
            "gifts":cohort["diagnostics"]["gifts"],
            "groups_created":cohort["diagnostics"]["groups_created"],
            "valid_actions_per_decision":raw["execution_valid_actions"]/len(usage),
            "action_point_overruns":raw["action_point_overruns"],
            "integrity":"clean", "usage_coverage_pct":100,
            "model_provenance":"requested_only",
            "report":str(paths[0].relative_to(ROOT)),
            "hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        })
    assert all(c == configs[0] for c in configs)
    assert len(static_hashes) == 1
    old, new = rows[2]["source"], rows[3]["source"]
    changed = subprocess.check_output(["git","diff","--name-only",old,new,"--","agent_world"],cwd=ROOT,text=True).splitlines()
    assert changed == ["agent_world/managed_runs.py"], changed
    result = {"scope":"Four seed-11 worlds; diagnostic effort comparison; historical medium baselines",
              "world_configs_identical":True, "static_prompt_sha256":next(iter(static_hashes)),
              "mini_source_changes_in_package":changed, "rows":rows}
    (ROOT/"docs/capability-effort-comparison.json").write_text(json.dumps(result,indent=2)+"\n")
    lines = ["# Capability effort comparison", "",
        "Matched seed 11, 60 ticks, ten agents; diagnostic experiments versus historical medium baselines.",
        "All four completed with clean integrity, 100% decision usage coverage, zero output/provider/harness",
        "failures and no discarded or unaccounted attempts. Requested model identity is retained;",
        "the CLI does not independently return serving model or observed effort. All use Codex CLI 0.147.0.",
        "World configs and static prompt hashes match. Both high runs and 5.5 medium pin 39232e4.",
        "Mini medium pins 783341a; the only intervening package change is managed-launch PATH capture",
        "and preflight validation, not engine, prompt, parser, connector or scoring changes.",
        "High runs are diagnostic_only; benchmark fingerprint/effort flags do not invalidate this",
        "deliberately non-benchmark comparison. Do not add them to the medium leaderboard.", "",
        "| Model | Effort | Capability | Execution | Production | Survivors | Reasoning/call | Seconds/decision | API-equivalent $/world |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f'| {r["model"]} | {r["effort"]} | {r["capability"]:.2f} | {r["execution"]:.2f} | {r["production"]:.2f} | {r["survivors"]}/10 | {r["reasoning_mean"]:.0f} | {r["mean_decision_seconds"]:.2f} | {r["api_equivalent_cost_usd"]:.2f} |')
    lines += ["", "Costs use each frozen report's September 5 rate card, not current prices or subscription charges.",
              "Longer survival increases decision count, so full-world cost changes also reflect more decisions.", "",
              "## Behavioral diagnostics", ""]
    for r in rows:
        lines += [f'### {r["model"]} {r["effort"]}',"",
            f'- Season mean health: {", ".join(f"{h:.2f}" for h in r["season_health"])}.',
            f'- Completed structures: {r["structures"]}. Production by source: {r["production_by_source"]}.',
            f'- Damage cause occurrences (causes can overlap): {r["damage_cause_events"]}.',
            f'- Zero-reasoning calls: {r["zero_reasoning_pct"]:.2f}%; successful actions per decision: {r["valid_actions_per_decision"]:.2f}.',
            f'- Accepted trades: {r["trades_accepted"]}; gifts: {r["gifts"]}; groups: {r["groups_created"]}.',
            f'- Evidence: [{r["job"]}](../{r["report"]}).',""]
    lines += ["## Interpretation and limits","",
        "5.5 gains 16.85 Capability points; Mini gains 11.01. The gap widens from 2.36 to",
        "8.20, a 5.84-point difference in observed effort gains. Production rises 45.87%",
        "for 5.5 and 41.46% for Mini. Most health separation emerges after the first season.",
        "Both models improve in Capability and Production. 5.5 gains more Capability, while Mini's",
        "Execution slightly decreases despite substantially better survival and output. Thus a higher",
        "valid-action fraction alone does not explain improvement. This supports preserving Execution",
        "as a separate narrow metric rather than using it to predetermine Capability.",
        "The same fixed Capability formula already distinguishes the high-effort outcomes; a score",
        "redesign is not required to reveal this gap. Healing remains a separate world-design question.",
        "Both models allocate more reasoning. 5.5 remains much more token-frugal even at high.",
        "This strengthens the under-deliberation hypothesis, but does not establish that every score",
        "difference is caused by reasoning tokens. There is one world per condition and historical",
        "rather than randomized repeated baselines; ten interacting agents are not ten independent",
        "replications. Do not compare high seed 11 against pooled medium seeds 11/41.",
        "High is a promising experimental setting, not grounds on its own to change the baseline",
        "for every provider. No new world mechanics or scoring changes were made.","",
        "Reproduce: python3 scripts/compare-capability-effort.py. Exact numerators, derived metrics,",
        "per-tick trajectories, provenance and evidence hashes are in capability-effort-comparison.json.",""]
    (ROOT/"docs/capability-effort-comparison.md").write_text("\n".join(lines))
    for r in rows:
        print(json.dumps({k:v for k,v in r.items() if k not in ["hashes","health_by_tick","report"]}))
if __name__ == "__main__":
    main()
