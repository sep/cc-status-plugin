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
import re
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


def plugin_root() -> Path:
    """
    Claude Code and Copilot CLI (>= 1.0.26) both export CLAUDE_PLUGIN_ROOT
    for plugin hooks. Repo-level hook installs (e.g. Copilot's
    .github/hooks/*.json) run without it — emit.py lives in
    <plugin root>/bin/, so our own location is an equivalent answer.
    """
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent


def spawn_broker(session_id: str) -> int | None:
    root = plugin_root()
    data_dir().mkdir(parents=True, exist_ok=True)
    broker_path = root / "bin" / "broker.py"
    subprocess.Popen(
        # sys.executable is the exact Python interpreter currently
        # running emit.py — avoids the "is python3 on PATH" class of
        # question on Windows where the python.org installer only
        # puts `python.exe` (not `python3.exe`) on PATH.
        #
        # DEVNULL stdio on purpose: handing the broker an inherited
        # broker.log handle would hold a lock inside the plugin-data
        # dir for the broker's lifetime, which blocks plugin
        # uninstall/update on Windows. The broker appends to
        # broker.log itself, open-and-close per line.
        [sys.executable, str(broker_path), session_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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


def _debug_log(record: dict) -> None:
    """
    Append one NDJSON line describing this hook invocation to
    debug.log in both the data dir and the well-known discovery dir.
    Enabled by CLAUDE_STATUS_DEBUG=1 in the agent's environment (the
    hook process inherits it). This is the primary tool for answering
    "did the hook fire at all, and with what payload?" when a new
    agent host (e.g. a Copilot CLI release) changes behavior.
    """
    if os.environ.get("CLAUDE_STATUS_DEBUG", "").strip().lower() not in ("1", "true", "yes"):
        return
    # Shallow-truncate long string fields (tool_response and friends)
    # so one noisy event can't balloon the log.
    payload = record.get("payload")
    if isinstance(payload, dict):
        record = dict(record)
        record["payload"] = {
            k: (v[:2000] + "…" if isinstance(v, str) and len(v) > 2000 else v)
            for k, v in payload.items()
        }
    targets = [data_dir()]
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from broker import discovery_dir  # noqa: WPS433
        d = discovery_dir()
        if d is not None:
            targets.append(d)
    except Exception:
        pass
    line = json.dumps({"ts": time.time(), **record}, default=str) + "\n"
    for t in targets:
        try:
            t.mkdir(parents=True, exist_ok=True)
            with open(t / "debug.log", "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


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


_SLASH_PREFIX = "/llmstatus:"

# GitHub Copilot CLI rewrites a slash-command invocation before the
# userPromptSubmitted hook sees it: the raw typed text is replaced by
#   The user explicitly invoked the "/llmstatus:<verb>" skill. ...
#   <skill-context name="<verb>">...body...ARGUMENTS: <args>\n</skill-context>
# The verb comes from the first line and the arguments from the trailing
# ARGUMENTS: line (absent when the user passed none).
_COPILOT_SKILL_RE = re.compile(
    r'^The user explicitly invoked the "' + re.escape(_SLASH_PREFIX) + r'([a-z]+)" skill'
)
_COPILOT_ARGS_RE = re.compile(r"^ARGUMENTS:[ \t]*(.*)$", re.MULTILINE)


def _extract_command_body(prompt: str) -> str | None:
    """
    Return the '<verb> [args]' body of a /llmstatus command, or None
    if the prompt isn't one. Handles both hosts: Claude Code passes the
    raw typed text ('/llmstatus:show 1'); Copilot CLI passes its
    rewritten skill-invocation form (see _COPILOT_SKILL_RE).
    """
    if prompt.startswith(_SLASH_PREFIX):
        return prompt[len(_SLASH_PREFIX):].strip()
    m = _COPILOT_SKILL_RE.match(prompt)
    if m:
        verb = m.group(1)
        arg_lines = _COPILOT_ARGS_RE.findall(prompt)
        args = arg_lines[-1].strip() if arg_lines else ""
        return f"{verb} {args}".strip()
    return None


def _handle_slash_command(body: str, session_id: str) -> dict | None:
    """
    React to /llmstatus:* slash commands at hook time, where we have an
    authoritative session_id. Eliminates the "guess by newest broker"
    heuristic that breaks under multi-session use.

    `body` is the extracted '<verb> [args]' text (see
    _extract_command_body).

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

    # v0.4 primary verbs: show / hide.
    # `show <slot>` binds this session to <slot>, displacing any prior
    # occupant and releasing any prior slot this session held.
    # `hide` removes this session's binding entirely.
    if body.startswith("show "):
        slot = body[len("show "):].strip()
        ok, _ = pin.bind_slot(session_id, slot)
        if not ok:
            sys.stderr.write(f"[emit] /llmstatus:show: invalid slot '{slot}'\n")
            return None
        sys.stderr.write(f"[emit] /llmstatus:show {slot} -> bound {session_id}\n")
    elif body == "hide":
        pin.unbind_session(session_id)
        sys.stderr.write(f"[emit] /llmstatus:hide -> {session_id} unbound\n")
    elif body == "reset":
        removed = pin.reset_all()
        sys.stderr.write(
            f"[emit] /llmstatus:reset -> removed {len(removed)} file(s)\n"
        )
    elif body.startswith("configure "):
        rest = body[len("configure "):].strip()
        try:
            count = int(rest.split()[0])
        except (ValueError, IndexError):
            sys.stderr.write(f"[emit] /llmstatus:configure: invalid panel count '{rest}'\n")
            return None
        ok, _ = pin.set_panel_layout(panel_count=count)
        if ok:
            sys.stderr.write(f"[emit] /llmstatus:configure -> panel_count={count}\n")
        else:
            sys.stderr.write(f"[emit] /llmstatus:configure: panel_count {count} out of range (1-4)\n")
    elif body == "identify" or body.startswith("identify "):
        rest = body[len("identify"):].strip()
        duration_ms = 5000
        if rest:
            try:
                duration_ms = int(float(rest) * 1000)
            except ValueError:
                sys.stderr.write(f"[emit] /llmstatus:identify: invalid duration '{rest}'\n")
                return None
        sys.stderr.write(f"[emit] /llmstatus:identify -> duration_ms={duration_ms}\n")
        return {"type": "identify", "duration_ms": duration_ms}
    return None
    # `status` is read-only; no action needed at hook time


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception as e:
        _debug_log({"error": f"bad stdin JSON: {e}", "raw": raw[:2000]})
        sys.stderr.write(f"[emit] bad stdin JSON: {e}\n")
        return
    _debug_log({
        "exe": sys.executable,
        "plugin_root_env": os.environ.get("CLAUDE_PLUGIN_ROOT"),
        "plugin_data_env": os.environ.get("CLAUDE_PLUGIN_DATA"),
        "payload": payload,
    })
    # Copilot CLI's notification event arrives as a camelCase/snake_case
    # hybrid: hook_event_name is present but the session id is spelled
    # sessionId. Normalize so build_event and routing see one shape.
    session_id = payload.get("session_id") or payload.get("sessionId")
    if session_id:
        payload["session_id"] = session_id
    if not session_id or not payload.get("hook_event_name"):
        sys.stderr.write("[emit] missing session_id or hook_event_name\n")
        return

    # Hook-driven slash command handling. We do this BEFORE publishing to
    # the broker, so that even if broker spawn fails, the action still ran.
    firmware_command: dict | None = None
    event_name = payload.get("hook_event_name")
    if event_name == "UserPromptSubmit":
        prompt = (payload.get("prompt") or "").strip()
        body = _extract_command_body(prompt)
        if body is not None:
            firmware_command = _handle_slash_command(body, session_id)
    elif event_name == "SessionStart":
        # CLI pairing: `CLAUDE_STATUS_SLOT=1 claude` binds the session
        # to slot 1 the moment it starts, without the user having to
        # type `/llmstatus:show 1`. Invalid slots are logged and
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
        # SessionEnd's only broker-side job is telling a live broker to
        # retire; spawning one just to kill it would be silly.
        if event_name == "SessionEnd":
            return
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
