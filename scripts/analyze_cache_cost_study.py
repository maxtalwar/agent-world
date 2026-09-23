"""Reproduce the bounded 2026-09-22 native cache-cost study (no model calls)."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
BASELINES = {
    "astra": "runs/managed/gpt-6-astra-v8-revised-20260907/seed-11/run-usage.jsonl",
    "sol56": "runs/benchmarks/gpt-5-6-sol-participant-v6-provisional-seed11-20260728-195329/seed-11/run-usage.jsonl",
}
MODELS = {"astra": "gpt-6-astra", "sol56": "gpt-5.6-sol"}
RATES = {"astra": [10, 1, 12.5, 50], "sol56": [4, .4, 5, 20]}
OLD_RATES = {"astra": RATES["astra"], "sol56": [5, .5, 6.25, 30]}
FIELDS = ("prompt_tokens", "cached_tokens", "cache_write_tokens", "completion_tokens")


def cost(row, rates):
    prompt, cached, writes, output = (row.get(k, 0) for k in FIELDS)
    if min(prompt, cached, writes, output) < 0 or cached + writes > prompt:
        raise ValueError("Invalid token accounting")
    input_cost = ((prompt - cached - writes) * rates[0]
                  + cached * rates[1] + writes * rates[2]) / 1e6
    return {"input": input_cost, "output": output * rates[3] / 1e6,
            "total": input_cost + output * rates[3] / 1e6}


def summarize(rows, rates):
    totals = {key: sum(row.get(key, 0) for row in rows) for key in FIELDS}
    return {"calls": len(rows), **totals, "usd": cost(totals, rates),
            "cache_read_calls": sum(row.get("cached_tokens", 0) > 0 for row in rows),
            "cache_read_histogram": dict(Counter(row.get("cached_tokens", 0) for row in rows))}


def comparison(before, after):
    return {"before_usd": before, "after_usd": after,
            "saving_usd": before - after,
            "saving_percent": 100 * (before - after) / before}


def historical_projection(history, fresh, fork, templates, rates, cache_override=None):
    """Sensitivity only: retain old observations/output; transplant fork cache."""
    overhead = mean(r["prompt_tokens"] for r in fork) - mean(r["prompt_tokens"] for r in fresh)
    cache_values = ([cache_override] if cache_override is not None
                    else [r.get("cached_tokens", 0) for r in fork])
    write_values = [r.get("cache_write_tokens", 0) for r in fork]
    projected = 0
    # Average every historical row over the empirical cache distribution rather
    # than imposing an invented correspondence between old and new decisions.
    for row in history:
        prompt = row["prompt_tokens"] + overhead
        for cached in cache_values:
            for writes in write_values:
                cached = min(prompt, cached)
                projected += cost({
                    "prompt_tokens": prompt, "cached_tokens": cached,
                    "cache_write_tokens": min(prompt - cached, writes),
                    "completion_tokens": row["completion_tokens"],
                }, rates)["total"] / (len(cache_values) * len(write_values))
    projected += summarize(templates, rates)["usd"]["total"]
    return comparison(summarize(history, rates)["usd"]["total"], projected)


def analyze(root=ROOT):
    evidence = {}

    def read(path, lines=False):
        raw = (root / path).read_bytes()
        evidence[str(path)] = hashlib.sha256(raw).hexdigest()
        return ([json.loads(line) for line in raw.splitlines()]
                if lines else json.loads(raw))

    models = {}
    for tag, baseline in BASELINES.items():
        arms = {}
        for mode in ("fresh", "fork"):
            run_id = f"cache-{tag}-{mode}-20260922"
            job = Path("runs/jobs") / run_id
            heartbeat = read(job / "controller-heartbeat.json")
            if heartbeat["controller_status"] != "completed":
                raise ValueError(f"{run_id} is not completed")
            manifest = read(job / "job.json")
            report = read(Path("runs/managed") / run_id / "seed-11/run-report.json")
            reliability = report["reliability"]
            if (not report["run"]["completed"] or report["run"]["final_tick"] != 1
                    or reliability["decision_attempts"] != 10
                    or reliability["decision_failure_rate_pct"] != 0
                    or reliability["usage_record_coverage_pct"] != 100):
                raise ValueError("Incomplete or failed diagnostic decisions")
            rows = read(Path("runs/managed") / run_id / "seed-11/run-usage.jsonl", True)
            decisions = [r for r in rows if r.get("agent_id") is not None]
            templates = [r for r in rows if r.get("usage_kind") == "cache_template"]
            if len(decisions) != 10 or len(templates) != (mode == "fork"):
                raise ValueError(f"{run_id}: unexpected call coverage")
            if len(rows) != len(decisions) + len(templates):
                raise ValueError("Unclassified usage")
            if any(r["model"] != MODELS[tag] or r["reasoning_effort"] != "medium"
                   or r["cli_version"] != "codex-cli 0.156.0" for r in rows):
                raise ValueError("Model/effort/CLI mismatch")
            keys = {(r["agent_id"], r["tick"]): r["request_sha256"] for r in decisions}
            if len(keys) != 10 or {k[1] for k in keys} != {0}:
                raise ValueError("Duplicate decisions or unexpected ticks")
            if mode == "fork":
                if len({r["codex_session_id"] for r in decisions}) != 10:
                    raise ValueError("Fork sessions are not independent")
                if {r.get("cache_template_session_id") for r in decisions} != {templates[0]["codex_session_id"]}:
                    raise ValueError("Fork template mismatch")
                if any(r.get("codex_usage_scope") != "fork_delta" for r in decisions):
                    raise ValueError("Cumulative fork usage was not differenced")
            arms[mode] = {"rows": rows, "decisions": decisions, "templates": templates,
                          "keys": keys, "commit": manifest["launch_commit"],
                          "reliability": reliability}
        fresh, fork = arms["fresh"], arms["fork"]
        if fresh["keys"] != fork["keys"] or fresh["commit"] != fork["commit"]:
            raise ValueError("Unmatched prompts or source")
        history = read(Path(baseline), True)
        initial = [r for r in history if r["tick"] == 0]
        if {(r["agent_id"], r["tick"]): r["request_sha256"] for r in initial} != fresh["keys"]:
            raise ValueError("Historical startup observations differ")
        growth = mean(r["prompt_tokens"] for r in history) - mean(r["prompt_tokens"] for r in initial)
        result = {"source_commit": fresh["commit"], "matched_observations": 10,
                  "historical_startup_prompts_match": True,
                  "historical_mean_prompt_growth_tokens": growth,
                  "reliability": {mode: arm["reliability"] for mode, arm in arms.items()},
                  "static_prompt_hashes": {
                      "historical": sorted({r.get("static_prompt_sha256", "") for r in history}),
                      "current": sorted({r.get("static_prompt_sha256", "") for r in fresh["decisions"]})},
                  "historical_calls": len(history), "historical_usage": baseline,
                  "mean_fork_extra_input_tokens": mean(r["prompt_tokens"] for r in fork["decisions"])
                  - mean(r["prompt_tokens"] for r in fresh["decisions"]), "price_cards": {}}
        for name, rates in (("current", RATES[tag]), ("legacy_price_sensitivity", OLD_RATES[tag])):
            fs = summarize(fresh["decisions"], rates)
            ks = summarize(fork["decisions"], rates)
            ts = summarize(fork["templates"], rates)
            hs = summarize(history, rates)
            count = len(history)
            fixed_output = hs["usd"]["output"]
            forward = comparison(count * fs["usd"]["input"] / 10 + fixed_output,
                                 count * ks["usd"]["input"] / 10 + fixed_output + ts["usd"]["total"])
            growth_cost = count * growth * rates[0] / 1e6
            growth_adjusted = comparison(forward["before_usd"] + growth_cost,
                                         forward["after_usd"] + growth_cost)
            result["price_cards"][name] = {
                "rates_per_million_input_cached_write_output": rates,
                "fresh": fs, "fork_decisions": ks, "template": ts, "historical": hs,
                "observed_total": comparison(fs["usd"]["total"], ks["usd"]["total"] + ts["usd"]["total"]),
                "decision_input_only": comparison(fs["usd"]["input"], ks["usd"]["input"]),
                "startup_input_extrapolation_fixed_historical_output": forward,
                "prompt_growth_adjusted_current_cli_projection": growth_adjusted,
                "historical_vs_current_fork_projection": comparison(hs["usd"]["total"], growth_adjusted["after_usd"]),
                "historical_ledger_sensitivity": historical_projection(history, fresh["decisions"], fork["decisions"], fork["templates"], rates),
                "historical_all_miss_sensitivity": historical_projection(history, fresh["decisions"], fork["decisions"], fork["templates"], rates, 0),
                "historical_all_hit_sensitivity": historical_projection(history, fresh["decisions"], fork["decisions"], fork["templates"], rates, max(r["cached_tokens"] for r in fork["decisions"])),
            }
        models[tag] = result
    return {"schema_version": 1, "study_date": "2026-09-22",
            "basis": "API equivalent, not provider charge or subscription quota",
            "models": models, "source_sha256": evidence}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(analyze(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")
