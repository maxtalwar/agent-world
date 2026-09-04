"""Run from outside the checkout after installing the wheel. No model calls."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import agent_world
from agent_world.persistence import load_run_checkpoint

package = Path(agent_world.__file__).resolve().parent
checkout = Path(__file__).resolve().parents[1]
assert package != checkout / "agent_world", f"Imported checkout instead of wheel: {package}"
assert (package / "static" / "observer.html").is_file()
assert (package / "recipes" / "participant-v6.json").is_file()
assert (package / "recipes" / "participant-v7.json").is_file()
with tempfile.TemporaryDirectory(prefix="agent-world-wheel-smoke-") as temporary:
    for recipe in (None, "participant-v6", "participant-v7"):
        root = Path(temporary) / (recipe or "experiment")
        root.mkdir()
        command = [
            sys.executable, "-m", "agent_world.cli", "run", "--brain", "survival",
            "--ticks", "2", "--agents", "2", "--seed", "11",
            "--out", str(root/"run.jsonl"), "--snapshot", str(root/"run-snapshot.json"),
        ]
        if recipe:
            command.extend(["--recipe", recipe])
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        engine, extra = load_run_checkpoint(root/"run-checkpoint.pkl")
        assert engine.state.tick == 2
        assert extra["run"]["recipe"] == recipe
        assert extra["run"]["benchmark_protocol"] is None
        report = json.loads((root/"run-report.json").read_text())
        assert report["run"]["final_tick"] == 2
        assert report["benchmarks"]["protocol"]["id"] == (recipe or "participant-v7")
result = subprocess.run([
    sys.executable, "-m", "agent_world.cli", "recipes", "--validate",
    str(checkout / "configs" / "recipe-examples" / "small-society.json"),
], cwd=tempfile.gettempdir(), text=True, capture_output=True, timeout=30)
assert result.returncode == 0, result.stdout + result.stderr
assert json.loads(result.stdout)[0]["id"] == "small-society"
print("Installed wheel: JSON recipes, authoring validation, simulations, reports and checkpoints passed.")
