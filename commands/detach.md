---
description: Fully detach this session from the display — releases the pin AND removes the route. Use /claude-status:unroute if you only want to drop the route while keeping the pin.
---

The pin has been released and this session's route removed by the plugin's hook. Run this command to confirm and report the current state to the user:

```bash
python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
```

One line is enough.
