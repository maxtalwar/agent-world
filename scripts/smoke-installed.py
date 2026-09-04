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
with tempfile.TemporaryDirectory(prefix="agent-world-wheel-smoke-") as temporary:
    root = Path(temporary)
    result = subprocess.run([
        sys.executable, "-m", "agent_world.cli", "run", "--brain", "survival",
        "--ticks", "2", "--agents", "2", "--seed", "11",
        "--out", str(root/"run.jsonl"), "--snapshot", str(root/"run-snapshot.json"),
    ], cwd=root, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    engine, _ = load_run_checkpoint(root/"run-checkpoint.pkl")
    assert engine.state.tick == 2
    report = json.loads((root/"run-report.json").read_text())
    assert report["run"]["final_tick"] == 2
print("Installed wheel: assets, CLI, simulation, report and checkpoint passed.")
