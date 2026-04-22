#!/usr/bin/env python3
"""
Hook emit script. Called by Claude Code for each configured hook event.

Reads the hook JSON payload from stdin, extracts session_id and
hook_event_name, and publishes one NDJSON line to the session's broker
(spawning the broker if it's not already running).

Designed to be fast and never block Claude on failures: any error
results in exit 0 with a message to stderr.
"""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SPAWN_TIMEOUT_SECONDS = 3.0
CONNECT_TIMEOUT_SECONDS = 0.5


def data_dir() -> Path:
    d = os.environ.get("CLAUDE_PLUGIN_DATA")
    if d:
        return Path(d)
    return Path.home() / ".claude" / "status-data"


def state_path(session_id: str) -> Path:
    return data_dir() / "sessions" / session_id / "broker.json"


def read_port(session_id: str) -> int | None:
    p = state_path(session_id)
    if not p.exists():
        return None
    try:
        return int(json.loads(p.read_text())["port"])
    except Exception:
        return None


def try_connect(port: int) -> socket.socket | None:
    try:
        return socket.create_connection(("127.0.0.1", port), timeout=CONNECT_TIMEOUT_SECONDS)
    except Exception:
        return None


def spawn_broker(session_id: str) -> int | None:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        sys.stderr.write("[emit] CLAUDE_PLUGIN_ROOT not set; cannot spawn broker\n")
        return None
    log_dir = data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "broker.log"
    broker_path = Path(root) / "bin" / "broker.py"
    with open(log_file, "ab") as lf:
        subprocess.Popen(
            ["python3", str(broker_path), session_id],
            stdout=lf,
            stderr=lf,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    deadline = time.time() + SPAWN_TIMEOUT_SECONDS
    while time.time() < deadline:
        port = read_port(session_id)
        if port:
            sock = try_connect(port)
            if sock is not None:
                sock.close()
                return port
        time.sleep(0.05)
    return None


_FORWARDED_FIELDS = (
    "prompt",
    "message",
    "title",
    "notification_type",
    "tool_name",
    "tool_input",
    "tool_response",
    "reason",
    "trigger",
    "success",
    "error",
)


def build_event(payload: dict) -> dict:
    event = {
        "ts": time.time(),
        "event": payload.get("hook_event_name"),
        "session_id": payload.get("session_id"),
    }
    for key in _FORWARDED_FIELDS:
        if key in payload:
            event[key] = payload[key]
    return event


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        sys.stderr.write(f"[emit] bad stdin JSON: {e}\n")
        return
    session_id = payload.get("session_id")
    if not session_id or not payload.get("hook_event_name"):
        sys.stderr.write("[emit] missing session_id or hook_event_name\n")
        return

    port = read_port(session_id)
    sock = try_connect(port) if port else None
    if sock is None:
        port = spawn_broker(session_id)
        if port is None:
            sys.stderr.write("[emit] broker unreachable\n")
            return
        sock = try_connect(port)
        if sock is None:
            sys.stderr.write("[emit] spawned but unreachable\n")
            return

    try:
        line = json.dumps(build_event(payload)).encode("utf-8") + b"\n"
        sock.sendall(b"PUB\n" + line)
    except Exception as e:
        sys.stderr.write(f"[emit] send failed: {e}\n")
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
