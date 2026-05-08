# prd-tasks-loop

`prd-tasks-loop` is a Codex skill repo that combines PRD authoring and PRD execution (a.k.a. [Ralph Loop](https://ghuntley.com/ralph/)) into one workflow.

The skill itself lives under `./prd-tasks-loop/`.

It provides:

- a canonical Markdown PRD format
- a script (python) loop runner for executing PRDs
- visible runtime logs beside each PRD
- a generic agent prompt contract plus agent-specific invocation notes

## Versioning

- Released versions are tracked with Git tags such as `v0.1.0`.
- User-facing changes to the skill should update [CHANGELOG.md](CHANGELOG.md) in the same change set as the code and docs.
- New release tags should be created only after the changelog entry for that version is present.

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
- `--timeout <duration>`: timeout per agent run attempt for one user story, not for the whole PRD or the whole loop
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
- `**Dependencies:**` currently supports only story IDs from the same PRD, such as `US-001`.
- `Blocked by dependencies` means that no remaining incomplete story can run with the set of completed stories currently detected from the PRD and runtime state.
- When the worktree starts clean inside a Git repository, a successful story is expected to produce a new commit.
- Story commits should use Conventional Commits and include both the active `US-xxx` identifier and the attached PRD ID.
- Agents should never modify `.json.log` or `.progress.log` directly.
- When a PRD is fully completed, its `.json.log` and `.progress.log` files are removed automatically.

## Credits

- Original loop inspiration: [snarktank/ralph](https://github.com/snarktank/ralph)
- This repo keeps the fresh-context loop idea, but replaces the original runtime model with a simpler Python runner and visible per-PRD state logs.

## Tests

Run:

```bash
python3 tests/test_prd_tasks_loop.py
python3 tests/cli-contracts/assert_real_cli_contracts.py
python3 tests/agent-presets/assert_agent_preset.py codex
python3 tests/agent-presets/assert_agent_preset.py gemini
python3 tests/agent-presets/assert_agent_preset.py opencode
```

The GitHub Actions workflow `.github/workflows/cli-contracts.yml` runs the upstream CLI help-contract checks on pull requests with `ubuntu-22.04`.

## Real agent E2E on GitHub Actions

The workflow `.github/workflows/real-agent-e2e.yml` runs a pull-request-only blocking matrix on `ubuntu-22.04` for these real CLI entrypoints:

- `codex`
- `@google/gemini-cli`
- `opencode`

The workflow uses `npx`. The `codex` job is pinned to the OpenAI provider with `gpt-5.4`, while `gemini` and `opencode` continue to use the OpenRouter-compatible environment setup.

Required repository secret:

```text
OPENAI_API_KEY
OPENROUTER_API_KEY
```

Default remote models configured in the workflow:

```text
codex: gpt-5.4
meta-llama/llama-3.1-8b-instruct:free
```

The real E2E smoke test copies `tests/e2e-real/fixture/` into a temporary Git repository, runs `prd-tasks-loop/scripts/prd-tasks-loop.py`, and expects the agent to:

- create `project/result.txt` with exactly `STATUS=done`
- check the active story acceptance criteria in the PRD
- create one Git commit for the story with a Conventional Commits subject that includes the story ID and PRD ID
- allow the runner to clean up the runtime log files

You can run the harness locally if you already have a valid `OPENROUTER_API_KEY` in your environment:

```bash
OPENAI_API_KEY=... python3 tests/e2e-real/run_real_agent_e2e.py codex
OPENROUTER_API_KEY=... python3 tests/e2e-real/run_real_agent_e2e.py gemini
OPENROUTER_API_KEY=... python3 tests/e2e-real/run_real_agent_e2e.py opencode
```

Notes:

- this is a true remote E2E smoke test, so it depends on CLI package availability, provider compatibility, and OpenRouter model availability
- the configured `:free` model may change or disappear on OpenRouter over time
- if one agent CLI requires different provider variables than the current OpenAI-compatible setup, the workflow will need a follow-up adjustment

## Demo Site

A static showcase site lives in `docs-site/` and is deployed with GitHub Pages through `.github/workflows/pages.yml`.
