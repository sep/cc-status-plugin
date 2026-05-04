---
description: One-time setup — add the plugin's slash-command Bash invocations to ~/.claude/settings.json's permissions.allow so future runs of /claude-status:show, /hide, /status, etc. stop asking for permission.
---

The user wants to stop being prompted for permission on every claude-status slash command. Run the permit script to add the necessary allowlist entries to their global Claude settings:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/permit.py"
```

Show the user the script's output verbatim — it lists what was added vs already present. Then mention that this is one-time setup, and that the new entries take effect on the next Claude Code conversation (existing sessions may need a restart to pick up the updated settings).
