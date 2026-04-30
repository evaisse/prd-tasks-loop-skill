---
name: prd-tasks-loop
description: "Create, normalize, and execute PRDs stored under docs/prd/ using a canonical Markdown format and a Python loop runner with visible JSON/progress logs."
---

# PRD Tasks Loop

Use this skill when the user wants one of these outcomes:

- create a new PRD
- rewrite or normalize an existing PRD
- execute one or more PRDs through a repeatable loop runner

This skill owns both the canonical PRD format and the loop runner workflow.

## Canonical Layout

Store PRDs under:

```text
docs/prd/
```

Canonical file name:

```text
YYYY-MM-DD-HHMMSS-<slug>.md
```

Examples:

```text
docs/prd/2026-04-30-104512-jwt-authentication.md
docs/prd/2026-04-30-164001-refresh-dashboard.md
```

Runtime state lives beside the PRD as visible log files:

```text
docs/prd/<prd-id>.json.log
docs/prd/<prd-id>.progress.log
```

`<prd-id>` is always the PRD basename without `.md`.

## What To Do

When the user needs a PRD:

- write or update the PRD directly in `docs/prd/`
- keep the document explicit, implementation-ready, and easy to validate
- follow the canonical format in [references/PRD_FORMAT.md](references/PRD_FORMAT.md)

When the user needs execution:

- use `scripts/prd-tasks-loop.py`
- treat the script as the runtime source of truth
- do not edit `.json.log` or `.progress.log` files manually

## Public Script

Use this path when suggesting direct operator usage:

```bash
$HOME/Sites/projects/prd-tasks-loop/prd-tasks-loop/scripts/prd-tasks-loop.py
```

Common commands:

```bash
# Run a PRD with Codex
$HOME/Sites/projects/prd-tasks-loop/prd-tasks-loop/scripts/prd-tasks-loop.py --agent=codex docs/prd/2026-04-30-104512-jwt-authentication.md

# Run several PRDs in order with a custom agent command
$HOME/Sites/projects/prd-tasks-loop/prd-tasks-loop/scripts/prd-tasks-loop.py \
  --agent='my-agent --stdin' \
  docs/prd/2026-04-30-104512-jwt-authentication.md \
  docs/prd/2026-04-30-111200-rate-limiter.md
```

## Required PRD Structure

Every PRD must contain:

- `# PRD: <title>`
- `## Introduction/Overview`
- `## Goals`
- `## User Stories`
- `## Functional Requirements`
- `## Non-Goals`
- `## Success Metrics`
- `## Open Questions`

Optional section:

- `## Execution Settings`

Each user story must use this shape:

```markdown
### US-001: Protect authenticated routes
**Description:** As an API consumer, I want protected routes to reject missing tokens so that unauthorized requests fail safely.

**Acceptance Criteria:**
- [ ] Requests without a bearer token return HTTP 401
- [ ] Requests with a valid token continue to the handler

**TDD Plan:**
- Test: Add a failing integration test for a protected route without a token.
- Implementation: Add auth middleware that validates the Authorization header.

**Dependencies:** -
**Parallel Group:** auth
```

Validation rules:

- at least one `### US-xxx:` story is required
- story IDs must be unique
- every story must define `Description`, `Acceptance Criteria`, `TDD Plan`, `Dependencies`, and `Parallel Group`
- `Acceptance Criteria` must contain at least one bullet
- `TDD Plan` must contain both `- Test:` and `- Implementation:`

## Execution Settings

`## Execution Settings` is optional. When present, use this compact Markdown shape:

```markdown
## Execution Settings
Agent Command: codex exec --skip-git-repo-check --yolo -
Test Command: npm test
Quality Gates:
- npm run lint
- npm run typecheck
```

Rules:

- CLI flags override `Execution Settings`
- `Quality Gates:` can be empty
- if the section is missing, the runner uses only CLI-provided runtime settings

## Routing Rules

- PRD creation or rewrite: edit the PRD directly
- explicit PRD execution: run `scripts/prd-tasks-loop.py` with `--agent=<preset-or-command>`

## Prompt Contract

The runner sends one-story prompts to coding agents. The prompt contract is documented in:

- [references/PROMPT_TEMPLATE.md](references/PROMPT_TEMPLATE.md)
- [references/PROMPT_AGENT_NOTES.md](references/PROMPT_AGENT_NOTES.md)

Agents must:

- read the PRD and both runtime logs before making changes
- work on exactly one story
- prefer TDD-first execution
- run tests and quality gates when defined
- never modify runtime logs directly
- never commit from inside the agent run

## References

- [references/PRD_FORMAT.md](references/PRD_FORMAT.md): canonical PRD format and example
- [references/PROMPT_TEMPLATE.md](references/PROMPT_TEMPLATE.md): generic one-story prompt template
- [references/PROMPT_AGENT_NOTES.md](references/PROMPT_AGENT_NOTES.md): invocation notes per supported agent family
- [references/WORKFLOW.md](references/WORKFLOW.md): operator and runner workflow
