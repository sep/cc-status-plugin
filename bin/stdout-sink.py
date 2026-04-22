#!/usr/bin/env python3
"""
Subscribe to a session's broker and print events to stdout.

Usage:
  stdout-sink.py <session_id>      Subscribe to a specific session.
  stdout-sink.py --find            Auto-discover the newest live broker and
                                   subscribe. Useful for external validation
                                   when CLAUDE_PLUGIN_DATA isn't inherited.
"""
import json
import os
import socket
import sys
import time
from pathlib import Path


CANDIDATE_DATA_DIRS = [
    os.environ.get("CLAUDE_PLUGIN_DATA"),
    str(Path.home() / ".claude" / "status-data"),
    "/tmp/claude-status-test",
]
CLAUDE_PLUGINS_DATA_ROOT = Path.home() / ".claude" / "plugins" / "data"


def candidate_sessions_dirs() -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        try:
            r = p.resolve()
        except OSError:
            return
        if r not in seen and p.is_dir():
            seen.add(r)
            out.append(p)

    for c in CANDIDATE_DATA_DIRS:
        if c:
            add(Path(c) / "sessions")

    if CLAUDE_PLUGINS_DATA_ROOT.is_dir():
        for sub in CLAUDE_PLUGINS_DATA_ROOT.iterdir():
            if sub.is_dir():
                add(sub / "sessions")

    return out


def state_path_for(session_id: str) -> Path | None:
    for sd in candidate_sessions_dirs():
        p = sd / session_id / "broker.json"
        if p.exists():
            return p
    return None


def read_port_at(state_file: Path) -> int | None:
    try:
        return int(json.loads(state_file.read_text())["port"])
    except Exception:
        return None


def find_newest_session() -> tuple[str, Path] | None:
    best: tuple[float, str, Path] | None = None
    for sd in candidate_sessions_dirs():
        for session_dir in sd.iterdir():
            bj = session_dir / "broker.json"
            if not bj.exists():
                continue
            mtime = bj.stat().st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, session_dir.name, bj)
    if best is None:
        return None
    return best[1], best[2]


def _connect_blocking(port: int) -> socket.socket | None:
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=1.0)
    except OSError:
        return None
    sock.settimeout(None)
    return sock


def wait_for_broker_by_id(session_id: str) -> socket.socket:
    waited = 0.0
    while True:
        sf = state_path_for(session_id)
        if sf is not None:
            port = read_port_at(sf)
            if port:
                sock = _connect_blocking(port)
                if sock:
                    return sock
        if waited % 5 < 1.0:
            sys.stderr.write(f"[sink] waiting for broker (session {session_id[:8]})...\n")
        time.sleep(1.0)
        waited += 1.0


def wait_for_any_broker() -> tuple[str, socket.socket]:
    waited = 0.0
    while True:
        found = find_newest_session()
        if found:
            session_id, sf = found
            port = read_port_at(sf)
            if port:
                sock = _connect_blocking(port)
                if sock:
                    return session_id, sock
        if waited % 5 < 1.0:
            dirs = [str(d) for d in candidate_sessions_dirs()] or ["(none found)"]
            sys.stderr.write(f"[sink] scanning for broker under: {', '.join(dirs)}\n")
        time.sleep(1.0)
        waited += 1.0


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: stdout-sink.py <session_id>|--find", file=sys.stderr)
        sys.exit(2)
    arg = sys.argv[1]
    if arg == "--find":
        session_id, sock = wait_for_any_broker()
    else:
        session_id = arg
        sock = wait_for_broker_by_id(session_id)
    sock.sendall(b"SUB\n")
    sys.stderr.write(f"[sink] connected, streaming session {session_id[:8]}\n")
    f = sock.makefile("r", encoding="utf-8")
    for line in f:
        line = line.rstrip()
        if not line:
            continue
        try:
            evt = json.loads(line)
            ts = evt.get("ts", time.time())
            stamp = time.strftime("%H:%M:%S", time.localtime(ts))
            name = evt.get("event", "?")
            extra = {k: v for k, v in evt.items() if k not in ("ts", "event", "session_id")}
            suffix = f"  {json.dumps(extra)}" if extra else ""
            print(f"[{stamp}] {name}{suffix}", flush=True)
        except Exception:
            print(line, flush=True)


if __name__ == "__main__":
    main()
