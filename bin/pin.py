#!/usr/bin/env python3
"""
Slot routing helpers for the llmstatus transport.

Routes map Claude Code session_ids to display slots ("1", "2b", etc.):
  routes.json    {"<session_id>": "<slot>", ...}

Each session occupies at most one slot, and each slot holds at most one
session. `bind_slot` enforces both constraints by displacement — when a
new session takes a slot, any prior occupant is evicted, and any prior
slot the same session held is released — and additionally prunes routes
whose session no longer has broker state in any base, so stale entries
merged in from divergent data dirs can't pile up on a slot.

The bridge subscribes only to sessions present in routes.json; sessions
without a binding are invisible to the display.

CLI usage (invoked by emit.py from slash-command hook context, or
directly for testing):
  pin.py show <session_id> <slot>       Bind session to slot
  pin.py hide <session_id>              Remove any binding for session
  pin.py reset                          Wipe all routes
  pin.py configure <count> [k=v ...]    Panel layout
  pin.py status                         Print routes + panel layout
"""
import json
import os
import re
import sys
from pathlib import Path

# Force UTF-8 on stdout/stderr so the unicode glyphs we use in status
# output (×, →) don't crash on Windows where Python's default codepage
# can't encode them. Tolerantly wrapped for stdio backed by a pipe.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, TypeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import data_dir, windows_mirror_dir  # noqa: E402


ROUTES_FILENAME        = "routes.json"
PANEL_LAYOUT_FILENAME  = "panel_layout.json"

SLOT_PATTERN = re.compile(r"^\d{1,2}[ab]?$")

PANEL_DEFAULTS = {
    "panel_count":  1,
    "panel_width":  64,
    "panel_height": 32,
    "layout":       "horizontal",
    "first_id":     1,
}


# ----------------------------- PATHS -----------------------------

def routes_path(base: Path) -> Path:
    return base / ROUTES_FILENAME


def panel_layout_path(base: Path) -> Path:
    return base / PANEL_LAYOUT_FILENAME


def targets() -> list[Path]:
    """
    Bases for WRITES — the canonical place to land new route state.
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
    Bases for READS / REMOVES — wider than targets() because state may
    have been written by an earlier emit.py invocation under a different
    CLAUDE_PLUGIN_DATA, by direct CLI use (which falls back to
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

    add(data_dir())
    add(Path.home() / ".claude" / "status-data")
    plugins_data = Path.home() / ".claude" / "plugins" / "data"
    if plugins_data.is_dir():
        for sub in plugins_data.iterdir():
            if sub.is_dir():
                add(sub)
    add(windows_mirror_dir())

    return out


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


def _session_has_broker_state(session_id: str) -> bool:
    """
    Liveness proxy: does any base hold a broker.json for this session?
    The broker writes it on (re)spawn and removes it on SessionEnd or
    idle-exit, and mirrors it to the well-known status dir — so it's
    visible from both sides of a WSL/Windows boundary. We deliberately
    don't port-probe: a WSL process can't reach a Windows broker's
    loopback port (and vice versa), so connectivity would misreport
    live cross-OS sessions as dead.
    """
    for base in read_bases():
        if (base / "sessions" / session_id / "broker.json").is_file():
            return True
    return False


def bind_slot(session_id: str, slot: str) -> tuple[bool, list[Path]]:
    """
    Bind a session to a slot with two-axis displacement: any other
    session holding the slot is evicted, and any prior slot this session
    held is released. Result: at most one session per slot, at most one
    slot per session. Idempotent — re-binding the same pair is a no-op.

    Binding also prunes routes whose session has no broker state left
    in any base. Displacement alone only resolves the slot being bound:
    when bases diverge (two OSes, plugin reinstalls under new data
    dirs), read_routes() merges stale entries back in, and a later bind
    to a *different* slot would faithfully persist that union — piling
    dead sessions onto a slot. Pruning at bind time restores the
    one-session-per-slot invariant globally.

    Returns (ok, paths_written). ok=False only on invalid slot syntax.
    """
    if not is_valid_slot(slot):
        return False, []
    routes = read_routes()
    to_remove = [
        sid for sid, s in routes.items()
        # Anyone else holding this slot, and any prior slot this
        # session held (built separately so we don't mutate the dict
        # mid-iteration)...
        if (s == slot and sid != session_id) or (sid == session_id and s != slot)
        # ...plus any session that no longer has a broker anywhere.
        or (sid != session_id and not _session_has_broker_state(sid))
    ]
    for sid in to_remove:
        del routes[sid]
    routes[session_id] = slot
    return True, _write_routes(routes)


def unbind_session(session_id: str) -> list[Path]:
    """Remove this session's binding from every routes.json. Idempotent."""
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


# --------------------------- PANEL LAYOUT ---------------------------

def read_panel_layout() -> dict | None:
    """
    Return the panel layout from the NEWEST file across all bases, or
    None. First-found would let a stale copy in an abandoned data dir
    (plugin reinstalls, cross-OS use) shadow the layout the user most
    recently configured; set_panel_layout only writes to targets(), so
    stale copies in wider read_bases() never get refreshed.
    """
    newest: tuple[float, dict] | None = None
    for base in read_bases():
        p = panel_layout_path(base)
        if not p.is_file():
            continue
        try:
            mtime = p.stat().st_mtime
            data = json.loads(p.read_text())
        except Exception:
            continue
        if isinstance(data, dict) and (newest is None or mtime > newest[0]):
            newest = (mtime, data)
    return newest[1] if newest else None


