import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent_world.run_controller import _retryable, DEFAULT_POLICY

class StartupEnvironmentRoutingTests(unittest.TestCase):
    def test_current_environment_failure_is_not_retryable(self):
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/"cell.log"
            log.write_text("old output\n")
            cell={"log":str(log),"launch_log_offset":log.stat().st_size,"events":str(Path(d)/"run.jsonl")}
            with log.open("a") as f:f.write("ValueError: Execution environment changed for agent-1; an explicit migration is required\n")
            with patch("agent_world.run_controller._requires_authentication",return_value=False):
                self.assertEqual(_retryable(cell,{"state":"interrupted"},DEFAULT_POLICY),(False,"execution_environment_mismatch"))
                cell["launch_log_offset"]=log.stat().st_size
                self.assertEqual(_retryable(cell,{"state":"interrupted"},DEFAULT_POLICY),(True,"supervisor_interrupted"))
