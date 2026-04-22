---
description: Pin the claude-status transport to this session so it won't auto-switch to newer Claude sessions.
---

Run this command and report its output tersely to the user. One line of confirmation is enough on success; on failure, read the error and suggest fixes.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" attach
```
