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
| **Copilot CLI releases** | Whenever GitHub ships | <https://github.com/github/copilot-cli/blob/main/changelog.md> | Hook/plugin protocol changes on the Copilot side — especially anything touching Claude-compat behavior (PascalCase event payloads, `CLAUDE_PLUGIN_*` env vars, `.claude-plugin/` manifest discovery). |

## Dependencies

### Claude Code plugin protocol

- **Currently exercised features:** lifecycle hooks
  (`SessionStart`, `SessionEnd`, `UserPromptSubmit`, `Stop`,
  `Notification`, `PreCompact`, `PostCompact`, `PreToolUse`,
  `PostToolUse`, `PostToolUseFailure`, `SubagentStop`),
  `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` env vars, slash
  commands with frontmatter `description`, the `permissions.allow`
  settings shape (used by `/permit`). `SessionEnd` is what retires
  the session's broker process — without it brokers linger until the
  idle timeout, and on Windows a lingering broker blocks plugin
  uninstall/update.
- **Watch:** <https://docs.claude.com/en/docs/claude-code/plugins>
  and Claude Code release notes. Hook events occasionally get added,
  renamed, or have their payload shape extended.
- **Bump procedure:** when a hook payload shape changes, update
  `bin/emit.py`'s parsing. When a new hook event we care about is
  added, register it in `hooks/hooks.json` **and**
  `hooks/copilot-hooks.json` (if Copilot supports it). Bump
  `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` +
  `.github/plugin/plugin.json` versions in lockstep so existing
  installs pick up the change via `/plugin update`.

### GitHub Copilot CLI plugin protocol

Copilot CLI (>= 1.0.66) deliberately mirrors Claude Code's plugin
surface, which is what makes dual support cheap. What we lean on:

- **Manifest discovery order:** `.plugin/plugin.json` →
  `plugin.json` → `.github/plugin/plugin.json` →
  `.claude-plugin/plugin.json`. Our `.github/plugin/plugin.json` is
  the Copilot-facing manifest (Claude Code never reads it); it points
  `hooks` at `hooks/copilot-hooks.json` and `commands` at
  `commands/` explicitly (Copilot has no default commands path).
  Copilot also reads `.claude-plugin/marketplace.json`, so
  `/plugin marketplace add sep/cc-status-plugin` works verbatim.
- **PascalCase event names ⇒ Claude-shaped payloads.** Hooks
  registered with PascalCase names (`PreToolUse`, not `preToolUse`)
  receive VS Code-compatible snake_case payloads carrying
  `hook_event_name`, `session_id`, and Claude tool names (`Bash`,
  `Agent`) — the exact shape `emit.py` parses. Never switch
  `copilot-hooks.json` to camelCase names; that flips the payloads to
  camelCase and silently breaks `emit.py`'s field extraction.
- **Env vars:** Copilot exports `CLAUDE_PLUGIN_ROOT` (>= 1.0.26) and
  `CLAUDE_PLUGIN_DATA` (>= 1.0.12) to plugin hooks, so `emit.py` and
  `broker.py` resolve paths identically under both agents. `emit.py`
  additionally falls back to its own file location for the plugin
  root, covering repo-level `.github/hooks/*.json` installs where no
  plugin env exists.
- **Event-name deltas:** Copilot has no `PostCompact` — it's
  registered only in the Claude hooks file, and the bridge already
  recovers from *compacting* on the next tool call or `Stop`.
  Copilot's `agentStop` and `notification` map to `Stop` /
  `Notification` under PascalCase registration, with matching
  `notification_type` values (`permission_prompt`,
  `elicitation_dialog`).
- **Slash-command rewriting:** Copilot does NOT pass the raw typed
  `/llmstatus:show 1` to `userPromptSubmitted`. It rewrites the
  prompt to `The user explicitly invoked the "/llmstatus:show"
  skill. …` followed by a `<skill-context>` block whose LAST line
  carries `ARGUMENTS: <args>` (absent when no args were typed).
  `emit.py`'s `_extract_command_body` parses both shapes; if Copilot
  changes this wrapper text, that regex is the thing to fix
  (`CLAUDE_STATUS_DEBUG=1` shows the actual delivered prompt).
