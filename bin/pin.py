#!/usr/bin/env python3
"""
Pin the claude-status transport to a specific Claude Code session, or
release the pin.

While pinned, the Windows-side bridge ignores newer sessions and stays
subscribed to the pinned one. This prevents a freshly-opened Claude
session somewhere else from hijacking the visible status indicator.

Usage:
  pin.py attach [<session_id>]
      Pin to the given session. If omitted, pins to the most recently
      active session (useful right after a hook has fired in the
      session you want to pin).
  pin.py detach
      Remove the pin. Auto-switching resumes.
  pin.py status
      Print the current pin state to stdout.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import data_dir, windows_mirror_dir  # noqa: E402


PIN_FILENAME = "pin.json"


def pin_path(base: Path) -> Path:
    return base / PIN_FILENAME


def targets() -> list[Path]:
    """Locations where the pin file should live. Primary data dir always;
    Windows mirror too if we can see it."""
    out = [pin_path(data_dir())]
    mirror = windows_mirror_dir()
    if mirror:
        out.append(pin_path(mirror))
    return out


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
    for p in targets():
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
    removed: list[Path] = []
    for p in targets():
        if p.exists():
            try:
                p.unlink()
                removed.append(p)
            except Exception as e:
                sys.stderr.write(f"[pin] failed to remove {p}: {e}\n")
    return removed


def read_pin() -> str | None:
    for p in targets():
        if p.is_file():
            try:
                return json.loads(p.read_text())["session_id"]
            except Exception:
                pass
    return None


def cmd_attach(session_id: str | None) -> int:
    if session_id is None:
        # Prefer the mirror dir for discovery because that's where the bridge
        # looks; fall back to primary data dir otherwise.
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


def cmd_status() -> int:
    sid = read_pin()
    if sid:
        print(f"pinned: {sid}")
    else:
        print("not pinned (auto-switching enabled)")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: pin.py attach [<session_id>] | detach | status", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "attach":
        session_id = sys.argv[2] if len(sys.argv) >= 3 else None
        return cmd_attach(session_id)
    if cmd == "detach":
        return cmd_detach()
    if cmd == "status":
        return cmd_status()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
