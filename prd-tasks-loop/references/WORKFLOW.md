# Workflow

This document describes the simplified `prd-tasks-loop` workflow.

## High-Level Flow

```mermaid
flowchart TD
    A[User request] --> B{Need a PRD?}
    B -->|Yes| C[Write or normalize docs/prd/YYYY-MM-DD-HHMMSS-slug.md]
    B -->|No| D[Run prd-tasks-loop.py with one or more PRDs]
    D --> E[Validate PRD structure]
    E -->|Invalid| F[Stop and report errors]
    E -->|Valid| G[Create visible runtime logs if missing]
    G --> H[Select next actionable user story]
    H -->|No story left| I[Mark PRD completed]
    H -->|Story found| J[Render one-story prompt]
    J --> K[Run selected agent command]
    K -->|Exit 0| L[Record success in JSON log]
    K -->|Exit non-zero| M[Record failure, backoff, and retry]
    L --> H
    M -->|Retries left| H
    M -->|Retries exhausted| N[Mark PRD failed and stop]
```

## State Files

For a PRD named `docs/prd/2026-04-30-104512-jwt-authentication.md`, the runner writes:

- `docs/prd/2026-04-30-104512-jwt-authentication.json.log`
- `docs/prd/2026-04-30-104512-jwt-authentication.progress.log`

The JSON log is the machine-readable source of truth.

The progress log is append-only operator output.

## Operator Rules

- validate PRDs before running them
- keep PRD names stable after execution starts
- do not edit runtime logs by hand
- prefer CLI flags when you need temporary runtime overrides
- expect the runner to stop on the first incomplete or failed PRD
