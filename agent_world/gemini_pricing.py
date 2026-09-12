"""Verified Gemini API-equivalent pricing; never a subscription charge."""
import re

SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
VERIFIED_DATE = "2026-09-12"
# Standard text rates through 2026-12-31. Output includes thinking tokens.
RATES = {model: {"input": 0.75, "cached_input": 0.075, "cache_write": 0.75, "output": 3.75}
         for model in ("gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash")}


def historical_cost(summary, model):
    """Fill a missing price from already-normalized, single-model token totals.

    Does not rewrite the immutable report or reprice an existing estimate.
    Cache storage is excluded, as with other token-only leaderboard estimates.
    """
    if not isinstance(summary, dict) or summary.get("available"):
        return None
    base = re.sub(r"-(?:low|medium|high|max)$", "", model)
    if base not in RATES or summary.get("unknown_models") != [model] or summary.get("models"):
        return None
    fields = {"input": "uncached_input_tokens", "cached_input": "cached_input_tokens",
              "cache_write": "cache_write_tokens", "output": "output_tokens"}
    if any(not isinstance(summary.get(f), (int, float)) or summary[f] < 0 for f in fields.values()):
        return None
    return round(sum(summary[f] * RATES[base][rate] for rate, f in fields.items()) / 1_000_000, 6)
