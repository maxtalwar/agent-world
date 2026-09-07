"""Zero-model-call audit of health discrimination in completed v8.1 studies."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import statistics

ROOT = Path(__file__).resolve().parents[1]
STUDIES = {
    "gpt-5.6-sol": "gpt-5-6-sol-v8-revised-20260906",
    "gpt-5.6-terra": "gpt-5-6-terra-v8-revised-20260905",
    "gpt-5.6-luna": "gpt-5-6-luna-v8-revised-20260905",
    "gpt-5.5": "gpt-5-5-v8-revised-20260906",
    "gpt-5.4-mini": "gpt-5-4-mini-v8-revised-20260905",
}

def audit():
    result = {"evidence_class": "offline_capability_construct_audit", "studies": {}}
    for model, job_id in STUDIES.items():
        job = json.loads((ROOT/"runs/jobs"/job_id/"job.json").read_text())
        ready = job["analysis_readiness"]
        assert ready["status"] == "ready" and ready["integrity"] == "clean"
        assert ready["usage_coverage_pct"] == 100 and not ready["blockers"]
        cells = []
        for seed in (11, 41):
            folder = ROOT/"runs/managed"/job_id/f"seed-{seed}"
            report = json.loads((folder/"run-report.json").read_text())
            snapshot = json.loads((folder/"run-snapshot.json").read_text())
            cohort = next(iter(report["benchmarks"]["cohorts"].values()))
            events = [json.loads(s) for s in (folder/"run.jsonl").open()]
            obs = {(e["tick"],e["actor_id"]): e["data"]["observation"]["self"]
                   for e in events if e["type"] == "agent_observation"}
            damage = {(e["tick"],e["actor_id"]): e["data"]
                      for e in events if e["type"] == "survival_damage"}
            assert sum(e["type"]=="survival_damage" for e in events) == len(damage)
            health = []
            alive_ticks = safe_ticks = 0
            weighted_loss = Counter()
            loss = Counter()
            cause_occurrences = Counter()
            for tick in range(60):
                total = 0
                for aid in cohort["agents"]:
                    before = obs.get((tick,aid),{}).get("health",0)
                    after = (obs.get((tick+1,aid),{}).get("health",0) if tick<59
                             else snapshot["agents"][aid]["health"] if snapshot["agents"][aid]["alive"] else 0)
                    assert 0 <= after <= before <= 100
                    total += after
                    alive_ticks += after > 0
                    safe_ticks += after > 0 and (tick,aid) not in damage
                    if before > after:
                        e = damage[tick,aid]
                        assert after == e["health"]
                        causes = "+".join(sorted(e["causes"]))
                        loss[causes] += before-after
                        weighted_loss[causes] += (before-after)*(60-tick)/600
                        cause_occurrences.update(e["causes"])
                health.append(total/10)
            raw = cohort["raw"]
            assert abs(sum(health)*10-raw["health_point_ticks"])<1e-7
            assert abs(statistics.mean(health)-(100-sum(weighted_loss.values())))<1e-7
            usage = [json.loads(s) for s in (folder/"run-usage.jsonl").open()]
            reasoning = [u["reasoning_tokens"] for u in usage if u.get("reasoning_tokens") is not None]
            assert len(reasoning)==len(usage)
            cells.append({
                "seed": seed, "source": job["launch_commit"], "health_mean": statistics.mean(health),
                "alive_completed_agent_ticks": alive_ticks, "possible_agent_ticks":600,
                "alive_tick_pct":100*alive_ticks/600,
                "conditional_alive_health":sum(health)*10/alive_ticks,
                "damage_free_alive_tick_pct":100*safe_ticks/600,
                "health_by_tick":health,
                "season_health":[statistics.mean(health[i:i+12]) for i in range(0,60,12)],
                "endpoint_health":health[-1],
                "survivors":sum(a["alive"] for a in snapshot["agents"].values()),
                "actual_health_loss_by_joint_cause":dict(loss),
                "capability_penalty_by_joint_cause":dict(weighted_loss),
                "damage_cause_occurrences":dict(cause_occurrences),
                "reasoning_mean":statistics.mean(reasoning), "reasoning_median":statistics.median(reasoning),
                "reasoning_zero_count":reasoning.count(0), "reasoning_calls":len(reasoning),
                "reasoning_sum":sum(reasoning),
                "production":cohort["scores"]["production"]["score"],
                "structures": report["structures"]["complete"],
                "raw":raw,
                "hashes": {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                           [folder/"run-report.json",folder/"run.jsonl",folder/"run-snapshot.json",folder/"run-usage.jsonl"]},
                "report":str((folder/"run-report.json").relative_to(ROOT)),
            })
        total_alive = sum(c["alive_completed_agent_ticks"] for c in cells)
        total_hp = sum(sum(c["health_by_tick"])*10 for c in cells)
        summary = {
            "capability":total_hp/1200,
            "alive_tick_pct":100*total_alive/1200,
            "conditional_alive_health":total_hp/total_alive,
            "damage_free_alive_tick_pct":statistics.mean(c["damage_free_alive_tick_pct"] for c in cells),
            "survivors":sum(c["survivors"] for c in cells),
            "reasoning_mean":sum(c["reasoning_sum"] for c in cells)/sum(c["reasoning_calls"] for c in cells),
            "reasoning_zero_pct":100*sum(c["reasoning_zero_count"] for c in cells)/sum(c["reasoning_calls"] for c in cells),
            "production":statistics.mean(c["production"] for c in cells),
            "season_health":[statistics.mean(c["season_health"][i] for c in cells) for i in range(5)],
        }
        result["studies"][model] = {"job":job_id,"cells":cells,"summary":summary}
        print(model,json.dumps(summary),flush=True)

    # Stylized policy experiment, not a counterfactual model/world run.
    toy = {}
    for policy in ("no_mistakes","early_damage_then_stable","persistent_damage"):
        for recovery in ("none","two_on_damage_free_ticks","two_every_tick"):
            hp=100;series=[]
            for t in range(1,61):
                dmg = (20 if t==10 else 0) if policy=="early_damage_then_stable" else (
                    1 if policy=="persistent_damage" and t>=10 else 0)
                hp=max(0,hp-dmg)
                if hp>0 and (recovery=="two_every_tick" or
                             (recovery=="two_on_damage_free_ticks" and dmg==0)):
                    hp=min(100,hp+2)
                series.append(hp)
            toy[policy+"/"+recovery]={"mean_health":statistics.mean(series),"endpoint":hp}
    result["toy_recovery"] = toy
    return result

if __name__ == "__main__":
    out = ROOT/"docs/capability-health-audit.json"
    out.write_text(json.dumps(audit(),indent=2)+"\n")
