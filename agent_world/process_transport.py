"""Bounded subprocess transport shared by command-line model adapters."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from typing import Any

MAX_OUTPUT_BYTES = 16 * 1024 * 1024


class ProcessOutputLimitError(RuntimeError):
    pass


def terminate_owned_process(process: subprocess.Popen) -> None:
    """Reap an owned process group, including descendants holding inherited pipes."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def run_process(args: list[str], *, input: str | bytes | None = None,
                text: bool = False, capture_output: bool = True,
                timeout: float = 300, check: bool = False,
                max_output_bytes: int = MAX_OUTPUT_BYTES, **kwargs: Any) -> subprocess.CompletedProcess:
    """Run a fresh process with one deadline and bounded, concurrently drained pipes."""
    if not capture_output:
        raise ValueError("Model transports require captured output")
    deadline = time.monotonic() + timeout
    payload = input.encode("utf-8") if isinstance(input, str) else input or b""
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True, **kwargs)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    try:
        for name in output:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        if payload:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        else:
            process.stdin.close()
        sent = 0
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(args, timeout, bytes(output["stdout"]), bytes(output["stderr"]))
            for key, mask in selector.select(remaining):
                if key.data == "stdin":
                    try:
                        sent += os.write(key.fd, payload[sent:sent + 65536])
                    except BrokenPipeError:
                        sent = len(payload)
                    if sent == len(payload):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                output[key.data].extend(chunk)
                if sum(map(len, output.values())) > max_output_bytes:
                    raise ProcessOutputLimitError(f"Process exceeded {max_output_bytes} output bytes")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(args, timeout, bytes(output["stdout"]), bytes(output["stderr"]))
        process.wait(timeout=remaining)
        stdout, stderr = bytes(output["stdout"]), bytes(output["stderr"])
        if text:
            stdout, stderr = stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
    finally:
        selector.close()
        terminate_owned_process(process)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
