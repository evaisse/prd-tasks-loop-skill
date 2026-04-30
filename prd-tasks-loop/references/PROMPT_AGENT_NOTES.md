# Prompt Agent Notes

These notes document the supported `--agent=...` values used by `scripts/prd-tasks-loop.py`.

The runner always renders the generic prompt template first. These notes only explain how the prompt is fed to each agent family and what operator assumptions the preset encodes.

## Codex

- `--agent=codex`
- default command: `codex exec --skip-git-repo-check --yolo -`
- prompt transport: stdin
- expectation: non-zero exit means retry or failure

## Amp

- `--agent=amp`
- default command: `amp -p -`
- prompt transport: stdin
- expectation: command must read the rendered prompt from stdin

## Claude Code

- `--agent=claude-code`
- default command: `claude -p`
- prompt transport: stdin
- expectation: command must return non-zero when the story remains blocked

## Gemini

- `--agent=gemini`
- default command: `gemini -p`
- prompt transport: stdin
- expectation: keep shell quoting simple and avoid extra wrappers when overriding

## OpenCode

- `--agent=opencode`
- default command: `opencode run -`
- prompt transport: stdin
- expectation: preserve the rendered prompt exactly

## Custom

- `--agent='<command>'`
- prompt transport: stdin
- expectation: the command must read stdin and use exit status as the success contract

## Runner Conventions

- `--agent=<preset-or-command>` overrides any `Agent Command:` declared inside the PRD when explicitly supplied.
- The runner treats agent stdout and stderr as operator feedback only.
- The runner uses process exit status as the story success signal.
