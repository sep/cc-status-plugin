#!/usr/bin/env python3
"""
TCP NDJSON broker for claude-status.

Protocol per connection:
  line 1: "PUB\\n" or "SUB\\n" (optional JSON filter after SUB is ignored in v0)
  PUB connections: subsequent lines are JSON events, fanned out to all subscribers.
  SUB connections: receive fanned-out events until they disconnect.

State file: <data_dir>/sessions/<session_id>/broker.json holds {"pid": N, "port": N}.
Broker self-terminates after IDLE_EXIT_SECONDS of no events and no subscribers.
"""
import asyncio
import json
import os
import signal
import socket
import sys
import time
from pathlib import Path

IDLE_EXIT_SECONDS = 900
HANDSHAKE_TIMEOUT = 5.0


def data_dir() -> Path:
    d = os.environ.get("CLAUDE_PLUGIN_DATA")
    if d:
        return Path(d)
    return Path.home() / ".claude" / "status-data"


def _port_listening(port: int) -> bool:
    if port <= 0:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except Exception:
        return False


def discovery_dir() -> Path | None:
    """
    Canonical well-known discovery location for broker state, pin, and
    routes. Independent of CLAUDE_PLUGIN_DATA and CLAUDE_CONFIG_DIR, so
    any bridge on the same machine can find Claude session state
    regardless of how Claude was launched — including clean-room runs
    with `CLAUDE_CONFIG_DIR=$(mktemp -d)` whose plugin data lives under
    a temporary path that's invisible to the bridge's normal globbing.

    Locations:
      - WSL:                 /mnt/c/Users/<user>/.claude-status
                             (Windows-visible so a Windows bridge can read
                             without crossing \\\\wsl$\\)
      - Native Linux/macOS:  $HOME/.claude-status

    Override: CLAUDE_STATUS_MIRROR_DIR env var (any platform).
    """
    override = os.environ.get("CLAUDE_STATUS_MIRROR_DIR")
    if override:
        return Path(override)

    # WSL gets the Windows-side path so a Windows bridge can read.
    try:
        proc_version = Path("/proc/version").read_text().lower()
    except (OSError, FileNotFoundError):
        proc_version = ""
    if "microsoft" in proc_version:
        user = os.environ.get("USER") or os.environ.get("USERNAME")
        if user:
            win_home = Path(f"/mnt/c/Users/{user}")
            if win_home.is_dir():
                return win_home / ".claude-status"
        return None  # WSL but Windows home unavailable; caller falls back

    # Native (macOS / Linux / non-WSL).
    home = Path.home()
    if home and home.exists():
        return home / ".claude-status"
    return None


# Backwards-compatible alias for the prior name. Remove after callers
# settle on `discovery_dir`.
windows_mirror_dir = discovery_dir


