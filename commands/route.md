---
description: Route this session's status events to a specific display client slot (e.g. "1", "2b"). Usage: /claude-status:route <slot>
---

The route has been recorded by the plugin's hook (or an invalid-slot error has been logged to the broker log if the slot was malformed). Run this command to confirm and report the current state to the user:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
```

If the user's slot does not appear in the routes table after running status, gently report that the slot was likely invalid (valid format is `<N>` or `<N>a` or `<N>b`, e.g. `1`, `1a`, `1b`, `2`, `2b`).
