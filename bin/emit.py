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

# Force UTF-8 on stderr — same reason as pin.py: avoids
# UnicodeEncodeError on Windows when stderr writes contain non-ANSI-
# codepage glyphs. emit.py is meant to be silent on success; this just
# makes failure messages survive the journey.
try:
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, TypeError, ValueError):
    pass

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
            # sys.executable is the exact Python interpreter currently
            # running emit.py — avoids the "is python3 on PATH" class of
            # question on Windows where the python.org installer only
            # puts `python.exe` (not `python3.exe`) on PATH.
            [sys.executable, str(broker_path), session_id],
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


_SLASH_PREFIX = "/claude-status:"


def _handle_slash_command(prompt: str, session_id: str) -> dict | None:
    """
    React to /claude-status:* slash commands at hook time, where we have an
    authoritative session_id. Eliminates the "guess by newest broker"
    heuristic that breaks under multi-session use.

    Returns an optional firmware_command dict that the caller should
    inject into the broker event so the bridge can forward it verbatim
    to the serial port (used for one-shot commands like identify that
    don't fit the persistent-state-file pattern).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import pin  # noqa: WPS433
    except Exception as e:
        sys.stderr.write(f"[emit] cannot import pin module: {e}\n")
        return None

    body = prompt[len(_SLASH_PREFIX):].strip()

    # v0.4 primary verbs: show / hide.
    # `show <slot>` binds this session to <slot>, displacing any prior
    # occupant and releasing any prior slot this session held.
    # `hide` removes this session's binding entirely.
    if body.startswith("show "):
        slot = body[len("show "):].strip()
        ok, _ = pin.bind_slot(session_id, slot)
        if not ok:
            sys.stderr.write(f"[emit] /claude-status:show: invalid slot '{slot}'\n")
            return None
        sys.stderr.write(f"[emit] /claude-status:show {slot} -> bound {session_id}\n")
    elif body == "hide":
        pin.unbind_session(session_id)
        sys.stderr.write(f"[emit] /claude-status:hide -> {session_id} unbound\n")
    elif body == "reset":
        removed = pin.reset_all()
        sys.stderr.write(
            f"[emit] /claude-status:reset -> removed {len(removed)} file(s)\n"
        )
    elif body.startswith("configure "):
        rest = body[len("configure "):].strip()
        try:
            count = int(rest.split()[0])
        except (ValueError, IndexError):
            sys.stderr.write(f"[emit] /claude-status:configure: invalid panel count '{rest}'\n")
            return None
        ok, _ = pin.set_panel_layout(panel_count=count)
        if ok:
            sys.stderr.write(f"[emit] /claude-status:configure -> panel_count={count}\n")
        else:
            sys.stderr.write(f"[emit] /claude-status:configure: panel_count {count} out of range (1-4)\n")
    elif body == "identify" or body.startswith("identify "):
        rest = body[len("identify"):].strip()
        duration_ms = 5000
        if rest:
            try:
                duration_ms = int(float(rest) * 1000)
            except ValueError:
                sys.stderr.write(f"[emit] /claude-status:identify: invalid duration '{rest}'\n")
                return None
        sys.stderr.write(f"[emit] /claude-status:identify -> duration_ms={duration_ms}\n")
        return {"type": "identify", "duration_ms": duration_ms}
    return None
    # `status` is read-only; no action needed at hook time


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

    # Hook-driven slash command handling. We do this BEFORE publishing to
    # the broker, so that even if broker spawn fails, the action still ran.
    firmware_command: dict | None = None
    event_name = payload.get("hook_event_name")
    if event_name == "UserPromptSubmit":
        prompt = (payload.get("prompt") or "").strip()
        if prompt.startswith(_SLASH_PREFIX):
            firmware_command = _handle_slash_command(prompt, session_id)
    elif event_name == "SessionStart":
        # CLI pairing: `CLAUDE_STATUS_SLOT=1 claude` binds the session
        # to slot 1 the moment it starts, without the user having to
        # type `/claude-status:show 1`. Invalid slots are logged and
        # ignored — we never fail the hook.
        slot = os.environ.get("CLAUDE_STATUS_SLOT", "").strip()
        if slot:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            try:
                import pin  # noqa: WPS433
                ok, _ = pin.bind_slot(session_id, slot)
                if ok:
                    sys.stderr.write(
                        f"[emit] SessionStart -> bound to slot {slot} "
                        f"via CLAUDE_STATUS_SLOT\n"
                    )
                else:
                    sys.stderr.write(
                        f"[emit] SessionStart: invalid CLAUDE_STATUS_SLOT "
                        f"'{slot}'\n"
                    )
            except Exception as e:
                sys.stderr.write(f"[emit] SessionStart: pin import failed: {e}\n")

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
        event = build_event(payload)
        if firmware_command is not None:
            event["firmware_command"] = firmware_command
        line = json.dumps(event).encode("utf-8") + b"\n"
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
