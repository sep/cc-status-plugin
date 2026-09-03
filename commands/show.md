---
description: "Show this session's status on a specific display slot. Usage: /llmstatus:show <slot> (e.g. '1', '2b')"
---

The session has been routed to the requested slot by the plugin's hook (or an invalid-slot error has been logged to the broker log if the slot was malformed). Confirm and report the current state to the user:

- If the path below is a real absolute path (Claude Code expands `${CLAUDE_PLUGIN_ROOT}` before you see this), run:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status || python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
  ```

  In PowerShell, invoke with `python` only — on Windows, `python3` is a Microsoft Store alias that opens an app-picker dialog instead of Python.

- If the literal `${CLAUDE_PLUGIN_ROOT}` placeholder survived into the text above (GitHub Copilot CLI doesn't expand it), skip pin.py and read the status files straight from the status directory — `~/.claude-status`, except under WSL where it's the Windows-side `/mnt/c/Users/<you>/.claude-status`. `routes.json` maps session-id → slot; `panel_layout.json` is the panel config. Report those.

If the user's slot does not appear in the routes table, gently report that the slot was likely invalid (valid format is `<N>` or `<N>a` or `<N>b`, e.g. `1`, `1a`, `1b`, `2`, `2b`). Under Copilot CLI only: if the routes table shows no change at all, the prompt-interception hook may not have fired — report that, and suggest `CLAUDE_STATUS_SLOT=<slot> copilot` at launch as the reliable pairing path.
