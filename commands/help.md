---
description: List the claude-status slash commands with a one-line synopsis of each.
---

Print the synopsis below to the user verbatim. No preamble, no follow-up questions, no `pin.py status` call — just the list.

```
claude-status — slash commands

  Everyday:
    /claude-status:show <slot>     Send this session's status to a panel
                                   slot (e.g. 1, 2a, 2b). Routes + pins.
    /claude-status:hide            Stop sending this session to the
                                   display. Clears route + pin.
    /claude-status:status          Show what's currently pinned and
                                   what each panel slot is routing.
    /claude-status:identify [N]    Flash each panel's slot ID for N
                                   seconds (default 5) so you can tell
                                   which physical panel is which slot.

  Setup:
    /claude-status:configure <N>   Tell the firmware your panel-chain
                                   length (1-4). Persists in NVS.
    /claude-status:reset           Wipe the entire pin + routes table.
                                   Use when state has gotten kludged.

  Granular (when show/hide aren't enough):
    /claude-status:route <slot>    Route this session's events to a
                                   slot, without changing the pin.
    /claude-status:unroute         Drop this session's route only.
    /claude-status:attach          Pin transport to this session only.
    /claude-status:detach          Release pin AND remove route.

  Permissions:
    /claude-status:permit          One-time setup: allowlist the
                                   plugin's hook commands in
                                   ~/.claude/settings.json so Claude
                                   stops asking for permission on
                                   every plugin-driven hook.

  Help:
    /claude-status:help            This message.
```
