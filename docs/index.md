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
  panel. Lives at
  [sep/cc-status-display](https://github.com/sep/cc-status-display).

## Setup

ClaudePanel has three pieces and they need to come up in a specific
order: **firmware first**, then **bridge**, then **plugin**. Each
piece has detailed docs of its own — this page is the orientation
that ties them together.

### 1. Flash the firmware

Build and flash the ESP32-S3 firmware to your panel hardware. You'll
need ESP-IDF v6.0 installed locally and a HUB75 panel wired up
(default expectation is a 64×32 WaveShare RGB-Matrix-P2.5; multi-
panel chains are supported).

→ **[github.com/sep/cc-status-display](https://github.com/sep/cc-status-display)**

Once flashed, plug the ESP32-S3 into your computer over USB. It
enumerates as a serial device — `COM5` on Windows, `/dev/cu.usbmodem*`
on macOS, `/dev/ttyACM0` on Linux — and the panel boots into an
"unknown" state, ready to receive events.

### 2. Install + configure the bridge

The bridge is a system-tray app (Windows notification area / macOS
menu bar / Linux status icon) that subscribes to the plugin's local
broker and forwards each Claude Code event to the firmware over USB
serial. Cross-platform installers ship on every release.

→ **[sep.github.io/cc-status-bridge](https://sep.github.io/cc-status-bridge/)**

That page auto-detects your OS and shows the right download
(`Setup.exe` on Windows, `.dmg` on macOS, `.AppImage` on Linux). It
also covers the OS-specific quirks (SmartScreen on Windows,
Gatekeeper on macOS, tray-host extensions on GNOME). After install,
right-click the tray icon → **Connect device** to point the bridge
at the ClaudePanel you connected in step 1.

### 3. Install the plugin

The plugin (this repo) is the Claude Code half of the system: it
hooks every lifecycle event and publishes the state stream the
bridge subscribes to. Install it from inside Claude Code:

```
/plugin marketplace add sep/cc-status-plugin
/plugin install claude-status@claude-status-local
```

Then run the one-time permission setup so Claude Code stops asking
to approve every plugin-driven Bash invocation:

```
/claude-status:permit
```

If you have a multi-panel chain (rather than a single 64×32), tell
the firmware once — the layout is cached in NVS so it survives
reboots:

```
/claude-status:configure 2
```

`/claude-status:help` lists every slash command the plugin provides.

### Verify

Send any prompt in Claude Code. The panel should light up — yellow
while Claude is working, green when it goes idle. Run
`/claude-status:identify` to flash each physical panel's slot ID
large and centered, so you can confirm wiring matches what the
firmware thinks the layout is.

If nothing happens, the bridge's tray icon's **Show logs** menu
item is the first place to look.

## Repos

- Plugin (this site): [sep/cc-status-plugin](https://github.com/sep/cc-status-plugin)
- Bridge: [sep/cc-status-bridge](https://github.com/sep/cc-status-bridge)
- Firmware: [sep/cc-status-display](https://github.com/sep/cc-status-display)
