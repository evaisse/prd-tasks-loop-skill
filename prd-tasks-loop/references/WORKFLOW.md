# Workflow

This document describes the simplified `prd-tasks-loop` workflow.

## High-Level Flow

```mermaid
flowchart TD
    A[User request] --> B{Need a PRD?}
    B -->|Yes| C[Write or normalize docs/prd/YYYY-MM-DD-HHMMSS-slug.md]
    B -->|No| D[Resolve PRD list]
    D --> E[Show confirmation prompt]
    E --> F[Validate PRD structure]
    F -->|Invalid| G[Stop and report errors]
    F -->|Valid| H[Create visible runtime logs if missing]
    H --> I[Select next actionable user story]
    I -->|No story left| J[Mark PRD completed and delete runtime logs]
    I -->|Story found| K[Render one-story prompt]
    K --> L[Run selected agent command]
    L -->|Exit 0| M[Verify PRD update and optional Git commit]
    L -->|Exit non-zero| N[Record failure, backoff, and retry]
    M --> I
    N -->|Retries left| I
    N -->|Retries exhausted| O[Mark PRD failed and stop]
```

## State Files

For a PRD named `docs/prd/2026-04-30-104512-jwt-authentication.md`, the runner writes:

- `docs/prd/2026-04-30-104512-jwt-authentication.json.log`
- `docs/prd/2026-04-30-104512-jwt-authentication.progress.log`

The JSON log is the machine-readable source of truth while the PRD is in progress.

The progress log is append-only operator output while the PRD is in progress.

Both runtime log files are deleted automatically when the PRD completes successfully.

## Operator Rules

- validate PRDs before running them
- confirm the PRD list before launching the loop
- keep PRD names stable after execution starts
- do not edit runtime logs by hand
- prefer CLI flags when you need temporary runtime overrides
- expect the runner to stop on the first incomplete or failed PRD
