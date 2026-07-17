from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest

from agent_world.models import AgentDecision, WorldConfig
from agent_world.observer import (
    CSS,
    HTML,
    JAVASCRIPT,
    RunController,
    SnapshotHistory,
    _observer_config_payload,
    _parse_run_config,
    load_catalog_run_detail,
    load_catalog_run_state,
    load_observer_state,
    summarize,
)
from agent_world.world import WorldEngine


class ObserverTests(unittest.TestCase):
    def _wait_for_completion(self, controller: RunController, timeout: float = 5) -> dict:
        deadline = time.time() + timeout
        while controller.status()["state"] == "running" and time.time() < deadline:
            time.sleep(0.02)
        return controller.status()

    def test_frontend_is_a_new_multi_page_packaged_application(self) -> None:
        self.assertIn('id="world-page"', HTML)
        self.assertIn('id="runs-page"', HTML)
        self.assertIn('href="/runs" data-route="runs"', HTML)
        self.assertIn('id="world-canvas"', HTML)
        self.assertIn('id="analytics-drawer"', HTML)
        self.assertIn('id="run-form"', HTML)
        self.assertIn('id="archive-list"', HTML)
        self.assertIn('id="compare-view"', HTML)
        self.assertIn('/static/observer.css', HTML)
        self.assertIn('/static/observer.js', HTML)
        self.assertNotIn("<style>", HTML)
        self.assertNotIn("<script>", HTML)
        self.assertGreater(len(CSS), 20_000)
        self.assertGreater(len(JAVASCRIPT), 40_000)

    def test_world_surface_has_game_controls_and_rich_analytics(self) -> None:
        for element_id in (
            "pulse-chart",
            "inspector",
            "chronicle-drawer",
            "timeline-slider",
            "tick-live",
            "analytics-open",
            "event-agent-filter",
            "event-type-filter",
        ):
            self.assertIn(f'id="{element_id}"', HTML)
        for analytics_tab in ("economy", "population", "civilization", "models"):
            self.assertIn(f'data-analytics="{analytics_tab}"', HTML)
        for renderer in (
            "function drawTerrain(",
            "function drawStructures(",
            "function drawAgents(",
            "function renderInspector(",
            "function renderAnalytics(",
            "function renderEvents(",
        ):
            self.assertIn(renderer, JAVASCRIPT)

    def test_run_lab_supports_presets_mixed_cohorts_history_and_comparison(self) -> None:
        for element_id in (
            "preset-grid",
            "cohort-list",
            "add-cohort",
            "assignment-strategy",
            "observation-mode",
            "turn-mode",
            "decision-mode",
            "archive-search",
            "archive-preview",
        ):
            self.assertIn(f'id="{element_id}"', HTML)
        self.assertIn('fetchJSON("/api/run/start"', JAVASCRIPT)
        self.assertIn('fetchJSON("/api/runs"', JAVASCRIPT)
        self.assertIn("function cloneRun(", JAVASCRIPT)
        self.assertIn("function renderComparison(", JAVASCRIPT)
        self.assertIn("population: cohortRows()", JAVASCRIPT)

    def test_observer_config_exposes_frontend_capabilities(self) -> None:
        payload = _observer_config_payload()
        self.assertIn("organic-generalists", payload["presets"])
        self.assertIn("experimental-organic-specialists", payload["presets"])
        self.assertIn("gpt-5.6-sol", payload["models"]["codex"])
        self.assertIn("fable", payload["models"]["claude"])
        self.assertIn("compact-v2", payload["observation_modes"])
        self.assertIn("shuffled-sequential-v1", payload["turn_modes"])
        self.assertEqual(payload["limits"]["agents"], 100)

    def test_run_config_parses_mixed_population_and_experimental_preset(self) -> None:
        config = _parse_run_config(
            {
                "preset": "experimental-organic-specialists",
                "seed": 17,
                "ticks": 40,
                "max_workers": 8,
                "codex_max_workers": 4,
                "claude_max_workers": 3,
                "assignment_strategy": "stratified",
                "assignment_seed": 99,
                "observation_mode": "indexed-v3",
                "turn_mode": "shuffled-sequential-v1",
                "population": [
                    {
                        "count": 5,
                        "brain": "codex",
                        "model": "gpt-5.6-luna",
                        "reasoning_effort": "low",
                    },
                    {
                        "count": 5,
                        "brain": "claude",
                        "model": "fable",
                        "reasoning_effort": "low",
                        "thinking_budget_tokens": 0,
                    },
                ],
            }
        )
        self.assertEqual(config.brain, "mixed")
        self.assertEqual(config.agents, 10)
        self.assertEqual(config.population.total_agents, 10)
        self.assertEqual(config.population.groups[1].brain.model, "fable")
        self.assertEqual(config.population.groups[1].brain.type, "claude")
        self.assertEqual(config.assignment_strategy, "stratified")
        self.assertEqual(config.assignment_seed, 99)
        self.assertEqual(config.observation_mode, "indexed-v3")
        self.assertEqual(config.turn_mode, "shuffled-sequential-v1")
        self.assertEqual(config.provider_max_workers["codex_cli"], 4)
        self.assertEqual(config.world_config.specialization_mode, "specialists")
        self.assertEqual(config.world_config.economy_mode, "organic")

    def test_default_run_uses_open_frontier_profile(self) -> None:
        config = _parse_run_config({})
        self.assertEqual(config.brain, "llm")
        self.assertEqual(config.ticks, 20)
        self.assertEqual(config.agents, 5)
        self.assertEqual(config.model, "z-ai/glm-5.2")
        self.assertEqual(config.reasoning_effort, "medium")
        self.assertEqual(config.max_workers, 1)
        self.assertEqual(config.preset, "organic-generalists")
        self.assertEqual(config.world_config.seed, 11)
        self.assertEqual(config.world_config.economy_mode, "organic")
        self.assertEqual(config.world_config.geography_mode, "dispersed")
        self.assertEqual(config.world_config.specialization_mode, "generalists")

    def test_run_config_parses_world_knobs(self) -> None:
        config = _parse_run_config(
            {
                "preset": "baseline",
                "action_points_per_tick": 4,
                "default_carry_capacity": 18,
                "storage_capacity": 140,
                "food_reserve_start": 6,
                "food_reserve_max": 20,
                "water_reserve_start": 7,
                "water_reserve_max": 21,
                "energy_reserve_start": 12,
                "energy_reserve_max": 40,
                "resource_base_multiplier": 1.5,
                "plains_food_regen": 0.25,
                "forest_wood_regen": 0.5,
                "water_water_regen": 0.9,
                "wild_food_density": 0.4,
                "wild_fiber_density": 0.7,
                "starter_resource_radius": 2,
                "carried_food_spoil_interval": 9,
                "carried_food_spoil_quantity": 2,
                "farm_food_added": 8,
                "brain": "llm",
                "model": "gpt-5.4-mini",
                "reasoning_effort": "high",
            }
        )
        self.assertEqual(config.model, "gpt-5.4-mini")
        self.assertEqual(config.reasoning_effort, "high")
        self.assertEqual(config.world_config.default_carry_capacity, 18)
        self.assertEqual(config.world_config.storage_capacity, 140)
        self.assertEqual(config.world_config.energy_reserve_max, 40)
        self.assertEqual(config.world_config.resource_base_multiplier, 1.5)
        self.assertEqual(config.world_config.plains_food_regen, 0.25)
        self.assertEqual(config.world_config.forest_wood_regen, 0.5)
        self.assertEqual(config.world_config.water_water_regen, 0.9)
        self.assertEqual(config.world_config.wild_food_density, 0.4)
        self.assertEqual(config.world_config.wild_fiber_density, 0.7)
        self.assertEqual(config.world_config.starter_resource_radius, 2)
        self.assertEqual(config.world_config.carried_food_spoil_interval, 9)
        self.assertEqual(config.world_config.farm_food_added, 8)

    def test_run_config_validates_population_and_world_inputs(self) -> None:
        with self.assertRaises(ValueError):
            _parse_run_config({"food_reserve_start": 16, "food_reserve_max": 15})
        with self.assertRaises(ValueError):
            _parse_run_config({"brain": "llm", "reasoning_effort": "maximum"})
        with self.assertRaises(ValueError):
            _parse_run_config({"population": []})
        with self.assertRaises(ValueError):
            _parse_run_config({"population": [{"count": 101, "brain": "codex"}]})
        with self.assertRaises(ValueError):
            _parse_run_config({"preset": "forced-capitalism"})

    def test_run_controller_pause_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            controller = RunController(snapshot_path=tmp_path / "s.json", events_path=tmp_path / "e.jsonl")
            status, payload = controller.start(
                {"brain": "survival", "preset": "baseline", "ticks": 1000, "agents": 1, "log_agent_io": False}
            )
            self.assertEqual(status, 202)
            deadline = time.time() + 5
            while controller.status()["current_tick"] < 2 and time.time() < deadline:
                time.sleep(0.01)
            status, payload = controller.pause()
            self.assertEqual(status, 200)
            self.assertTrue(payload["run"]["paused"])
            time.sleep(0.2)
            tick_a = controller.status()["current_tick"]
            time.sleep(0.2)
            tick_b = controller.status()["current_tick"]
            self.assertLessEqual(tick_b - tick_a, 1)
            status, payload = controller.resume()
            self.assertEqual(status, 200)
            self.assertFalse(payload["run"]["paused"])
            controller.stop()
            result = self._wait_for_completion(controller)
            self.assertEqual(result["state"], "stopped")
            self.assertTrue((tmp_path / "e-report.json").exists())
            self.assertTrue((tmp_path / "e-manifest.json").exists())

    def test_pause_requires_running_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            controller = RunController(Path(tmp) / "s.json", Path(tmp) / "e.jsonl")
            status, payload = controller.pause()
            self.assertEqual(status, 409)
            self.assertFalse(payload["ok"])

    def test_archived_browser_run_writes_timestamped_artifacts_and_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            root.mkdir()
            controller = RunController(root / "live-snapshot.json", root / "live.jsonl", runs_root=root)
            status, payload = controller.start(
                {
                    "name": "Tiny Republic",
                    "brain": "survival",
                    "preset": "organic-generalists",
                    "ticks": 2,
                    "agents": 2,
                    "seed": 3,
                    "log_agent_io": False,
                }
            )
            self.assertEqual(status, 202)
            self.assertIn("observatory/", payload["run"]["run_id"])
            result = self._wait_for_completion(controller)
            self.assertEqual(result["state"], "completed", result)
            run_dir = root / result["run_id"]
            self.assertTrue((run_dir / "run.jsonl").exists())
            self.assertTrue((run_dir / "run-snapshot.json").exists())
            self.assertTrue((run_dir / "run-report.json").exists())
            self.assertTrue((run_dir / "run-manifest.json").exists())
            manifest = json.loads((run_dir / "run-manifest.json").read_text())
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["preset"], "organic-generalists")
            self.assertEqual(manifest["population"]["total_agents"], 2)
            self.assertTrue((root / "catalog.json").exists())
            detail = load_catalog_run_detail(root, result["run_id"])
            self.assertEqual(detail["report"]["run"]["final_tick"], 2)
            state = load_catalog_run_state(root, result["run_id"])
            self.assertEqual(state["snapshot"]["tick"], 2)
            self.assertEqual(state["source"], "archive")
            artifact_ref = f'{result["run_id"]}/run-report.json'
            self.assertEqual(
                load_catalog_run_detail(root, artifact_ref)["report"]["run"]["final_tick"],
                2,
            )

    def test_archive_report_references_disambiguate_shared_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            shared = root / "tuning"
            shared.mkdir(parents=True)
            for name, tick in (("alpha", 3), ("beta", 9)):
                (shared / f"{name}-report.json").write_text(
                    json.dumps({"run": {"final_tick": tick, "target_ticks": tick}}),
                    encoding="utf-8",
                )
                (shared / f"{name}-snapshot.json").write_text(
                    json.dumps({"tick": tick, "agents": {}, "tiles": []}),
                    encoding="utf-8",
                )

            alpha = load_catalog_run_state(root, "tuning/alpha-report.json")
            beta = load_catalog_run_state(root, "tuning/beta-report.json")
            self.assertEqual(alpha["snapshot"]["tick"], 3)
            self.assertEqual(beta["snapshot"]["tick"], 9)
            self.assertEqual(alpha["report"]["run"]["final_tick"], 3)
            self.assertEqual(beta["report"]["run"]["final_tick"], 9)
            with self.assertRaises(ValueError):
                load_catalog_run_detail(root, "../outside-report.json")

    def test_snapshot_history_records_resets_and_serves_past_ticks(self) -> None:
        history = SnapshotHistory(Path("unused"))
        history.record({"tick": 0, "agents": {"agent-1": {"alive": True}}})
        history.record({"tick": 1, "agents": {}})
        history.record({"tick": 1, "agents": {"ignored": "duplicate tick"}})
        self.assertEqual(history.tick_range(), {"min_tick": 0, "max_tick": 1, "count": 2})
        history.set_path(Path("new-snapshot.json"))
        self.assertEqual(history.tick_range()["count"], 0)
        history.record({"tick": 4, "agents": {"old": True}})
        history.record({"tick": 0, "agents": {"fresh": True}})
        self.assertEqual(history.tick_range()["count"], 1)
        self.assertIn("fresh", history.get(0)["agents"])

    def test_load_observer_state_filters_private_io_and_includes_report(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=["A1"])
        engine.log_event("agent_prompt", actor_id="agent-1", recipients={"agent-1"}, scope="private")
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "run-snapshot.json"
            events = root / "run.jsonl"
            report = root / "run-report.json"
            snapshot.write_text(json.dumps(engine.snapshot()), encoding="utf-8")
            events.write_text(engine.export_events_jsonl() + "\n", encoding="utf-8")
            report.write_text(json.dumps({"run": {"final_tick": 1}}), encoding="utf-8")
            state = load_observer_state(snapshot, events)
        event_types = {event["type"] for event in state["recent_events"]}
        self.assertIn("wait", event_types)
        self.assertNotIn("agent_prompt", event_types)
        self.assertEqual(state["report"]["run"]["final_tick"], 1)

    def test_summary_includes_civilization_series(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=["A1", "A2"])
        engine.tick({agent_id: AgentDecision(actions=[{"type": "wait"}]) for agent_id in engine.state.agents})
        engine.tick({agent_id: AgentDecision(actions=[{"type": "wait"}]) for agent_id in engine.state.agents})
        series = summarize(
            engine.snapshot(),
            [
                {"type": "say", "tick": 0},
                {"type": "death", "tick": 1},
                {"type": "build", "tick": 2},
                {"type": "accept_trade", "tick": 2},
            ],
        )["series"]
        self.assertEqual(series["ticks"], [0, 1, 2])
        self.assertEqual(series["population"], [2, 1, 1])
        self.assertEqual(series["structures"], [0, 0, 1])
        self.assertEqual(series["trades"], [0, 0, 1])
        self.assertEqual(series["messages"], [1, 1, 1])


if __name__ == "__main__":
    unittest.main()