- **Payload-shape wobble:** Copilot's `notification` event is a
  camelCase/snake_case hybrid — `hook_event_name` is present but the
  session id is spelled `sessionId` (and `timestamp` is Unix ms, not
  ISO). `emit.py` normalizes `sessionId` → `session_id`; watch for
  the same hybrid creeping into other events. `PostToolUse` carries
  `tool_result` (not Claude's `tool_response`) — currently unused.
- **Permissions:** `permit.py --copilot` writes command-prefix
  approvals into `~/.copilot/permissions-config.json`
  (`COPILOT_HOME` honored), scoped per location the way Copilot
  itself scopes them (git repo root, else cwd; no global scope).
  It also adds the well-known status dir to the location's
  `allowed_directories` — Copilot gates file access outside the
  workspace separately from shell commands, and the command bodies
  have the model read `routes.json` / `panel_layout.json` from that
  dir directly.
  Schema documented at
  <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference> —
  if that schema shifts, `copilot_main()` in `bin/permit.py` is the
  code to fix.
- **Strict frontmatter parsing:** Copilot's command→skill translation
  parses `commands/*.md` frontmatter with a strict YAML parser.
  Unquoted `description` values containing colon+space fail to load
  (Claude Code tolerates them, masking the bug). `.gitattributes`
  pins LF so Windows clones can't CRLF-poison the frontmatter either.
- **Watch:**
  <https://docs.github.com/en/copilot/reference/hooks-reference> and
  the Copilot CLI changelog. The Claude-compat layer is the newest
  and least-settled part of their protocol; payload-shape regressions
  land there first.

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

### State topology across OS boundaries

On a WSL + Windows machine, route/layout/broker state legitimately
exists in several places, and the design treats them differently:

- **The well-known status dir is the rendezvous** —
  `~/.claude-status` (on WSL: `/mnt/c/Users/<you>/.claude-status`,
  i.e. the *Windows* home, so both sides and the bridge share one
  directory). Every write (`pin.py` targets(), broker state mirroring)
  lands there; the bridge reads only there.
- **Per-agent data dirs are private caches** (`CLAUDE_PLUGIN_DATA`
  under `~/.claude/...` or `~/.copilot/plugin-data/...`). They're
  unreachable from the other OS and go stale; `read_routes()` merges
  them back in, so every route write is preceded by bind-time pruning
  (`_session_has_broker_state`) to stop stale entries from
  resurrecting.
- **Liveness travels as mirrored `broker.json` existence, not
  connectivity.** A WSL process cannot probe a Windows broker's
  loopback port (or reliably vice versa), so: pin.py prunes on
  *existence* of `broker.json` in any base, brokers stamp a
  `platform` tag into `broker.json`, and the startup janitor
  port-probes ONLY brokers from its own platform tag — cross-platform
  corpses are the other side's janitor's job.

**Naming note:** the plugin renamed to `llmstatus` (v0.5), but the
well-known status dir (`~/.claude-status`), its env-var overrides
(`CLAUDE_STATUS_SLOT`, `CLAUDE_STATUS_DEBUG`,
`CLAUDE_STATUS_MIRROR_DIR`), and the `CLAUDE_PLUGIN_*` variables keep
their names on purpose: the dir and env overrides are the contract the
bridge discovers state through (renaming them is a coordinated
bridge-plugin release), and `CLAUDE_PLUGIN_ROOT`/`_DATA` are set by
the host agents, not by us.

No broker↔broker or broker↔client heartbeat is needed: creation at
spawn plus deletion at SessionEnd/idle-exit, both mirrored, gives
eventual consistency with zero cross-OS connectivity assumptions.

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

The plugin's source of truth is the `version` field in **three**
files, kept in lockstep:

- `.claude-plugin/plugin.json` — Claude Code reads this to decide
  whether `/plugin update` should pull a new copy. The `version`
  field is the cache key.
- `.claude-plugin/marketplace.json` — listed in the marketplace
  metadata; should match `plugin.json`.
- `.github/plugin/plugin.json` — the Copilot CLI-facing manifest;
  same role as the Claude one, for Copilot's update detection.

**All must bump together.** Mismatch means Claude Code's
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

1. Bump `.claude-plugin/plugin.json`,
   `.claude-plugin/marketplace.json`, and `.github/plugin/plugin.json`
   to the new version (in lockstep). Commit on `main`.
2. Verify the slash commands still fire by sending any prompt with
   the plugin loaded, then watching for the `idle` → `working` → `idle`
   transition on the panel.
3. Run `/llmstatus:permit` if the script's pattern shape changed
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
