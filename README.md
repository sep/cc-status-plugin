# llmstatus — plugin

Agent status plugin that hooks every lifecycle event in your coding
session and publishes a small NDJSON state stream to a local TCP
broker. Built as a Claude Code plugin, and not Claude-specific: any
agent that implements Claude Code's plugin architecture (lifecycle
hooks with Claude-shaped payloads, `CLAUDE_PLUGIN_ROOT` /
`CLAUDE_PLUGIN_DATA`, markdown slash commands) can drive the panel —
[GitHub Copilot CLI](#github-copilot-cli) is the tested example. The [bridge][bridge] subscribes to that broker and forwards
each state to the [ESP32-S3 firmware][firmware], which renders it on
a HUB75 LED panel sitting on your desk.

**This repo is the umbrella** — full system overview, hardware
selection, and install walkthrough live on the project site:

**→ <https://sep.github.io/cc-status-plugin/>**

```
 Claude Code  ──►  Plugin  ──►  Bridge  ──►  Firmware  ──►  Display
                  (this repo) (cross-      (ESP32-S3)     (RGB matrix)
                              platform)
```

[bridge]: https://github.com/sep/cc-status-bridge
[firmware]: https://github.com/sep/cc-status-display

## What you see

| State          | Meaning                                                  |
|----------------|----------------------------------------------------------|
| **idle**       | Claude has finished its turn; waiting for you.           |
| **working**    | Claude is actively processing your prompt.               |
| **thinking**   | Claude has been responding for a while without firing a  |
|                | tool — usually composing prose.                          |
| **blocked**    | Claude needs your input (permission prompt, etc.)        |
| **compacting** | Claude Code is compressing the conversation context.     |
| **error**      | A tool call returned an error.                           |

Plus running counts of subagents and active tasks alongside the state.

## Install

Three pieces, in order: firmware → bridge → plugin. Each piece has its
own docs; the [install walkthrough on the project
site](https://sep.github.io/cc-status-plugin/#installation) sequences
them.

The plugin itself installs from inside Claude Code:

```
/plugin marketplace add sep/cc-status-plugin
/plugin install llmstatus@llmstatus-market
/llmstatus:permit
```

`/llmstatus:help` lists every available slash command. Python 3
must be on PATH as the command `python` (any modern Windows / macOS /
Linux install; on default Ubuntu / Debian, install
`python-is-python3`).

### GitHub Copilot CLI

The plugin also works with [GitHub Copilot CLI][copilot-cli]
(>= 1.0.66), which speaks a Claude-compatible plugin protocol — and
should work with any other agent that implements Claude Code's plugin
architecture; Copilot is the one we test. Same marketplace, same
install commands, from inside `copilot`:

```
/plugin marketplace add sep/cc-status-plugin
/plugin install llmstatus@llmstatus-market
```

Copilot picks up the manifest in `.github/plugin/plugin.json`, which
routes hook registration to
[`hooks/copilot-hooks.json`](hooks/copilot-hooks.json) — same events,
same `emit.py`, so Copilot sessions light up the panel exactly like
Claude sessions and can share slots with them.

Copilot-flavored caveats:

- **Slot pairing** — `CLAUDE_STATUS_SLOT=1 copilot` binds the session
  to slot 1 at startup, exactly like the `claude` equivalent. The
  `/llmstatus:*` commands are surfaced as skills; if your Copilot
  build doesn't route them, env pairing is the reliable path.
- **`/llmstatus:permit` knows both hosts** — under Claude Code it
  writes `permissions.allow` in `~/.claude/settings.json`; under
  Copilot it runs `permit.py --copilot`, writing command-prefix
  approvals to `~/.copilot/permissions-config.json` and allowlisting
  the `~/.claude-status` status dir so file reads stop raising path
  prompts. Copilot scopes approvals per repo/directory (no global
  scope), so re-run it once per repo where you use the panel.
- **No `PostCompact` event** — after a context compaction the panel
  shows *compacting* until the next tool call or end of turn, then
  recovers on its own.
- **Restart sessions after install/update** — hooks bind at session
  creation, and a resumed session keeps its original registration.
  Skills refresh on resume, so `/llmstatus:*` commands will respond
  while the panel stays dark; `/restart` (or a fresh session) fixes it.

[copilot-cli]: https://github.com/github/copilot-cli

## Developers

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — coding conventions, slash
  command protocol, commit style.
- [`MAINTENANCE.md`](MAINTENANCE.md) — what the plugin watches for
  (Claude Code plugin protocol changes, the Python ecosystem) and how
  to cut a release.
- [`bin/`](bin/) — Python sources. `emit.py` is the per-event hook;
  `broker.py` is the TCP NDJSON broker; `pin.py` manages
  session-to-slot bindings; `permit.py` writes the
  permission-allowlist entries; `stdout-sink.py` is a debugging
  subscriber.
- [`commands/`](commands/) — slash command bodies (one markdown file
  per command).
- [`hooks/hooks.json`](hooks/hooks.json) — Claude Code lifecycle-hook
  registration. Every event invokes `emit.py`.
- [`hooks/copilot-hooks.json`](hooks/copilot-hooks.json) — the same
  registration in Copilot CLI's native hook format (referenced from
  `.github/plugin/plugin.json`). PascalCase event names are load-bearing:
  they make Copilot deliver Claude-shaped snake_case payloads
  (`hook_event_name`, `session_id`) that `emit.py` parses unchanged.

### Wire-protocol spec

The bridge ↔ firmware contract — what bytes go over USB serial —
lives canonically in the bridge repo: [FIRMWARE.md][spec]. The plugin
publishes events into the broker; the bridge translates them into the
wire format. If you're adding a new state or hook, read the spec
first.

[spec]: https://github.com/sep/cc-status-bridge/blob/main/FIRMWARE.md

### Cutting a release

The plugin's `version` field in `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, and `.github/plugin/plugin.json` is
the cache key `/plugin update` checks against (Claude Code and Copilot
respectively). Bump all three in lockstep before tagging:

```sh
# bump all three manifests to the new version
git commit -am "Plugin: bump to vX.Y.Z"
git tag vX.Y.Z
git push --tags
```

Existing installs pick up the new version on their next
`/plugin update`.

## License

[MIT](LICENSE). © 2026 SEP.
