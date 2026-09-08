#!/usr/bin/env python3
"""Audit gross damage/recovery in the paired regeneration pilot without model calls.

Run from the repository root. Reads actual completed reports/ledgers; the earlier
trajectory artifact supplies only the explicit list of cells, never current scores.
"""
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path


def analyze(base):
    folder = Path(base["path"])
    report_path = folder / "run-report.json"
    event_path = folder / "run.jsonl"
    report = json.loads(report_path.read_text())
    assert report["run"]["completed"], str(folder)
    horizon = report["run"]["final_tick"]
    assert horizon == report["run"]["target_ticks"] == 60
    raw = report["benchmarks"]["cohorts"]["cohort-1"]["raw"]
    quality = report["reliability"]
    assert quality["benchmark_integrity_status"] == "clean"
    assert quality["usage_record_coverage_pct"] == 100
    events = [json.loads(line) for line in event_path.read_text().splitlines()]
    starts = [e for e in events if e["type"] == "agent_spawned"]
    assert len(starts) == raw["initial_agents"] == 10
    health = {e["actor_id"]: e["data"]["agent"]["health"] for e in starts}
    assert all(h == 100 for h in health.values())
    agents = {aid: {"damage": 0, "nominal_damage": 0, "healed": 0,
                    "alive_ticks": 0, "death_tick": None} for aid in health}
    alive = set(health)
    by_tick = collections.defaultdict(list)
    for event in events:
        if 0 <= event["tick"] < horizon:
            by_tick[event["tick"]].append(event)
    damage_curve, healed_curve, health_curve, living_start_curve = [], [], [], []
    causes = collections.Counter()
    for tick in range(horizon):
        living_start_curve.append(len(alive))
        for aid in alive:
            agents[aid]["alive_ticks"] += 1
        damage = healed = 0
        for event in by_tick[tick]:
            aid, data, kind = event.get("actor_id"), event.get("data", {}), event["type"]
            if kind == "survival_damage":
                loss = health[aid] - data["health"]
                assert 0 <= loss <= data["damage"]
                agents[aid]["damage"] += loss
                agents[aid]["nominal_damage"] += data["damage"]
                damage += loss
                health[aid] = data["health"]
                causes.update(data["causes"])
            elif kind in ("health_recovery", "health_recovery_check"):
                restored = data.get("restored", 0)
                assert data["health"] == health[aid] + restored
                agents[aid]["healed"] += restored
                healed += restored
                health[aid] = data["health"]
            elif kind == "death":
                assert health[aid] == 0
                alive.remove(aid)
                agents[aid]["death_tick"] = tick
        damage_curve.append(damage)
        healed_curve.append(healed)
        health_curve.append(sum(health.values()))
    for aid, record in agents.items():
        record["final_health"] = health[aid]
        assert 100 - record["damage"] + record["healed"] == health[aid]
    assert sum(health_curve) == raw["health_point_ticks"]
    assert health_curve[-1] == raw["endpoint_health_points"]
    assert len(alive) == raw["living_agents"]
    assert sum(living_start_curve) == raw["decisions"]
    penalty = sum(d * (horizon - t) for t, d in enumerate(damage_curve)) / (10 * horizon)
    credit = sum(h * (horizon - t) for t, h in enumerate(healed_curve)) / (10 * horizon)
    score = sum(health_curve) / (10 * horizon)
    assert abs(score - (100 - penalty + credit)) < 1e-9
    return {"model": base["model"], "healing": base["healing"], "seed": base["seed"],
            "path": str(folder), "horizon": horizon, "agents": agents,
            "damage": sum(damage_curve), "nominal_damage": sum(a["nominal_damage"] for a in agents.values()),
            "restored": sum(healed_curve), "alive_ticks": sum(living_start_curve),
            "survivors": len(alive), "final_health": health_curve[-1], "health_score": score,
            "weighted_damage_penalty": penalty, "weighted_healing_credit": credit,
            "damage_curve": damage_curve, "healed_curve": healed_curve,
            "health_curve": health_curve, "living_start_curve": living_start_curve,
            "damage_cause_event_counts": dict(causes), "reliability": quality,
            "source": report["source"], "config": report["config"],
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "events_sha256": hashlib.sha256(event_path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(Path("docs/regeneration-health-trajectories.json").read_text())["cells"]
    cells = [analyze(base) for base in inventory]
    summary = {}
    for model in dict.fromkeys(c["model"] for c in cells):
        summary[model] = {}
        for enabled in (False, True):
            group = [c for c in cells if c["model"] == model and c["healing"] == enabled]
            assert len(group) == 2 and {c["seed"] for c in group} == {11, 41}
            summary[model]["on" if enabled else "off"] = {
                **{key: sum(c[key] for c in group) for key in
                   ("damage", "nominal_damage", "restored", "alive_ticks", "survivors", "final_health")},
                **{key: sum(c[key] for c in group) / 2 for key in
                   ("health_score", "weighted_damage_penalty", "weighted_healing_credit")},
                "first24_damage": sum(sum(c["damage_curve"][:24]) for c in group),
                "first24_healed": sum(sum(c["healed_curve"][:24]) for c in group),
                "near_full_health_final_agents": sum(a["final_health"] >= 90 for c in group for a in c["agents"].values())}
            assert all(c["living_start_curve"][:24] == [10] * 24 for c in group)
        for seed in (11, 41):
            a, b = [next(c for c in cells if c["model"] == model and c["seed"] == seed and c["healing"] == enabled) for enabled in (False, True)]
            differences = {k for k in a["config"].keys() | b["config"].keys() if a["config"].get(k) != b["config"].get(k)}
            assert differences == {"health_regen_rate", "health_regen_reserve_fraction", "health_regen_stable_ticks"}
    result = {"analyzed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "method": "Actual clipped HP loss; nominal damage retained separately. Per-original-agent totals use 20 agents per paired condition. Live exposure includes the death tick. Weighted damage/healing exactly reconcile the existing health score; they are accounting components, not counterfactual simulations or new benchmark scores.",
              "summary": summary, "cells": cells}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print("Validated 20 completed cells, 200 agent health balances, report totals and score decomposition.")


if __name__ == "__main__":
    main()
