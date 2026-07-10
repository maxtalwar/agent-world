"""Run-scoped token and plan-credit accounting.

API dollars and subscription-plan credits are deliberately separate units.
Codex calls report their own token usage, which lets a run calculate its exact
model-credit consumption without attributing unrelated account activity from a
before/after rate-limit snapshot.
"""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import threading
from typing import Any


CODEX_RATE_CARD_SOURCE = "https://help.openai.com/en/articles/20001106-codex-rate-card-2"
CODEX_RATE_CARD_EFFECTIVE_DATE = "2026-07-10"
CODEX_CREDIT_RATES_PER_MILLION: dict[str, dict[str, Decimal]] = {
    "gpt-5.6-sol": {
        "input": Decimal("125"),
        "cached_input": Decimal("12.5"),
        "output": Decimal("750"),
    },
    "gpt-5.6-terra": {
        "input": Decimal("62.5"),
        "cached_input": Decimal("6.25"),
        "output": Decimal("375"),
    },
    "gpt-5.6-luna": {
        "input": Decimal("25"),
        "cached_input": Decimal("2.5"),
        "output": Decimal("150"),
    },
}

_USAGE_LOG_LOCK = threading.Lock()


def append_usage_record(record: dict[str, Any], usage_path: Path | None) -> bool:
    """Append one complete JSONL usage record without concurrent interleaving."""

    if usage_path is None:
        return False
    try:
        with _USAGE_LOG_LOCK:
            usage_path.parent.mkdir(parents=True, exist_ok=True)
            with usage_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        return True
    except OSError:
        return False


def summarize_codex_simulation_credits(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Calculate credits from Codex calls owned by this simulation run.

    ``prompt_tokens`` includes cached input, while ``cached_tokens`` is the
    cached subset. Reasoning tokens are already included in output tokens and
    therefore must not be charged a second time.
    """

    codex_records = [record for record in records if record.get("provider") == "codex_cli"]
    if not codex_records:
        return None

    totals = {
        "calls": len(codex_records),
        "uncached_input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    credits = {"uncached_input": Decimal(0), "cached_input": Decimal(0), "output": Decimal(0)}
    models: dict[str, dict[str, Any]] = {}
    unknown_models: set[str] = set()

    for record in codex_records:
        prompt_tokens = _nonnegative_int(record.get("prompt_tokens"))
        cached_tokens = min(prompt_tokens, _nonnegative_int(record.get("cached_tokens")))
        uncached_tokens = prompt_tokens - cached_tokens
        output_tokens = _nonnegative_int(record.get("completion_tokens"))
        reasoning_tokens = min(output_tokens, _nonnegative_int(record.get("reasoning_tokens")))
        totals["uncached_input_tokens"] += uncached_tokens
        totals["cached_input_tokens"] += cached_tokens
        totals["output_tokens"] += output_tokens
        totals["reasoning_output_tokens"] += reasoning_tokens

        raw_model = str(record.get("model") or record.get("response_model") or "unknown")
        rate_model = _rate_model(raw_model)
        if rate_model is None:
            unknown_models.add(raw_model)
            continue
        rates = CODEX_CREDIT_RATES_PER_MILLION[rate_model]
        model_row = models.setdefault(
            rate_model,
            {
                "calls": 0,
                "uncached_input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "credits": Decimal(0),
            },
        )
        model_row["calls"] += 1
        model_row["uncached_input_tokens"] += uncached_tokens
        model_row["cached_input_tokens"] += cached_tokens
        model_row["output_tokens"] += output_tokens
        components = {
            "uncached_input": _credits(uncached_tokens, rates["input"]),
            "cached_input": _credits(cached_tokens, rates["cached_input"]),
            "output": _credits(output_tokens, rates["output"]),
        }
        for name, value in components.items():
            credits[name] += value
            model_row["credits"] += value

    total_credits = sum(credits.values(), Decimal(0))
    return {
        "available": not unknown_models,
        "attribution": "Exact token usage from Codex decisions made by this simulation run only.",
        **totals,
        "credits": {
            "uncached_input": _decimal_number(credits["uncached_input"]),
            "cached_input": _decimal_number(credits["cached_input"]),
            "output": _decimal_number(credits["output"]),
            "total": _decimal_number(total_credits),
        },
        "models": {
            model: {
                **{key: value for key, value in row.items() if key != "credits"},
                "credits": _decimal_number(row["credits"]),
                "rates_per_million_tokens": {
                    key: _decimal_number(value)
                    for key, value in CODEX_CREDIT_RATES_PER_MILLION[model].items()
                },
            }
            for model, row in sorted(models.items())
        },
        "unknown_models": sorted(unknown_models),
        "rate_card": {
            "source": CODEX_RATE_CARD_SOURCE,
            "effective_date": CODEX_RATE_CARD_EFFECTIVE_DATE,
            "unit": "credits_per_million_tokens",
        },
    }


def _rate_model(model: str) -> str | None:
    normalized = model.lower()
    for rate_model in CODEX_CREDIT_RATES_PER_MILLION:
        if normalized == rate_model or normalized.startswith(rate_model + "-"):
            return rate_model
    return None


def _credits(tokens: int, rate: Decimal) -> Decimal:
    return Decimal(tokens) * rate / Decimal(1_000_000)


def _decimal_number(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def _nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)
