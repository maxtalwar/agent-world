"""Versioned post-hoc capability projections; never alter frozen run evidence."""
from __future__ import annotations
import hashlib
import json
import math
from functools import lru_cache
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def policies(root):
    path = Path(root) / "data/run-sources.json"
    if not path.exists():
        return {}
    specs = json.loads(path.read_text()).get("capability_reanalyses", [])
    result = {}
    for spec in specs:
        validate_policy(spec)
        if spec["source_recipe"] in result:
            raise ValueError("Multiple active capability reanalyses for one recipe")
        result[spec["source_recipe"]] = spec
    return result


def validate_policy(spec):
    for key in ("horizon", "season_length_ticks"):
        if type(spec.get(key)) is not int or spec[key] <= 0:
            raise ValueError("Invalid reanalysis horizon/season length")
    if type(spec.get("season_index")) is not int or not 0 <= spec["season_index"] <= 3:
        raise ValueError("Invalid season index")
    multiplier = spec.get("season_damage_multiplier")
    if type(multiplier) not in (int, float) or not math.isfinite(multiplier) or multiplier < 1:
        raise ValueError("Season damage multiplier must be finite and at least one")
    if not spec.get("id") or not spec.get("source_recipe") or not spec.get("source_recipe_digest"):
        raise ValueError("Reanalysis requires a version and exact source recipe identity")
    seeds = spec.get("required_seeds")
    if not isinstance(seeds, list) or not seeds or any(type(x) is not int for x in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Invalid required reanalysis seeds")
    season_ticks(spec)


def season_ticks(spec):
    length, horizon = spec["season_length_ticks"], spec["horizon"]
    starts = [t for t in range(0, horizon, length) if (t // length) % 4 == spec["season_index"] and t + length <= horizon]
    if not starts:
        raise ValueError("No complete requested season in the run")
    start = starts[-1]
    # End-of-tick health for season actions t=start..start+length-1.
    return list(range(start + 1, start + length + 1))


def formula(spec):
    extra = spec["season_damage_multiplier"] - 1
    return (f"Final original-population health minus {extra:.0%} of health lost during the last "
            f"{spec['season_name']} per original agent; minimum zero")


def health_counts(report, snapshot, events, spec):
    validate_policy(spec)
    protocol = report.get("benchmarks", {}).get("protocol", {})
    if protocol.get("id") != spec["source_recipe"] or protocol.get("recipe_fingerprint_sha256") != spec["source_recipe_digest"]:
        raise ValueError("Source recipe identity does not match scoring revision")
    if not report.get("run", {}).get("completed") or report["run"]["target_ticks"] != spec["horizon"]:
        raise ValueError("Capability reanalysis requires completed source evidence")
    if report["config"].get("health_regen_rate", 0) != 0:
        raise ValueError("This scoring revision applies only to the original no-healing world")
    if report["config"]["season_length_ticks"] != spec["season_length_ticks"]:
        raise ValueError("Source season length differs from scoring revision")
    cohorts = report["benchmarks"]["cohorts"]
    if len(cohorts) != 1:
        raise ValueError("Reanalysis requires a uniform benchmark population")
    cohort = next(iter(cohorts.values()))
    members = cohort["agents"]
    if not members or len(members) != len(set(members)):
        raise ValueError("Missing original population")
    health, deaths = {}, {}
    for event in events:
        actor = event.get("actor_id")
        if actor not in members:
            continue
        tick = event.get("tick", 0)
        if event["type"] == "death":
            deaths[actor] = min(tick, deaths.get(actor, tick))
        elif event["type"] == "agent_observation":
            value = event["data"]["observation"]["self"]["health"]
            if (tick, actor) in health and health[tick, actor] != value:
                raise ValueError("Conflicting health observations")
            health[tick, actor] = value
    curve = []
    for tick in range(1, spec["horizon"] + 1):
        total = 0.0
        for actor in members:
            dead = actor in deaths and deaths[actor] < tick
            if tick == spec["horizon"]:
                terminal = snapshot["agents"][actor]
                if bool(terminal["alive"]) == dead:
                    raise ValueError("Death ledger disagrees with final snapshot")
                value = terminal["health"] if terminal["alive"] else 0
            elif dead:
                value = 0
            else:
                if (tick, actor) not in health:
                    raise ValueError(f"Missing living health evidence at {tick}/{actor}")
                value = health[tick, actor]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError("Invalid population health")
            total += value
        curve.append(total)
    raw = cohort["raw"]
    if not math.isclose(sum(curve), raw["health_point_ticks"]) or not math.isclose(curve[-1], raw["endpoint_health_points"]):
        raise ValueError("Health reconstruction disagrees with frozen report")
    selected = season_ticks(spec)
    start = selected[0] - 1
    before = curve[start - 1] if start else 100 * len(members)
    after = curve[selected[-1] - 1]
    winter_damage = before - after
    if winter_damage < 0:
        raise ValueError("Health increased in a no-healing winter")
    return {"seed": report["config"]["seed"], "model": cohort["model"],
            "endpoint_points": curve[-1], "endpoint_capacity": 100 * len(members),
            "season_damage_points": winter_damage, "season_start_health_points": before, "season_end_health_points": after,
            "full_points": sum(curve), "full_capacity": 100 * len(members) * len(curve),
            "season_completed_ticks": selected, "curve": curve}


def score_counts(counts, spec):
    def pct(n, d):
        a, b = counts[n], counts[d]
        if not math.isfinite(a) or not math.isfinite(b) or b <= 0 or not 0 <= a <= b:
            raise ValueError("Invalid reanalysis counts")
        return 100 * a / b
    endpoint = pct("endpoint_points", "endpoint_capacity")
    winter_damage = pct("season_damage_points", "endpoint_capacity")
    penalty = float((Decimal(str(spec["season_damage_multiplier"])) - 1) * Decimal(str(winter_damage)))
    before_floor = float(Decimal(str(endpoint)) - Decimal(str(penalty)))
    value = max(0.0, before_floor)
    return {"score": float(Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)), "unrounded_score": value, "formula": formula(spec),
            "endpoint": endpoint, "winter_damage": winter_damage, "winter_surcharge": penalty,
            "pre_floor_score": before_floor, "floor_applied": before_floor < 0,
            "original_full_horizon": pct("full_points", "full_capacity")}



@lru_cache(maxsize=256)
def _cell(root, relative, policy_json, signatures):
    folder = Path(root) / relative
    report, snapshot = [json.loads(folder.with_name(name).read_text()) for name in ("run-report.json", "run-snapshot.json")]
    event_path = folder.with_name("run.jsonl")
    events = [json.loads(line) for line in event_path.read_text().splitlines()]
    result = health_counts(report, snapshot, events, json.loads(policy_json))
    result["report_path"] = relative
    result["report_sha256"] = hashlib.sha256(folder.read_bytes()).hexdigest()
    result["events_sha256"] = hashlib.sha256(event_path.read_bytes()).hexdigest()
    result["source"] = report.get("source")
    return result


def rescore(root, report_paths, spec):
    root = Path(root).resolve()
    results = []
    for value in report_paths:
        path = Path(value)
        path = path.resolve() if path.is_absolute() else (root / path).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Reanalysis evidence must remain inside the repository")
        siblings = [path, path.with_name("run-snapshot.json"), path.with_name("run.jsonl")]
        signatures = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in siblings)
        results.append(_cell(str(root), str(path.relative_to(root)), json.dumps(spec, sort_keys=True), signatures))
    if sorted(r["seed"] for r in results) != sorted(spec["required_seeds"]):
        raise ValueError("Reanalysis requires exactly the required original seeds")
    if len({r["model"] for r in results}) != 1:
        raise ValueError("Cannot pool different models")
    pooled = {key: sum(r[key] for r in results) for key in ("endpoint_points", "endpoint_capacity", "season_damage_points", "season_start_health_points", "season_end_health_points", "full_points", "full_capacity")}
    return {"policy_id": spec["id"], "source_recipe": spec["source_recipe"], "capability": score_counts(pooled, spec),
            "raw": pooled, "cells": [{**r, "capability": score_counts(r, spec)} for r in results]}
