from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from agent_world.usage import append_usage_record, summarize_codex_simulation_credits


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
