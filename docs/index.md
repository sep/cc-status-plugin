---
layout: default
title: ClaudePanel
---

# ClaudePanel

**Claude Code External Status Display**

ClaudePanel is a small hardware indicator that shows what Claude Code is
doing right now — whether it's processing your prompt, waiting on you to
approve a tool, finished its turn, or stuck on something — so you can
glance at a panel on your desk instead of watching your terminal.

> *Photo of the device displaying different states will land here once
> we've got hardware in front of a camera.*

## What it shows

| State          | Meaning                                           |
|----------------|---------------------------------------------------|
| **idle**       | Claude has finished its turn; waiting for you.    |
| **working**    | Claude is actively processing your prompt.        |
| **thinking**   | Claude is in the middle of a response but hasn't  |
|                | called a tool for a while — usually composing.    |
| **blocked**    | Claude needs your input (permission prompt, etc.) |
| **compacting** | Claude Code is summarizing the conversation       |
|                | history — usually a 10–60s pause.                 |
| **error**      | A tool call returned an error.                    |

The panel also displays counts of running subagents and active tasks,
so you can keep an eye on parallel work without scrolling.

## How it's built

ClaudePanel is three pieces working together:

```
 Claude Code  ──►  Plugin  ──►  Bridge  ──►  Firmware  ──►  Display
                  (Python)    (cross-     (ESP32-S3)     (RGB matrix
                              platform)                   panel)
```

- **The plugin** *(this repo)* listens to Claude Code's lifecycle hooks
  and publishes session events over a local TCP broker.
- **The bridge** subscribes to the broker and forwards each event over
  USB serial. Cross-platform: Windows, macOS, and Linux. Lives at
  [sep/cc-status-bridge](https://github.com/sep/cc-status-bridge).
- **The firmware** runs on an ESP32-S3 driving a HUB75 RGB matrix
  panel. Lives at *(firmware repo link to come)*.

## Project status

ClaudePanel is in active development. We're shipping cross-platform
binaries of the bridge automatically on every release — see the
[bridge releases page](https://github.com/sep/cc-status-bridge/releases)
for `win-x64`, `linux-x64`, `osx-x64`, and `osx-arm64` builds.

End-user installation guides, troubleshooting docs, and a hardware
build guide are coming. For now, the project is best suited to
developers who are comfortable building and flashing their own
ESP32-S3 firmware from source.

## Repos

- Plugin (this site): [sep/cc-status-plugin](https://github.com/sep/cc-status-plugin)
- Bridge: [sep/cc-status-bridge](https://github.com/sep/cc-status-bridge)
- Firmware: *coming soon*
