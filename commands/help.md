---
description: List the llmstatus slash commands with a one-line synopsis of each.
---

Print the synopsis below to the user verbatim. No preamble, no follow-up questions, no `pin.py status` call — just the list.

```
llmstatus — slash commands

The panel has numbered slots (1, 2, ...). Slash commands bind your
Claude session to a slot, or release the binding.

  Everyday:
    /llmstatus:show <slot>     Bind this session to slot N
                                   (e.g. 1, 2b). Displaces any prior
                                   occupant of the slot, and releases
                                   any prior slot this session held.
    /llmstatus:hide            Release this session's slot binding.
                                   Display becomes blank if no other
                                   session is bound to that slot.
    /llmstatus:status          Show which sessions are bound
                                   to which slots.
    /llmstatus:identify [N]    Flash each panel's slot ID for N
                                   seconds (default 5) so you can see
                                   which physical panel is which slot.

  Setup:
    /llmstatus:configure <N>   Tell the firmware your panel-chain
                                   length (1-4). Persists in NVS.
    /llmstatus:permit          One-time: allowlist the plugin's
                                   Bash invocations so commands stop
                                   prompting for permission.
    /llmstatus:reset           Wipe all sessions' slot bindings —
                                   clean slate.

  Help:
    /llmstatus:help            This message.

  Tip — CLI pairing:
    CLAUDE_STATUS_SLOT=1 claude    Auto-binds the session to slot 1
                                   on start, no slash command needed.
                                   Pair with shell aliases for
                                   different slots. Works for Copilot
                                   sessions too: CLAUDE_STATUS_SLOT=1
                                   copilot
```
