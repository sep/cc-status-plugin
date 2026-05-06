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
    pin_py = bin_dir / "pin.py"
    emit_py = bin_dir / "emit.py"

    # We add three forms of each script's pattern, defensively, because
    # Claude Code's Bash-permission matcher does literal prefix matching
    # against the *exact* command string the model emits — and that
    # string varies subtly across installs:
    #
    #   1. The literal `${CLAUDE_PLUGIN_ROOT}/bin/pin.py` form — covers
    #      the case where Claude Code matches before shell expansion.
    #
    #   2. The `__file__`-resolved absolute form (e.g.
    #      "/mnt/w/sep/claude-status/bin/pin.py") — covers the case
    #      where __file__'s parent matches CLAUDE_PLUGIN_ROOT exactly,
    #      with no trailing slash in the env var.
    #
    #   3. The runtime-concatenated form using `os.environ["CLAUDE_PLUGIN_ROOT"]`
    #      with the same `/bin/pin.py` suffix the slash-command bodies
    #      use — covers the (commonly-hit) case where CLAUDE_PLUGIN_ROOT
    #      ends with a trailing slash and the resulting string contains a
    #      double slash (e.g. "/path/to/claude-status//bin/pin.py").
    #      That double-slash is what the matcher actually compares against
    #      and was the silent cause of /permit "not working" pre-0.3.5.
    patterns = [
        'Bash(python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py":*)',
        'Bash(python "${CLAUDE_PLUGIN_ROOT}/bin/emit.py":*)',
        f'Bash(python "{pin_py}":*)',
        f'Bash(python "{emit_py}":*)',
    ]
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        # Same f-string concat the slash-command bodies use: produces
        # the exact path string (with whatever slash quirks) the matcher
        # will see. Add only if it's actually different from the two
        # patterns above to avoid duplicate entries on tidy installs.
        runtime_pin  = f"{plugin_root}/bin/pin.py"
        runtime_emit = f"{plugin_root}/bin/emit.py"
        for runtime in (runtime_pin, runtime_emit):
            pattern = f'Bash(python "{runtime}":*)'
            if pattern not in patterns:
                patterns.append(pattern)

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
