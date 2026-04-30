#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "prd-tasks-loop" / "scripts" / "prd-tasks-loop.py"


def write_prd(workspace: Path, name: str, title: str, story_two_dep: str = "US-001") -> Path:
    path = workspace / "docs" / "prd" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""\
            # PRD: {title}

            ## Introduction/Overview
            Implement {title.lower()}.

            ## Goals
            - Deliver the behavior.

            ## Execution Settings
            Test Command: ./scripts/test.sh
            Quality Gates:
            - ./scripts/lint.sh

            ## User Stories
            ### US-001: First step
            **Description:** Build the first step.

            **Acceptance Criteria:**
            - [ ] The first step is complete.

            **TDD Plan:**
            - Test: Add a failing test for the first step.
            - Implementation: Implement the first step.

            **Dependencies:** -
            **Parallel Group:** core

            ### US-002: Second step
            **Description:** Build the second step.

            **Acceptance Criteria:**
            - [ ] The second step is complete.

            **TDD Plan:**
            - Test: Add a failing test for the second step.
            - Implementation: Implement the second step.

            **Dependencies:** {story_two_dep}
            **Parallel Group:** core

            ## Functional Requirements
            - The system must support the requested feature.

            ## Non-Goals
            - No unrelated work.

            ## Success Metrics
            - The change can be validated.

            ## Open Questions
            - None.
            """
        )
    )
    return path


def write_bad_prd(workspace: Path, name: str) -> Path:
    path = workspace / "docs" / "prd" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# PRD: Broken\n\n## Introduction/Overview\nBroken.\n")
    return path


def write_agent(workspace: Path, name: str, body: str) -> Path:
    path = workspace / "bin" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


class PrdTasksLoopTests(unittest.TestCase):
    def make_workspace(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="prd-tasks-loop-test."))

    def run_script(self, workspace: Path, *args: str, allow_failure: bool = False, extra_env: dict | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{workspace / 'bin'}:{env.get('PATH', '')}"
        env["PRD_TASKS_LOOP_BACKOFF_SCALE"] = "0"
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH), *args],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
        )
        if not allow_failure and result.returncode != 0:
            self.fail(result.stdout + result.stderr)
        return result

    def test_no_prd_files_found(self) -> None:
        workspace = self.make_workspace()
        result = self.run_script(workspace, allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error: No PRD files found.", result.stderr)

    def test_invalid_prd_fails_before_execution(self) -> None:
        workspace = self.make_workspace()
        write_bad_prd(workspace, "wrong-name.md")
        result = self.run_script(workspace, allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error: No PRD files found.", result.stderr)

    def test_explicit_invalid_prd_still_fails_validation(self) -> None:
        workspace = self.make_workspace()
        prd = write_bad_prd(workspace, "wrong-name.md")
        result = self.run_script(workspace, str(prd), allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid PRD filename `wrong-name.md`", result.stdout)
        self.assertIn("Missing required section `## Goals`.", result.stdout)

    def test_auto_discovery_skips_non_canonical_prd_names(self) -> None:
        workspace = self.make_workspace()
        valid = write_prd(workspace, "2026-04-30-104512-valid.md", "Valid")
        write_bad_prd(workspace, "prd-agent-attention-plan-mode.md")
        write_agent(workspace, "success-agent", "#!/usr/bin/env bash\ncat >/dev/null\nexit 0\n")
        result = self.run_script(workspace, "--agent=success-agent")
        self.assertIn("1/1 2026-04-30-104512-valid.md", result.stdout)
        self.assertNotIn("prd-agent-attention-plan-mode.md", result.stdout)
        self.assertTrue(valid.with_suffix(".json.log").exists())

    def test_run_creates_state_logs_and_parses_dependencies(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-happy-path.md", "Happy Path")
        write_agent(workspace, "success-agent", "#!/usr/bin/env bash\ncat >/dev/null\nprintf 'story ok\\n'\nexit 0\n")
        result = self.run_script(workspace, "--agent=success-agent", str(prd))
        state_file = prd.with_suffix(".json.log")
        progress_file = prd.with_suffix(".progress.log")
        self.assertTrue(state_file.exists())
        self.assertTrue(progress_file.exists())
        self.assertIn("US-001 passed (1/3)", result.stdout)
        self.assertIn("US-002 passed (1/3)", result.stdout)
        state = json.loads(state_file.read_text())
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["completed_story_ids"], ["US-001", "US-002"])
        self.assertEqual(len(state["attempts"]), 2)

    def test_custom_agent_overrides_preset(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-custom-override.md", "Custom Override")
        write_agent(workspace, "custom-agent", "#!/usr/bin/env bash\ncat >/dev/null\nexit 0\n")
        self.run_script(workspace, "--agent=custom-agent", str(prd))
        state = json.loads(prd.with_suffix(".json.log").read_text())
        self.assertEqual(state["selected_agent"], "custom-agent")

    def test_timeout_retry_exhaustion_and_backoff(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-timeout-case.md", "Timeout Case")
        write_agent(workspace, "sleep-agent", "#!/usr/bin/env bash\ncat >/dev/null\nsleep 2\n")
        result = self.run_script(
            workspace,
            "--agent=sleep-agent",
            "--timeout",
            "1s",
            "--retries",
            "2",
            str(prd),
            allow_failure=True,
        )
        self.assertIn("US-001 failed (1/2, exit 124)", result.stdout)
        self.assertIn("US-001 backing off 0s before retry", result.stdout)
        self.assertIn("US-001 retrying", result.stdout)
        self.assertIn("US-001 failed permanently", result.stdout)
        state = json.loads(prd.with_suffix(".json.log").read_text())
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["failed_story_id"], "US-001")
        self.assertEqual(len(state["attempts"]), 2)

    def test_caffeinate_wrap_on_mac(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-caffeinate.md", "Caffeinate")
        write_agent(workspace, "success-agent", "#!/usr/bin/env bash\ncat >/dev/null\nexit 0\n")
        write_agent(workspace, "caffeinate", "#!/usr/bin/env bash\nprintf 'CAFFEINATE\\n' >&2\nshift 1\nexec \"$@\"\n")
        result = self.run_script(
            workspace,
            "--agent=success-agent",
            str(prd),
            extra_env={"PRD_TASKS_LOOP_OS": "Darwin"},
        )
        self.assertIn("CAFFEINATE", result.stderr)

    def test_multiple_prds_stop_on_first_failure_with_positional_args(self) -> None:
        workspace = self.make_workspace()
        first = write_prd(workspace, "2026-04-30-104512-first-fails.md", "First Fails")
        second = write_prd(workspace, "2026-04-30-104513-second-skipped.md", "Second Skipped")
        write_agent(workspace, "fail-agent", "#!/usr/bin/env bash\ncat >/dev/null\nexit 7\n")
        result = self.run_script(
            workspace,
            "--agent=fail-agent",
            "--retries",
            "1",
            str(first),
            str(second),
            allow_failure=True,
        )
        self.assertIn("1/2 2026-04-30-104512-first-fails.md", result.stdout)
        self.assertIn("Failed after retries", result.stdout)
        self.assertTrue(first.with_suffix(".json.log").exists())
        self.assertFalse(second.with_suffix(".json.log").exists())

    def test_help_mentions_agent_and_multiple_prds(self) -> None:
        workspace = self.make_workspace()
        result = self.run_script(workspace, "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--agent", result.stdout)
        self.assertIn("Built-in presets: codex, amp, claude-code, gemini, opencode", result.stdout)
        self.assertIn("prd1.md prd2.md prd3.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
