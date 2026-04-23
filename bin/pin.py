#!/usr/bin/env python3
"""
Pin and routing helpers for the claude-status transport.

Two related but distinct concepts:

* PIN — which Claude Code session does the bridge SUBSCRIBE to? (one
  bridge listens to one broker at a time today.)
* ROUTE — which display client slot does the bridge tag a session's
  outgoing snapshots with? (lets you direct one session's events to
  panel "1", another to "2b", etc.)

Both pin and route state live next to each other in the plugin data
dir (and a Windows mirror, on WSL):
  pin.json       {"session_id": "..."}
  routes.json    {"<session_id>": "<slot>", ...}

CLI usage (mostly invoked by emit.py from slash-command hook context;
direct CLI use is also supported):

  pin.py attach [<session_id>]            Pin (defaults to newest)
  pin.py detach                           Remove pin
  pin.py route <session_id> <slot>        Set route entry
  pin.py unroute <session_id>             Remove route entry
  pin.py status                           Print pin + route table
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import data_dir, windows_mirror_dir  # noqa: E402


PIN_FILENAME    = "pin.json"
ROUTES_FILENAME = "routes.json"

SLOT_PATTERN = re.compile(r"^\d{1,2}[ab]?$")


# ----------------------------- PATHS -----------------------------

def pin_path(base: Path) -> Path:
    return base / PIN_FILENAME


def routes_path(base: Path) -> Path:
    return base / ROUTES_FILENAME


def targets() -> list[Path]:
    """
    Bases for WRITES — the canonical place to land new pin/route state.
    Current plugin context's data dir, plus the Windows mirror on WSL so
    the Windows-side bridge can read without traversing \\\\wsl$\\.
    """
    out = [data_dir()]
    mirror = windows_mirror_dir()
    if mirror:
        out.append(mirror)
    return out


def read_bases() -> list[Path]:
    """
    Bases for READS / REMOVES — wider than targets() because pin/route
    state may have been written by an earlier emit.py invocation under a
    different CLAUDE_PLUGIN_DATA, by direct CLI use (which falls back to
    ~/.claude/status-data), or by the hook (which lands under
    ~/.claude/plugins/data/<plugin-name>/). We walk all of these so reads
    and removes catch every copy and keep state coherent across contexts.
    """
    seen: set[Path] = set()
    out: list[Path] = []

    def add(p: Path | None) -> None:
        if p is None:
            return
        try:
            r = p.resolve()
        except OSError:
            return
        if r not in seen:
            seen.add(r)
            out.append(p)

    # Whatever the current context says is "the" data dir.
    add(data_dir())
    # Legacy default location, in case earlier CLI runs landed here.
    add(Path.home() / ".claude" / "status-data")
    # All plugin data subdirs — the hook writes here when CLAUDE_PLUGIN_DATA
    # is set by Claude Code at hook-fire time.
    plugins_data = Path.home() / ".claude" / "plugins" / "data"
    if plugins_data.is_dir():
        for sub in plugins_data.iterdir():
            if sub.is_dir():
                add(sub)
    # Windows mirror (WSL crossing).
    add(windows_mirror_dir())

    return out


# --------------------------- PIN STATE ---------------------------

def find_newest_session(base: Path) -> str | None:
    sessions_dir = base / "sessions"
    if not sessions_dir.is_dir():
        return None
    best: tuple[float, str] | None = None
    for session_dir in sessions_dir.iterdir():
        bj = session_dir / "broker.json"
        if not bj.is_file():
            continue
        mtime = bj.stat().st_mtime
        if best is None or mtime > best[0]:
            best = (mtime, session_dir.name)
    return best[1] if best else None


def write_pin(session_id: str) -> list[Path]:
    payload = json.dumps({"session_id": session_id, "ts": time.time()})
    written: list[Path] = []
    for base in targets():
        p = pin_path(base)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(payload)
            os.replace(tmp, p)
            written.append(p)
        except Exception as e:
            sys.stderr.write(f"[pin] failed to write {p}: {e}\n")
    return written


def remove_pin() -> list[Path]:
    # Walk read_bases() so we clean every copy of pin.json, including
    # stale ones written under a different CLAUDE_PLUGIN_DATA.
    removed: list[Path] = []
    for base in read_bases():
        p = pin_path(base)
        if p.exists():
            try:
                p.unlink()
                removed.append(p)
            except Exception as e:
                sys.stderr.write(f"[pin] failed to remove {p}: {e}\n")
    return removed


def read_pin() -> str | None:
    for base in read_bases():
        p = pin_path(base)
        if p.is_file():
            try:
                return json.loads(p.read_text())["session_id"]
            except Exception:
                pass
    return None


# ------------------------- ROUTE STATE -------------------------

def is_valid_slot(slot: str) -> bool:
    """A valid slot is `<N>[a|b]`, e.g. "1", "1a", "1b", "2", "12a"."""
    return bool(SLOT_PATTERN.fullmatch(slot))


def read_routes() -> dict[str, str]:
    """Merge route entries from every known base."""
    merged: dict[str, str] = {}
    for base in read_bases():
        p = routes_path(base)
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str):
                        merged[k] = v
        except Exception:
            pass
    return merged


def _write_routes(routes: dict[str, str]) -> list[Path]:
    payload = json.dumps(routes, indent=2)
    written: list[Path] = []
    for base in targets():
        p = routes_path(base)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(payload)
            os.replace(tmp, p)
            written.append(p)
        except Exception as e:
            sys.stderr.write(f"[route] failed to write {p}: {e}\n")
    return written


def set_route(session_id: str, slot: str) -> tuple[bool, list[Path]]:
    if not is_valid_slot(slot):
        return False, []
    routes = read_routes()
    routes[session_id] = slot
    return True, _write_routes(routes)


def remove_route(session_id: str) -> list[Path]:
    """
    Remove a route entry from every known base. We walk read_bases() so
    no stale copies linger after detach/unroute.
    """
    written: list[Path] = []
    for base in read_bases():
        p = routes_path(base)
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text())
            if not isinstance(data, dict) or session_id not in data:
                continue
            del data[session_id]
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2))
            os.replace(tmp, p)
            written.append(p)
        except Exception as e:
            sys.stderr.write(f"[route] failed to update {p}: {e}\n")
    return written


# --------------------------- COMMANDS ---------------------------

def cmd_attach(session_id: str | None) -> int:
    if session_id is None:
        base = windows_mirror_dir() or data_dir()
        session_id = find_newest_session(base)
        if session_id is None:
            print(
                "no active broker found — make sure at least one hook has fired "
                "in the session you want to pin (send any prompt).",
                file=sys.stderr,
            )
            return 1
    paths = write_pin(session_id)
    if not paths:
        print("failed to write pin file anywhere", file=sys.stderr)
        return 1
    print(f"pinned to session {session_id}")
    for p in paths:
        print(f"  wrote {p}")
    return 0


def cmd_detach() -> int:
    paths = remove_pin()
    if not paths:
        print("no pin was set")
    else:
        print("pin released")
        for p in paths:
            print(f"  removed {p}")
    return 0


def cmd_route(session_id: str, slot: str) -> int:
    ok, paths = set_route(session_id, slot)
    if not ok:
        print(f"invalid slot '{slot}' (expected N or Na or Nb, e.g. 1, 2b)",
              file=sys.stderr)
        return 1
    print(f"routed {session_id} -> {slot}")
    for p in paths:
        print(f"  wrote {p}")
    return 0


def cmd_unroute(session_id: str) -> int:
    paths = remove_route(session_id)
    if not paths:
        print(f"no route for {session_id}")
    else:
        print(f"unrouted {session_id}")
        for p in paths:
            print(f"  wrote {p}")
    return 0


def cmd_status() -> int:
    sid = read_pin()
    print(f"pin:    {sid if sid else '(none — auto-switching enabled)'}")
    routes = read_routes()
    if not routes:
        print("routes: (none)")
    else:
        print("routes:")
        for k, v in routes.items():
            marker = " ← pinned" if k == sid else ""
            print(f"  {k} -> {v}{marker}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "attach":
        return cmd_attach(sys.argv[2] if len(sys.argv) >= 3 else None)
    if cmd == "detach":
        return cmd_detach()
    if cmd == "route":
        if len(sys.argv) < 4:
            print("usage: pin.py route <session_id> <slot>", file=sys.stderr)
            return 2
        return cmd_route(sys.argv[2], sys.argv[3])
    if cmd == "unroute":
        if len(sys.argv) < 3:
            print("usage: pin.py unroute <session_id>", file=sys.stderr)
            return 2
        return cmd_unroute(sys.argv[2])
    if cmd == "status":
        return cmd_status()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
