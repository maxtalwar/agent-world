from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from agent_world.usage import (
    append_usage_record,
    summarize_codex_simulation_credits,
    summarize_usd_cost,
)


class UsageTests(unittest.TestCase):
    def test_codex_credits_are_run_scoped_and_reasoning_is_not_double_counted(self) -> None:
        summary = summarize_codex_simulation_credits(
            [
                {
                    "provider": "codex_cli",
                    "model": "gpt-5.6-luna",
                    "prompt_tokens": 1_000_000,
                    "cached_tokens": 400_000,
                    "completion_tokens": 100_000,
                    "reasoning_tokens": 80_000,
                },
                {
                    "provider": "openrouter",
                    "model": "gpt-5.6-luna",
                    "prompt_tokens": 99_000_000,
                    "completion_tokens": 99_000_000,
                },
            ]
        )

        assert summary is not None
        self.assertEqual(summary["calls"], 1)
        self.assertEqual(summary["uncached_input_tokens"], 600_000)
        self.assertEqual(summary["cached_input_tokens"], 400_000)
        self.assertEqual(summary["output_tokens"], 100_000)
        self.assertEqual(summary["credits"]["total"], 31.0)

    def test_unknown_codex_model_is_explicitly_unpriced(self) -> None:
        summary = summarize_codex_simulation_credits(
            [{"provider": "codex_cli", "model": "future-model", "prompt_tokens": 10}]
        )

        assert summary is not None
        self.assertFalse(summary["available"])
        self.assertEqual(summary["unknown_models"], ["future-model"])

    def test_non_codex_records_have_no_plan_credit_summary(self) -> None:
        self.assertIsNone(summarize_codex_simulation_credits([{"provider": "openrouter"}]))

    def test_usd_cost_prices_cache_tiers_and_never_double_counts_reasoning(self) -> None:
        summary = summarize_usd_cost(
            [
                {
                    "provider": "codex_cli",
                    "model": "gpt-5.6-luna",
                    "prompt_tokens": 1_000_000,
                    "cached_tokens": 400_000,
                    "cache_write_tokens": 100_000,
                    "completion_tokens": 100_000,
                    "reasoning_tokens": 80_000,
                }
            ]
        )

        assert summary is not None
        self.assertTrue(summary["available"])
        self.assertEqual(summary["uncached_input_tokens"], 500_000)
        self.assertEqual(summary["cached_input_tokens"], 400_000)
        self.assertEqual(summary["cache_write_tokens"], 100_000)
        self.assertEqual(summary["output_tokens"], 100_000)
        # 0.5M * $0.2 + 0.4M * $0.02 + 0.1M * $0.25 + 0.1M * $1.2, per million
        self.assertEqual(summary["cost_usd"]["total"], 0.253)
        self.assertEqual(summary["reasoning_output_tokens"], 80_000)

    def test_usd_cost_resolves_provider_model_spellings_and_aliases(self) -> None:
        summary = summarize_usd_cost(
            [
                {"model": "gpt-5-6-luna-medium", "prompt_tokens": 1_000_000},
                {"model": "fable", "response_model": "claude-fable-5", "completion_tokens": 1_000_000},
            ]
        )

        assert summary is not None
        self.assertTrue(summary["available"])
        self.assertIn("gpt-5.6-luna", summary["models"])
        self.assertIn("claude-fable-5", summary["models"])
        self.assertEqual(summary["cost_usd"]["total"], 50.2)

    def test_usd_cost_without_cache_write_field_prices_writes_as_uncached_input(self) -> None:
        summary = summarize_usd_cost(
            [
                {
                    "model": "claude-opus-4-6",
                    "prompt_tokens": 1_000_000,
                    "cached_tokens": 400_000,
                    "completion_tokens": 0,
                }
            ]
        )

        assert summary is not None
        # 0.6M * $5 + 0.4M * $0.5
        self.assertEqual(summary["cost_usd"]["total"], 3.2)
        self.assertEqual(summary["cache_write_tokens"], 0)

    def test_usd_cost_flags_unknown_models_and_keeps_provider_reported_cost(self) -> None:
        summary = summarize_usd_cost(
            [
                {"model": "future-model", "prompt_tokens": 10, "cost": 1.25},
                {"model": "gpt-5.6-sol", "prompt_tokens": 1_000_000},
            ]
        )

        assert summary is not None
        self.assertFalse(summary["available"])
        self.assertEqual(summary["unknown_models"], ["future-model"])
        self.assertEqual(summary["provider_reported_cost_usd"], 1.25)
        # Known models are still priced even when others are unknown.
        self.assertEqual(summary["models"]["gpt-5.6-sol"]["cost_usd"], 5.0)

    def test_usd_cost_is_none_without_records(self) -> None:
        self.assertIsNone(summarize_usd_cost([]))

    def test_concurrent_usage_records_remain_valid_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            usage_path = Path(temp_dir) / "usage.jsonl"
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(
                    executor.map(
                        lambda index: append_usage_record({"call": index}, usage_path),
                        range(100),
                    )
                )

            records = [json.loads(line) for line in usage_path.read_text().splitlines()]
            self.assertTrue(all(results))
            self.assertEqual(len(records), 100)
            self.assertEqual({record["call"] for record in records}, set(range(100)))


if __name__ == "__main__":
    unittest.main()
