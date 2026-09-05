"""Opt-in protocol integration against an installed binary and a loopback fake API.

No external API, real credentials, or model quota. Run with
AGENT_WORLD_TEST_MUSE_NATIVE=1 python3 -m unittest discover -s tests -p test_muse_native_offline.py
"""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import threading
import unittest
from unittest.mock import patch

from agent_world.muse_brain import MuseBrain, pinned_muse_executable
from agent_world.process_transport import run_process

DECISION = {"intent": "fixture", "actions": [{"type": "wait"}], "messages": [], "memory_updates": []}


@unittest.skipUnless(os.environ.get("AGENT_WORLD_TEST_MUSE_NATIVE") == "1", "opt-in installed Muse binary")
class NativeMuseOfflineTest(unittest.TestCase):
    def test_installed_cli_request_and_retained_usage(self):
        requests = []
        returned_model = "muse-spark-1.3"

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = json.dumps({"object": "list", "data": [{"id": "muse-spark-1.3",
                    "object": "model", "owned_by": "meta", "context_window": 1000000}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(data)
                msg = json.dumps(DECISION)
                response = {
                    "id": "fixture", "object": "response", "status": "completed", "model": returned_model,
                    "output": [{"id": "msg_fixture", "type": "message", "role": "assistant",
                                "status": "completed", "content": [{"type": "output_text", "text": msg, "annotations": []}]}],
                    "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
                              "input_tokens_details": {"cached_tokens": 50},
                              "output_tokens_details": {"reasoning_tokens": 8}},
                    "created_at": 1780000000, "error": None, "incomplete_details": None, "instructions": None,
                    "max_output_tokens": 100, "parallel_tool_calls": False, "previous_response_id": None,
                    "reasoning": {"effort": "low", "summary": None}, "store": False, "temperature": 1,
                    "text": {"format": {"type": "text"}}, "tool_choice": "auto", "tools": [], "top_p": 1,
                    "truncation": "disabled", "user": None, "metadata": {},
                }
                frames = [
                    {"type": "response.output_text.delta", "item_id": "msg_fixture",
                     "output_index": 0, "content_index": 0, "delta": msg, "logprobs": []},
                    {"type": "response.completed", "response": response},
                ]
                for index, frame in enumerate(frames):
                    frame["sequence_number"] = index
                body = "".join("event: " + f["type"] + "\ndata: " + json.dumps(f) + "\n\n" for f in frames)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(body.encode())

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        binary = pinned_muse_executable()
        self.assertTrue(binary, "Install Muse before enabling this test")
        brain = MuseBrain(executable=binary, timeout_seconds=30)

        def loopback(command, **kwargs):
            # The production adapter cannot choose this test endpoint or API key.
            command = [*command, "--base-url", f"http://127.0.0.1:{server.server_port}"]
            kwargs["env"]["META_API_KEY"] = "offline-fixture"
            # No account credentials are needed, even if the host has a login.
            kwargs["env"]["MUSE_AUTH_PATH"] = "/nonexistent/offline-auth"
            return run_process(command, **kwargs)

        with patch("agent_world.muse_brain.run_process", side_effect=loopback):
            decision = brain.decide({"tick": 1, "self": {"id": "fixture"}})
        self.assertIsNone(decision.failure_kind, decision.intent)
        self.assertEqual(len(requests), 1, "Background reminders must not create extra model calls")
        self.assertEqual(requests[0]["model"], "muse-spark-1.3")
        self.assertEqual(requests[0]["reasoning"]["effort"], "low")
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["prompt_tokens"], 100)
        self.assertEqual(record["completion_tokens"], 20)
        self.assertEqual(record["cached_tokens"], 50)
        self.assertEqual(record["reasoning_tokens"], 8)
        self.assertIsNone(record["response_model"])
        self.assertEqual(record["native_configured_model"], "muse-spark-1.3")
        self.assertEqual(record["tool_calls"], 0)
        self.assertEqual(record["model_provenance"], "requested_only")
        self.assertEqual(len(record["native_trace_sha256"]), 64)

        # Native model_completed.model repeats the request, not the returned ID.
        # Keep this regression so it can never silently become "observed" evidence.
        returned_model = "provider-reported-different"
        with patch("agent_world.muse_brain.run_process", side_effect=loopback):
            second = brain.decide({"tick": 2, "self": {"id": "fixture"}})
        self.assertIsNone(second.failure_kind, second.intent)
        record = brain.runtime.usage_records()[-1]
        self.assertIsNone(record["response_model"])
        self.assertEqual(record["model_provenance"], "requested_only")
        self.assertEqual(len(requests), 2)


if __name__ == "__main__":
    unittest.main()
