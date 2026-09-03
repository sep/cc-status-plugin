#!/usr/bin/env python3
"""Allowlist the llmstatus plugin's Bash invocations so slash
commands like /llmstatus:show don't prompt for permission on every
invocation. Idempotent.

Default (no args): Claude Code — writes permissions.allow patterns to
~/.claude/settings.json.

--copilot: GitHub Copilot CLI — writes command-prefix approvals to
~/.copilot/permissions-config.json (COPILOT_HOME honored). Copilot
scopes approvals to a location (the git repo root of the working
directory, or the working directory itself outside a repo); there is
no global scope, so this must be re-run once per repo.
"""

import json
import os
import sys
from pathlib import Path

# Force UTF-8 on stdout/stderr — same reason as pin.py: avoids
# UnicodeEncodeError on Windows when output contains non-ANSI-codepage
# glyphs. Tolerant wrap in case stdio doesn't support reconfigure.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, TypeError, ValueError):
    pass


def copilot_config_dir() -> Path:
    home = os.environ.get("COPILOT_HOME")
    if home:
        return Path(home)
    return Path.home() / ".copilot"


def copilot_location_key() -> str:
    """Copilot scopes tool approvals to the git repository root of the
    working directory, or the working directory itself outside a repo."""
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(cwd)


def copilot_main() -> int:
    plugin_root = Path(__file__).resolve().parent.parent

    # Copilot's commandIdentifiers are literal prefixes with a `:*`
    # wildcard suffix. Cover both interpreters (POSIX Copilot runs the
    # python3||python polyglot; Windows uses bare python) and both
    # quoted/unquoted path spellings the model may emit.
    identifiers = []
    for interpreter in ("python", "python3"):
        for name in ("pin.py", "emit.py", "permit.py"):
            script = plugin_root / "bin" / name
            identifiers.append(f'{interpreter} "{script}":*')
            identifiers.append(f"{interpreter} {script}:*")

    config_path = copilot_config_dir() / "permissions-config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError as e:
            print(f"error: {config_path} is not valid JSON: {e}", file=sys.stderr)
            return 1
    else:
        config = {}

    location = copilot_location_key()
    loc = config.setdefault("locations", {}).setdefault(location, {})
    approvals = loc.setdefault("tool_approvals", [])
    existing = set()
    for entry in approvals:
        if entry.get("kind") == "commands":
            existing.update(entry.get("commandIdentifiers", []))

    missing = [i for i in identifiers if i not in existing]
    if missing:
        approvals.append({"kind": "commands", "commandIdentifiers": missing})

    # The slash-command bodies have the model read routes.json /
    # panel_layout.json straight from the well-known status dir, which
    # lives outside the workspace — Copilot raises a path prompt for
    # every such read unless the dir is in allowed_directories.
    added_dir = None
    status_dir = None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from broker import discovery_dir  # noqa: WPS433
        status_dir = discovery_dir()
    except Exception:
        pass
    if status_dir is None:
        status_dir = Path.home() / ".claude-status"
    allowed = loc.setdefault("allowed_directories", [])
    if str(status_dir) not in allowed:
        allowed.append(str(status_dir))
        added_dir = str(status_dir)

    if missing or added_dir:
        config_path.write_text(json.dumps(config, indent=2) + "\n")

    print(f"permissions: {config_path}")
    print(f"location:    {location}")
    if missing:
        print(f"added ({len(missing)}):")
        for i in missing:
            print(f"  + {i}")
    if added_dir:
        print(f"allowed directory (path prompts): + {added_dir}")
    if not missing and not added_dir:
        print("(all approvals already present)")
    print(
        "note: approvals are scoped to this repo/directory — re-run "
        "/llmstatus:permit in other repos as needed. Takes effect "
        "next session; if Copilot rewrites the file on exit, re-run "
        "this once no session is active."
    )
    return 0


def main():
    bin_dir = Path(__file__).resolve().parent
    plugin_root = bin_dir.parent  # canonical, no trailing slash

    # Claude Code's Bash permission matcher expands ${CLAUDE_PLUGIN_ROOT}
    # before checking allowlist patterns, then splits the command on
    # shell operators (||, &&, ;, |) and prefix-checks each subcommand
    # independently. Our slash commands invoke a polyglot:
    #     python3 "${...}/bin/X.py" ... || python "${...}/bin/X.py" ...
    # so BOTH the `python3 ...` and `python ...` subcommand prefixes
    # need an allowlist entry, with absolute paths (placeholder forms
    # never match — Claude Code expands them away before checking).
    #
    # Edge case: when CLAUDE_PLUGIN_ROOT ends with a trailing slash
    # (the dev-style local marketplace pointing to `./`), the emitted
    # command contains a double slash mid-path (`/root//bin/X.py`).
    # The matcher does literal prefix matching, so we write a second
    # variant covering that case only when we observe the env var
    # actually has the trailing slash this run — avoids cluttering
    # proper installs with patterns they don't need.
    patterns = []
    for interpreter in ("python3", "python"):
        for name in ("pin.py", "emit.py"):
            patterns.append(f'Bash({interpreter} "{plugin_root}/bin/{name}":*)')

    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if env_root.endswith("/"):
        for interpreter in ("python3", "python"):
            for name in ("pin.py", "emit.py"):
                patterns.append(f'Bash({interpreter} "{env_root}/bin/{name}":*)')

    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError as e:
            print(f"error: {settings_path} is not valid JSON: {e}", file=sys.stderr)
            return 1
    else:
        settings = {}

    permissions = settings.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])

    added, skipped = [], []
    for p in patterns:
        if p in allow:
            skipped.append(p)
        else:
            allow.append(p)
            added.append(p)

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    print(f"settings: {settings_path}")
    if added:
        print(f"added ({len(added)}):")
        for p in added:
            print(f"  + {p}")
    if skipped:
        print(f"already present ({len(skipped)}):")
        for p in skipped:
            print(f"  = {p}")
    if not added and not skipped:
        print("(nothing to do)")
    return 0


if __name__ == "__main__":
    if "--copilot" in sys.argv[1:]:
        sys.exit(copilot_main())
    sys.exit(main())
