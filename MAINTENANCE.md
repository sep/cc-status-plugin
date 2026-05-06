# Maintenance

Single living document of every external dependency the plugin relies
on, where to watch them, how to bump them, and what to test after.
**If you're picking the plugin back up after months away, start here**
— it's designed to remove the "where do I even look?" phase of
catching up.

The plugin's surface is intentionally tiny — pure stdlib Python plus
the Claude Code plugin protocol — so this document is shorter than
its sibling in the bridge repo. Most of what we watch is upstream's
plugin protocol, not third-party packages.

## Active maintenance signals

| Signal | Cadence | Lives in | What it means |
| --- | --- | --- | --- |
| **Dependabot PRs** | Mondays | `.github/dependabot.yml` | Currently watches GitHub Actions only (no third-party Python deps yet). Will activate when CI workflows land. |
| **Claude Code releases** | Whenever Anthropic ships | <https://github.com/anthropics/claude-code/releases> | Plugin protocol changes (new hook events, hook payload shape changes, slash-command frontmatter additions). Read release notes before bumping any plugin metadata. |

## Dependencies

### Claude Code plugin protocol

- **Currently exercised features:** lifecycle hooks
  (`UserPromptSubmit`, `Stop`, `Notification`, `PreCompact`,
  `PostCompact`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`,
  `SubagentStop`), `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}`
  env vars, slash commands with frontmatter `description`, the
  `permissions.allow` settings shape (used by `/permit`).
- **Watch:** <https://docs.claude.com/en/docs/claude-code/plugins>
  and Claude Code release notes. Hook events occasionally get added,
  renamed, or have their payload shape extended.
- **Bump procedure:** when a hook payload shape changes, update
  `bin/emit.py`'s parsing. When a new hook event we care about is
  added, register it in `hooks/hooks.json`. Bump
  `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`
  versions in lockstep so existing installs pick up the change via
  `/plugin update`.

### Python (stdlib only)

- **Currently exercised:** Python 3.7+ surface (`pathlib`,
  `subprocess`, `socket`, `json`, `asyncio`, `dataclasses`,
  `sys.stdout.reconfigure`).
- **Pinned:** invocations use `python` (not `python3`) to be
  cross-platform-friendly — Windows Python installers only put
  `python.exe` on PATH, while modern Linux/macOS treat `python` as
  Python 3. Default Ubuntu/Debian without `python-is-python3` is the
  one common gotcha; documented in the install instructions.
- **Watch:** <https://www.python.org/downloads/> for major releases
  that might deprecate stdlib APIs we use.
- **Risk:** very low. Stdlib doesn't churn.

### Wire-protocol contract

The plugin publishes events to the broker; the bridge translates them
into the wire format the firmware expects. The canonical wire-protocol
spec lives in the **bridge repo**:

→ <https://github.com/sep/cc-status-bridge/blob/main/FIRMWARE.md>

When the wire protocol gains a new state, command, or hint kind, the
relevant code path is usually in the bridge (translation layer), not
here. The plugin generally only needs updating when a new lifecycle
hook event needs to publish into the broker.

### GitHub Actions

When CI workflows land here, all actions should be **pinned to commit
SHAs** (not tags) for supply-chain security — Dependabot rewrites
both the SHA and the trailing version comment when bumping. Currently
no workflows.

## Versioning

The plugin's source of truth is the `version` field in **two**
files, kept in lockstep:

- `.claude-plugin/plugin.json` — Claude Code reads this to decide
  whether `/plugin update` should pull a new copy. The `version`
  field is the cache key.
- `.claude-plugin/marketplace.json` — listed in the marketplace
  metadata; should match `plugin.json`.

**Both must bump together.** Mismatch means Claude Code's
update-detection sees the marketplace listing as stale even after
users install the new version, or vice versa.

Versions follow loose semver:

- **Major (X.0.0)** — slash-command surface change a user has to
  know about (renaming `/show`, removing a command, changing the
  semantic of an existing one). Rare.
- **Minor (X.Y.0)** — a new slash command, a new hook the plugin
  registers, a new env var the broker writes. Additive.
- **Patch (X.Y.Z)** — bug fixes, doc edits, internal refactors.

Pre-1.0 the bar is looser — minor bumps for behavior changes are
fine.

## Cutting a release

1. Bump `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json` to the new version (in lockstep).
   Commit on `main`.
2. Verify the slash commands still fire by sending any prompt with
   the plugin loaded, then watching for the `idle` → `working` → `idle`
   transition on the panel.
3. Run `/claude-status:permit` if the script's pattern shape changed
   in this version (so the new patterns get added to settings.json).
4. `git tag vX.Y.Z && git push --tags`.
5. Existing installs pick up the new version on their next
   `/plugin update`. If the plugin's `version` field didn't change,
   `/plugin update` reports "already at the latest version" — even if
   the repo has new commits. This is by design (the version field is
   the cache key); double-check the bump if updates aren't reaching
   users.

## When a Monday is loud

The plugin's surface is small enough that simultaneous signals are
rare. If they happen:

1. **Claude Code release with breaking plugin-protocol changes.**
   Most urgent — fix `bin/emit.py` parsing or `hooks/hooks.json` to
   match.
2. **Dependabot PRs.** GitHub Action SHAs only; should be benign.
