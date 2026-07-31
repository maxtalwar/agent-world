"""Run-scoped token and plan-credit accounting.

API dollars and subscription-plan credits are deliberately separate units.
Codex calls report their own token usage, which lets a run calculate its exact
model-credit consumption without attributing unrelated account activity from a
before/after rate-limit snapshot.
"""

from __future__ import annotations

from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
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

USD_RATE_CARD_SOURCES = {
    "openai": "https://developers.openai.com/api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/pricing",
}
USD_RATE_CARD_EFFECTIVE_DATE = "2026-07-30"
# List-price API rates. Cached reads use the published cached-input rate.
# Models with a distinct cache-write tier bill writes at that published rate;
# models without one fall back to ordinary input pricing. Rate keys are matched
# by longest prefix against the normalized model string, so provider suffixes
# ("gpt-5-6-luna-medium") and effort-tagged variants resolve to their base
# model without collapsing "gpt-5.4-mini" into "gpt-5.4".
MODEL_USD_RATES_PER_MILLION: dict[str, dict[str, Decimal]] = {
    "gpt-5.6-sol": {
        "input": Decimal("5"),
        "cached_input": Decimal("0.5"),
        "cache_write": Decimal("6.25"),
        "output": Decimal("30"),
    },
    "gpt-5.6-terra": {
        "input": Decimal("2"),
        "cached_input": Decimal("0.2"),
        "cache_write": Decimal("2.5"),
        "output": Decimal("12"),
    },
    "gpt-5.6-luna": {
        "input": Decimal("0.2"),
        "cached_input": Decimal("0.02"),
        "cache_write": Decimal("0.25"),
        "output": Decimal("1.2"),
    },
    "gpt-5.5": {
        "input": Decimal("5"),
        "cached_input": Decimal("0.5"),
        "cache_write": Decimal("5"),
        "output": Decimal("30"),
    },
    "gpt-5.4-mini": {
        "input": Decimal("0.75"),
        "cached_input": Decimal("0.075"),
        "cache_write": Decimal("0.75"),
        "output": Decimal("4.5"),
    },
    "gpt-5.4-nano": {
        "input": Decimal("0.2"),
        "cached_input": Decimal("0.02"),
        "cache_write": Decimal("0.2"),
        "output": Decimal("1.25"),
    },
    "gpt-5.4": {
        "input": Decimal("2.5"),
        "cached_input": Decimal("0.25"),
        "cache_write": Decimal("2.5"),
        "output": Decimal("15"),
    },
    "gpt-5.1": {
        "input": Decimal("1.25"),
        "cached_input": Decimal("0.125"),
        "cache_write": Decimal("1.25"),
        "output": Decimal("10"),
    },
    "gpt-5-mini": {
        "input": Decimal("0.25"),
        "cached_input": Decimal("0.025"),
        "cache_write": Decimal("0.25"),
        "output": Decimal("2"),
    },
    "claude-fable-5": {
        "input": Decimal("10"),
        "cached_input": Decimal("1"),
        "cache_write": Decimal("12.5"),
        "output": Decimal("50"),
    },
    "claude-opus-5": {
        "input": Decimal("5"),
        "cached_input": Decimal("0.5"),
        "cache_write": Decimal("6.25"),
        "output": Decimal("25"),
    },
    "claude-opus-4-8": {
        "input": Decimal("5"),
        "cached_input": Decimal("0.5"),
        "cache_write": Decimal("6.25"),
        "output": Decimal("25"),
    },
    "claude-opus-4-7": {
        "input": Decimal("5"),
        "cached_input": Decimal("0.5"),
        "cache_write": Decimal("6.25"),
        "output": Decimal("25"),
    },
    "claude-opus-4-6": {
        "input": Decimal("5"),
        "cached_input": Decimal("0.5"),
        "cache_write": Decimal("6.25"),
        "output": Decimal("25"),
    },
    "claude-sonnet-5": {
        "input": Decimal("3"),
        "cached_input": Decimal("0.3"),
        "cache_write": Decimal("3.75"),
        "output": Decimal("15"),
    },
    "claude-sonnet-4-6": {
        "input": Decimal("3"),
        "cached_input": Decimal("0.3"),
        "cache_write": Decimal("3.75"),
        "output": Decimal("15"),
    },
    "claude-haiku-4-5": {
        "input": Decimal("1"),
        "cached_input": Decimal("0.1"),
        "cache_write": Decimal("1.25"),
        "output": Decimal("5"),
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


def append_usage_records(records: list[dict[str, Any]], usage_path: Path | None) -> bool:
    """Append complete records as one locked batch."""

    if usage_path is None or not records:
        return False
    try:
        with _USAGE_LOG_LOCK:
            usage_path.parent.mkdir(parents=True, exist_ok=True)
            with usage_path.open("a", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
        return True
    except OSError:
        return False


def replace_usage_records(records: list[dict[str, Any]], usage_path: Path | None) -> bool:
    """Atomically replace a run's active usage ledger."""

    if usage_path is None:
        return False
    temp_path: Path | None = None
    try:
        with _USAGE_LOG_LOCK:
            usage_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=usage_path.name + ".", suffix=".tmp", dir=usage_path.parent
            )
            temp_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, usage_path)
        return True
    except OSError:
        return False
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


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


def summarize_usd_cost(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Estimate a run's USD cost from token usage at API list prices.

    ``prompt_tokens`` includes cached reads and cache writes; ``cached_tokens``
    and ``cache_write_tokens`` are the discounted/premium subsets. Records
    without a ``cache_write_tokens`` field price those tokens as ordinary
    uncached input. Reasoning tokens are already included in output tokens and
    are never charged a second time. Subscription-billed calls (Codex, Claude,
    Cursor plans) are priced at what the same tokens would cost on the API —
    an estimate, not a provider charge.
    """

    if not records:
        return None

    totals = {
        "calls": len(records),
        "uncached_input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    components = {
        "uncached_input": Decimal(0),
        "cached_input": Decimal(0),
        "cache_write": Decimal(0),
        "output": Decimal(0),
    }
    models: dict[str, dict[str, Any]] = {}
    unknown_models: set[str] = set()
    provider_reported = 0.0

    for record in records:
        provider_reported += float(record.get("cost") or 0)
        prompt_tokens = _nonnegative_int(record.get("prompt_tokens"))
        cached_tokens = min(prompt_tokens, _nonnegative_int(record.get("cached_tokens")))
        cache_write_tokens = min(
            prompt_tokens - cached_tokens, _nonnegative_int(record.get("cache_write_tokens"))
        )
        uncached_tokens = prompt_tokens - cached_tokens - cache_write_tokens
        output_tokens = _nonnegative_int(record.get("completion_tokens"))
        reasoning_tokens = min(output_tokens, _nonnegative_int(record.get("reasoning_tokens")))
        totals["uncached_input_tokens"] += uncached_tokens
        totals["cached_input_tokens"] += cached_tokens
        totals["cache_write_tokens"] += cache_write_tokens
        totals["output_tokens"] += output_tokens
        totals["reasoning_output_tokens"] += reasoning_tokens

        raw_model = str(record.get("model") or record.get("response_model") or "unknown")
        rate_model = _usd_rate_model(raw_model)
        if rate_model is None and record.get("response_model"):
            rate_model = _usd_rate_model(str(record["response_model"]))
        if rate_model is None:
            unknown_models.add(raw_model)
            continue
        rates = MODEL_USD_RATES_PER_MILLION[rate_model]
        model_row = models.setdefault(
            rate_model,
            {
                "calls": 0,
                "uncached_input_tokens": 0,
                "cached_input_tokens": 0,
                "cache_write_tokens": 0,
                "output_tokens": 0,
                "cost_usd": Decimal(0),
            },
        )
        model_row["calls"] += 1
        model_row["uncached_input_tokens"] += uncached_tokens
        model_row["cached_input_tokens"] += cached_tokens
        model_row["cache_write_tokens"] += cache_write_tokens
        model_row["output_tokens"] += output_tokens
        record_components = {
            "uncached_input": _credits(uncached_tokens, rates["input"]),
            "cached_input": _credits(cached_tokens, rates["cached_input"]),
            "cache_write": _credits(cache_write_tokens, rates["cache_write"]),
            "output": _credits(output_tokens, rates["output"]),
        }
        for name, value in record_components.items():
            components[name] += value
            model_row["cost_usd"] += value

    total_cost = sum(components.values(), Decimal(0))
    return {
        "available": not unknown_models,
        "basis": "token_derived_api_list_price",
        "attribution": (
            "Token usage from this run priced at API list rates; an estimate, "
            "not a provider charge, for subscription-billed connectors."
        ),
        **totals,
        "cost_usd": {
            "uncached_input": _decimal_number(components["uncached_input"]),
            "cached_input": _decimal_number(components["cached_input"]),
            "cache_write": _decimal_number(components["cache_write"]),
            "output": _decimal_number(components["output"]),
            "total": _decimal_number(total_cost),
        },
        "provider_reported_cost_usd": round(provider_reported, 6),
        "models": {
            model: {
                **{key: value for key, value in row.items() if key != "cost_usd"},
                "cost_usd": _decimal_number(row["cost_usd"]),
                "rates_per_million_tokens": {
                    key: _decimal_number(value)
                    for key, value in MODEL_USD_RATES_PER_MILLION[model].items()
                },
            }
            for model, row in sorted(models.items())
        },
        "unknown_models": sorted(unknown_models),
        "rate_card": {
            "sources": dict(USD_RATE_CARD_SOURCES),
            "effective_date": USD_RATE_CARD_EFFECTIVE_DATE,
            "unit": "usd_per_million_tokens",
        },
    }


def _usd_rate_model(model: str) -> str | None:
    normalized = _normalize_model_id(model)
    for rate_model in sorted(MODEL_USD_RATES_PER_MILLION, key=len, reverse=True):
        candidate = _normalize_model_id(rate_model)
        if normalized == candidate or normalized.startswith(candidate + "-"):
            return rate_model
    return None


def _normalize_model_id(model: str) -> str:
    """Collapse provider spelling variants: ``gpt-5-6-luna`` == ``gpt-5.6-luna``."""

    return model.lower().replace(".", "-")


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
