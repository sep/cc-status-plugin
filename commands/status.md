---
description: Report the llmstatus transport's current pin and per-slot routes.
---

Report the transport's routes and panel layout to the user without embellishment.

- If the path below is a real absolute path (Claude Code expands `${CLAUDE_PLUGIN_ROOT}` before you see this), run it and show the output:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status || python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
  ```

  In PowerShell, invoke with `python` only — on Windows, `python3` is a Microsoft Store alias that opens an app-picker dialog instead of Python.

- If the literal `${CLAUDE_PLUGIN_ROOT}` placeholder survived into the text above (GitHub Copilot CLI doesn't expand it), skip pin.py and read the status files straight from the status directory — `~/.claude-status`, except under WSL where it's the Windows-side `/mnt/c/Users/<you>/.claude-status`. `routes.json` maps session-id → slot; `panel_layout.json` is the panel config.
