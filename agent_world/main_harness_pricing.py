"""Published main-harness API-equivalent rates, verified 2026-09-12.

Sources: https://platform.claude.com/docs/en/about-claude/pricing
https://developers.openai.com/api/docs/pricing
Existing xAI rates are retained in usage.py from its model-specific rate cards.
"""
from decimal import Decimal
VERIFIED_DATE = "2026-09-12"

def rates(input, cached, write, output):
    return dict(zip(("input", "cached_input", "cache_write", "output"),
                    map(lambda n: Decimal(str(n)), (input, cached, write, output))))

RATES = {
    **{m: rates(5, .5, 6.25, 25) for m in ["claude-opus-5", "claude-opus-4-8",
        "claude-opus-4-7", "claude-opus-4-6", "claude-opus-4-5"]},
    **{m: rates(15, 1.5, 18.75, 75) for m in ["claude-opus-4-1", "claude-opus-4"]},
    **{m: rates(3, .3, 3.75, 15) for m in ["claude-sonnet-4-6", "claude-sonnet-4-5", "claude-sonnet-4"]},
    "claude-sonnet-5": rates(2, .2, 2.5, 10),
    "claude-haiku-4-5": rates(1, .1, 1.25, 5),
    "claude-haiku-3-5": rates(.8, .08, 1, 4),
    **{m: rates(10, 1, 12.5, 50) for m in ["claude-fable-5", "claude-mythos-5"]},
    **{m: rates(10, .25, 12.5, 50) for m in ["claude-fable-5-1", "claude-mythos-5-1"]},
    "gpt-5.6-sol": rates(4, .4, 5, 20),
    "gpt-5.3-codex": rates(1.75, .175, 1.75, 14),
}
# No published API-equivalent price: never substitute the non-Spark Codex rate.
UNPRICED = {"gpt-5.3-codex-spark": "No published API-equivalent price."}