def set_panel_layout(**fields) -> tuple[bool, list[Path]]:
    """
    Update the panel layout, merging caller-supplied fields with defaults
    for unset keys. Returns (ok, paths_written). Validates panel_count
    1..4, panel_width in {32,64}, panel_height in {16,32,64},
    layout in {horizontal,vertical,serpentine}, first_id 1..99.
    """
    existing = read_panel_layout() or {}
    merged = {**PANEL_DEFAULTS, **existing}
    for k, v in fields.items():
        if v is not None:
            merged[k] = v

    if not (1 <= merged["panel_count"] <= 4):
        return False, []
    if merged["panel_width"] not in (32, 64):
        return False, []
    if merged["panel_height"] not in (16, 32, 64):
        return False, []
    if merged["layout"] not in ("horizontal", "vertical", "serpentine"):
        return False, []
    if not (1 <= merged["first_id"] <= 99):
        return False, []

    payload = json.dumps(merged, indent=2)
    written: list[Path] = []
    for base in targets():
        p = panel_layout_path(base)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(payload)
            os.replace(tmp, p)
            written.append(p)
        except Exception as e:
            sys.stderr.write(f"[panel] failed to write {p}: {e}\n")
    return True, written


# --------------------------- COMMANDS ---------------------------

def reset_all() -> list[Path]:
    """
    Wipe all routes from every known data location. Returns the list of
    files removed. Idempotent — safe to run when nothing is set.

    Also cleans up any pre-v0.4 pin.json files lying around. They're
    inert under v0.4 (nothing reads them) but tidying avoids confusion
    for users poking at their data dirs.
    """
    removed: list[Path] = []
    for base in read_bases():
        r = routes_path(base)
        if r.exists():
            try:
                r.unlink()
                removed.append(r)
            except Exception as e:
                sys.stderr.write(f"[reset] failed to remove {r}: {e}\n")
        legacy_pin = base / "pin.json"
        if legacy_pin.exists():
            try:
                legacy_pin.unlink()
                removed.append(legacy_pin)
            except Exception as e:
                sys.stderr.write(f"[reset] failed to remove {legacy_pin}: {e}\n")
    return removed


def cmd_show(session_id: str, slot: str) -> int:
    ok, paths = bind_slot(session_id, slot)
    if not ok:
        print(f"invalid slot '{slot}' (expected N or Na or Nb, e.g. 1, 2b)",
              file=sys.stderr)
        return 1
    print(f"bound {session_id} -> {slot}")
    for p in paths:
        print(f"  wrote {p}")
    return 0


def cmd_hide(session_id: str) -> int:
    paths = unbind_session(session_id)
    if not paths:
        print(f"no binding to remove for {session_id}")
    else:
        print(f"unbound {session_id}")
        for p in paths:
            print(f"  wrote {p}")
    return 0


def cmd_reset() -> int:
    removed = reset_all()
    if not removed:
        print("nothing to reset (no routes were set)")
        return 0
    print(f"removed {len(removed)} file(s):")
    for p in removed:
        print(f"  {p}")
    return 0


def cmd_status() -> int:
    routes = read_routes()
    if not routes:
        print("routes: (none)")
    else:
        print("routes:")
        for k, v in routes.items():
            print(f"  {k} -> {v}")
    layout = read_panel_layout()
    if layout:
        merged = {**PANEL_DEFAULTS, **layout}
        print(f"panels: {merged['panel_count']} × "
              f"{merged['panel_width']}×{merged['panel_height']} "
              f"({merged['layout']}, first_id={merged['first_id']})")
    else:
        print("panels: (default — single 64×32 panel)")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "show":
        if len(sys.argv) < 4:
            print("usage: pin.py show <session_id> <slot>", file=sys.stderr)
            return 2
        return cmd_show(sys.argv[2], sys.argv[3])
    if cmd == "hide":
        if len(sys.argv) < 3:
            print("usage: pin.py hide <session_id>", file=sys.stderr)
            return 2
        return cmd_hide(sys.argv[2])
    if cmd == "reset":
        return cmd_reset()
    if cmd == "configure":
        if len(sys.argv) < 3:
            print("usage: pin.py configure <panel_count> [k=v ...]", file=sys.stderr)
            return 2
        try:
            count = int(sys.argv[2])
        except ValueError:
            print(f"invalid panel_count '{sys.argv[2]}'", file=sys.stderr)
            return 2
        kwargs: dict = {"panel_count": count}
        for tok in sys.argv[3:]:
            if "=" not in tok:
                print(f"expected key=value, got '{tok}'", file=sys.stderr)
                return 2
            k, v = tok.split("=", 1)
            if k in ("panel_width", "panel_height", "first_id", "width", "height"):
                if k == "width": k = "panel_width"
                if k == "height": k = "panel_height"
                try:
                    kwargs[k] = int(v)
                except ValueError:
                    print(f"invalid integer for {k}: '{v}'", file=sys.stderr)
                    return 2
            else:
                kwargs[k] = v
        ok, paths = set_panel_layout(**kwargs)
        if not ok:
            print("invalid layout (panel_count 1-4, width 32|64, height 16|32|64, "
                  "layout horizontal|vertical|serpentine, first_id 1-99)",
                  file=sys.stderr)
            return 1
        print(f"panel layout updated: {kwargs}")
        for p in paths:
            print(f"  wrote {p}")
        return 0
    if cmd == "status":
        return cmd_status()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
