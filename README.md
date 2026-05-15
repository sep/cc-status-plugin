# claude-status — plugin

Claude Code plugin that hooks every lifecycle event in your Claude
Code session and publishes a small NDJSON state stream to a local TCP
broker. The [bridge][bridge] subscribes to that broker and forwards
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
/plugin install claude-status@claude-status-local
/claude-status:permit
```

`/claude-status:help` lists every available slash command. Python 3
must be on PATH as the command `python` (any modern Windows / macOS /
Linux install; on default Ubuntu / Debian, install
`python-is-python3`).

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

### Wire-protocol spec

The bridge ↔ firmware contract — what bytes go over USB serial —
lives canonically in the bridge repo: [FIRMWARE.md][spec]. The plugin
publishes events into the broker; the bridge translates them into the
wire format. If you're adding a new state or hook, read the spec
first.

[spec]: https://github.com/sep/cc-status-bridge/blob/main/FIRMWARE.md

### Cutting a release

The plugin's `version` field in `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` is the cache key Claude Code's
`/plugin update` checks against. Bump it in lockstep before tagging:

```sh
# bump both .claude-plugin/{plugin,marketplace}.json to the new version
git commit -am "Plugin: bump to vX.Y.Z"
git tag vX.Y.Z
git push --tags
```

Existing installs pick up the new version on their next
`/plugin update`.

## License

[MIT](LICENSE). © 2026 SEP.
