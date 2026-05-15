#!/usr/bin/env python3
"""Allowlist the claude-status plugin's Bash invocations in the user's
~/.claude/settings.json so slash commands like /claude-status:show don't
prompt for permission on every invocation. Idempotent.
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
    sys.exit(main())
