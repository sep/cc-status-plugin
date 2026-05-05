---
description: List the claude-status slash commands with a one-line synopsis of each.
---

Print the synopsis below to the user verbatim. No preamble, no follow-up questions, no `pin.py status` call — just the list.

```
claude-status — slash commands

The panel has numbered slots (1, 2, ...). Slash commands move your
Claude session onto, off, or between those slots.

  Everyday:
    /claude-status:show <slot>     Send this session's state to slot N
                                   (e.g. 1, 2b). Slot stays bound to
                                   you until you /hide.
    /claude-status:hide            Stop sending this session to the
                                   display.
    /claude-status:status          Show which sessions are routed
                                   to which slots.
    /claude-status:identify [N]    Flash each panel's slot ID for N
                                   seconds (default 5) so you can see
                                   which physical panel is which slot.

  Setup:
    /claude-status:configure <N>   Tell the firmware your panel-chain
                                   length (1-4). Persists in NVS.
    /claude-status:permit          One-time: allowlist the plugin's
                                   Bash invocations so commands stop
                                   prompting for permission.
    /claude-status:reset           Wipe all sessions' slot bindings —
                                   clean slate.

  Power users only (these split /show and /hide into their two
  sub-operations: route = which slot, pin = exclusive transport claim):
    /claude-status:route <slot>    Route to a slot without claiming
                                   the transport.
    /claude-status:unroute         Drop route only.
    /claude-status:attach          Claim the transport for this
                                   session (no route change).
    /claude-status:detach          Drop both claim and route.

  Help:
    /claude-status:help            This message.
```
