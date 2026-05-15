# Contributing to claude-status (the plugin)

## Coding conventions

### Layout

Python defaults: 4-space indent, follows PEP 8 broadly. The plugin's
code is small enough that we don't gate on a formatter / linter, but
matching what's already there keeps things tidy.

- ~88-column soft limit, ~100 hard.
- Type hints where they aid readability (`def foo(x: str) -> int`)
  but not enforced everywhere.
- Stdlib only — keep the dependency surface zero so the plugin
  installs cleanly on any Python 3.7+ install without a venv.

### Naming

PEP 8:

| Kind                | Style                | Example                              |
| ------------------- | -------------------- | ------------------------------------ |
| Functions           | `snake_case`         | `data_dir`, `read_port`              |
| Local variables     | `snake_case`         | `session_id`, `payload`              |
| Module-level consts | `SCREAMING_SNAKE`    | `SPAWN_TIMEOUT_SECONDS`              |
| Classes             | `PascalCase`         | `Broker`                             |
| Files               | `snake_case.py`      | `emit.py`, `pin.py`, `permit.py`     |

## Slash-command protocol

Each slash command is a markdown file under [`commands/`](commands/)
with a frontmatter `description` field and a body that's
**instructions to Claude**, not user-facing text. Conventions:

- The body usually describes what the plugin's hook ALREADY did
  (e.g. "the session has been bound by the plugin's hook"), then
  asks Claude to confirm via the polyglot invocation
  `python3 "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status || python "${CLAUDE_PLUGIN_ROOT}/bin/pin.py" status`.
- Use the polyglot `python3 ... || python ...` form everywhere, not a
  bare `python` or `python3`. Claude Code's matcher splits commands
  on `||` and prefix-checks each subcommand independently, so both
  branches must be allowlisted.
- Description in frontmatter is the one-liner that shows up in
  Claude Code's slash-command picker; keep it scannable.
- If the command takes arguments, document the format in the
  description (`Usage: /claude-status:show <slot>`).

## Adding a new slash command

1. Create `commands/<verb>.md` with frontmatter + body following the
   conventions above.
2. If the body invokes a Bash command, `bin/permit.py` already covers
   both interpreter prefixes (`python3`, `python`) and both slash
   variants for the canonical `pin.py` / `emit.py` paths. New
   commands that invoke a NEW script under `bin/` need that script
   added to permit.py's pattern loops.
3. Add a one-line entry to `commands/help.md`'s tier-grouped synopsis.
4. Add a one-line entry to the hub site's "Commands" section in
   [`docs/index.md`](docs/index.md).
5. Bump `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json` versions in lockstep so existing
   installs pick the new command up via `/plugin update`.

## Wire-protocol changes

The wire-protocol contract is the canonical [FIRMWARE.md in the
bridge repo][spec]. The plugin publishes events into the broker; the
bridge translates them into the wire format. If you're adding a new
state, hint kind, or device-bound command, the change lands in the
bridge first — the plugin only changes if a NEW event source needs
to publish.

[spec]: https://github.com/sep/cc-status-bridge/blob/main/FIRMWARE.md

## Cross-OS gotchas

- Use the polyglot `python3 ... || python ...` in hooks.json + slash
  commands, never just one. `python3` exists on POSIX but not Windows;
  `python` is Python 3 on Windows but Python 2 on legacy macOS. The
  fallback chain covers all three. Claude Code's matcher splits on
  `||` and checks each side, so both interpreter prefixes have to be
  in the allowlist (permit.py writes both).
- For subprocess spawn, use `sys.executable` instead of any literal
  command name — that's whatever Python is currently running.
- Force UTF-8 on stdout/stderr at the top of any script that prints
  non-ASCII (the `pin.py status` output uses `×` and `—` which
  Windows ANSI codepages can't encode):

  ```python
  try:
      sys.stdout.reconfigure(encoding="utf-8")
      sys.stderr.reconfigure(encoding="utf-8")
  except (AttributeError, TypeError, ValueError):
      pass
  ```

## Commit & PR style

- Keep commits small and reviewable.
- Commit messages: imperative subject, body if non-obvious. "Why"
  matters more than "what".
- Don't commit `__pycache__/`, `*.pyc`, IDE settings — they're in
  [`.gitignore`](.gitignore).
- Tag releases with `vX.Y.Z` after bumping the two `.claude-plugin/*.json`
  version fields in lockstep.
