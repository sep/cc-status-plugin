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

<style>
  .feature-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin: 2rem 0 2.5rem;
  }
  @media (max-width: 600px) {
    .feature-cards { grid-template-columns: 1fr; }
  }
  .feature-card {
    display: block;
    padding: 1.5rem 1.25rem;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    text-decoration: none !important;
    color: #24292f;
    background: #fff;
    transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
    text-align: center;
  }
  .feature-card:hover {
    border-color: #159957;
    box-shadow: 0 2px 12px rgba(21, 153, 87, 0.18);
    transform: translateY(-2px);
  }
  .feature-card .feature-card-title {
    display: block;
    margin: 0 0 0.4rem;
    font-size: 1.18em;
    font-weight: 600;
    color: #24292f;
  }
  .feature-card .feature-card-sub {
    display: block;
    color: #57606a;
    font-size: 0.92em;
    line-height: 1.4;
  }
</style>

<div class="feature-cards">
  <a class="feature-card" href="#the-panel">
    <span class="feature-card-title">The Panel</span>
    <span class="feature-card-sub">What you see, and what each state means.</span>
  </a>
  <a class="feature-card" href="#installation">
    <span class="feature-card-title">Installation</span>
    <span class="feature-card-sub">Firmware → bridge → plugin, in that order.</span>
  </a>
  <a class="feature-card" href="#how-it-works">
    <span class="feature-card-title">How it works</span>
    <span class="feature-card-sub">From prompt to pixels in three hops.</span>
  </a>
</div>

## The Panel

The panel renders one of six states at any given time, picked to be
distinguishable at a glance from across a desk:

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

Alongside the state, the panel also shows running counts of subagents
and active tasks — handy when you've kicked off parallel work and want
to monitor it without scrolling the terminal.

A single firmware instance can drive one panel or a chain of up to
four 64×32 panels, with each panel optionally split into two
half-panel "client slots" so multiple Claude Code sessions can share a
display.

## How it works

When you write a prompt in Claude Code, ClaudePanel converts that
keystroke into pixels in three hops:

1. **The plugin** *(this repo)* hooks every Claude Code lifecycle event
   — `UserPromptSubmit`, `Stop`, `PreToolUse`, `PostCompact`, and so on
   — and publishes a small JSON event for each one to a local TCP
   broker on your machine.
2. **The bridge** subscribes to the broker, runs a state machine over
   the event stream (idle / working / thinking / blocked / compacting
   / error), and forwards each state change as a one-line JSON message
   over USB serial.
3. **The firmware** on the ESP32-S3 reads the serial line, picks the
   right palette and glyph, and updates the HUB75 panel's framebuffer.

The whole loop is fast enough that the panel reacts within a few
hundred milliseconds of you pressing Enter.

```
 Claude Code  ──►  Plugin  ──►  Bridge  ──►  Firmware  ──►  Display
                  (Python)    (cross-     (ESP32-S3)     (RGB matrix
                              platform)                   panel)
```

Each piece lives in its own repo and is the source of truth for its
own internals. See [Repos](#repos) at the bottom.

## Installation

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
