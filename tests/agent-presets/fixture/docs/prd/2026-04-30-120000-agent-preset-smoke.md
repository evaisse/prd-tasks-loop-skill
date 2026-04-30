# PRD: Agent preset smoke test

## Introduction/Overview
This PRD validates that the loop runner invokes a built-in agent preset with the expected CLI shape and passes the rendered prompt over stdin.

## Goals
- Verify the selected preset command is invoked.
- Verify stdin contains the rendered story prompt.
- Verify a successful agent run can complete one story in a clean Git repository.

## User Stories
### US-001: Validate preset agent invocation
**Description:** As a maintainer, I want the preset command to receive the loop prompt over stdin so that built-in agents can be wired safely.

**Acceptance Criteria:**
- [ ] The preset stub records the expected CLI arguments
- [ ] The preset stub records a non-empty stdin payload
- [ ] The fixture target file records the invoked agent metadata

**TDD Plan:**
- Test: Run the loop against a fixture repository and assert the stub artifacts were written.
- Implementation: Invoke the built-in preset and let the stub update the fixture files and PRD.

**Dependencies:** -
**Parallel Group:** presets

## Functional Requirements
- The runner must pass the prompt over stdin to the built-in preset command.
- The agent must update the current story acceptance criteria before exiting successfully.
- The agent must create a Git commit when the repository starts clean.

## Non-Goals
- Calling a real remote model provider.
- Validating semantic quality of model output.

## Success Metrics
- The loop exits with status code 0.
- The fixture repository ends with a second Git commit.
- The expected stub artifacts exist after the run.

## Open Questions
- None.
