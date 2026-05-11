---
description: Tell the firmware about your panel layout (e.g. "I have 2 panels chained"). Usage: /claude-status:configure <panel_count>
---

The panel layout has been recorded by the plugin's hook (or an invalid-count error has been logged to the broker log). The bridge will send a `configure` message to the firmware on its next connect, and the firmware will cache the layout in NVS so it survives reboots.

Run this command to confirm the layout is set:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
```

If the panels line in the output does not match what the user requested, gently report that the count was out of range (must be 1–4) or that the request was malformed. Suggest restarting the bridge (`bridge restart`) so the new layout is sent to the firmware right away — otherwise it will be applied on the next bridge reconnect.

For non-default panel sizes (32-wide panels, taller panels, vertical/serpentine layouts), tell the user they can edit `panel_layout.json` directly in their plugin data directory. Defaults are 64×32 horizontal.
