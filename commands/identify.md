---
description: "Briefly flash each panel's ID on the display, so you can see which physical panel is which logical slot. Usage: /llmstatus:identify [seconds]"
---

The identify command has been issued via the plugin's hook. The bridge will forward it to the firmware as soon as it processes this prompt's event, and each panel will display its slot ID in large glyphs for the requested duration (default 5 seconds; firmware clamps to 0.5–30s).

Briefly confirm to the user that identify is on its way. No status check needed — there's nothing persisted to read back. If they don't see panel IDs flash within a second or two, the most likely causes are: (a) the bridge isn't running, or (b) the firmware doesn't yet implement the v1.2 `identify` command from FIRMWARE.md §8.
