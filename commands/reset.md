---
description: Wipe the entire llmstatus pin and route table — every session, every slot. Use when things have gotten kludged and you want a clean slate.
---

The full reset has been performed by the plugin's hook (pin and all routes cleared from every known data location). Confirm and report the current state to the user:

- If the path below is a real absolute path (Claude Code expands `${CLAUDE_PLUGIN_ROOT}` before you see this), run:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status || python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
  ```

  In PowerShell, invoke with `python` only — on Windows, `python3` is a Microsoft Store alias that opens an app-picker dialog instead of Python.

- If the literal `${CLAUDE_PLUGIN_ROOT}` placeholder survived into the text above (GitHub Copilot CLI doesn't expand it), skip pin.py and read `routes.json` from the status directory — `~/.claude-status`, except under WSL where it's the Windows-side `/mnt/c/Users/<you>/.claude-status`.

The user should see no pin and no routes — confirming the reset took. If anything is still set, point them at the path that's still holding state so they can investigate.
