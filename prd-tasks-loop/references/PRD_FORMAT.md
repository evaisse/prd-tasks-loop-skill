# PRD Format

This repository uses a canonical Markdown PRD format without YAML frontmatter.

## File Naming

Store every PRD in `docs/prd/` with this filename pattern:

```text
YYYY-MM-DD-HHMMSS-<slug>.md
```

Rules:

- use a lowercase hyphenated slug
- keep the basename stable after execution starts
- derive the canonical PRD identifier from the basename without `.md`

## Required Sections

Every PRD must contain:

- `# PRD: <title>`
- `## Introduction/Overview`
- `## Goals`
- `## User Stories`
- `## Functional Requirements`
- `## Non-Goals`
- `## Success Metrics`
- `## Open Questions`

Optional sections:

- `## Execution Settings`
- `## Design Considerations`
- `## Technical Considerations`

## Execution Settings

This section is optional. Use it only for PRD-local runner defaults.

```markdown
## Execution Settings
Agent Command: codex exec --skip-git-repo-check --yolo -
Test Command: npm test
Quality Gates:
- npm run lint
- npm run typecheck
```

CLI flags always override these settings.

## User Story Template

Each story must use this shape:

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

- story IDs must be unique
- every story must define all required fields
- `Acceptance Criteria` must contain at least one bullet
- `TDD Plan` must contain both `- Test:` and `- Implementation:`

## Canonical Example

```markdown
# PRD: JWT Authentication

## Introduction/Overview
Add JWT-based authentication to protect private API routes and prepare the application for authenticated user sessions.

## Goals
- Reject unauthenticated requests on protected endpoints.
- Validate JWT signatures and expiry consistently.
- Keep the authentication flow testable and easy to extend.

## Execution Settings
Test Command: npm test
Quality Gates:
- npm run lint
- npm run typecheck

## User Stories
### US-001: Reject missing tokens on protected routes
**Description:** As an API consumer, I want protected routes to reject missing bearer tokens so that unauthorized requests fail safely.

**Acceptance Criteria:**
- [ ] Requests without a bearer token return HTTP 401
- [ ] Requests with a malformed token return HTTP 401
- [ ] Requests with a valid token continue to the handler

**TDD Plan:**
- Test: Add failing integration tests for missing and malformed bearer tokens on a protected route.
- Implementation: Add authentication middleware that reads the Authorization header and rejects missing or malformed tokens.

**Dependencies:** -
**Parallel Group:** auth

### US-002: Validate JWT signature and expiry
**Description:** As a backend developer, I want JWTs to be validated for signature and expiry so that only trusted and current tokens are accepted.

**Acceptance Criteria:**
- [ ] Tokens signed with the configured secret are accepted
- [ ] Tokens with an invalid signature return HTTP 401
- [ ] Expired tokens return HTTP 401

**TDD Plan:**
- Test: Add unit tests covering valid, invalid-signature, and expired JWTs.
- Implementation: Add a token validation service that verifies signature and expiry before attaching claims to the request context.

**Dependencies:** US-001
**Parallel Group:** auth

## Functional Requirements
- Protected routes must require a bearer token.
- The application must validate JWT signature and expiry before authorizing a request.
- Authentication failures must return HTTP 401 without exposing internal details.
- Validated claims must be made available to downstream handlers.

## Non-Goals
- Implementing refresh tokens.
- Adding social login providers.
- Building a user-facing login UI.

## Success Metrics
- Protected route coverage includes both success and failure-path tests.
- Invalid tokens are rejected consistently across protected endpoints.
- The feature ships with passing tests and quality gates.

## Open Questions
- Which JWT secret management mechanism is the target environment using?
- Do we need role or scope checks in this PRD, or only authentication?
```
