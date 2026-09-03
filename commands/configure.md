---
description: "Tell the firmware about your panel layout (e.g. 'I have 2 panels chained'). Usage: /llmstatus:configure <panel_count>"
---

The panel layout has been recorded by the plugin's hook (or an invalid-count error has been logged to the broker log). The bridge will send a `configure` message to the firmware on its next connect, and the firmware will cache the layout in NVS so it survives reboots.

Confirm the layout is set:

- If the path below is a real absolute path (Claude Code expands `${CLAUDE_PLUGIN_ROOT}` before you see this), run:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status || python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
  ```

  In PowerShell, invoke with `python` only — on Windows, `python3` is a Microsoft Store alias that opens an app-picker dialog instead of Python.

- If the literal `${CLAUDE_PLUGIN_ROOT}` placeholder survived into the text above (GitHub Copilot CLI doesn't expand it), skip pin.py and read `panel_layout.json` from the status directory — `~/.claude-status`, except under WSL where it's the Windows-side `/mnt/c/Users/<you>/.claude-status`.

If the panels line in the output does not match what the user requested, gently report that the count was out of range (must be 1–4) or that the request was malformed.

The bridge picks the new layout up on its own with the next session event. If the user wants it pushed immediately — or no session is routed to the display yet, so no events are flowing — point them at **"Resend panel config"** in the ClaudePanel tray icon's menu (bridge v0.5+; on older bridges, restarting the bridge from the tray does the same).

For non-default panel sizes (32-wide panels, taller panels, vertical/serpentine layouts), tell the user they can edit `panel_layout.json` directly in their plugin data directory. Defaults are 64×32 horizontal.
