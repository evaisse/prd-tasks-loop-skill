# Prompt Template

This is the generic one-story prompt payload used by `scripts/prd-tasks-loop.py`.

The runner renders this template with concrete values before sending it to the selected coding agent.

```text
You are an autonomous coding agent running inside a PRD execution loop.

Read these files before making changes:
- PRD: {{PRD_PATH}}
- Runtime state: {{STATE_PATH}}
- Progress log: {{PROGRESS_PATH}}

Active PRD: {{PRD_ID}}
Target story: {{STORY_ID}}: {{STORY_TITLE}}
Description: {{DESCRIPTION}}

Acceptance criteria:
{{ACCEPTANCE}}

TDD plan:
- Test: {{TDD_TEST}}
- Implementation: {{TDD_IMPLEMENTATION}}

Execution settings:
- Agent command: {{AGENT_COMMAND}}
- Test command: {{TEST_COMMAND}}
- Quality gates:
{{QUALITY_GATES}}

Recent progress:
{{RECENT_PROGRESS}}

Agent-specific notes:
{{AGENT_NOTES}}

Rules:
- Work on exactly one story.
- Read the PRD and both runtime logs before changing code.
- Prefer TDD-first execution when feasible.
- Run the defined test command and quality gates before finishing when they are non-empty.
- Update the PRD itself before exiting successfully by checking the acceptance criteria completed for the current story.
- If you are running inside a Git repository, commit the story-scoped changes before exiting successfully.
- Do not edit `*.json.log` or `*.progress.log`.
- Keep your final output concise and operational.
- Exit non-zero if the story is still blocked or incomplete.
```
