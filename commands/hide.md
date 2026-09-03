---
description: Hide this session from the display (clears its route and pin). Use /llmstatus:show <slot> later to bring it back.
---

This session has been removed from the display by the plugin's hook (pin and route both cleared). Confirm and report the current state to the user:

- If the path below is a real absolute path (Claude Code expands `${CLAUDE_PLUGIN_ROOT}` before you see this), run:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status || python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
  ```

  In PowerShell, invoke with `python` only — on Windows, `python3` is a Microsoft Store alias that opens an app-picker dialog instead of Python.

- If the literal `${CLAUDE_PLUGIN_ROOT}` placeholder survived into the text above (GitHub Copilot CLI doesn't expand it), skip pin.py and read `routes.json` from the status directory — `~/.claude-status`, except under WSL where it's the Windows-side `/mnt/c/Users/<you>/.claude-status`.

One line is enough.
