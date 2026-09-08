"""Muse standard API-equivalent rates; separate from subscription billing."""
SOURCE = "https://cursor.com/docs/models/muse-spark-1-3"
VERIFIED_DATE = "2026-09-08"
RATES = {"muse-spark-1.3": {"input": 1.25, "cached_input": 0.15, "cache_write": 0, "output": 4.25}}


def historical_cost(summary, model):
    if not isinstance(summary, dict) or summary.get("available"):
        return None
    if model not in RATES or summary.get("unknown_models") != [model] or summary.get("models"):
        return None
    fields = {"input": "uncached_input_tokens", "cached_input": "cached_input_tokens",
              "cache_write": "cache_write_tokens", "output": "output_tokens"}
    if any(not isinstance(summary.get(f), (int, float)) or summary[f] < 0 for f in fields.values()):
        return None
    return round(sum(summary[f] * RATES[model][rate] for rate, f in fields.items()) / 1_000_000, 6)
