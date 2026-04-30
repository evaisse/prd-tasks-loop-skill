# prd-tasks-loop

`prd-tasks-loop` is a Codex skill repo that combines PRD authoring and PRD execution into one workflow.

The skill itself lives under `./prd-tasks-loop/`.

It provides:

- a canonical Markdown PRD format without YAML frontmatter
- a Python loop runner for executing PRDs
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

## Layout

```text
.
├── README.md
├── prd-tasks-loop/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── docs/prd/
│   ├── references/
│   └── scripts/prd-tasks-loop.py
└── tests/test_prd_tasks_loop.py
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

## Supported Flags

- `<prd1> <prd2> ...`
- `--agent=<preset-or-command>`
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
- Agents should never modify `.json.log` or `.progress.log` directly.

## Credits

- Original loop inspiration: [snarktank/ralph](https://github.com/snarktank/ralph)
- This repo keeps the fresh-context loop idea, but replaces the original runtime model with a simpler Python runner and visible per-PRD state logs.

## Tests

Run:

```bash
python3 tests/test_prd_tasks_loop.py
```
