---
description: Hide this session from the display (clears its route and pin). Use /claude-status:show <slot> later to bring it back.
---

This session has been removed from the display by the plugin's hook (pin and route both cleared). Run this command to confirm and report the current state to the user:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
```

One line is enough.
