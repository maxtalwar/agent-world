from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_world.agents import SurvivalBrain
from agent_world.models import WorldConfig
from agent_world.run_report import build_report, format_comparison, render_markdown, write_report
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


def _run_short_sim(ticks: int = 4) -> tuple[list[dict], dict]:
    config = WorldConfig(seed=5)
    engine = WorldEngine.create(config=config, agent_names=["A1", "A2"])
    brains = {agent_id: SurvivalBrain() for agent_id in engine.state.agents}
    runner = SimulationRunner(engine, brains, log_agent_io=False)
    for _ in range(ticks):
        runner.step()
    events = [json.loads(line) for line in engine.export_events_jsonl().splitlines() if line.strip()]
    return events, engine.snapshot()


class RunReportTests(unittest.TestCase):
    def test_build_report_covers_core_sections(self) -> None:
        events, snapshot = _run_short_sim()
        report = build_report(events, snapshot, source="unit-test")

        self.assertEqual(report["source"], "unit-test")
        self.assertEqual(report["run"]["final_tick"], snapshot["tick"])
        self.assertTrue(report["run"]["completed"])
        self.assertEqual(report["config"]["seed"], 5)
        self.assertEqual(report["survival"]["living"], 2)
        self.assertIn("agent-1", report["survival"]["agents"])
        self.assertNotIn("agent_observation", report["actions"]["counts"])
        self.assertGreaterEqual(report["communication"]["says_total"], 0)
        self.assertIsInstance(report["milestone_first_ticks"], dict)
        self.assertEqual(report["usage"]["calls"], 0)

    def test_build_report_marks_stopped_runs(self) -> None:
        events, snapshot = _run_short_sim()
        events.append(
            {
                "type": "run_stopped",
                "tick": snapshot["tick"],
                "actor_id": None,
                "message": "stopped",
                "data": {"reason": "insufficient_quota", "target_ticks": 40},
            }
        )
        report = build_report(events, snapshot)
        self.assertFalse(report["run"]["completed"])
        self.assertEqual(report["run"]["stop_reason"], "insufficient_quota")
        self.assertEqual(report["run"]["target_ticks"], 40)

    def test_usage_records_are_aggregated(self) -> None:
        events, snapshot = _run_short_sim()
        usage = [
            {"cost": 0.01, "prompt_tokens": 1000, "cached_tokens": 500, "completion_tokens": 200, "reasoning_tokens": 100},
            {"cost": 0.02, "prompt_tokens": 1000, "cached_tokens": 900, "completion_tokens": 300, "reasoning_tokens": 150},
        ]
        report = build_report(events, snapshot, usage)
        self.assertEqual(report["usage"]["calls"], 2)
        self.assertAlmostEqual(report["usage"]["total_cost_usd"], 0.03)
        self.assertEqual(report["usage"]["cache_hit_rate_pct"], 70.0)

    def test_write_report_creates_json_and_markdown(self) -> None:
        events, snapshot = _run_short_sim()
        with tempfile.TemporaryDirectory() as tmp:
            stem = Path(tmp) / "sample"
            report = write_report(events, snapshot, [], stem)
            loaded = json.loads((Path(tmp) / "sample-report.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["run"], report["run"])
            markdown = (Path(tmp) / "sample-report.md").read_text(encoding="utf-8")
            self.assertIn("# Run report: sample", markdown)
            self.assertIn("agent-1", markdown)

    def test_render_markdown_mentions_early_stop(self) -> None:
        events, snapshot = _run_short_sim()
        events.append(
            {
                "type": "run_stopped",
                "tick": snapshot["tick"],
                "actor_id": None,
                "message": "stopped",
                "data": {"reason": "insufficient_quota", "target_ticks": 40},
            }
        )
        markdown = render_markdown(build_report(events, snapshot))
        self.assertIn("stopped early: insufficient_quota", markdown)

    def test_format_comparison_lines_up_runs(self) -> None:
        events, snapshot = _run_short_sim()
        first = build_report(events, snapshot, source="run-a")
        second = build_report(events, snapshot, source="run-b")
        table = format_comparison([first, second])
        self.assertIn("run-a", table.splitlines()[0])
        self.assertIn("run-b", table.splitlines()[0])
        self.assertIn("trades accepted", table)


if __name__ == "__main__":
    unittest.main()
