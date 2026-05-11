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
  /* ---- feature cards (the three "panelly" buttons) ---- */
  .feature-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
    margin: 2.5rem 0 3rem;
  }
  @media (max-width: 600px) {
    .feature-cards { grid-template-columns: 1fr; }
  }
  .feature-card {
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    min-height: 200px;
    padding: 1.5rem 1.25rem;
    border-radius: 10px;
    overflow: hidden;
    text-decoration: none !important;
    color: #fff !important;
    background-color: #1f2933;
    background-size: cover;
    background-position: center;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    text-align: left;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
  }
  /* dark + green gradient overlay so text stays readable
     regardless of which photo loremflickr happens to hand back */
  .feature-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(
      135deg,
      rgba(15, 32, 28, 0.78) 0%,
      rgba(21, 153, 87, 0.55) 100%
    );
    transition: opacity 0.18s ease;
    z-index: 1;
  }
  .feature-card > * { position: relative; z-index: 2; }
  .feature-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 18px rgba(21, 153, 87, 0.28);
  }
  .feature-card:hover::before { opacity: 0.85; }
  .feature-card .feature-card-title {
    display: block;
    margin: 0 0 0.45rem;
    font-size: 1.35em;
    font-weight: 600;
    color: #fff;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
  }
  .feature-card .feature-card-sub {
    display: block;
    color: rgba(255, 255, 255, 0.92);
    font-size: 0.95em;
    line-height: 1.45;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
  }

  /* ---- section dividers ---- */
  .section-divider {
    border: 0;
    height: 3px;
    background: linear-gradient(
      90deg,
      transparent 0%,
      #159957 50%,
      transparent 100%
    );
    margin: 4rem auto 3rem;
    max-width: 60%;
    border-radius: 2px;
  }
</style>

<div class="feature-cards">
  <a class="feature-card" href="#the-panel"
     style="background-image: url('https://loremflickr.com/600/300/led,matrix,pixel');">
    <span class="feature-card-title">The Panel</span>
    <span class="feature-card-sub">What you see, and what each state means.</span>
  </a>
  <a class="feature-card" href="#installation"
     style="background-image: url('https://loremflickr.com/600/300/circuit,electronics,solder');">
    <span class="feature-card-title">Installation</span>
    <span class="feature-card-sub">Firmware → bridge → plugin, in that order.</span>
  </a>
  <a class="feature-card" href="#how-it-works"
     style="background-image: url('https://loremflickr.com/600/300/network,data,signal');">
    <span class="feature-card-title">How it works</span>
    <span class="feature-card-sub">From prompt to pixels in three hops.</span>
  </a>
</div>

<hr class="section-divider">

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

<hr class="section-divider">

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

<hr class="section-divider">

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

→ **[the firmware repo on GitHub]({{ site.firmware_site }})**

Once flashed, plug the ESP32-S3 into your computer over USB. It
enumerates as a serial device — `COM5` on Windows, `/dev/cu.usbmodem*`
on macOS, `/dev/ttyACM0` on Linux — and the panel boots into an
"unknown" state, ready to receive events.

### 2. Install + configure the bridge

The bridge is a system-tray app (Windows notification area / macOS
menu bar / Linux status icon) that subscribes to the plugin's local
broker and forwards each Claude Code event to the firmware over USB
serial. Cross-platform installers ship on every release.

→ **[the bridge install page]({{ site.bridge_site }})**

That page auto-detects your OS and shows the right download
(`Setup.exe` on Windows, `.dmg` on macOS, `.AppImage` on Linux). It
also covers the OS-specific quirks (SmartScreen on Windows,
Gatekeeper on macOS, tray-host extensions on GNOME). After install,
right-click the tray icon → **Connect device** to point the bridge
at the ClaudePanel you connected in step 1.

### 3. Install the plugin

The plugin (this repo) is the Claude Code half of the system: it
hooks every lifecycle event and publishes the state stream the
bridge subscribes to.

**Prerequisite:** Python 3 installed. The plugin's scripts use a
`#!/usr/bin/env python3` shebang, so the OS picks the interpreter
itself — you don't need any particular alias on your `PATH`.

  - **macOS / Linux / WSL:** any Python 3 install with `python3`
    on `PATH` works (Homebrew, pyenv, system package manager, etc.).
  - **Windows:** the python.org or Microsoft Store installer sets up
    the `py.exe` launcher and the `.py` file association — both honor
    the shebang. No extra config needed.

Install the plugin from inside Claude Code:

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

<hr class="section-divider">

## Commands

The panel has numbered **slots** (`1`, `2`, ...) and optional half-slots
(`1a`, `1b`, ...) that each render one Claude session's state. Slash
commands move sessions between slots; bridge subcommands manage the
bridge process itself. Most users only ever need the everyday tier.

### Plugin slash commands

Run these inside Claude Code (with the plugin installed).

#### Everyday

| Command                         | What it does                                            |
|---------------------------------|---------------------------------------------------------|
| `/claude-status:show <slot>`    | Send this session's state to slot N (e.g. `1`, `2b`).   |
| `/claude-status:hide`           | Stop sending this session to the display.               |
| `/claude-status:status`         | Show which sessions are routed to which slots.          |
| `/claude-status:identify [N]`   | Flash each panel's slot ID for N seconds (default 5).   |

#### Setup

| Command                         | What it does                                            |
|---------------------------------|---------------------------------------------------------|
| `/claude-status:configure <N>`  | Tell the firmware your panel-chain length (1–4).        |
| `/claude-status:permit`         | One-time: allowlist the plugin's Bash invocations so    |
|                                 | commands stop prompting.                                |
| `/claude-status:reset`          | Wipe all session slot bindings — clean slate.           |
| `/claude-status:help`           | List every slash command, briefly.                      |

#### Power users only

These split `show` and `hide` into their two sub-operations: a **route**
(which slot a session lands on) and a **pin** (which session exclusively
owns the bridge's transport). Most users don't need them — `show` /
`hide` cover the everyday flow.

| Command                       | What it does                                              |
|-------------------------------|-----------------------------------------------------------|
| `/claude-status:route <slot>` | Set a route only; don't claim the transport.              |
| `/claude-status:unroute`      | Drop the route only.                                      |
| `/claude-status:attach`       | Claim the transport for this session; don't change route. |
| `/claude-status:detach`       | Drop both claim and route.                                |

### Bridge CLI

Run these in a terminal (or in pwsh on Windows). Most users won't need
to — the tray menu covers Connect device / Show logs / Pause / Quit.
The bridge install page documents each subcommand in detail.

→ **[bridge subcommand reference]({{ site.bridge_site }}#cli-usage)**

<hr class="section-divider">

## Repos

- Plugin (this site): [cc-status-plugin]({{ site.plugin_repo }})
- Bridge: [cc-status-bridge]({{ site.bridge_repo }})
- Firmware: [cc-status-display]({{ site.firmware_repo }})
