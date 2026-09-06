"""Codex App Server client for durable, event-driven Astra supervision."""
from __future__ import annotations
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

MODEL = "gpt-6-astra"
EFFORT = "low"


class SupervisorError(RuntimeError):
    pass


class SupervisorTimeout(SupervisorError):
    pass


class AstraClient:
    def __init__(self, binary: str, root: Path):
        self.root = root
        self.native_windows = binary.lower().endswith(".exe")
        self.process = subprocess.Popen(
            [binary, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
            env={**os.environ, "PATH": str(Path.home() / ".local/bin") + ":" + os.environ.get("PATH", "")},
        )
        self.messages = queue.Queue()
        self.events = []
        self.sequence = 0
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.rpc("initialize", {"clientInfo": {"name": "agent_world_leaderboard", "version": "1.0"},
                                    "capabilities": {"experimentalApi": True}})
            self.send({"method": "initialized", "params": {}})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            self.messages.put(None)

    def send(self, payload):
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def receive(self, timeout=30):
        try:
            item = self.messages.get(timeout=timeout)
        except queue.Empty:
            raise SupervisorTimeout("Astra supervisor did not respond in time")
        if item is None:
            raise SupervisorError("Astra supervisor connection closed")
        # Automatic approval review is configured on the thread. If a request
        # still reaches this headless client, never approve it silently.
        if "id" in item and "method" in item:
            self.send({"id": item["id"], "error": {"code": -32000,
                       "message": "This request requires operator attention in the dashboard."}})
            raise SupervisorError("Astra needs operator input: " + item["method"])
        return item

    def rpc(self, method, params, timeout=30):
        self.sequence += 1
        request_id = self.sequence
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self.receive(max(0.1, deadline - time.monotonic()))
            if msg.get("id") == request_id:
                if "error" in msg:
                    raise SupervisorError(str(msg["error"].get("message", "Codex request failed"))[:500])
                return msg.get("result", {})
            self.events.append(msg)
        raise SupervisorError("Codex request timed out")

    def verify(self):
        cursor = None
        while True:
            params = {"includeHidden": True}
            if cursor:
                params["cursor"] = cursor
            result = self.rpc("model/list", params)
            for model in result.get("data", []):
                if model.get("model") == MODEL and any(
                    level.get("reasoningEffort") == EFFORT
                    for level in model.get("supportedReasoningEfforts", [])
                ):
                    return {"model": MODEL, "effort": EFFORT}
            cursor = result.get("nextCursor")
            if not cursor:
                break
        raise SupervisorError("GPT-6 Astra with low effort is unavailable in the configured Codex runtime")

    def attach(self, thread_id=None):
        cwd = str(self.root)
        if self.native_windows:
            cwd = subprocess.check_output(["wslpath", "-w", cwd], text=True).strip()
        params = {
            "cwd": cwd, "model": MODEL, "sandbox": "workspace-write",
            "approvalPolicy": "on-request", "approvalsReviewer": "auto_review",
            "config": {"model_reasoning_effort": EFFORT},
        }
        if thread_id:
            params["threadId"] = thread_id
        result = self.rpc("thread/resume" if thread_id else "thread/start", params)
        if result.get("model") != MODEL:
            raise SupervisorError("Codex did not confirm the requested Astra model")
        return result["thread"]["id"]

    def turn(self, thread_id, prompt, on_update):
        result = self.rpc("turn/start", {
            "threadId": thread_id, "model": MODEL, "effort": EFFORT,
            "input": [{"type": "text", "text": prompt}],
        })
        turn_id = result["turn"]["id"]
        on_update({"supervisor_turn_id": turn_id, "supervisor_state": "working"})
        pending, self.events = self.events, []
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            try:
                msg = pending.pop(0) if pending else self.receive(timeout=30)
            except SupervisorTimeout:
                if self.process.poll() is None:
                    continue
                raise
            params = msg.get("params", {})
            if params.get("threadId") != thread_id:
                continue
            method = msg.get("method")
            if method == "item/completed":
                item = params.get("item", {})
                if item.get("type") == "agentMessage":
                    on_update({"supervisor_message": item.get("text", "")[-6000:]})
            if method == "turn/completed" and params.get("turn", {}).get("id") == turn_id:
                turn = params["turn"]
                if turn.get("status") != "completed":
                    raise SupervisorError("Astra turn failed: " + str(turn.get("error") or turn.get("status")))
                on_update({"supervisor_state": "watching"})
                return
        try:
            self.rpc("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
        finally:
            raise SupervisorError("Astra supervision turn exceeded its time allowance")

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
