---
description: Wipe the entire claude-status pin and route table — every session, every slot. Use when things have gotten kludged and you want a clean slate.
---

The full reset has been performed by the plugin's hook (pin and all routes cleared from every known data location). Run this command to confirm and report the current state to the user:

```bash
python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status
```

The user should see no pin and no routes — confirming the reset took. If anything is still set, point them at the path that's still holding state so they can investigate.
