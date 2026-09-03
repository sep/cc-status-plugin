---
description: One-time setup — allowlist the plugin's slash-command invocations (Claude Code's permissions.allow, or Copilot CLI's permissions-config.json) so future runs of /llmstatus:show, /hide, /status, etc. stop asking for permission.
---

The user wants to stop being prompted for permission on every llmstatus slash command. Pick the branch for your host:

- **Claude Code** — the path below is already expanded to a real absolute path. Run the permit script to add allowlist entries to the user's global Claude settings:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/permit.py" || python "${CLAUDE_PLUGIN_ROOT}/bin/permit.py"
  ```

- **GitHub Copilot CLI** — the literal `${CLAUDE_PLUGIN_ROOT}` placeholder survived into the text above (Copilot doesn't expand it). Locate the plugin's installed directory (this command file lives inside it; otherwise look for the llmstatus plugin under the Copilot config dir, default `~/.copilot`) and run permit in Copilot mode. Use `python` in PowerShell — on Windows, `python3` is a Microsoft Store alias that opens an app-picker dialog:

  ```
  python "<plugin-root>/bin/permit.py" --copilot
  ```

  This writes prefix approvals for the plugin's scripts into Copilot's `permissions-config.json`, and adds the well-known status directory (`~/.claude-status`) to `allowed_directories` so reading `routes.json` / `panel_layout.json` stops raising path prompts. Both are scoped to the current repo/directory — Copilot has no global scope, so mention the user should re-run `/llmstatus:permit` once in each repo where they use the panel.

Show the user the script's output verbatim — it lists what was added vs already present. Then mention that this is one-time setup (per host; per repo on Copilot), and that the new entries take effect on the next conversation (existing sessions may need a restart to pick up the updated settings).
