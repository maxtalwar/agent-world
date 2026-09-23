"""Offline analysis of the counterbalanced Codex and historical Claude study."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.analyze_cache_cost_study import summarize


CLAUDE_RUNS = (
    "web-claude-fable-5-1-22113c5f3d1f:seed-41",
    "claude-fable-5-v81-20260907:seed-41",
    "web-claude-opus-5-1m-680839180c53:seed-11",
    "web-claude-opus-5-1m-680839180c53:seed-41",
    "claude-fable-5:seed-11", "claude-fable-5:seed-41",
    "claude-opus-5:seed-11", "claude-opus-5:seed-41",
)
MODELS = ("gpt-6-astra", "gpt-5.6-sol")
RATES = {"gpt-6-astra": [10, 1, 12.5, 50], "gpt-5.6-sol": [4, .4, 5, 20]}


def ttl_estimate(rows, rates):
    if any("cache_write_tokens" not in r for r in rows):
        return {"available": False, "reason": "Historical cache-write counts were not retained",
                "known_write_rows": sum("cache_write_tokens" in r for r in rows),
                "calls": len(rows)}
    five = summarize(rows, rates)
    one_rates = [rates[0], rates[1], rates[0] * 2, rates[3]]
    one = summarize(rows, one_rates)
    delta = one["usd"]["total"] - five["usd"]["total"]
    return {"available": True, "historical_ttl_verified": False,
            "assumption": "All recorded writes move from 1h to 5m; read/output budgets unchanged",
            "five_minute": five, "conditional_one_hour": one,
            "saving_usd": delta, "saving_percent": 100 * delta / one["usd"]["total"],
            "rates_per_million_input_cached_5mwrite_output": rates}


def cache_class(cached, template_input):
    # Provider counters expose token counts, not the exact cached text. A
    # near-template read is a full-prefix proxy allowing cache-block rounding.
    if cached == 0:
        return "miss"
    return "near_template" if cached >= template_input - 256 else "partial"


def refresh_projection(prior, mapped_cached_tokens):
    """Transfer hit frequencies, retaining the original matched input budgets."""
    rates = prior["rates_per_million_input_cached_write_output"]
    old_mean = prior["fork_decisions"]["cached_tokens"] / prior["fork_decisions"]["calls"]
    adjustment = (old_mean - mean(mapped_cached_tokens)) * (rates[0] - rates[1]) * prior["historical"]["calls"] / 1e6
    after = prior["prompt_growth_adjusted_current_cli_projection"]["after_usd"] + adjustment
    before = prior["historical"]["usd"]["total"]
    return {"historical_usd": before, "projected_fork_usd": after,
            "saving_usd": before - after, "saving_percent": 100 * (before - after) / before,
            "mapped_mean_cached_tokens": mean(mapped_cached_tokens),
            "basis": "Follow-up hit frequencies on original model-specific prefix sizes; original cold template, prompt growth and output held fixed"}


def analyze(root=ROOT, claude_only=False):
    hashes = {}

    def read(path, lines=False):
        path = Path(path)
        raw = (root / path).read_bytes()
        hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        return [json.loads(l) for l in raw.splitlines()] if lines else json.loads(raw)

    claude = {}
    with sqlite3.connect(f"file:{root / 'data/model-benchmarks.sqlite'}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        for run_id in CLAUDE_RUNS:
            source = db.execute(
                "SELECT r.*, rc.resolved_model FROM runs r JOIN run_cohorts rc USING(run_id) WHERE r.run_id=?",
                (run_id,)).fetchone()
            if source is None:
                raise ValueError(f"Missing cataloged run: {run_id}")
            rows = read(source["source_usage"], True)
            manifest = read(source["source_manifest"])
            if manifest["status"] != "completed" or len(rows) != source["calls"]:
                raise ValueError("Incomplete historical evidence")
            if any(r["provider"] != "claude_cli" for r in rows):
                raise ValueError("Non-native Claude evidence")
            model = source["resolved_model"]
            if any((r.get("response_model") or r["model"]) != model for r in rows):
                raise ValueError("Historical model identity mismatch")
            rate = 10 if "fable" in model else 5
            cached_rate = .25 if model == "claude-fable-5-1" else rate / 10
            rates = [rate, cached_rate, rate * 1.25, rate * 5]
            estimate = ttl_estimate(rows, rates)
            if estimate["available"]:
                if abs(estimate["five_minute"]["usd"]["total"] - source["api_list_cost_usd"]) > .000002:
                    raise ValueError("Ledger pricing does not reproduce the stored cost")
            claude[run_id] = {**estimate, "model": model, "seed": source["seed"],
                             "usage_path": source["source_usage"],
                             "stored_benchmark_cost_usd": source["api_list_cost_usd"]}

    passes = {}
    pairs = {}
    commits = set()
    static_hashes = set()
    mapped_reads = {m: [] for m in MODELS}
    projections = {}
    if not claude_only:
        prior_study = read("docs/cache-cost-study-20260922.json")
        for pass_index, name in enumerate(("ab", "ba")):
            run_id = f"cache-interleaved-{name}-20260922"
            base = Path("runs/managed") / run_id / "seed-11"
            job = Path("runs/jobs") / run_id
            heartbeat = read(job / "controller-heartbeat.json")
            report = read(base / "run-report.json")
            if heartbeat["controller_status"] != "completed" or not report["run"]["completed"]:
                raise ValueError("Interleaved pass not completed")
            if report["run"]["final_tick"] != 1 or report["reliability"]["decision_failure_rate_pct"] != 0:
                raise ValueError("Unexpected endpoint or failed decisions")
            commits.add(read(job / "job.json")["launch_commit"])
            rows = read(base / "run-usage.jsonl", True)
            ds = sorted([r for r in rows if r.get("agent_id")], key=lambda r: r["time"])
            ts = [r for r in rows if r.get("usage_kind") == "cache_template"]
            if len(rows) != 22 or len(ds) != 20 or len(ts) != 2:
                raise ValueError("Unexpected interleaved usage coverage")
            if len({r["codex_session_id"] for r in ds}) != 20:
                raise ValueError("Non-independent fork sessions")
            if any(r["cli_version"] != "codex-cli 0.156.0" or r["reasoning_effort"] != "medium" for r in rows):
                raise ValueError("Unexpected CLI or effort")
            expected = [MODELS[(i + pass_index) % 2] for i in range(20)]
            if [r["model"] for r in ds] != expected:
                raise ValueError("Call order was not interleaved as preregistered")
            pairs[name] = {r["agent_id"]: (r["request_sha256"], r["model"]) for r in ds}
            if len(pairs[name]) != 20:
                raise ValueError("Duplicate observation")
            static_hashes.update(r["static_prompt_sha256"] for r in ds)
            summary = {}
            for model in MODELS:
                decisions = [r for r in ds if r["model"] == model]
                templates = [r for r in ts if r["model"] == model]
                if len(templates) != 1 or len(decisions) != 10:
                    raise ValueError("Unexpected model coverage")
                template = templates[0]
                if any(r.get("codex_usage_scope") != "fork_delta" or
                       r["cache_template_session_id"] != template["codex_session_id"] for r in decisions):
                    raise ValueError("Fork accounting or template mismatch")
                gaps = [b["time"] - b["duration_seconds"] - a["time"]
                        for a, b in zip(decisions, decisions[1:])]
                tag = "astra" if model == MODELS[0] else "sol56"
                prior = prior_study["models"][tag]["price_cards"]["current"]
                original_reads = [int(k) for k in prior["fork_decisions"]["cache_read_histogram"]]
                for row in decisions:
                    cached = row["cached_tokens"]
                    category = cache_class(cached, template["prompt_tokens"])
                    if category == "near_template":
                        mapped_reads[model].append(max(original_reads))
                    elif category == "miss":
                        mapped_reads[model].append(0)
                    elif prior_study["models"][tag]["static_prompt_hashes"]["current"] == [row["static_prompt_sha256"]]:
                        # Astra retains the identical rulebook/CLI/template
                        # length, so its newly observed partial count transfers
                        # directly. Sol's changed recipe does not get this rule.
                        if template["prompt_tokens"] != prior["template"]["prompt_tokens"]:
                            raise ValueError("Template size changed for direct partial-prefix mapping")
                        mapped_reads[model].append(cached)
                    elif cached in original_reads:
                        mapped_reads[model].append(cached)
                    else:
                        raise ValueError("Novel partial prefix needs explicit mapping review")
                summary[model] = {
                    "decisions": summarize(decisions, RATES[model]),
                    "template": summarize(templates, RATES[model]),
                    "template_session_id": template["codex_session_id"],
                    "classes": dict(Counter(cache_class(r["cached_tokens"], template["prompt_tokens"]) for r in decisions)),
                    "mean_cached_fraction_of_template": mean(r["cached_tokens"] / template["prompt_tokens"] for r in decisions),
                    "same_model_idle_gap_seconds": {"min": min(gaps), "max": max(gaps), "mean": mean(gaps)},
                }
            passes[name] = {"models": summary, "reliability": report["reliability"],
                            "sequence": [{k: r.get(k) for k in
                                ("agent_id", "model", "request_sha256", "prompt_tokens", "cached_tokens", "completion_tokens", "time", "duration_seconds")}
                                for r in ds]}
        if len(commits) != 1 or len(static_hashes) != 1:
            raise ValueError("Source or static rulebook mismatch")
        if set(pairs["ab"]) != set(pairs["ba"]):
            raise ValueError("Observation coverage mismatch")
        if any(pairs["ab"][k][0] != pairs["ba"][k][0] or pairs["ab"][k][1] == pairs["ba"][k][1] for k in pairs["ab"]):
            raise ValueError("Counterbalanced observations did not match")
        for model, tag in zip(MODELS, ("astra", "sol56")):
            projections[model] = refresh_projection(prior_study["models"][tag]["price_cards"]["current"], mapped_reads[model])
    return {"schema_version": 1, "claude": claude, "interleaved": passes,
            "updated_historical_cost_projections": projections,
            "source_commits": sorted(commits), "static_prompt_hashes": sorted(static_hashes),
            "source_sha256": hashes, "basis": "API-equivalent estimates; not subscription quota"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--claude-only", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(analyze(claude_only=args.claude_only), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end="")