class Broker:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state_dir = data_dir() / "sessions" / session_id
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "broker.json"
        self.subscribers: set[asyncio.StreamWriter] = set()
        self.last_activity = time.time()
        self.last_event: bytes | None = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                hello = await asyncio.wait_for(reader.readline(), timeout=HANDSHAKE_TIMEOUT)
            except asyncio.TimeoutError:
                return
            if not hello:
                return
            token = hello.decode("utf-8", errors="replace").strip().split(None, 1)[0] if hello.strip() else ""
            if token == "PUB":
                await self._handle_publisher(reader)
            elif token == "SUB":
                await self._handle_subscriber(reader, writer)
            else:
                writer.write(b'{"error":"expected PUB or SUB handshake"}\n')
                try:
                    await writer.drain()
                except Exception:
                    pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_publisher(self, reader: asyncio.StreamReader) -> None:
        while True:
            try:
                line = await reader.readline()
            except Exception:
                break
            if not line:
                break
            self.last_activity = time.time()
            self.last_event = line
            self._log(line.decode("utf-8", errors="replace").rstrip())
            for sub in list(self.subscribers):
                try:
                    sub.write(line)
                except Exception:
                    self.subscribers.discard(sub)

    async def _handle_subscriber(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # Atomic (single-threaded asyncio): replay catch-up, then register for
        # live fan-out. Any events that fire after this point are delivered
        # via the subscribers set, guaranteeing correct ordering.
        if self.last_event is not None:
            try:
                writer.write(self.last_event)
                self._log("replayed last event to new subscriber")
            except Exception:
                pass
        self.subscribers.add(writer)
        self.last_activity = time.time()
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
        except Exception:
            pass
        finally:
            self.subscribers.discard(writer)

    async def _idle_monitor(self) -> None:
        while True:
            await asyncio.sleep(30)
            idle = time.time() - self.last_activity
            if idle > IDLE_EXIT_SECONDS and not self.subscribers:
                self._log(f"idle {idle:.0f}s, exiting")
                self._cleanup_state()
                os._exit(0)

    def _log(self, msg: str) -> None:
        sys.stderr.write(f"[broker {self.session_id[:8]}] {msg}\n")
        sys.stderr.flush()

    def _cleanup_state(self) -> None:
        try:
            self.state_file.unlink()
        except Exception:
            pass
        mirror = windows_mirror_dir()
        if mirror:
            try:
                (mirror / "sessions" / self.session_id / "broker.json").unlink()
            except Exception:
                pass

    def _write_state(self, port: int) -> None:
        payload = json.dumps({"pid": os.getpid(), "port": port, "session_id": self.session_id})
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(payload)
        os.replace(tmp, self.state_file)
        mirror = windows_mirror_dir()
        if mirror:
            try:
                mdir = mirror / "sessions" / self.session_id
                mdir.mkdir(parents=True, exist_ok=True)
                mf = mdir / "broker.json"
                mtmp = mf.with_suffix(".tmp")
                mtmp.write_text(payload)
                os.replace(mtmp, mf)
                self._log(f"mirrored state to {mf}")
            except Exception as e:
                self._log(f"mirror write failed: {e}")

    async def serve(self) -> None:
        server = await asyncio.start_server(self.handle_client, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        self._janitor_sweep()
        self._write_state(port)
        self._log(f"listening on 127.0.0.1:{port} pid={os.getpid()}")
        asyncio.create_task(self._idle_monitor())
        async with server:
            await server.serve_forever()

    def _janitor_sweep(self) -> None:
        """
        Remove state files from sibling sessions whose brokers are dead
        (e.g., left over from a hard shutdown or WSL restart). Detection is
        port-based: if nothing is listening on the recorded port, the broker
        is gone. Also clears the pin file if it points to a session we
        cleaned up, and prunes empty session directories.
        """
        cleaned_sessions: set[str] = set()
        empty_dirs_removed = 0
        for base in (data_dir(), windows_mirror_dir()):
            if base is None:
                continue
            sessions_root = base / "sessions"
            if not sessions_root.is_dir():
                continue
            for session_dir in sessions_root.iterdir():
                if not session_dir.is_dir():
                    continue
                if session_dir.name == self.session_id:
                    continue
                bj = session_dir / "broker.json"
                if bj.is_file():
                    try:
                        meta = json.loads(bj.read_text())
                        port = int(meta.get("port", 0))
                    except Exception:
                        port = 0
                    if port > 0 and _port_listening(port):
                        continue
                    try:
                        bj.unlink()
                        cleaned_sessions.add(session_dir.name)
                    except Exception:
                        pass
                try:
                    session_dir.rmdir()
                    empty_dirs_removed += 1
                except OSError:
                    pass
        if cleaned_sessions:
            self._log(f"janitor: removed {len(cleaned_sessions)} stale state file(s)")
            self._clean_stale_pin(cleaned_sessions)
        if empty_dirs_removed:
            self._log(f"janitor: pruned {empty_dirs_removed} empty session dir(s)")

    def _clean_stale_pin(self, removed_session_ids: set[str]) -> None:
        for base in (data_dir(), windows_mirror_dir()):
            if base is None:
                continue
            pin = base / "pin.json"
            if not pin.is_file():
                continue
            try:
                pinned_id = json.loads(pin.read_text()).get("session_id")
            except Exception:
                pinned_id = None
            if pinned_id and pinned_id in removed_session_ids:
                try:
                    pin.unlink()
                    self._log(f"janitor: cleared stale pin pointing to {pinned_id}")
                except Exception:
                    pass


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: broker.py <session_id>", file=sys.stderr)
        sys.exit(2)
    session_id = sys.argv[1]
    broker = Broker(session_id)

    def shutdown(*_):
        broker._cleanup_state()
        os._exit(0)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass
    try:
        loop.run_until_complete(broker.serve())
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
