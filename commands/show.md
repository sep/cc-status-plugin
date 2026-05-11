---
description: Show this session's status on a specific display slot. Usage: /claude-status:show <slot> (e.g. "1", "2b")
---

The session has been routed to the requested slot by the plugin's hook (or an invalid-slot error has been logged to the broker log if the slot was malformed). Run this command to confirm and report the current state to the user:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status || python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
```

If the user's slot does not appear in the routes table after running status, gently report that the slot was likely invalid (valid format is `<N>` or `<N>a` or `<N>b`, e.g. `1`, `1a`, `1b`, `2`, `2b`).
