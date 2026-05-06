#!/usr/bin/env python3
"""Allowlist the claude-status plugin's Bash invocations in the user's
~/.claude/settings.json so slash commands like /claude-status:show don't
prompt for permission on every invocation. Idempotent.
"""

import json
import sys
from pathlib import Path


def main():
    bin_dir = Path(__file__).resolve().parent
    pin_py = bin_dir / "pin.py"
    emit_py = bin_dir / "emit.py"

    # Defensive: cover both the ${CLAUDE_PLUGIN_ROOT} (unexpanded) form
    # that the slash-command markdown writes, and the absolute-path form
    # that Bash sees after env-var expansion. Claude Code's permission
    # matcher works on the command string at submission time, and which
    # form it sees depends on shell-expansion timing — including both
    # makes the allowlist robust to either.
    patterns = [
        'Bash(python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py":*)',
        'Bash(python "${CLAUDE_PLUGIN_ROOT}/bin/emit.py":*)',
        f'Bash(python "{pin_py}":*)',
        f'Bash(python "{emit_py}":*)',
    ]

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
