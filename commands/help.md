---
description: List the claude-status slash commands with a one-line synopsis of each.
---

Print the synopsis below to the user verbatim. No preamble, no follow-up questions, no `pin.py status` call — just the list.

```
claude-status — slash commands

The panel has numbered slots (1, 2, ...). Slash commands bind your
Claude session to a slot, or release the binding.

  Everyday:
    /claude-status:show <slot>     Bind this session to slot N
                                   (e.g. 1, 2b). Displaces any prior
                                   occupant of the slot, and releases
                                   any prior slot this session held.
    /claude-status:hide            Release this session's slot binding.
                                   Display becomes blank if no other
                                   session is bound to that slot.
    /claude-status:status          Show which sessions are bound
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

  Help:
    /claude-status:help            This message.

  Tip — CLI pairing:
    CLAUDE_STATUS_SLOT=1 claude    Auto-binds the session to slot 1
                                   on start, no slash command needed.
                                   Pair with shell aliases for
                                   different slots.
```
