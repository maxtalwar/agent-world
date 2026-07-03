from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest

from agent_world.models import AgentDecision, WorldConfig
from agent_world.observer import HTML, RunController, SnapshotHistory, _parse_run_config, load_observer_state, summarize
from agent_world.world import WorldEngine


class ObserverTests(unittest.TestCase):
    def test_run_controller_pause_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            controller = RunController(snapshot_path=tmp_path / "s.json", events_path=tmp_path / "e.jsonl")
            status, payload = controller.start({"brain": "survival", "ticks": 1000, "agents": 1, "log_agent_io": False})
            self.assertEqual(status, 202)
            deadline = time.time() + 5
            while controller.status()["current_tick"] < 2 and time.time() < deadline:
                time.sleep(0.01)

            status, payload = controller.pause()
            self.assertEqual(status, 200)
            self.assertTrue(payload["run"]["paused"])
            time.sleep(0.3)
            tick_a = controller.status()["current_tick"]
            time.sleep(0.3)
            tick_b = controller.status()["current_tick"]
            self.assertLessEqual(tick_b - tick_a, 1)  # at most one in-flight tick finishes

            status, payload = controller.resume()
            self.assertEqual(status, 200)
            self.assertFalse(payload["run"]["paused"])
            deadline = time.time() + 5
            while controller.status()["current_tick"] <= tick_b and time.time() < deadline:
                time.sleep(0.01)
            self.assertGreater(controller.status()["current_tick"], tick_b)
            controller.stop()
            deadline = time.time() + 5
            while controller.status()["state"] == "running" and time.time() < deadline:
                time.sleep(0.02)
            self.assertEqual(controller.status()["state"], "stopped")

    def test_pause_requires_running_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            controller = RunController(snapshot_path=tmp_path / "s.json", events_path=tmp_path / "e.jsonl")
            status, payload = controller.pause()
            self.assertEqual(status, 409)
            self.assertFalse(payload["ok"])

    def test_snapshot_history_records_and_serves_past_ticks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = SnapshotHistory(Path(tmp) / "s.json")
            history.record({"tick": 0, "agents": {"agent-1": {"alive": True}}})
            history.record({"tick": 1, "agents": {}})
            history.record({"tick": 1, "agents": {"ignored": "duplicate tick"}})
            self.assertEqual(history.tick_range(), {"min_tick": 0, "max_tick": 1, "count": 2})
            self.assertIn("agent-1", history.get(0)["agents"])
            self.assertEqual(history.get(1)["agents"], {})
            # A restarted run (tick goes backwards) clears the archive.
            history.record({"tick": 0, "agents": {"fresh": True}})
            self.assertEqual(history.tick_range()["count"], 1)
            self.assertIn("fresh", history.get(0)["agents"])

    def test_load_observer_state_serves_historical_tick(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=["A1"])
        history = SnapshotHistory(Path("unused"))
        history.record(json.loads(json.dumps(engine.snapshot())))
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        history.record(json.loads(json.dumps(engine.snapshot())))
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            snapshot_path = tmp_path / "snapshot.json"
            events_path = tmp_path / "events.jsonl"
            snapshot_path.write_text(json.dumps(engine.snapshot()), encoding="utf-8")
            events_path.write_text(engine.export_events_jsonl() + "\n", encoding="utf-8")

            past = load_observer_state(snapshot_path, events_path, at_tick=0, history=history)
            self.assertEqual(past["snapshot"]["tick"], 0)
            self.assertEqual(past["history"]["viewing_tick"], 0)
            self.assertEqual(past["history"]["live_tick"], 2)
            self.assertTrue(all(event["tick"] <= 0 for event in past["recent_events"]))

            live = load_observer_state(snapshot_path, events_path, history=history)
            self.assertEqual(live["snapshot"]["tick"], 2)
            self.assertIsNone(live["history"]["viewing_tick"])

    def test_html_has_pause_and_timeline_controls(self) -> None:
        self.assertIn('id="pause-run"', HTML)
        self.assertIn('id="timeline-slider"', HTML)
        self.assertIn('id="tick-back"', HTML)
        self.assertIn('id="tick-forward"', HTML)
        self.assertIn('id="tick-live"', HTML)
        self.assertIn('"/api/run/resume" : "/api/run/pause"', HTML)
        self.assertIn("function renderTimeline(history, run)", HTML)
        self.assertIn("function setViewTick(value)", HTML)
        self.assertIn('`/api/state?tick=${viewTick}`', HTML)

    def test_snapshot_contains_tiles_and_positions(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=["A1"])
        snapshot = engine.snapshot()
        self.assertEqual(len(snapshot["tiles"]), 16)
        self.assertEqual(len(snapshot["tiles"][0]), 16)
        self.assertIn("resources", snapshot["tiles"][0][0])
        self.assertEqual(snapshot["agents"]["agent-1"]["position"], {"x": 8, "y": 8})
        self.assertIn("build_readiness", snapshot["diagnostics"])

    def test_observer_state_filters_private_io_events(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=["A1"])
        engine.log_event("agent_prompt", actor_id="agent-1", recipients={"agent-1"}, scope="private")
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            snapshot_path = tmp_path / "snapshot.json"
            events_path = tmp_path / "events.jsonl"
            snapshot_path.write_text(json.dumps(engine.snapshot()), encoding="utf-8")
            events_path.write_text(engine.export_events_jsonl() + "\n", encoding="utf-8")
            state = load_observer_state(snapshot_path, events_path)
        event_types = {event["type"] for event in state["recent_events"]}
        self.assertIn("wait", event_types)
        self.assertNotIn("agent_prompt", event_types)
        self.assertIn("build_ready", state["summary"])

    def test_model_selector_is_dropdown_with_recommended_models(self) -> None:
        self.assertIn('<select id="run-model" class="lock">', HTML)
        self.assertNotIn('<input id="run-model" type="text"', HTML)
        for model in ["z-ai/glm-5.2", "z-ai/glm-5.1", "z-ai/glm-4.7", "z-ai/glm-4.5-air"]:
            self.assertIn(f'value="{model}"', HTML)
        self.assertIn('<option value="z-ai/glm-5.2" selected>', HTML)
        self.assertIn('<select id="run-reasoning" class="lock">', HTML)
        self.assertIn('<option value="medium" selected>', HTML)
        self.assertIn('reasoning_effort: document.getElementById("run-reasoning").value', HTML)

    def test_event_timeline_has_agent_and_action_filters(self) -> None:
        self.assertIn('id="filter-agent"', HTML)
        self.assertIn('id="filter-type"', HTML)
        self.assertIn("function renderEventFilters(events, agents)", HTML)
        self.assertIn('standardActionTypes', HTML)
        self.assertIn('"say"', HTML)
        self.assertIn('{ value: "trade", label: "trade" }', HTML)
        self.assertIn('function eventMatchesTypeFilter(event, typeFilter)', HTML)
        self.assertIn('if (typeFilter === "trade") return eventClass(event.type) === "trade";', HTML)
        self.assertIn('document.getElementById("filter-agent").addEventListener("change"', HTML)
        self.assertIn('document.getElementById("filter-type").addEventListener("change"', HTML)
        self.assertIn('case "well"', HTML)

    def test_agent_status_bars_display_percentages(self) -> None:
        self.assertIn('const percentage = max > 0 ? Math.round', HTML)
        self.assertIn('${percentage}%', HTML)
        self.assertIn('config.food_reserve_max || 20', HTML)
        self.assertIn('config.water_reserve_max || 20', HTML)
        self.assertIn('config.energy_reserve_max || 30', HTML)

    def test_config_tab_controls_simulation_knobs(self) -> None:
        self.assertIn('id="tab-config"', HTML)
        self.assertIn('id="panel-config"', HTML)
        self.assertIn('id="cfg-carry-capacity"', HTML)
        self.assertIn('id="cfg-action-points"', HTML)
        self.assertIn('id="cfg-storage-capacity"', HTML)
        self.assertIn('id="cfg-food-start"', HTML)
        self.assertIn('id="cfg-food-spoil-interval"', HTML)
        self.assertIn('id="cfg-starter-radius"', HTML)
        self.assertIn('id="cfg-wild-food"', HTML)
        self.assertIn('id="cfg-wild-fiber"', HTML)
        self.assertIn('class="terrain-grid"', HTML)
        self.assertIn('class="tb-title">Plains</legend>', HTML)
        self.assertIn('class="tb-title">Forest</legend>', HTML)
        self.assertIn('class="tb-title">Mountain</legend>', HTML)
        self.assertIn('class="tb-title">Water</legend>', HTML)
        self.assertIn('id="cfg-plains-food"', HTML)
        self.assertIn('id="cfg-forest-wood"', HTML)
        self.assertIn('id="cfg-water-water"', HTML)
        self.assertIn('<option value="llm" selected>llm</option>', HTML)
        self.assertIn('id="run-ticks" class="lock" type="number" min="1" max="1000" value="20"', HTML)
        self.assertIn('id="run-seed" class="lock" type="number" min="0" value="11"', HTML)
        self.assertIn('action_points_per_tick: numberValue("cfg-action-points")', HTML)
        self.assertIn('default_carry_capacity: numberValue("cfg-carry-capacity")', HTML)
        self.assertIn('storage_capacity: numberValue("cfg-storage-capacity")', HTML)
        self.assertIn('carried_food_spoil_interval: numberValue("cfg-food-spoil-interval")', HTML)
        self.assertIn('starter_resource_radius: numberValue("cfg-starter-radius")', HTML)
        self.assertIn('wild_food_density: numberValue("cfg-wild-food")', HTML)
        self.assertIn('plains_food_regen: numberValue("cfg-plains-food")', HTML)
        self.assertIn('water_water_regen: numberValue("cfg-water-water")', HTML)
        self.assertIn('const TERRAIN_STORAGE_KEY = "agentWorldObservatory.terrainRegrowth"', HTML)
        self.assertIn("loadTerrainConfig();", HTML)
        self.assertIn("saveTerrainConfig", HTML)

    def test_map_renders_illustrated_structures_and_agent_figures(self) -> None:
        self.assertIn(':root {\n      color-scheme: light;', HTML)
        self.assertIn("function structureIcon(type", HTML)
        self.assertIn("function drawStructure(type", HTML)
        for structure_type in ["house", "well", "farm_plot", "storage", "shelter", "workshop"]:
            self.assertIn(f'case "{structure_type}":', HTML)
        self.assertIn("function forestDecor", HTML)
        self.assertIn("function mountainDecor", HTML)
        self.assertIn("function waterDecor", HTML)
        self.assertIn("function plainsDecor", HTML)
        self.assertIn("function agentFigure", HTML)
        self.assertIn("function graveFigure", HTML)
        self.assertIn("function pileFigure", HTML)
        self.assertIn("under_construction", HTML)
        self.assertIn("function tipContent", HTML)
        self.assertIn("function renderInspector", HTML)
        self.assertIn('id="hover-rect"', HTML)
        self.assertIn("data-tx", HTML)

    def test_civilization_panel_charts_progress_series(self) -> None:
        self.assertIn('id="civ-chart"', HTML)
        self.assertIn('id="civ-structures"', HTML)
        self.assertIn("function renderChart(series)", HTML)
        for key in ["population", "structures", "trades", "messages"]:
            self.assertIn(f'"{key}"', HTML)

    def test_summary_includes_civilization_series(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=["A1", "A2"])
        engine.tick({aid: AgentDecision(actions=[{"type": "wait"}]) for aid in engine.state.agents})
        engine.tick({aid: AgentDecision(actions=[{"type": "wait"}]) for aid in engine.state.agents})
        snapshot = engine.snapshot()
        events = [
            {"type": "say", "tick": 0},
            {"type": "death", "tick": 1},
            {"type": "build", "tick": 2},
            {"type": "accept_trade", "tick": 2},
        ]
        series = summarize(snapshot, events)["series"]
        self.assertEqual(series["ticks"], [0, 1, 2])
        self.assertEqual(series["population"], [2, 1, 1])
        self.assertEqual(series["structures"], [0, 0, 1])
        self.assertEqual(series["trades"], [0, 0, 1])
        self.assertEqual(series["messages"], [1, 1, 1])

    def test_observatory_default_run_matches_latest_tuned_profile(self) -> None:
        config = _parse_run_config({})
        self.assertEqual(config.brain, "llm")
        self.assertEqual(config.ticks, 20)
        self.assertEqual(config.agents, 5)
        self.assertEqual(config.model, "z-ai/glm-5.2")
        self.assertEqual(config.reasoning_effort, "medium")
        self.assertEqual(config.max_workers, 1)
        self.assertEqual(config.world_config.seed, 11)
        self.assertEqual(config.world_config.action_points_per_tick, 3)
        self.assertEqual(config.world_config.carried_food_spoil_interval, 6)
        self.assertEqual(config.world_config.starter_resource_radius, 1)
        self.assertEqual(config.world_config.wild_food_density, 0.35)
        self.assertEqual(config.world_config.wild_fiber_density, 0.85)

    def test_run_config_parses_world_knobs(self) -> None:
        config = _parse_run_config(
            {
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
        self.assertEqual(config.brain, "llm")
        self.assertEqual(config.model, "gpt-5.4-mini")
        self.assertEqual(config.reasoning_effort, "high")
        self.assertEqual(config.world_config.action_points_per_tick, 4)
        self.assertEqual(config.world_config.default_carry_capacity, 18)
        self.assertEqual(config.world_config.storage_capacity, 140)
        self.assertEqual(config.world_config.food_reserve_start, 6)
        self.assertEqual(config.world_config.food_reserve_max, 20)
        self.assertEqual(config.world_config.energy_reserve_max, 40)
        self.assertEqual(config.world_config.resource_base_multiplier, 1.5)
        self.assertEqual(config.world_config.plains_food_regen, 0.25)
        self.assertEqual(config.world_config.forest_wood_regen, 0.5)
        self.assertEqual(config.world_config.water_water_regen, 0.9)
        self.assertEqual(config.world_config.wild_food_density, 0.4)
        self.assertEqual(config.world_config.wild_fiber_density, 0.7)
        self.assertEqual(config.world_config.starter_resource_radius, 2)
        self.assertEqual(config.world_config.carried_food_spoil_interval, 9)
        self.assertEqual(config.world_config.carried_food_spoil_quantity, 2)
        self.assertEqual(config.world_config.farm_food_added, 8)

    def test_run_config_rejects_starting_reserve_above_max(self) -> None:
        with self.assertRaises(ValueError):
            _parse_run_config({"food_reserve_start": 16, "food_reserve_max": 15})

    def test_run_config_rejects_invalid_reasoning_effort(self) -> None:
        with self.assertRaises(ValueError):
            _parse_run_config({"brain": "llm", "reasoning_effort": "maximum"})

    def test_run_controller_starts_survival_run_and_writes_live_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            snapshot_path = tmp_path / "snapshot.json"
            events_path = tmp_path / "events.jsonl"
            controller = RunController(snapshot_path=snapshot_path, events_path=events_path)

            status, payload = controller.start(
                {
                    "brain": "survival",
                    "ticks": 2,
                    "agents": 2,
                    "seed": 3,
                    "log_agent_io": False,
                    "max_workers": 1,
                    "default_carry_capacity": 17,
                    "food_reserve_start": 6,
                    "food_reserve_max": 20,
                    "forest_wood_regen": 0.33,
                }
            )
            self.assertEqual(status, 202)
            self.assertTrue(payload["ok"])

            deadline = time.time() + 5
            while controller.status()["state"] == "running" and time.time() < deadline:
                time.sleep(0.05)

            run_status = controller.status()
            self.assertEqual(run_status["state"], "completed", run_status)
            self.assertEqual(run_status["current_tick"], 2)
            self.assertTrue(snapshot_path.exists())
            self.assertTrue(events_path.exists())

            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["tick"], 2)
            self.assertEqual(snapshot["config"]["default_carry_capacity"], 17)
            self.assertEqual(snapshot["config"]["food_reserve_max"], 20)
            self.assertEqual(snapshot["config"]["forest_wood_regen"], 0.33)
            self.assertEqual(snapshot["agents"]["agent-1"]["carry_capacity"], 17)
            self.assertIn("run_completed", events_path.read_text(encoding="utf-8"))

            state = load_observer_state(snapshot_path, events_path, run_status=run_status)
            self.assertEqual(state["run"]["state"], "completed")
            self.assertEqual(state["run"]["agents"], 2)


if __name__ == "__main__":
    unittest.main()
