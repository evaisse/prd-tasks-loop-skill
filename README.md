# prd-tasks-loop

`prd-tasks-loop` is a Codex skill repo that combines PRD authoring and PRD execution (a.k.a. [Ralph Loop](https://ghuntley.com/ralph/)) into one workflow.

The skill itself lives under `./prd-tasks-loop/`.

It provides:

- a canonical Markdown PRD format
- a script (python) loop runner for executing PRDs
- visible runtime logs beside each PRD
- a generic agent prompt contract plus agent-specific invocation notes

## Workflow

```text
write PRD
   |
   v
pick next US ----> invalid/blocked ----> stop
   |
   v
render prompt
   |
   v
run agent
   |
   +---- success ----> mark US passed ----+
   |                                      |
   +---- failure ----> retry / mark failed|
                                          |
                                          v
                              next US or PRD completed
```

## Canonical PRD Name

PRDs live under `docs/prd/` and use this filename pattern:

```text
YYYY-MM-DD-HHMMSS-<slug>.md
```

Example:

```text
docs/prd/2026-04-30-104512-jwt-authentication.md
```

The runtime logs for that PRD are:

```text
docs/prd/2026-04-30-104512-jwt-authentication.json.log
docs/prd/2026-04-30-104512-jwt-authentication.progress.log
```

## Runner Usage

Run one PRD with a built-in preset:

```bash
python3 prd-tasks-loop/scripts/prd-tasks-loop.py --agent=codex docs/prd/2026-04-30-104512-jwt-authentication.md
```

Run multiple PRDs in order with a custom command:

```bash
python3 prd-tasks-loop/scripts/prd-tasks-loop.py \
  --agent='./my-agent --stdin' \
  docs/prd/2026-04-30-104512-jwt-authentication.md \
  docs/prd/2026-04-30-111200-rate-limiter.md
```

Run multiple PRDs with another built-in preset:

```bash
python3 prd-tasks-loop/scripts/prd-tasks-loop.py \
  --agent=amp \
  docs/prd/2026-04-30-104512-auth.md \
  docs/prd/2026-04-30-111200-rate-limit.md \
  docs/prd/2026-04-30-121500-billing.md
```

Run on a specific Git branch:

```bash
python3 prd-tasks-loop/scripts/prd-tasks-loop.py \
  --branch=feature/prd-loop \
  --agent=codex \
  docs/prd/2026-04-30-104512-jwt-authentication.md
```

## Supported Flags

- `<prd1> <prd2> ...`
- `--agent=<preset-or-command>`
- `--branch=<git-branch>`
- `--retries <n>`
- `--timeout <duration>`
- `--verbose`

## Notes

- CLI flags override `## Execution Settings` in the PRD.
- The runner processes positional PRDs sequentially and stops on the first incomplete or failed PRD.
- On macOS, the runner uses `caffeinate` by default to prevent sleep during the execution loop.
- Failed stories use exponential backoff before retrying.
- `--agent=codex`, `--agent=amp`, `--agent=claude-code`, `--agent=gemini`, and `--agent=opencode` map to built-in commands.
- Any other `--agent=...` value is executed as a custom stdin-reading command.
- Before starting, the runner shows the PRDs that will be processed and asks for confirmation.
- In a Git repository, the startup prompt shows the current branch and optional `--branch=...` target.
- Outside a Git repository, the startup prompt only asks for confirmation that the loop should run without Git support.
- When the worktree starts clean inside a Git repository, a successful story is expected to produce a new commit.
- Agents should never modify `.json.log` or `.progress.log` directly.
- When a PRD is fully completed, its `.json.log` and `.progress.log` files are removed automatically.

## Credits

- Original loop inspiration: [snarktank/ralph](https://github.com/snarktank/ralph)
- This repo keeps the fresh-context loop idea, but replaces the original runtime model with a simpler Python runner and visible per-PRD state logs.

## Tests

Run:

```bash
python3 tests/test_prd_tasks_loop.py
```
