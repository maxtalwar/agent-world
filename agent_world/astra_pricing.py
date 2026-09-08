"""Verified standard API-equivalent Astra pricing, separate from plan charges."""
from decimal import Decimal
import json
from pathlib import Path

SOURCE = "https://developers.openai.com/api/docs/models/gpt-6-astra"
VERIFIED_DATE = "2026-09-07"
RATES = {"input": Decimal("10"), "cached_input": Decimal("1"),
         "cache_write": Decimal("12.5"), "output": Decimal("50")}


def rates_for_prompt(prompt_tokens):
    # The surcharge applies to the entire request above 272K input tokens.
    if prompt_tokens <= 272000:
        return dict(RATES)
    return {k: v * (Decimal("1.5") if k == "output" else 2) for k, v in RATES.items()}


def historical_cost(summary, model, report_path):
    """Reprice only missing Astra costs, reconciling all recorded attempts.

    Frozen reports stay unchanged. Ledger reconciliation prevents a partial
    ledger or missing retry file from silently producing a smaller estimate.
    Reasoning is a subset of completion tokens, so it is not charged again.
    """
    if model != "gpt-6-astra" or not isinstance(summary, dict) or summary.get("available"):
        return None
    if summary.get("unknown_models") != [model] or summary.get("models"):
        return None
    totals = dict(uncached_input_tokens=0, cached_input_tokens=0, cache_write_tokens=0, output_tokens=0)
    cost, calls = Decimal(0), 0
    try:
        for path in Path(report_path).parent.glob("run-usage*.jsonl"):
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if row.get("model") != model:
                    return None
                prompt, cached, write, output = [row.get(k, 0) for k in
                    ("prompt_tokens", "cached_tokens", "cache_write_tokens", "completion_tokens")]
                if any(type(v) is not int or v < 0 for v in (prompt, cached, write, output)) or cached + write > prompt:
                    return None
                values = (prompt - cached - write, cached, write, output)
                rates = rates_for_prompt(prompt)
                for field, value, rate in zip(totals, values, ("input", "cached_input", "cache_write", "output")):
                    totals[field] += value
                    cost += value * rates[rate] / 1000000
                calls += 1
    except (OSError, ValueError, TypeError):
        return None
    if not calls or calls != summary.get("calls") or any(summary.get(k) != v for k, v in totals.items()):
        return None
    return float(cost.quantize(Decimal(".000001")))
